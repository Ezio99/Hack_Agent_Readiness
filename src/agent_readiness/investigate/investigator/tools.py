"""Read-only evidence tools for the investigator (plan D8). The model decides WHICH to call and with what arguments; the tools are generic (no site-specific logic) and deterministic.

Isolation: tools read only the frozen snapshot, the inspector/trace observations, and INVESTIGATION-partition trials. Holdout trials and tasks do not exist as far as tools are
concerned; expected-answer values and `private/criteria.json` are never read here. Page-derived text is returned inside `untrusted_page_text` fields and is capped. Every fact-bearing
result is recorded as an Observation, so a hypothesis can cite it by id. `request_extra_trial` only RECORDS a request for the owner; nothing is executed or spent."""
from __future__ import annotations

import json
from typing import Any, Literal, Optional

from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict

from ..inspect.pagemodel import accessible_name, internal_path, norm, visible_text
from ..inspect.stage import load_snapshot
from ..models import Observation, Provenance
from ..run import InvestigationRun
from ..taskgen import freeze as freezer
from ..trials.trace import load_observations
from ..zoo.sealed import assert_blind

TOOLS = ("list_observations", "get_observation", "list_trials", "trial_summary", "get_step", "page_text", "page_dom", "links_from", "search_site", "compare_observation_to_dom", "check_claim",
         "request_extra_trial", "finish")
MAX_TEXT = 1500


class ToolCall(BaseModel):
    """One investigator action. Flat on purpose (strict structured output): fill the fields the tool uses, null the rest."""
    model_config = ConfigDict(extra="forbid")
    tool: Literal["list_observations", "get_observation", "list_trials", "trial_summary", "get_step", "page_text", "page_dom", "links_from", "search_site", "compare_observation_to_dom",
                  "check_claim", "request_extra_trial", "finish"]
    evidence_id: Optional[str]
    trial_id: Optional[str]
    task_id: Optional[str]
    step: Optional[int]
    path: Optional[str]
    css: Optional[str]
    text: Optional[str]
    claim_kind: Optional[str]
    label: Optional[str]
    scope: Optional[str]
    k: Optional[int]


def _cap(s: str, n: int = MAX_TEXT) -> str:
    return s if len(s) <= n else s[:n] + " …[truncated]"


