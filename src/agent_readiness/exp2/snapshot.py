"""Ironbark -> investigation-pipeline integration: crawl a site variant into a `Snapshot` with the pipeline's own crawler (offline `MappingFetcher`, same capture rules as every other site),
then verify the capture is faithful. The pipeline's DEFAULT crawl limits (60 pages, 20 assets) would silently drop 31 of the 51 CSS/SVG assets of this site, so Ironbark uses explicit limits."""
from __future__ import annotations

import re
from functools import lru_cache

from bs4 import BeautifulSoup

from ..investigate.inspect.crawl import Limits, MappingFetcher, crawl
from ..investigate.sitemodel.snapshot import Snapshot
from ..sites.ironbark import variants as V
from ..sites.ironbark.build import build_site, is_page

LIMITS = Limits(max_pages=120, max_depth=5, max_query_variants=5, max_assets=100, max_asset_bytes=300_000, max_total_asset_bytes=2_000_000)
CTYPES = {".css": "text/css", ".svg": "image/svg+xml"}


def mapping(files: dict[str, bytes]) -> dict:
    out: dict = {}
    for path, body in files.items():
        out[path] = body.decode() if is_page(path) else (200, CTYPES[path[path.rindex("."):]], body)
    return out


@lru_cache(maxsize=None)
def _snapshot(name: str) -> Snapshot:
    return crawl(MappingFetcher(mapping(build_site(V.parse(name)))), LIMITS)


def snapshot(variant: V.Variant | str = V.CONTROL) -> Snapshot:
    """The crawled snapshot of a variant (cached; deterministic)."""
    return _snapshot(variant if isinstance(variant, str) else variant.name)


def _text(html: bytes) -> str:
    s = BeautifulSoup(html, "html.parser")
    return re.sub(r"\s+", " ", s.get_text(" ", strip=True))


def _links(html: bytes) -> list[tuple[str, str]]:
    return [(a["href"], re.sub(r"\s+", " ", a.get_text(" ", strip=True))) for a in BeautifulSoup(html, "html.parser").find_all("a", href=True)]


def assess(variant: V.Variant | str = V.CONTROL) -> dict:
    return _assess(variant if isinstance(variant, str) else variant.name)


@lru_cache(maxsize=None)
def _assess(name: str) -> dict:
    """Credential-free integration report for one variant: is the crawled snapshot a faithful, self-contained, deterministic copy of the site? Problems are listed, never hidden."""
    v = V.parse(name)
    files = build_site(v)
    snap = snapshot(v)
    pages = {p: b for p, b in files.items() if is_page(p)}
    assets = {p: b for p, b in files.items() if not is_page(p)}
    problems: list[str] = []
    got = snap.resources
    for p in files:
        if p not in got:
            problems.append(f"missing from snapshot: {p}")
    for p, body in assets.items():
        if p in got and got[p].body != body:
            problems.append(f"asset altered by capture: {p}")
    for p, body in pages.items():
        r = got.get(p)
        if r is None:
            continue
        if _text(r.body) != _text(body):
            problems.append(f"visible text differs after capture: {p}")
        if _links(r.body) != _links(body):
            problems.append(f"links differ after capture: {p}")
        if b"data-variant" in body and r.body.count(b"data-variant") != body.count(b"data-variant"):
            problems.append(f"variant markers lost: {p}")
    refs = 0
    for p, r in got.items():
        if r.is_html:
            s = BeautifulSoup(r.body, "html.parser")
            for tag, attr in (("a", "href"), ("img", "src"), ("link", "href")):
                for el in s.find_all(tag, **{attr: True}):
                    t = el[attr]
                    if t.startswith(("mailto:", "tel:")):
                        continue
                    refs += 1
                    target = t.split("#")[0].rstrip("/") or "/"
                    if target not in got:
                        problems.append(f"{p}: reference not in snapshot: {t}")
    fid = snap.meta.get("fidelity", {})
    if fid.get("level") != "high":
        problems.append(f"fidelity level is {fid.get('level')}")
    if snap.meta.get("skipped"):
        problems.append(f"crawler skipped: {snap.meta['skipped']}")
    again = crawl(MappingFetcher(mapping(build_site(v))), LIMITS)
    if again.sha256 != snap.sha256:
        problems.append("crawl is not deterministic")
    return {"variant": v.name, "snapshot_sha256": snap.sha256, "pages": sum(r.is_html for r in got.values()), "assets": sum(not r.is_html for r in got.values()), "references_checked": refs,
            "expected_files": len(files), "fidelity": fid, "problems": problems, "ok": not problems}
