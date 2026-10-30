"""Build (in memory or to disk) and serve the Ironbark storefront. Output is deterministic; the default output directory `build/ironbark/<variant>/` is git-ignored."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import data as D
from .render import fingerprint, render_assets, render_pages
from .variants import CONTROL, Variant

CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".json": "application/json"}


def build_site(variant: Variant = CONTROL) -> dict[str, bytes]:
    """Every file of the site: canonical page paths ('/', '/hire', ...) and asset paths ('/assets/...') mapped to bytes."""
    files = {path: html.encode() for path, html in render_pages(variant).items()}
    files.update(render_assets())
    return files


def site_fingerprint(variant: Variant = CONTROL) -> str:
    return fingerprint(build_site(variant))


def is_page(path: str) -> bool:
    return not path.startswith("/assets/")


def write_site(variant: Variant, out: Path) -> Path:
    out = Path(out)
    for path, body in build_site(variant).items():
        target = out / path.lstrip("/") if not is_page(path) else (out / path.lstrip("/") / "index.html")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    (out / "VARIANT.json").write_text(json.dumps({"variant": variant.name, "as_of": D.AS_OF.isoformat(), "fingerprint": site_fingerprint(variant)}, indent=2) + "\n")
    return out


def make_handler(files: dict[str, bytes], not_found: bytes):
    class Handler(BaseHTTPRequestHandler):
        server_version = "IronbarkSite/1"

        def _send(self, status: int, body: bytes, ctype: str, head: bool = False, extra=()):
            self.send_response(status)
            self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store")
            for k, v in extra:
                self.send_header(k, v)
            self.end_headers()
            if not head:
                self.wfile.write(body)

        def _serve(self, head: bool):
            path = self.path.split("?", 1)[0].split("#", 1)[0]
            if len(path) > 1:
                path = path.rstrip("/")
            body = files.get(path)
            if body is None:
                return self._send(404, not_found, CONTENT_TYPES[".html"], head)
            return self._send(200, body, CONTENT_TYPES[Path(path).suffix] if Path(path).suffix in CONTENT_TYPES else CONTENT_TYPES[".html"], head)

        def do_GET(self):
            self._serve(False)

        def do_HEAD(self):
            self._serve(True)

        def _no(self):
            self._send(405, b"read-only demo site", "text/plain", extra=[("Allow", "GET, HEAD")])
        do_POST = do_PUT = do_DELETE = do_PATCH = _no

        def log_message(self, *a):
            pass
    return Handler


def serve(variant: Variant = CONTROL, port: int = 8200, host: str = "127.0.0.1"):
    from .render import _page
    files = build_site(variant)
    server = ThreadingHTTPServer((host, port), make_handler(files, _page("notfound.html", variant, current="", title="Page not found", description="Not found").encode()))
    return server
