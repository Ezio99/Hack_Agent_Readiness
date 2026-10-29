"""HTTP(S) network capture for external evaluators. Browser Use 0.11.13's built-in HAR recorder keeps HTTPS requests only (`_is_https` filter in
har_recording_watchdog.py), so on WebArena's plain-HTTP site its HAR is empty. This records every request/response of the agent's browser through a second
Playwright connection over CDP and writes a HAR 1.2 file containing what the official WebArena Verified evaluator reads (method, URL, request headers incl. Accept /
Sec-Fetch-*, post data, response status, JSON/text response bodies up to a size cap)."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

MAX_BODY = 200_000
TEXTUAL = ("json", "html", "text", "xml", "javascript")


class NetworkCapture:
    def __init__(self, har_path: Path, origin_prefixes: tuple[str, ...] = ()):
        self.path, self.prefixes = Path(har_path), origin_prefixes
        self.entries: list[dict] = []
        self._pw = self._browser = None
        self._tasks: set[asyncio.Task] = set()

    async def attach(self, cdp_url: str) -> None:
        from playwright.async_api import async_playwright
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.connect_over_cdp(cdp_url)
        for ctx in self._browser.contexts:
            ctx.on("requestfinished", lambda req: self._spawn(self._record(req)))
            ctx.on("requestfailed", lambda req: self._spawn(self._record(req, failed=True)))

    def _spawn(self, coro) -> None:
        t = asyncio.ensure_future(coro)
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)

    async def _record(self, req, failed: bool = False) -> None:
        try:
            if self.prefixes and not req.url.startswith(self.prefixes):
                return
            headers = await req.all_headers()
            resp = None if failed else await req.response()
            body, mime, status, rh = "", "", 0, {}
            if resp is not None:
                status, rh = resp.status, await resp.all_headers()
                mime = rh.get("content-type", "")
                if any(k in mime for k in TEXTUAL):
                    try:
                        body = (await resp.text())[:MAX_BODY]
                    except Exception:
                        body = ""        # redirects / aborted bodies
            entry = {"startedDateTime": datetime.now(timezone.utc).isoformat(), "time": 0,
                     "request": {"method": req.method, "url": req.url, "httpVersion": "HTTP/1.1", "headers": [{"name": k, "value": v} for k, v in headers.items()],
                                 "queryString": [], "cookies": [], "headersSize": -1, "bodySize": -1},
                     "response": {"status": status, "statusText": "", "httpVersion": "HTTP/1.1", "headers": [{"name": k, "value": v} for k, v in rh.items()], "cookies": [],
                                  "content": {"size": len(body), "mimeType": mime, "text": body}, "redirectURL": rh.get("location", ""), "headersSize": -1, "bodySize": -1},
                     "cache": {}, "timings": {"send": 0, "wait": 0, "receive": 0}}
            if req.post_data:
                entry["request"]["postData"] = {"mimeType": headers.get("content-type", ""), "text": req.post_data}
            self.entries.append(entry)
        except Exception:
            pass                          # a request that vanishes mid-capture must never break the run

    async def close(self) -> None:
        if self._tasks:
            await asyncio.wait(list(self._tasks), timeout=5)
        har = {"log": {"version": "1.2", "creator": {"name": "agent-readiness-capture", "version": "1"}, "pages": [], "entries": self.entries}}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(har))
        if self._browser is not None:
            try:
                await self._browser.close()          # disconnects our CDP client; the agent's browser is killed by the caller
            except Exception:
                pass
        if self._pw is not None:
            await self._pw.stop()


SENSITIVE_HEADERS = {"cookie", "set-cookie", "authorization", "proxy-authorization", "x-m2-customer-auto-login"}


def sanitize_har(src: Path, dst: Path) -> dict:
    """Write a storable copy of a captured HAR: sensitive headers redacted, response bodies dropped (sizes kept), post data replaced by its length.
    The official evaluator must run on the ORIGINAL HAR (it reads bodies); this copy is for inspection/archival only and remains private (site content is not for publication)."""
    har = json.loads(Path(src).read_text())
    redacted = 0
    for e in har["log"]["entries"]:
        for part in (e["request"], e["response"]):
            for h in part["headers"]:
                if h["name"].lower() in SENSITIVE_HEADERS:
                    h["value"], redacted = "[redacted]", redacted + 1
        e["response"]["content"]["text"] = ""
        if "postData" in e["request"]:
            e["request"]["postData"]["text"] = f"[{len(e['request']['postData']['text'])} chars removed]"
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    Path(dst).write_text(json.dumps(har))
    return {"entries": len(har["log"]["entries"]), "headers_redacted": redacted}