class Workspace:
    def __init__(self, run: InvestigationRun, *, mode: str | None = None):
        self.run, self.mode = run, mode or run.mode
        self.snapshot, self.profile = load_snapshot(run), run.artifact("site-profile")
        self.manifest, self.private = freezer.load(run)
        att = run.artifact("attribution") if run.has_artifact("attribution") else {}
        self.att = {k: v for k, v in att.items() if v["partition"] == "investigation"}                    # holdout trials are invisible
        self.trials = {k: run.artifact(f"trials/baseline-{k}") for k in self.att}
        self.inv_tasks = {t["task_id"]: t for t in self.manifest["tasks"] if t["partition"] == "investigation"}
        self.pending_requests: list[dict] = []
        self.prov = Provenance(mode=self.mode, source="tool:investigator")

    # -- helpers -------------------------------------------------------------------------------------------------------
    def _record(self, kind: str, summary: str, data: dict, refs: list[str]) -> str:
        return self.run.evidence.add_observation(Observation(kind=kind, summary=summary, data=data, refs=refs, provenance=self.prov)).id

    def _trial(self, trial_id: str | None) -> dict:
        if not trial_id or trial_id not in self.trials:
            raise KeyError("unknown trial id (only investigation trials listed by list_trials exist)")
        return self.trials[trial_id]

    def _page(self, path: str | None):
        r = self.snapshot.get(path or "")
        if r is None or not r.is_html:
            raise KeyError(f"no such page in the snapshot: {path!r}")
        return r

    # -- dispatch ------------------------------------------------------------------------------------------------------
    def call(self, c: ToolCall) -> dict[str, Any]:
        try:
            out = getattr(self, "t_" + c.tool)(c)
        except KeyError as exc:
            out = {"error": str(exc.args[0])}
        except Exception as exc:                                         # a bad argument must never crash the investigation
            out = {"error": f"{type(exc).__name__}: bad arguments"}
        assert_blind(json.dumps(out, default=str))                       # no protected diagnosis text may reach the model, even via tool output
        return out

    # -- tools ---------------------------------------------------------------------------------------------------------
    def t_list_observations(self, c):
        keep = [o for o in self.run.evidence.observations.values() if o.provenance.source in ("rule:inspector", "rule:trace-analysis")]
        return {"observations": [{"evidence_id": o.id, "kind": o.kind, "summary": _cap(o.summary, 400)} for o in keep][:60]}

    def t_get_observation(self, c):
        o = self.run.evidence.observations.get(c.evidence_id or "")
        if o is None:
            raise KeyError("unknown evidence id")
        return {"evidence_id": o.id, "kind": o.kind, "summary": o.summary, "data": json.loads(_cap(json.dumps(o.data, default=str), 3000)) if len(json.dumps(o.data, default=str)) <= 3000 else {"truncated": _cap(json.dumps(o.data, default=str), 3000)}, "refs": o.refs}

    def t_list_trials(self, c):
        return {"trials": [{"trial_id": k, "question": self.inv_tasks[a["task_id"]]["question"], "kind": a["kind"], "passed": a["passed"], "evidence_backed": a["evidence_backed"], "attribution": a["primary"],
                            "void": a["void"], "page_views": a["signals"]["page_views"]} for k, a in sorted(self.att.items())]}

    def t_trial_summary(self, c):
        t = self._trial(c.trial_id)
        a = self.att[c.trial_id]
        ev = t["evaluation"]
        data = {"trial_id": c.trial_id, "question": self.inv_tasks[a["task_id"]]["question"], "start_path": self.inv_tasks[a["task_id"]]["start_path"], "passed": ev["passed"], "evidence_backed": ev["evidence_backed"],
                "agent_answer": _cap(json.dumps(t["outcome"]["answer"], default=str), 300), "run_status": t["outcome"]["run_status"], "attribution": a["primary"], "attribution_why": a["why"], "signals": a["signals"],
                "pages_visited": [j["path"] for j in t["journey"]], "mirror_statuses": [e["status"] for e in t["mirror"]["log"]], "model_requests": t["metrics"]["model_requests"]}
        return {"evidence_id": self._record("trial_detail", f"Trial {c.trial_id} detail: {a['primary']}, {len(data['pages_visited'])} pages visited, passed={ev['passed']}", data, [f"trial:{c.trial_id}"]), **data}

    def t_get_step(self, c):
        t = self._trial(c.trial_id)
        n = c.step or 1
        if not 1 <= n <= len(t["journey"]):
            raise KeyError(f"step must be 1..{len(t['journey'])}")
        j = t["journey"][n - 1]
        obs = load_observations(self.run, t)
        text = obs[n - 1]["text"] if n - 1 < len(obs) else ""
        data = {"trial_id": c.trial_id, "step": n, "path": j["path"], "actions": j["actions"], "action_results": j["executed"], "observation_chars": len(text)}
        eid = self._record("trial_step", f"Trial {c.trial_id} step {n}: page {j['path']}, actions {[a['name'] for a in j['actions']]}", data, [f"trial:{c.trial_id}#step{n}"])
        return {"evidence_id": eid, **data, "untrusted_page_text": _cap(text, 1200)}

    def t_page_text(self, c):
        r = self._page(c.path)
        s = BeautifulSoup(r.text(), "html.parser")
        text = visible_text(s)
        eid = self._record("page_text", f"Visible text of {c.path} ({len(text)} characters)", {"path": c.path, "chars": len(text)}, [f"page:{c.path}"])
        return {"evidence_id": eid, "path": c.path, "title": s.title.get_text() if s.title else "", "untrusted_page_text": _cap(text)}

    def t_page_dom(self, c):
        r = self._page(c.path)
        s = BeautifulSoup(r.text(), "html.parser")
        els = s.select(c.css or "a")[:10]
        rows = [{"tag": e.name, "text": _cap(visible_text(e), 120), "accessible_name": accessible_name(e, s)[0], "name_source": accessible_name(e, s)[1],
                 "attrs": {k: e.get(k) for k in ("href", "aria-label", "alt", "title", "role", "type", "name", "for") if e.get(k)}} for e in els]
        eid = self._record("dom_query", f"{len(rows)} element(s) match {c.css!r} on {c.path}", {"path": c.path, "css": c.css, "matches": rows}, [f"page:{c.path}"])
        return {"evidence_id": eid, "path": c.path, "css": c.css, "matches": rows}

    def t_links_from(self, c):
        self._page(c.path)
        ctrls = [{"href": x["href"], "name": x["name"], "name_source": x["name_source"], "landmark": x["landmark"]} for x in self.profile["pages"][c.path]["controls"] if x["href"]][:30]
        eid = self._record("links", f"{len(ctrls)} link(s) on {c.path}; {sum(1 for x in ctrls if not x['name'])} without an accessible name", {"path": c.path, "links": ctrls}, [f"page:{c.path}"])
        return {"evidence_id": eid, "path": c.path, "links": ctrls}

    def t_search_site(self, c):
        q = norm(c.text or "").lower()
        if len(q) < 2:
            raise KeyError("text must have at least 2 characters")
        hits = []
        for r in self.snapshot.pages():
            t = visible_text(BeautifulSoup(r.text(), "html.parser"))
            i = t.lower().find(q)
            if i >= 0:
                hits.append({"path": r.path, "snippet": _cap(t[max(0, i - 40): i + 80], 140)})
        eid = self._record("site_search", f"{len(hits)} page(s) contain {q!r}", {"query": q, "paths": [h["path"] for h in hits[:10]]}, [f"page:{h['path']}" for h in hits[:5]])
        return {"evidence_id": eid, "matches": hits[:10]}

    def t_compare_observation_to_dom(self, c):
        t = self._trial(c.trial_id)
        n = c.step or 1
        if not 1 <= n <= len(t["journey"]):
            raise KeyError(f"step must be 1..{len(t['journey'])}")
        path = t["journey"][n - 1]["path"]
        obs = load_observations(self.run, t)
        seen = norm(obs[n - 1]["text"]).lower() if n - 1 < len(obs) else ""
        page = self.profile["pages"].get(path, {"facts": [], "headings": [], "controls": []})
        wanted = [f"{f['label']}: {f['value']}" for f in page["facts"]] + [h["text"] for h in page["headings"]]
        missing = [w for w in wanted if norm(w.split(": ")[-1]).lower() not in seen][:12]
        data = {"trial_id": c.trial_id, "step": n, "path": path, "page_facts_and_headings": len(wanted), "not_in_observation": missing}
        return {"evidence_id": self._record("observation_vs_dom", f"Trial {c.trial_id} step {n} ({path}): {len(missing)} of {len(wanted)} page facts/headings absent from the model's observation", data, [f"trial:{c.trial_id}#step{n}", f"page:{path}"]), **data}

    def t_check_claim(self, c):
        from .verifiers import preview
        return preview(self, c.claim_kind, {"label": c.label, "scope": c.scope, "k": c.k})

    def t_request_extra_trial(self, c):
        if c.task_id not in self.inv_tasks:
            raise KeyError("unknown task id (investigation tasks only)")
        self.pending_requests.append({"task_id": c.task_id, "reason": _cap(c.text or "", 300)})
        return {"recorded": True, "note": "Recorded as a request for the owner. Nothing is run or spent automatically."}
