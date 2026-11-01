#!/usr/bin/env python3
"""Capture a LOCALLY HOSTED static documentation build into a saved snapshot (offline operator tool; the product never fetches a URL).

    # 1. build the documentation yourself (example: Flask, BSD-3):  git clone https://github.com/pallets/flask && pip install -e flask && pip install pallets-sphinx-themes 'sphinx<9' sphinx-tabs sphinxcontrib-log-cabinet
    #    sphinx-build -b dirhtml flask/docs flask-site
    # 2. capture it (serves the directory on 127.0.0.1 only, crawls with the repository crawler: same origin, robots.txt honoured, GET only, bounded, scripts removed):
    #    python scripts/capture_docs_snapshot.py flask-site scanner-data/targets/flask-docs

The saved snapshot is what the registered `flask-docs` target loads. Fidelity limits are recorded in its metadata: scripts are removed, site search does not work, only GET was used."""
from __future__ import annotations

import functools
import http.server
import sys
import threading
from pathlib import Path

from agent_readiness.investigate.inspect.crawl import HttpFetcher, Limits, crawl


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    site, out = Path(argv[1]).resolve(), Path(argv[2])
    if not site.is_dir():
        print(f"not a directory: {site}")
        return 2
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a, **k):
            pass
    handler = functools.partial(Quiet, directory=str(site))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)                 # loopback only, ephemeral port
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        snap = crawl(HttpFetcher(f"http://127.0.0.1:{srv.server_address[1]}", allow_private_hosts=True), Limits(max_pages=150, max_depth=6))
    finally:
        srv.shutdown()
    snap.save(out)
    print(f"snapshot {snap.sha256}  pages={len(snap.pages())}  fidelity={snap.meta['fidelity']['level']}  saved to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
