"""Zero-spend DEV PROVIDER: a loopback stand-in for the Meta chat-completions endpoint, used to exercise the whole live path (preflight, spend gate, ledger, approvals, key handling, browser agent over HTTP,
structured outputs) without any real model. It is NOT a model: it replies from fixtures built out of the run's own captured site (rule candidates for task proposals, the scripted mock agent for browsing,
the scripted investigator). It refuses to listen on anything but loopback, and a real key is never needed (any string is accepted). Nothing it returns is evidence about model behaviour.

    python -m agent_readiness.live.devprovider --root scanner-data/live --port 8199
Then run the server with LIVE_MODEL_BASE_URL=http://127.0.0.1:8199/v1, SCANNER_LIVE_ENABLED=1, SCANNER_LIVE_BUDGET_USD=10 and any META_MODEL_API_KEY value."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request

from ..investigate.run import InvestigationRun
from ..investigate.taskgen import freeze as freezer
from ..investigate.taskgen.candidates import candidates
from ..investigate.trials.runner import mock_handler
from ..investigate.taskgen import goal as G
from . import mock_investigator
from .lexicon import RENTAL

TASKGEN_MARK, INVESTIGATOR_MARK = "You design evaluation tasks", "You are an investigator of why browsing agents"
CRITERION_KEYS = ("page", "label", "target", "listing", "direction", "conditions")


IMAGE = re.compile(r"data:image/[^\"]+")


def _text(body: dict) -> str:
    return json.dumps(body.get("messages", []))


def _chars(text: str) -> int:
    """Characters that would be billed as text: embedded images are replaced by a fixed small allowance, as a vision model counts them in tiles, not bytes."""
    return len(IMAGE.sub("", text)) + 800 * len(IMAGE.findall(text))


def _wrap(content: str, usage: dict, model: str = "dev-provider") -> dict:
    return {"id": "dev-1", "object": "chat.completion", "created": 0, "model": model, "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}], "usage": usage}


def follow_goal(goal: str, profile: dict, n: int = 12) -> tuple[dict, list[dict]]:
    """A deterministic stand-in for a goal-following MODEL (dev provider and tests only): tasks about the goal's entities and aspects, written from the captured site. Answers are never supplied; the gate
    derives them by code."""
    ga = G.analyse(goal, profile, RENTAL)
    pages = profile["pages"]
    name = lambda i: (pages[i]["headings"][0]["text"] if pages[i]["headings"] else pages[i]["title"].split("|")[0]).strip()
    tasks = []

    def add(q, crit, link):
        tasks.append({"question": q, "start_path": "/", "criterion": crit, "rationale": "stand-in for a goal-following model", "goal_link": link})
    for item in ga["entity_items"]:
        have = {f["label"] for f in pages[item]["facts"]}
        if "price" in ga["asked_aspects"] and "per day" in have:
            add(f"What is the per day hire rate listed on the page of the {name(item)}?", {"kind": "page_fact", "page": item, "label": "per day"}, f"{name(item)}: price")
        if "availability" in ga["asked_aspects"]:
            cal = item + "/availability"
            cells = [f["label"] for f in pages.get(cal, {"facts": []})["facts"] if f["how"] == "calendar-cell"]
            if cal in pages:
                add(f"Find the live availability calendar for the {name(item)} hire.", {"kind": "reach_page", "target": cal}, f"{name(item)}: availability")
            if "14 nov" in cells:
                add(f"What does the booking calendar of the {name(item)} show for 14 Nov?", {"kind": "page_fact", "page": cal, "label": "14 nov"}, f"{name(item)}: availability")
        for label in ga["attribute_labels"]:
            if label in have:
                add(f"What is the {label} listed on the page of the {name(item)}?", {"kind": "page_fact", "page": item, "label": label}, f"{name(item)}: {label}")
    if "price" in ga["asked_aspects"] and ga["entity_listings"] and all("per day" in {f["label"] for f in pages[i]["facts"]} for i in ga["entity_items"]):
        add("Which item in the cutting category has the lowest per day hire rate on its own page?", {"kind": "extremum", "listing": ga["entity_listings"][0], "label": "per day", "direction": "min"}, "cheapest cutting tool: price")
    analysis = {"entities": [name(i) for i in ga["entity_items"]], "attributes": ga["attribute_labels"] + ga["asked_aspects"], "comparisons": ga["ordering_terms"], "information_gaps": [d["detail"] for d in ga["limitation_details"]]}
    return analysis, tasks[:n]


class DevProvider:
    def __init__(self, root: Path, usage_scale: float = 1.0, scale_roles: tuple = ("taskgen", "agent", "investigator")):
        self.root, self.scale, self.scale_roles = Path(root), usage_scale, tuple(scale_roles)
        self.calls = {"taskgen": 0, "agent": 0, "investigator": 0}
        self._handlers: dict[tuple, object] = {}
        self._inv: dict[str, object] = {}
        self.keys_seen: set[str | None] = set()
        self.taskgen_prompts: list[str] = []
        self.investigator_prompts: list[str] = []

    def run(self) -> InvestigationRun:
        runs = sorted((p.parent for p in self.root.glob("live-*/run.json")), key=lambda d: d.stat().st_mtime)
        if not runs:
            raise RuntimeError("no live run directory yet")
        return InvestigationRun(runs[-1])

    def usage(self, prompt_chars: int, completion_chars: int, role: str = "taskgen") -> dict:
        k = self.scale if role in self.scale_roles else 1.0
        p, c = int(max(1, prompt_chars // 4) * k), int(max(1, completion_chars // 4) * k)
        return {"prompt_tokens": p, "completion_tokens": c, "total_tokens": p + c}

    def handle(self, body: dict) -> dict:
        text = _text(body)
        run = self.run()
        if TASKGEN_MARK in text:
            return self._taskgen(run, body, text)
        if INVESTIGATOR_MARK in text:
            return self._investigator(run, body, text)
        return self._agent(run, body, text)

    def _taskgen(self, run, body, text) -> dict:
        self.taskgen_prompts.append(text)
        i = self.calls["taskgen"]
        self.calls["taskgen"] += 1
        if "taskgen_goal" in json.dumps(body.get("response_format", {})):                                      # goal-bound request: emulate a model that follows the goal when the site allows it (deterministic stand-in), else an ignoring one
            m = re.search(r"EVALUATION GOAL \(binding\): (.*?)\\nStep 1", text)
            analysis, tasks = follow_goal(m.group(1) if m else "", run.artifact("site-profile"), 12)
            if not tasks:
                drafts = candidates(run.artifact("site-profile"))
                tasks = [{"question": d.question, "start_path": d.start_path, "criterion": {"kind": d.criterion["kind"], **{k: None for k in CRITERION_KEYS}, **d.criterion}, "rationale": "DEV PROVIDER fixture (ignores the goal)", "goal_link": "none"} for d in drafts[i * 3:i * 3 + 4]]
            else:
                tasks = [{**t, "criterion": {**{k: None for k in CRITERION_KEYS}, **t["criterion"]}} for t in tasks[i * 2: i * 2 + 4]] or tasks[:1]
            content = json.dumps({"goal_analysis": analysis, "tasks": tasks})
            return _wrap(content, self.usage(_chars(text), len(content), "taskgen"))
        drafts = candidates(run.artifact("site-profile"))
        pick = [drafts[(i * 3 + k) % len(drafts)] for k in range(4)] if drafts else []
        tasks = [{"question": d.question, "start_path": d.start_path, "criterion": {"kind": d.criterion["kind"], **{k: None for k in CRITERION_KEYS}, **d.criterion}, "rationale": f"DEV PROVIDER fixture: {d.rationale}"[:300]} for d in pick]
        content = json.dumps({"tasks": tasks})
        return _wrap(content, self.usage(_chars(text), len(content), "taskgen"))

    def _agent(self, run, body, text) -> dict:
        self.calls["agent"] += 1
        inst = next((x for x in freezer.instances(run) if x.spec.objective in text), None)
        if inst is None:
            raise RuntimeError("the browser agent asked about a task that is not in the run")
        base = re.search(r"http://127\.0\.0\.1:\d+", text)
        key = (run.state["id"], inst.spec.task_id)
        if key not in self._handlers:
            self._handlers[key] = mock_handler(inst, base.group(0) if base else "http://127.0.0.1", "correct", [r.value for r in inst.evidence if r.kind == "visited_path"])
        r = self._handlers[key](type("R", (), {"content": json.dumps(body).encode()})())
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        return _wrap(content, self.usage(_chars(text), len(content), "agent"))

    def _investigator(self, run, body, text) -> dict:
        self.calls["investigator"] += 1
        self.investigator_prompts.append(text)
        client = self._inv.setdefault(run.state["id"], mock_investigator.make(run))
        req = type("Q", (), {"messages": body["messages"]})()
        content = client._responses(req)
        return _wrap(content, self.usage(_chars(text), len(content), "investigator"))


def make_app(provider: DevProvider):
    app = FastAPI(docs_url=None, openapi_url=None)
    app.state.provider = provider

    @app.post("/v1/chat/completions")
    async def completions(request: Request):
        provider.keys_seen.add(request.headers.get("authorization"))
        try:
            return provider.handle(await request.json())
        except Exception as exc:
            raise HTTPException(500, f"dev provider: {type(exc).__name__}: {exc}"[:200])
    return app


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Zero-spend loopback stand-in for the Meta endpoint (NOT a model)")
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--port", type=int, default=8199)
    ap.add_argument("--usage-scale", type=float, default=1.0, help="multiply reported token usage (to exercise the budget stop)")
    ap.add_argument("--scale-roles", default="taskgen,agent,investigator", help="which roles --usage-scale applies to")
    a = ap.parse_args(argv)
    import uvicorn
    uvicorn.run(make_app(DevProvider(a.root, a.usage_scale, tuple(a.scale_roles.split(",")))), host="127.0.0.1", port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
