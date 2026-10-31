"""The text a model is actually SHOWN for every page of every arm of the Ironbark site, captured once through real Chromium with the SAME serializer the agent uses
(`browser_state_summary.dom_state.llm_representation()`, profile `suite-v2-compat1`). Evidence criteria are verified against these views, never against `get_text()` of the HTML: the first criteria
were verified against plain page text and so accepted needles that the live view (element markers such as `*[934]<td />` between a table label and its value) can never contain.

The captured views are committed (`collaboration/experiments/EXP2/model-views.json.gz`) so the credential-free tests and `readiness exp2 pool` need no browser. Each page records the SHA-256 of the HTML it
was captured from, so a changed template makes `stale()` non-empty (offline test); `capture_all` + a browser test prove the committed file equals what Chromium shows now."""
from __future__ import annotations

import gzip
import hashlib
import json
from functools import lru_cache
from pathlib import Path

from ..sites.ironbark import variants as V
from .evidence import BREAK
from ..sites.ironbark.build import build_site, is_page

PATH = Path(__file__).resolve().parents[3] / "collaboration" / "experiments" / "EXP2" / "model-views.json.gz"
SCHEMA = "exp2-model-views-v1"
PROFILE = "suite-v2-compat1"


def arm_names() -> list[str]:
    return [v.name for v in (V.CONTROL, *V.all_single(), V.parse("discoverability+availability+cost+compatibility"))]


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sources(arm: str) -> dict[str, bytes]:
    return {p: b for p, b in build_site(V.parse(arm)).items() if is_page(p)}


def changed_paths(arm: str) -> list[str]:
    """Pages whose HTML differs from the control's (all pages for the control itself): only these need their own capture."""
    if arm == V.CONTROL.name:
        return sorted(sources(arm))
    base = {p: _sha(b) for p, b in sources(V.CONTROL.name).items()}
    return sorted(p for p, b in sources(arm).items() if base.get(p) != _sha(b))


MAX_SCROLLS = 14


async def capture_arm(arm: str, paths: list[str] | None = None) -> dict[str, dict]:
    """{path: {"html_sha256", "views": [...]}} for the arm's pages, read through the production browser session and serializer. The model is shown only the part of a page near the viewport, so a page
    is captured at successive scroll positions until its bottom; `views` holds every DISTINCT view in order (a fact lower on the page is evidence the model can reach by scrolling, and the extra steps
    are a cost in browsing efficiency, never a missing fact)."""
    from playwright.async_api import async_playwright

    from ..agent import browser_options, prepare_browser_environment, profile
    from ..investigate.sitemodel.server import Mirror
    from ..scanner.serve import serve_app
    from . import snapshot as S

    prepare_browser_environment()
    from browser_use import Browser
    src, effective, out = sources(arm), profile(PROFILE), {}
    todo = paths if paths is not None else changed_paths(arm)
    async with serve_app(Mirror(S.snapshot(arm))) as base, async_playwright() as pw:
        session = Browser(**browser_options(base + "/", pw.chromium.executable_path, effective))
        try:
            await session.start()
            conn = await pw.chromium.connect_over_cdp(session.cdp_url)
            context = conn.contexts[0]
            page = context.pages[0] if context.pages else await context.new_page()
            for p in todo:
                await page.goto(base + p)
                await page.wait_for_load_state("load")
                views = []
                for _ in range(MAX_SCROLLS):
                    state = await session.get_browser_state_summary(include_screenshot=False, cached=False)
                    v = state.dom_state.llm_representation()
                    if v not in views:
                        views.append(v)
                    at_bottom = await page.evaluate("window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2")
                    if at_bottom:
                        break
                    await page.evaluate("window.scrollBy({top: window.innerHeight * 0.8, behavior: 'instant'})")      # instant: a smooth scroll can be captured mid-animation
                    await page.wait_for_timeout(150)
                out[p] = {"html_sha256": _sha(src[p]), "views": views}
        finally:
            await session.kill()
    return out


async def capture_all() -> dict:
    arms = {}
    for arm in arm_names():
        arms[arm] = await capture_arm(arm)
    return {"schema": SCHEMA, "profile": PROFILE, "arms": arms}


def write(doc: dict, path: Path = PATH) -> str:
    raw = json.dumps(doc, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    path.write_bytes(gzip.compress(raw, mtime=0))                                   # mtime 0: the file bytes are reproducible
    return hashlib.sha256(raw).hexdigest()


@lru_cache(maxsize=1)
def _doc() -> dict:
    if not PATH.exists():
        raise FileNotFoundError(f"{PATH} is missing: run `readiness exp2 views --write` (needs Chromium)")
    return json.loads(gzip.decompress(PATH.read_bytes()))


def views_sha256() -> str:
    return hashlib.sha256(json.dumps(_doc(), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def arm_views(arm: str) -> dict[str, str]:
    """{path: model-visible text} for every page of the arm (the control's capture for pages the arm leaves unchanged). A page's text is all its distinct scroll views, in order."""
    doc = _doc()["arms"]
    out = {p: BREAK.join(x["views"]) for p, x in doc[V.CONTROL.name].items()}
    if arm != V.CONTROL.name:
        out |= {p: BREAK.join(x["views"]) for p, x in doc[arm].items()}
    return out


def all_views() -> dict[str, dict[str, str]]:
    return {a: arm_views(a) for a in arm_names()}


def stale() -> list[str]:
    """Pages whose current HTML differs from the HTML the committed view was captured from (empty = the committed views are current)."""
    doc, bad = _doc()["arms"], []
    for arm in arm_names():
        want = changed_paths(arm)
        have = doc.get(arm, {})
        src = sources(arm)
        bad += [f"{arm}:{p}" for p in want if p not in have or have[p]["html_sha256"] != _sha(src[p])]
        bad += [f"{arm}:{p} (not a changed page)" for p in have if p not in want]
    return bad


def covers(a: str, b: str) -> list[str]:
    """Lines of capture `b` (views joined by BREAK) that capture `a` does not contain, compared on the canonical form. A line cut by the edge of the screen in one capture is a substring of its whole form in the
    other, so only content that is genuinely missing is reported."""
    from .evidence import norm
    whole = norm(a.replace(BREAK, "\n"))
    return sorted({n for ln in b.replace(BREAK, "\n").split("\n") if (n := norm(ln)) and n not in whole})
