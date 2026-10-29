"""Deterministic verifiers for the closed claim grammar (plan D8) and the promotion rule.

A verifier checks ONE claim kind against the frozen snapshot, the site profile and the attribution of INVESTIGATION trials. It never reads a model's reasoning; it reads the
hypothesis' parameters (label / scope / k) and recomputes the facts. A parameter value must also appear in the hypothesis statement, so a claim cannot be verified under
parameters its text does not state. Kinds without an implemented verifier return `unverifiable` — the grammar stays honest about what code can actually check.

Result per kind: supported | refuted | unverifiable, the evidence refs, SUPPORT (distinct investigation tasks whose trials show the effect) and `structural_proof` (a deterministic
structure that by itself blocks a task, e.g. the only path to the evidence goes through unnamed controls). Promotion to a Finding additionally needs >= 2 independent supports or a
structural proof (enforced in `EvidenceStore.promote`) and a website-side attribution (`ATTRIBUTION[kind]`)."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from statistics import median

from ..models import CLAIM_KINDS, Hypothesis, Provenance, Verification
from ..taskgen.criteria import norm_answer

ATTRIBUTION = {"info_absent_on_template": "website", "control_unlabeled": "website", "info_only_after_k_hops": "website", "error_response_on_path": "website",
               "observation_missing_dom_content": "undetermined", "step_overhead_vs_minimum": "undetermined", "repeated_navigation": "agent", "inconsistent_content_across_pages": "undetermined"}


@dataclass
class Result:
    result: str
    detail: str
    evidence: list[str] = field(default_factory=list)
    support: list[str] = field(default_factory=list)
    structural_proof: bool = False


def _one_per_task(ws, trial_ids: list[str]) -> list[str]:
    """Independent support = distinct TASKS. Repeats of one task are the same evidence several times, never independent."""
    seen, out = set(), []
    for t in sorted(trial_ids):
        task = ws.att[t]["task_id"]
        if task not in seen:
            seen.add(task)
            out.append(f"trial:{t}")
    return out


def _valid_trials(ws):
    return {k: a for k, a in ws.att.items() if not a["void"]}


SUPPORTING_CLASSES = ("undetermined", "website", "tool_interface")


def _impacted(ws, pred) -> list[str]:
    """Support = one non-void investigation trial per task in which the claimed pattern plausibly COST something and nothing else explains the trial:
    a clean success needing >= 2 extra page views, or a failure attributed to website / tool_interface / undetermined (e.g. budget spent before the evidence).
    Trials attributed to the agent (the decisive text was shown, a named link was not followed, malformed answer), invalid tasks and right-answer-without-evidence runs never count."""
    out, seen = [], set()
    for k, a in sorted(_valid_trials(ws).items()):
        if a["task_id"] in seen or not pred(a):
            continue
        if a["primary"] in SUPPORTING_CLASSES or (a["primary"] == "success" and a["signals"]["extra_page_views"] >= 2):
            seen.add(a["task_id"])
            out.append(f"trial:{k}")
    return out


def v_info_absent_on_template(ws, p):
    label = norm_answer(p.get("label") or "")
    if not label:
        return Result("unverifiable", "needs `label`: the labelled field claimed to be absent from the listing")
    for l in ws.profile["listings"]:
        f = next((v for k, v in l["fields"].items() if norm_answer(k) == label), None)
        if f is None or f["detail_pages"] < 2:
            continue
        if f["in_listing_item"] <= f["detail_pages"] * 0.5:
            prefix = l["detail_template"].replace("{}", "")
            sup = _impacted(ws, lambda a: any(pg.startswith(prefix) for pg in a["signals"]["evidence_pages_visited"] + a["signals"]["evidence_pages_unvisited"]))
            return Result("supported", f"on {l['listing']} the field {label!r} is on {f['detail_pages']} linked pages but shown in {f['in_listing_item']} listing items", [f"page:{l['listing']}"], sup)
        return Result("refuted", f"{label!r} is shown in the listing items of {l['listing']} ({f['in_listing_item']} of {f['detail_pages']})", [f"page:{l['listing']}"])
    return Result("unverifiable", f"no listing with a field labelled {label!r} on its linked pages")


def _named_reachable(ws, start: str) -> set[str]:
    pages, seen, q = ws.profile["pages"], {start}, deque([start])
    while q:
        cur = q.popleft()
        for c in pages[cur]["controls"]:
            if c["href"] in pages and c["name"] and c["href"] not in seen:
                seen.add(c["href"])
                q.append(c["href"])
    return seen


def v_control_unlabeled(ws, p):
    scope = p.get("scope")
    items = [(t, i) for t, rows in ws.profile["unnamed_controls"].items() for i in rows if not i["weak_only"] and (not scope or scope in (t, i["page"]))]
    if not items:
        return Result("refuted" if scope is None or scope in ws.profile["pages"] or scope in ws.profile["templates"] else "unverifiable", "no interactive control without an accessible name in scope")
    blocked = []
    for tid, tk in ws.inv_tasks.items():
        reach = _named_reachable(ws, tk["start_path"])
        ev = [pg for pg in ws.private[tid]["evidence_paths"]]
        if any(pg not in reach for pg in ev):
            blocked.append(tid)
    sup = _impacted(ws, lambda a: a["task_id"] in blocked or a["primary"] in ("website", "tool_interface"))
    return Result("supported", f"{len(items)} control(s) without an accessible name in scope; {len(blocked)} investigation task(s) cannot reach their evidence through named links alone",
                  [f"page:{i['page']}" for _, i in items[:5]], sup, structural_proof=bool(blocked))


def v_info_only_after_k_hops(ws, p):
    k = p.get("k")
    if not isinstance(k, int) or k < 2:
        return Result("unverifiable", "needs integer `k` >= 2")
    deep = {pg for pg, d in ws.profile["depth"].items() if d >= k}
    if not deep:
        return Result("refuted", f"no page is {k} or more link steps from the entry page")
    sup = _impacted(ws, lambda a: any(pg in deep for pg in a["signals"]["evidence_pages_visited"] + a["signals"]["evidence_pages_unvisited"]))
    return Result("supported", f"{len(deep)} page(s) are {k}+ link steps from the entry page", [f"page:{pg}" for pg in sorted(deep)[:5]], sup)


def v_step_overhead_vs_minimum(ws, p):
    k = p.get("k") if isinstance(p.get("k"), int) else 2
    v = _valid_trials(ws)
    if len(v) < 2:
        return Result("unverifiable", "fewer than 2 non-void investigation trials")
    med = median(a["signals"]["extra_page_views"] for a in v.values())
    sup = _one_per_task(ws, [t for t, a in sorted(v.items()) if a["signals"]["extra_page_views"] >= k])
    return Result("supported" if med >= k else "refuted", f"median extra page views over the minimum is {med} (threshold {k})", [], sup)


def v_repeated_navigation(ws, p):
    sup = _one_per_task(ws, [t for t, a in sorted(_valid_trials(ws).items()) if a["signals"]["revisited_pages"] or a["signals"]["max_identical_actions"] >= 3])
    return Result("supported" if sup else "refuted", f"{len(sup)} task(s) had a trial that revisited pages or repeated an identical action 3+ times", [], sup)


def v_observation_missing_dom_content(ws, p):
    sup = _one_per_task(ws, [t for t, a in sorted(_valid_trials(ws).items()) if a["primary"] == "tool_interface"])
    return Result("supported" if sup else "refuted", f"{len(sup)} task(s) had a trial that loaded a page whose decisive text never reached the model's text observation (the screenshot is not inspected, so this is never promoted to a finding)", [], sup)


def _linked_paths(ws) -> set[str]:
    """Every internal path some captured page links to (agents also request paths they merely GUESS; those are not website errors)."""
    out = set()
    for p in ws.profile["pages"].values():
        out |= {c["href"] for c in p["controls"] if c["href"]} | {l["href"] for l in p["links"] + p["nav_links"]}
    return out


def v_error_response_on_path(ws, p):
    linked = _linked_paths(ws)
    bad = sorted({e["path"] for t in ws.trials.values() for e in t["mirror"]["log"] if e["status"] >= 400 and e["path"] in linked})
    guessed = sorted({e["path"] for t in ws.trials.values() for e in t["mirror"]["log"] if e["status"] >= 400 and e["path"] not in linked})
    sup = _one_per_task(ws, [k for k, t in sorted(ws.trials.items()) if any(e["status"] >= 400 and e["path"] in linked for e in t["mirror"]["log"])])
    return Result("supported" if bad else "refuted", f"{len(bad)} link target(s) on the site returned an error status ({len(guessed)} other failing request(s) were paths no page links to and are not counted)", [f"page:{b}" for b in bad[:5]], sup)


def v_inconsistent_content_across_pages(ws, p):
    return Result("unverifiable", "no deterministic verifier is implemented for this claim kind yet")


VERIFIERS = {"info_absent_on_template": v_info_absent_on_template, "control_unlabeled": v_control_unlabeled, "info_only_after_k_hops": v_info_only_after_k_hops, "step_overhead_vs_minimum": v_step_overhead_vs_minimum,
             "repeated_navigation": v_repeated_navigation, "observation_missing_dom_content": v_observation_missing_dom_content, "error_response_on_path": v_error_response_on_path,
             "inconsistent_content_across_pages": v_inconsistent_content_across_pages}
assert set(VERIFIERS) == set(CLAIM_KINDS)


def run_verifier(ws, kind: str, params: dict, statement: str | None = None) -> Result:
    if kind not in VERIFIERS:
        return Result("unverifiable", f"unknown claim kind {kind!r}")
    if statement is not None:
        for key, val in params.items():
            if isinstance(val, str) and val and val.lower() not in statement.lower():
                return Result("unverifiable", f"parameter {key}={val!r} is not stated in the hypothesis text")
    try:
        return VERIFIERS[kind](ws, params)
    except Exception as exc:
        return Result("unverifiable", f"verifier error ({type(exc).__name__})")


def preview(ws, kind, params) -> dict:
    """check_claim tool: run a verifier now, store nothing."""
    r = run_verifier(ws, kind or "", params)
    return {"result": r.result, "detail": r.detail, "evidence": r.evidence[:5], "supporting_trials": len(r.support), "note": "preview only; verification of a submitted hypothesis is recorded separately"}


def verify_and_promote(ws, h: Hypothesis) -> dict:
    """Record the verification for a verifiable hypothesis and promote it when the rule allows. Returns a summary row."""
    store = ws.run.evidence
    r = run_verifier(ws, h.claim_kind, h.params, h.statement)
    store.record_verification(h.id, Verification(verifier=f"deterministic:{h.claim_kind}", result=r.result, evidence=r.evidence + r.support,
                                                 provenance=Provenance(mode=ws.mode, source="code:verifier")))
    row = {"hypothesis_id": h.id, "claim_kind": h.claim_kind, "result": r.result, "detail": r.detail, "support": len(r.support), "structural_proof": r.structural_proof, "finding_id": None, "promotion": None}
    if r.result == "supported":
        attribution = ATTRIBUTION[h.claim_kind]
        try:
            row["finding_id"] = store.promote(h.id, attribution=attribution, support=r.support, structural_proof=r.structural_proof).id
            row["promotion"] = "promoted"
        except Exception as exc:
            row["promotion"] = f"not promoted: {exc}"
    return row
