"""Bounded, polite, same-origin crawler that produces a `Snapshot`.

Boundaries (all enforced and tested): same origin only; robots.txt honoured; max pages / depth / query variants per path / body size / asset bytes; GET only; redirects followed
manually and only inside the origin; every hop re-checked against the public-address rule (SSRF) unless the caller explicitly allows private hosts (local fixtures / own network).
Capture makes the snapshot safe to serve: scripts, iframes, objects, <base>, meta-refresh and inline event handlers are removed (counted in `meta.fidelity`), and same-origin
absolute URLs are rewritten root-relative so the snapshot is origin-independent. Only crawl sites you operate or have permission to test."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Protocol
from urllib.parse import urldefrag, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from ...remediation.probe import MAX_BODY_BYTES, MAX_REDIRECTS, assert_public_host
from ..sitemodel.snapshot import Resource, Snapshot
from .pagemodel import internal_path, visible_text

USER_AGENT = "agent-readiness-inspector/1 (site owner testing)"
STATIC_SKIP = (".zip", ".pdf", ".mp4", ".mp3", ".woff", ".woff2", ".xml", ".json")
ASSET_TYPES = ("text/css", "image/png", "image/jpeg", "image/gif", "image/svg+xml", "image/webp")


@dataclass(frozen=True)
class Limits:
    max_pages: int = 60
    max_depth: int = 4
    max_query_variants: int = 5
    max_page_bytes: int = MAX_BODY_BYTES
    max_assets: int = 20
    max_asset_bytes: int = 300_000
    max_total_asset_bytes: int = 2_000_000
    delay_seconds: float = 0.0


@dataclass
class Fetched:
    status: int
    content_type: str = ""
    body: bytes = b""
    location: str | None = None


class Fetcher(Protocol):
    origin: str

    def get(self, url: str) -> Fetched: ...


class MappingFetcher:
    """Serves an in-memory site (`{path: html | (status, content_type, bytes) | ('redirect', target)}`): the offline path for fixtures and tests; never touches a socket."""
    origin = "http://fixture.invalid"

    def __init__(self, files: dict):
        self.files = files
        self.requests: list[str] = []

    def get(self, url: str) -> Fetched:
        p = urlsplit(url)
        key = (p.path or "/") + (f"?{p.query}" if p.query else "")
        self.requests.append(key)
        v = self.files.get(key)
        if v is None:
            return Fetched(404, "text/html", b"not found")
        if isinstance(v, str):
            return Fetched(200, "text/html; charset=utf-8", v.encode())
        if v[0] == "redirect":
            return Fetched(302, "", b"", v[1])
        return Fetched(v[0], v[1], v[2] if isinstance(v[2], bytes) else v[2].encode())


class HttpFetcher:
    def __init__(self, base_url: str, *, allow_private_hosts: bool = False, client: httpx.Client | None = None, timeout: float = 10.0):
        u = urlsplit(base_url)
        if u.scheme not in ("http", "https") or not u.netloc or u.username or u.password:
            raise ValueError("base_url must be an http(s) URL without credentials")
        self.origin, self.allow_private = f"{u.scheme}://{u.netloc}", allow_private_hosts
        if not allow_private_hosts:
            assert_public_host(u.hostname or "")
        self.client = client or httpx.Client(timeout=timeout, follow_redirects=False, headers={"User-Agent": USER_AGENT})

    def get(self, url: str) -> Fetched:
        p = urlsplit(url)
        if f"{p.scheme}://{p.netloc}" != self.origin:
            raise ValueError("refusing to fetch outside the audited origin")
        if not self.allow_private:
            assert_public_host(p.hostname or "")
        with self.client.stream("GET", url, follow_redirects=False) as r:
            loc = r.headers.get("location") if r.status_code in (301, 302, 303, 307, 308) else None
            ctype = r.headers.get("content-type", "")
            body, size = [], 0
            if not loc:
                for chunk in r.iter_bytes():
                    size += len(chunk)
                    body.append(chunk)
                    if size >= MAX_BODY_BYTES:
                        break
            return Fetched(r.status_code, ctype, b"".join(body)[:MAX_BODY_BYTES], loc)


def capture_html(html: str, path: str) -> tuple[bytes, dict]:
    """Make a fetched page safe and origin-independent. Returns (bytes, counts of what was removed)."""
    soup = BeautifulSoup(html, "html.parser")
    counts = {"scripts": 0, "iframes": 0, "handlers": 0}
    for el in soup.find_all(["script", "iframe", "object", "embed", "base"]):
        if el.name == "script":
            if (el.get("type") or "").lower() == "application/ld+json":
                continue                                      # inert structured data is kept (useful, executes nothing)
            counts["scripts"] += 1
        elif el.name != "base":
            counts["iframes"] += 1
        el.decompose()
    for m in soup.find_all("meta", attrs={"http-equiv": True}):
        if m["http-equiv"].lower() == "refresh":
            m.decompose()
    for el in soup.find_all(True):
        for attr in [a for a in el.attrs if a.lower().startswith("on")]:
            del el[attr]
            counts["handlers"] += 1
    return soup.decode().encode("utf-8"), counts


def _rewrite_same_origin(html: str, origin: str, path: str) -> str:
    """Rewrite absolute links to the crawled origin into root-relative ones (hash stability across origins)."""
    soup = BeautifulSoup(html, "html.parser")
    for el in soup.find_all(True):
        for attr in ("href", "src", "action"):
            v = el.get(attr)
            if v and v.startswith(("http://", "https://", "//")):
                u = urlsplit(urljoin(origin + path, v))
                if f"{u.scheme}://{u.netloc}" == origin:
                    el[attr] = (u.path or "/") + (f"?{u.query}" if u.query else "")
    return soup.decode()


class Crawler:
    def __init__(self, fetcher: Fetcher, limits: Limits = Limits(), *, sleep: Callable[[float], None] = time.sleep):
        self.f, self.limits, self.sleep = fetcher, limits, sleep
        self.origin = fetcher.origin
        self.skipped: dict[str, str] = {}
        self.errors: list[str] = []
        self._robots: RobotFileParser | None = None

    def _load_robots(self) -> None:
        rp = RobotFileParser()
        try:
            r = self.f.get(self.origin + "/robots.txt")
            rp.parse(r.body.decode("utf-8", "replace").splitlines() if r.status == 200 else [])
        except (httpx.HTTPError, ValueError):
            rp.parse([])
        self._robots = rp

    def _allowed(self, path: str) -> bool:
        return self._robots is None or self._robots.can_fetch(USER_AGENT, self.origin + path)

    def _fetch(self, path: str) -> Fetched | None:
        if self.limits.delay_seconds:
            self.sleep(self.limits.delay_seconds)
        try:
            return self.f.get(self.origin + path)
        except (httpx.HTTPError, ValueError) as exc:
            self.errors.append(f"{path.split('?')[0]}: {type(exc).__name__}")
            return None

    def run(self, start: str = "/") -> Snapshot:
        self._load_robots()
        res: dict[str, Resource] = {}
        queue, seen, variants = [(start, 0)], {start}, {}
        assets: list[str] = []
        scripts_removed = 0
        js_dependent: list[str] = []
        total_asset_bytes = 0
        while queue and sum(1 for r in res.values() if r.status in (200, 301, 302, 303, 307, 308)) < self.limits.max_pages:
            path, depth = queue.pop(0)
            if not self._allowed(path):
                self.skipped[path] = "robots.txt"
                continue
            r = self._fetch(path)
            if r is None:
                continue
            if r.location:
                target = internal_path(r.location, path)
                if target is None:
                    self.skipped[path] = "redirect_off_origin"
                    continue
                res[path] = Resource(path, r.status, "", b"", target)
                if target not in seen and depth <= self.limits.max_depth:
                    seen.add(target)
                    queue.append((target, depth))
                continue
            if "html" not in r.content_type:
                if r.status == 200:
                    self.skipped[path] = f"non_html:{r.content_type.split(';')[0]}"
                continue
            html = _rewrite_same_origin(r.body.decode("utf-8", "replace"), self.origin, path)
            body, counts = capture_html(html, path)
            scripts_removed += counts["scripts"]
            res[path] = Resource(path, r.status, "text/html; charset=utf-8", body)
            soup = BeautifulSoup(body, "html.parser")
            if counts["scripts"] and len(visible_text(soup)) < 200:
                js_dependent.append(path)
            for a in soup.find_all(["link", "img"]):
                ref = a.get("href") if a.name == "link" and "stylesheet" in (a.get("rel") or []) else a.get("src") if a.name == "img" else None
                p = internal_path(ref, path)
                if p and p not in assets and len(assets) < self.limits.max_assets:
                    assets.append(p)
            if depth < self.limits.max_depth:
                for a in soup.find_all("a", href=True):
                    p = internal_path(a["href"], path)
                    if not p or p in seen or urlsplit(p).path.lower().endswith(STATIC_SKIP):
                        continue
                    base = urlsplit(p).path
                    if "?" in p:
                        variants[base] = variants.get(base, 0) + 1
                        if variants[base] > self.limits.max_query_variants:
                            self.skipped[p] = "query_variant_cap"
                            continue
                    seen.add(p)
                    queue.append((p, depth + 1))
        for p in assets:
            if p in res or not self._allowed(p):
                continue
            r = self._fetch(p)
            if r is None or r.status != 200 or not any(r.content_type.startswith(t) for t in ASSET_TYPES):
                continue
            if len(r.body) > self.limits.max_asset_bytes or total_asset_bytes + len(r.body) > self.limits.max_total_asset_bytes:
                self.skipped[p] = "asset_size_cap"
                continue
            total_asset_bytes += len(r.body)
            res[p] = Resource(p, 200, r.content_type.split(";")[0], r.body)
        fidelity = {"scripts_removed": scripts_removed, "js_dependent_pages": sorted(js_dependent), "level": "low" if js_dependent else "high"}
        return Snapshot(res, {"schema": "site-snapshot-v1", "limits": self.limits.__dict__, "skipped": dict(sorted(self.skipped.items())), "errors": self.errors[:20], "fidelity": fidelity,
                              "pages": sum(1 for r in res.values() if r.is_html), "javascript": "removed", "methods": ["GET"]})


def crawl(fetcher: Fetcher, limits: Limits = Limits(), **kw) -> Snapshot:
    return Crawler(fetcher, limits, **kw).run()
