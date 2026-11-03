"""The public evaluation document (lifecycle M8): ONE projection from a Stage B evaluation (the lifecycle store + its run directories, one per wording
condition) to what the product shows. Used unchanged by the web API for evaluations launched in the product and by the dataset builder that turns
the real M7 experiment into the preloaded demo dataset, so both share one data model, one evidence model and one reporting experience.

Reads private data SERVER-SIDE (expected outcomes, snapshot-specific evidence requirements, the v2 answer key) and emits only:
  * the agent's own recorded answers, actions and page paths (run evidence, as the hosted product already shows);
  * grades as recorded (official grader v1), the post-hoc grader v2 view (labelled), prospective rules (labelled, never applied);
  * COUNTS derived from the oracle (e.g. "1 of 5 expected items named", "4 required pages not shown"), never the expected items, criteria truths,
    evidence texts or the required page paths.
`audit.check` verifies every emitted document; a document that fails the audit is never served.

Six reporting dimensions, each made of measured quantities with their basis stated and NO composite score (no scoring method has been validated):
  task_success, navigation_efficiency, evidence_quality, information_accessibility, agent_reliability, coverage."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from ..diagnostics.behavioral import BROWSER_AUTO
from ..grading import contrast as GC
from ..grading import evidence_ranked as ER
from ..grading import v2 as G2
from ..hosted import telemetry
from ..investigate.inspect.profile import build_profile
from ..investigate.run import InvestigationRun
from ..investigate.taskgen import freeze as freezer
from ..investigate.trials.stage import VOID_STATUSES
from ..suites.records import public_task_view
from ..suites.store import WriteOnceStore
from ..taskeval.v2 import kinds as KD

SCHEMA = "lifecycle-evaluation-v1"
VERSION = "projection-1"
MODES = {"paid": {"label": "Paid evaluation", "provider": "real model", "notice": None},
         "rehearsal": {"label": "Rehearsal", "provider": "loopback dev provider (scripted stand-in, NOT a model)",
                       "notice": "ZERO-COST REHEARSAL: the agent's replies came from a scripted stand-in built from the frozen tasks, not from a model. "
                                 "It proves the pipeline end to end; it says nothing about agent or website performance."}}
EXPLORATORY_NOTE = ("Exploratory. {tasks} task(s) x {reps} repetition(s) per variant: the design has no statistical power for a general improvement "
                    "claim, and none is made. Differences are descriptive observations of these runs.")
COST_BASIS = "calculated from provider-reported token usage at published prices; not a bill"


# ------------------------------------------------------------------------------------------------------------------------------- helpers
def _answer(outcome: dict):
    a = (outcome or {}).get("answer")
    if isinstance(a, dict):
        if "answers" in a:
            return [str(x) for x in (a.get("answers") or [])]
        if "answer" in a:
            return a.get("answer") if isinstance(a.get("answer"), str) else None
    return None


FIXTURE_ISOLATION = "netns-loopback-mirror-only"
FIXTURE_NOTE = ("The agent quoted the address of the local test copy of the website it browsed; that address is shown as a site path "
                "(the raw answer is unchanged in the evidence).")


def fixture_origin(trial_dir: Path) -> str | None:
    """The ONE browser-local origin a trial's snapshot was served from, as the runner recorded it at the start of the trial's own trace: the jailed
    browser's isolation mode (`netns-loopback-mirror-only`) and its initial navigation to `http://127.0.0.1:<port>/`. Anything else (no trace, another
    isolation mode, another scheme, host, path, query or credentials) is not an approved fixture origin and returns None (M9)."""
    from urllib.parse import urlsplit
    mode = url = None
    try:
        with open(Path(trial_dir) / "trace.jsonl") as f:
            for i, line in enumerate(f):
                if i >= 20 or (mode and url):
                    break
                e = json.loads(line)
                if e.get("kind") == "browser_isolation":
                    mode = e.get("mode")
                elif e.get("kind") == "initial_actions" and url is None:
                    url = next((a["navigate"].get("url") for a in e.get("actions") or [] if isinstance(a, dict) and isinstance(a.get("navigate"), dict)), None)
    except (OSError, ValueError):
        return None
    if mode != FIXTURE_ISOLATION or not isinstance(url, str):
        return None
    p = urlsplit(url)
    try:
        port = p.port
    except ValueError:
        return None
    if p.scheme != "http" or p.hostname != "127.0.0.1" or not port or p.username or p.password or p.path not in ("", "/") or p.query or p.fragment:
        return None
    return f"http://127.0.0.1:{port}"


def site_relative(value, origin: str | None):
    """Replace exactly the trial's fixture origin by a site path (`http://127.0.0.1:34723/courses/x` -> `/courses/x`); every other loopback origin,
    port or host is left as it is, so the leak audit still rejects it. Returns (value, replacements)."""
    if origin is None or value is None:
        return value, 0
    import re
    rx = re.compile(re.escape(origin) + r"(?![\d])/?")
    if isinstance(value, str):
        return rx.subn("/", value)
    if isinstance(value, list):
        out, n = [], 0
        for x in value:
            y, k = rx.subn("/", x) if isinstance(x, str) else (x, 0)
            out.append(y)
            n += k
        return out, n
    return value, 0


def _visits(paths: list[str]) -> list[str]:
    return [p for i, p in enumerate(paths) if i == 0 or p != paths[i - 1]]


def _mention_counts(key: G2.AnswerKey, answer) -> dict:
    """How many expected items the answer names, and how many other candidates or unrecognised elements it lists (counts only)."""
    truth = {G2.canon(t) for t in ([key.truth] if key.style == "string" else key.truth)}
    elements = [answer] if isinstance(answer, str) else [x for x in (answer or []) if isinstance(x, str)]
    named, unrecognised = set(), 0
    for el in elements:
        ms = G2._mentions(G2.canon(el).split(), key)
        if not ms and el.strip():
            unrecognised += 1
        named |= {G2.canon(m[2].name) for m in ms}
    return {"expected_items": len(truth), "named_expected": len(named & truth), "named_other": len(named - truth), "unrecognised": unrecognised}


def _observed_paths(run: InvestigationRun, trial: dict) -> set[str]:
    p = run.dir / trial["trial_dir"] / "observations.json"
    obs = json.loads(p.read_text()) if p.exists() else []
    return {o.get("path") for o in obs if o.get("path")} | {s.get("path") for s in trial.get("journey") or [] if s.get("path")}


def _placement(profile: dict, listing: str) -> dict:
    """Where each labelled fact of a listing's items is stated: on the listing cards, on the item pages (fractions of items, measured)."""
    l = next((x for x in profile["listings"] if x["listing"] == listing), None)
    if not l:
        return {}
    n = l["items"] if isinstance(l["items"], int) else len(l["items"])
    out = {}
    for label, c in sorted(l["fields"].items()):
        if c["distinct_pages"] / max(n, 1) < 0.5:
            continue                                                             # not a fact of the items (e.g. one course's own heading)
        out[label] = {"items": n, "on_listing_cards": c["in_listing_item"], "on_item_pages": c["distinct_pages"]}
    return out


def _labels(criterion: dict) -> list[str]:
    labels = [c.get("label") for c in criterion.get("conditions", [])] + ([criterion["label"]] if criterion.get("label") else [])
    return [x for x in dict.fromkeys(labels) if x]


# ------------------------------------------------------------------------------------------------------------------------------- per trial
def _trial_row(run: InvestigationRun, name: str, t: dict, graded: dict, task_n: dict, priv: dict, vpriv: dict | None, key: G2.AnswerKey | None,
               profile: dict, paid: bool) -> dict:
    ev, m, out = t.get("evaluation") or {}, t.get("metrics") or {}, t.get("outcome") or {}
    ans = _answer(out)
    status = out.get("run_status")
    void = status in VOID_STATUSES
    lim = (m.get("limits") or {}).get("max_model_requests")
    journey = t.get("journey") or []
    visits = _visits([s.get("path") for s in journey if s.get("path")])
    log = (t.get("mirror") or {}).get("log") or []
    http = [{"path": e.get("path"), "status": e.get("status")} for e in log if (e.get("status") or 200) >= 400 and not BROWSER_AUTO.match(e.get("path") or "")]
    failed = [s["step"] for s in journey for x in (s.get("executed") or []) if x.get("error")]
    blocked = len((t.get("mirror") or {}).get("blocked") or [])
    v2 = graded.get("v2") if graded else None
    counts = _mention_counts(key, ans) if key is not None and ans is not None else None
    contrast = GC.grade(key, ans) if key is not None and key.style == "string" and isinstance(ans, str) else None
    missing = ev.get("missing_evidence") or []
    observed = _observed_paths(run, t)
    ranked2 = ER.check(ER.required_pages(priv["criterion"], profile), observed) if priv else {"rule": ER.RULE_ID, "applies": False}
    empty = ans is None or (isinstance(ans, list) and not any(x.strip() for x in ans)) or (isinstance(ans, str) and not ans.strip())
    near_limit = bool(lim and (m.get("model_requests") or 0) >= lim - 1)
    dead_end = bool(http or failed or blocked)
    proto = t.get("protocol") or {}
    shown, replaced = site_relative(ans, fixture_origin(run.dir / t["trial_dir"]) if t.get("trial_dir") else None)
    return {
        "id": name, "task_id": t["task_id"], "task": task_n[t["task_id"]], "variant": t["variant"], "condition": t.get("condition"), "repetition": t.get("repeat"),
        "status": status, "stop_reason": out.get("stop_reason"), "void": void, "finished_at": t.get("finished_at"),
        "answer": shown,
        **({"answer_normalized": {"fixture_origin_replaced": replaced, "note": FIXTURE_NOTE}} if replaced else {}),
        "grades": {
            "v1": {"passed": bool(ev.get("passed")), "evidence_backed": bool(ev.get("evidence_backed")), "answer_valid": ev.get("answer_valid"),
                   "reasons": list(ev.get("reasons") or []), "official": True},
            "v2": None if v2 is None else {"passed": bool(v2.get("passed")), "evidence_backed": bool(v2.get("evidence_backed")),
                                           "reasons": list(v2.get("reasons") or []), "review": bool(v2.get("review")), "official": False, "post_hoc": True},
            "v2_1_contrast": None if contrast is None or not contrast["applied"] else
                {"passed": contrast["passed"], "reasons": contrast["reasons"], "review": contrast["review"], "status": contrast["status"]},
        },
        "answer_coverage": counts,
        "evidence": {"rule": "recorded evidence rule (pages and texts that hold the answer must have been shown)", "satisfied": bool(ev.get("evidence_satisfied")),
                     "required_pages": len((vpriv or {}).get("evidence_paths") or []),
                     "missing_pages": sum(x.startswith("visited_path:") for x in missing), "missing_texts": sum(x.startswith("observed_text:") for x in missing),
                     "ranked_subset_rule_2": ranked2},
        "metrics": {"model_requests": m.get("model_requests"), "request_limit": lim, "steps": m.get("steps"), "page_views": m.get("page_views"),
                    "elapsed_seconds": m.get("elapsed_seconds"), "prompt_tokens": m.get("prompt_tokens") if paid else None,
                    "completion_tokens": m.get("completion_tokens") if paid else None, "cost_usd": m.get("calculated_cost_usd") if paid else None},
        "navigation": {"visits": visits, "distinct_pages": len(set(visits)), "revisits": len(visits) - len(set(visits)),
                       "item_pages_opened": len({p for p in visits if p.count("/") >= 2})},
        "reliability": {"http_errors": http[:10], "failed_action_steps": failed[:10], "blocked_requests": blocked, "dead_end": dead_end,
                        "recovered": dead_end and status == "completed" and not empty, "near_request_limit": near_limit,
                        "limit_stop": "limit" in str(out.get("stop_reason") or ""), "empty_answer": empty and status == "completed",
                        "partial_answer": bool(counts and counts["expected_items"] > 1 and 0 < counts["named_expected"] < counts["expected_items"]),
                        "protocol": {"responses": proto.get("http_200_responses"), "noncompliant": proto.get("raw_protocol_noncompliant"),
                                     "recovered": proto.get("recovered_action_valid")}},
    }


# ------------------------------------------------------------------------------------------------------------------------------- dimensions
def _sum(rows, f):
    vals = [f(r) for r in rows]
    vals = [v for v in vals if v is not None]
    return round(sum(vals), 6) if vals else None


def _mean(rows, f):
    vals = [f(r) for r in rows if f(r) is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def dimensions(rows: list[dict], tasks: list[dict], variants: list[str], placements: dict, suite: dict, coverage_ctx: dict | None) -> dict:
    by_v = {v: [r for r in rows if r["variant"] == v and not r["void"]] for v in variants}
    executed = [t for t in tasks if t["executed"]]
    success = {"basis": "per completed trial; official = grader v1 as recorded; grader v2 is a labelled post-hoc rescore; prospective rules are shown, never applied",
               "variants": {v: {"trials": len(rs), "v1_passed": sum(r["grades"]["v1"]["passed"] for r in rs),
                                "v1_evidence_backed": sum(r["grades"]["v1"]["evidence_backed"] for r in rs),
                                "v2_passed": sum(bool(r["grades"]["v2"] and r["grades"]["v2"]["passed"]) for r in rs),
                                "v2_evidence_backed": sum(bool(r["grades"]["v2"] and r["grades"]["v2"]["evidence_backed"]) for r in rs),
                                "v2_1_contrast_review_passes": sum(bool(r["grades"]["v2_1_contrast"] and r["grades"]["v2_1_contrast"]["passed"]) for r in rs)}
                            for v, rs in by_v.items()}}
    nav = {"basis": "model requests, agent steps, page views and wall time per trial; revisits = returns to a page already visited (consecutive steps on one page count once)",
           "variants": {v: {"model_requests_total": _sum(rs, lambda r: r["metrics"]["model_requests"]), "model_requests_mean": _mean(rs, lambda r: r["metrics"]["model_requests"]),
                            "steps_mean": _mean(rs, lambda r: r["metrics"]["steps"]), "page_views_mean": _mean(rs, lambda r: r["metrics"]["page_views"]),
                            "elapsed_seconds_total": _sum(rs, lambda r: r["metrics"]["elapsed_seconds"]), "elapsed_seconds_mean": _mean(rs, lambda r: r["metrics"]["elapsed_seconds"]),
                            "revisits_total": _sum(rs, lambda r: r["navigation"]["revisits"]), "item_pages_opened_mean": _mean(rs, lambda r: r["navigation"]["item_pages_opened"]),
                            "cost_usd_total": _sum(rs, lambda r: r["metrics"]["cost_usd"])} for v, rs in by_v.items()}}
    evid = {"basis": "the recorded evidence rule: an answer is evidence-supported only if the pages holding it were shown to the agent; counts only (the required pages name answer items)",
            "variants": {v: {"evidence_satisfied": sum(r["evidence"]["satisfied"] for r in rs), "trials": len(rs),
                             "correct_but_unsupported_v2": sum(bool(r["grades"]["v2"] and r["grades"]["v2"]["passed"] and not r["evidence"]["satisfied"]) for r in rs),
                             "missing_pages_total": sum(r["evidence"]["missing_pages"] for r in rs),
                             "ranked_subset_rule_2": [{"task": r["task"], **{k: r["evidence"]["ranked_subset_rule_2"][k] for k in ("required_pages", "shown_pages", "satisfied")}}
                                                      for r in rs if r["evidence"]["ranked_subset_rule_2"].get("applies")]} for v, rs in by_v.items()},
            "prospective_rule": {"id": ER.RULE_ID, "status": ER.STATUS}}
    access = {"basis": "measured from each variant's frozen snapshot: on how many listing cards and item pages each fact is stated; per task, where the facts its question depends on are placed",
              "facts": placements,
              "tasks": [{"task": t["n"], "facts": t["facts"], "placement": {v: {f: ("listing cards" if (placements.get(v, {}).get(f) or {}).get("on_listing_cards", 0) >= 0.8 * (placements.get(v, {}).get(f) or {}).get("items", 1)
                                                                         else "item pages only" if f in placements.get(v, {}) else "not measured") for f in t["facts"]} for v in variants},
                         "min_link_steps": t.get("min_hops")} for t in executed]}
    rel = {"basis": "per trial, from the browser and request records: HTTP errors and failed actions (dead ends), whether the trial still ended with an answer, "
                    "partial and empty answers, trials at or within one request of the limit, and model-output recovery by the protocol parser",
           "variants": {v: {"dead_ends": sum(r["reliability"]["dead_end"] for r in rs), "recovered_after_dead_end": sum(r["reliability"]["recovered"] for r in rs),
                            "partial_answers": sum(r["reliability"]["partial_answer"] for r in rs), "empty_answers": sum(r["reliability"]["empty_answer"] for r in rs),
                            "near_request_limit": sum(r["reliability"]["near_request_limit"] for r in rs), "limit_stops": sum(r["reliability"]["limit_stop"] for r in rs),
                            "void": sum(r["void"] for r in rows if r["variant"] == v),
                            "protocol_recoveries": _sum(rs, lambda r: r["reliability"]["protocol"]["recovered"])} for v, rs in by_v.items()}}
    cov = suite.get("coverage") or {}
    cover = {"basis": "the frozen suite's own coverage record (Stage A), with its targets and gaps exactly as frozen; personas and journeys are "
                      + ((coverage_ctx or {}).get("label") or "as recorded"),
             "personas": cov.get("per_persona"), "journeys": cov.get("per_journey"), "capabilities": cov.get("capabilities"), "matrix": cov.get("matrix"),
             "status": cov.get("status"), "gaps": list(suite.get("gaps") or []), "executed_tasks": len(executed), "tasks": len(tasks),
             "context": coverage_ctx}
    return {"task_success": success, "navigation_efficiency": nav, "evidence_quality": evid, "information_accessibility": access,
            "agent_reliability": rel, "coverage": cover}


# ------------------------------------------------------------------------------------------------------------------------------- diagnostics
def _sanitize_finding(f: dict, task_n: dict) -> dict:
    ev = []
    for e in f.get("evidence") or []:
        detail = e.get("detail") or ""
        if f.get("rule") == "unnecessary-navigation":
            detail = detail.split(":")[0]                                          # "N pages off the evidence path" (the page list implies the answer pages)
        ev.append({"type": e.get("type"), "ref": e.get("ref"), "detail": detail})
    d = f.get("detail") or {}
    keep = {k: d[k] for k in ("listing", "label", "items", "detail_pages", "listing_cards", "per_version", "status_basis", "trials") if k in d}
    return {"id": f["id"], "layer": f["layer"], "rule": f["rule"], "title": f["title"], "variant": f["version"], "severity": f["severity"], "impact": f["impact"],
            "status": f["status"], "basis": f.get("basis") or ("observed" if f["status"] == "observed" else "hypothesis"), "recommendation": f["recommendation"],
            "verify": f["verify"], "tasks": sorted(task_n[t] for t in f.get("tasks") or [] if t in task_n), "evidence_origin": f.get("evidence_origin"),
            "evidence": ev[:12], "detail": keep}


def _diagnostics(run: InvestigationRun, variants: list[str], paid: bool, task_n: dict) -> dict:
    try:
        from ..diagnostics import run as D
        from ..framework.site import get
        site = get(run.state["config"]["site"])
        if list(site.variants) != variants:
            return {"available": False, "reason": "diagnostics compare the site's registered variants; this evaluation uses other snapshots"}
        bundle = D.from_framework_run(run.dir)
        bundle["origin"] = "real_model" if paid else "dev_fixture"
        d = D.diagnose(bundle)
        fs = [_sanitize_finding(f, task_n) for f in d["findings"]]
        return {"available": True, "schema": d["schema"], "rules": d.get("rules"), "evidence_origin": d["evidence_origin"],
                "summary": {"observed": sum(f["basis"] == "observed" for f in fs), "hypotheses": sum(f["basis"] == "hypothesis" for f in fs),
                            "by_layer_status": d["summary"]["by_layer_status"]},
                "structural_changes": {k: {"resolved": len(v["resolved"]), "introduced": len(v["introduced"]), "persisting": len(v["persisting"]),
                                           "resolved_titles": [v["titles"][i] for i in v["resolved"]]} for k, v in d["structural_changes"].items()},
                "findings": fs}
    except Exception as exc:                                                         # advisory: never affects grades or the rest of the document
        return {"available": False, "reason": f"{type(exc).__name__}: {str(exc)[:200]}"}


def _ledger_totals(runs: dict[str, InvestigationRun]) -> dict | None:
    """The durable experiment ledger's SETTLED totals for this evaluation's trials (reserve-before-send; settled from provider-reported usage).
    Only totals leave this function; the ledger itself, its location and the authorisation record stay server-side. None if unavailable."""
    settled, requests, open_ = 0.0, 0, 0
    found = False
    for run in runs.values():
        checks = sorted((run.dir / "artifacts").glob("authorization-check-*.json"))
        if not checks:
            continue
        lp = Path(json.loads(checks[-1].read_text()).get("ledger_dir") or "") / "ledger.jsonl"
        if not lp.is_file():
            continue
        found = True
        cond = run.state["config"]["condition"]
        res, sets = set(), {}
        for line in lp.read_text().splitlines():
            e = json.loads(line)
            if not str(e.get("id", "")).startswith(f"{cond}-"):
                continue
            if e["kind"] == "reserve":
                res.add(e["id"])
            elif e["kind"] == "settle":
                sets[e["id"]] = e["usd"]
        settled += sum(sets.values())
        requests += len(sets)
        open_ += len(res - set(sets))
    if not found:
        return None
    return {"settled_usd": round(settled, 6), "settled_requests": requests, "unsettled_requests": open_,
            "basis": "the experiment's durable ledger: every request reserved before sending and settled from provider-reported usage; totals only"}


# ------------------------------------------------------------------------------------------------------------------------------- project
def load_runs(run_dirs: list[Path]) -> dict[str, InvestigationRun]:
    runs = {}
    for d in run_dirs:
        r = InvestigationRun(Path(d))
        runs[r.state["config"]["condition"]] = r
    if not runs:
        raise ValueError("no run directories")
    if len({r.state["config"]["manifest_sha256"] for r in runs.values()}) != 1:
        raise ValueError("the runs belong to different manifests")
    return runs


def project(store: WriteOnceStore, runs: dict[str, InvestigationRun], *, evaluation_id: str, title: str | None = None, context: dict | None = None,
            diagnostics: bool = True) -> dict:
    from ..evalruns import runner as RN
    from ..evalruns.manifest import suite_tasks
    from ..framework.site import get
    from ..suites import plan as PL
    run0 = next(iter(runs.values()))
    cfg = run0.state["config"]
    mode = cfg.get("mode")
    if mode not in MODES:
        raise ValueError(f"unknown evaluation mode {mode!r}")
    paid = mode == "paid"
    manifest_sha = cfg["manifest_sha256"]
    manifest = store.get("manifest", manifest_sha)
    frozen, suite, task_records = suite_tasks(store, manifest.frozen_suite_sha256)
    approval = store.get("approval", frozen.approval_sha256)
    variants = [n for n, _ in manifest.variants]
    site = get(suite.site)
    snaps = RN.resolve_variants(site, manifest, None, run0.dir)
    profiles = {n: build_profile(s) for n, s in snaps.items()}
    listing = (site.listings or ("",))[0]
    placements = {n: _placement(p, listing) for n, p in profiles.items()}
    ordered = sorted(task_records, key=lambda t: t.task_id)
    task_n = {t.task_id: i + 1 for i, t in enumerate(ordered)}
    tasks, rows, analyses, execution = [], [], {}, {}
    min_hops: dict[str, dict] = {}
    for cond, run in sorted(runs.items()):
        if run.state["config"]["mode"] != mode:
            raise ValueError("an evaluation's runs share one mode")
        _, privs = freezer.load(run)
        per_variant = run.private("variant-criteria")
        base_profile = run.artifact("site-profile")
        keys = {}
        for tid, priv in privs.items():
            try:
                keys[tid] = KD.build_key_any(tid, priv, base_profile)
            except G2.KeyError_:
                pass
        res = RN.condition_results(run)
        graded = {r["trial"]: {"v2": None if r["v2_passed"] is None else {"passed": r["v2_passed"], "evidence_backed": r["v2_evidence_backed"],
                                                                         "reasons": r["v2_reasons"], "review": None}} for r in res["rows"]}
        for path in sorted((run.dir / "artifacts" / "trials").glob("*.json")):
            t = run.artifact(f"trials/{path.stem}")
            v, tid = t["variant"], t["task_id"]
            vpriv = (per_variant.get(v) or {}).get(tid)
            min_hops.setdefault(tid, {})[v] = (vpriv or {}).get("min_hops")
            row = _trial_row(run, path.stem, t, graded.get(path.stem), task_n, privs.get(tid), vpriv, keys.get(tid), profiles[v], paid)
            if row["grades"]["v2"] is not None and keys.get(tid) is not None:
                g = G2.grade(keys[tid], _answer(t.get("outcome")) if t["evaluation"].get("answer_valid") else None)     # the raw answer, as graded
                row["grades"]["v2"]["review"] = g.review
            if not paid:
                row["answer"] = None
                row["answer_withheld"] = STAND_IN_WITHHELD
            rows.append(row)
        per_task: dict = {}
        per_task_v2: dict = {}
        for r in rows:
            if r["condition"] == cond and not r["void"]:
                per_task.setdefault(r["task_id"], {}).setdefault(r["variant"], []).append(r["grades"]["v1"]["evidence_backed"])
                per_task_v2.setdefault(r["task_id"], {}).setdefault(r["variant"], []).append(bool(r["grades"]["v2"] and r["grades"]["v2"]["evidence_backed"]))
        if len(variants) >= 2:
            a1 = PL.analyse(manifest.plan, per_task, (variants[0], variants[1]))
            a2 = PL.analyse(manifest.plan, per_task_v2, (variants[0], variants[1]))
            label = "EXPLORATORY: no confirmatory claim may be made" if (manifest.plan.designation != "confirmatory" or cond != manifest.conditions[0]) else "pre-registered"
            strip = lambda a: {**{k: a[k] for k in ("designation", "test", "alpha", "pairs", "planned_pairs", "mean_difference", "p_value") if k in a},
                               "per_task": [{"task": task_n[x["task_id"]], "difference": x["difference"], **{v: x[v] for v in variants}} for x in a.get("per_task", [])]}
            analyses[cond] = {"label": label, "official_v1": strip(a1), "post_hoc_v2": strip(a2),
                              "outcome": "evidence-supported pass, per task (repetitions averaged), Modified minus Original"}
        execs = sorted((run.dir / "artifacts").glob("execution-*.json"))
        last = json.loads(execs[-1].read_text()) if execs else {}
        execution[cond] = {"planned": last.get("planned"), "executed": len(list((run.dir / "artifacts" / "trials").glob("*.json"))), "stopped": last.get("stopped"),
                           "jail_selftest_ok": bool((last.get("jail_selftest") or {}).get("ok")), "authorization_verified": bool(last.get("authorization_sha256")) if paid else None,
                           "invalidated": {v: [{"task": task_n.get(x["task_id"]), "reason": x["reason"]} for x in s["excluded"]]
                                           for v, s in run.artifact("snapshot-manifests").items() if s["excluded"]}}
    executed_ids = {r["task_id"] for r in rows}
    for t in ordered:
        view = public_task_view(t)
        w, spec = view["wording"], view["spec"]
        tasks.append({"n": task_n[t.task_id], "task_id": t.task_id, "sha256": view["sha256"], "persona": t.persona, "journey": t.journey, "capability": t.capability,
                      "kind": spec["kind"], "category": w["category"], "condition": t.condition, "verifiability": spec["verifiability"],
                      "customer_wording": w["customer"], "executed_wording": w["executed"], "assumptions": list(w["assumptions"]),
                      "interpretation_decisions": list(w["interpretation_decisions"]), "facts": _labels(spec["criterion"]),
                      "limits": view["limits"], "executed": t.task_id in executed_ids, "min_hops": min_hops.get(t.task_id)})
    diag = {cond: _diagnostics(run, variants, paid, task_n) for cond, run in runs.items()} if diagnostics else {}
    started = min((r.state.get("created_at") for r in runs.values()), default=None)
    finished = max((r["finished_at"] for r in rows if r.get("finished_at")), default=None)
    reps = manifest.repetitions
    n_exec = len([t for t in tasks if t["executed"]])
    by_v_cost = {v: _sum([r for r in rows if r["variant"] == v], lambda r: r["metrics"]["cost_usd"]) for v in variants}
    doc = {
        "schema": SCHEMA, "projection": VERSION, "id": evaluation_id,
        "title": title or f"{suite.suite_name} v{suite.version} on {site.label}",
        "mode": mode, "mode_label": MODES[mode]["label"], "execution_provider": MODES[mode]["provider"] if not paid else f"real model ({manifest.agent.model})",
        "notice": MODES[mode]["notice"],
        "site": {"id": site.id, "label": site.label, "domain": site.domain, "controlled": site.controlled},
        "suite": {"name": suite.suite_name, "version": suite.version, "sha256": frozen.suite_sha256, "created_by": suite.provenance.created_by,
                  "selection_rule": suite.selection_rule},
        "approval": {"sha256": frozen.approval_sha256, "decision": approval.decision, "role": approval.approver_role, "decided_at": approval.approved_at,
                     "method": "owner attestation of the exact suite hash at an interactive terminal",
                     "synthetic": suite.suite_name.startswith("synthetic-") or "SYNTHETIC" in approval.notes},
        "frozen_suite": {"sha256": manifest.frozen_suite_sha256, "frozen_at": frozen.frozen_at},
        "manifest": {"sha256": manifest_sha, "variants": [{"name": n, "snapshot_sha256": s} for n, s in manifest.variants], "conditions": list(manifest.conditions),
                     "repetitions": reps, "seed": manifest.seed, "plan": manifest.plan.designation,
                     "budget": {k: manifest.budget.get(k) for k in ("worst_case_reservation_usd", "hard_cap_usd", "per_request_cap_usd")}},
        "agent": {k: getattr(manifest.agent, k) for k in ("model", "reasoning_effort", "max_completion_tokens", "profile")},
        "graders": {"official": "grader v1 (generated-criteria v1), as recorded", "post_hoc": f"grader v2 (generated-criteria v{G2.GRADER_VERSION}), labelled post-hoc rescore",
                    "prospective": [{"id": f"{GC.GRADER_ID} v{GC.GRADER_VERSION}", "status": GC.STATUS}, {"id": ER.RULE_ID, "status": ER.STATUS}]},
        "started_at": started, "finished_at": finished,
        "execution": execution,
        "cost": {"by_variant": by_v_cost, "total_usd": _sum([{"c": c} for c in by_v_cost.values()], lambda r: r["c"]), "basis": COST_BASIS,
                 "settled_spend": _ledger_totals(runs)} if paid else
                {"by_variant": None, "total_usd": 0.0, "basis": "no model was called; nothing was spent"},
        "exploratory": manifest.plan.designation != "confirmatory",
        "caveat": EXPLORATORY_NOTE.format(tasks=n_exec, reps=reps) if manifest.plan.designation != "confirmatory" else None,
        "tasks": tasks,
        "trials": sorted(rows, key=lambda r: (r["task"], variants.index(r["variant"]) if r["variant"] in variants else 99, r["repetition"] or 0)),
        "analysis": analyses,
        "dimensions": dimensions(rows, tasks, variants, placements, suite.content(), context),
        "diagnostics": diag,
    }
    return doc


STAND_IN_WITHHELD = "withheld: a rehearsal's scripted stand-in derives its replies from the private expected outcomes"


def _redact_stand_in(steps: list[dict]) -> list[dict]:
    """Rehearsal timelines: the stand-in's stated memory, goals, assessments and answer are derived from the private expected outcomes, so they are
    never shown (paths, page titles, screenshots and action names are kept)."""
    out = []
    for s in steps:
        s = {**s, "assessment": None, "memory": None, "goal": None,
             "actions": [{**a, "target": STAND_IN_WITHHELD} if a.get("name") == "Answer" else a for a in s.get("actions") or []]}
        out.append(s)
    return out


def trial_timeline(run: InvestigationRun, trial_name: str) -> dict:
    """The public step timeline of one trial (hosted.telemetry's allowlisted projection of trace.jsonl, unchanged; redacted for rehearsals)."""
    t = run.artifact(f"trials/{trial_name}")
    d = run.dir / t["trial_dir"]
    tl = telemetry.timeline(d)
    rehearsal = run.state["config"].get("mode") != "paid"
    return {"id": trial_name, "mode": run.state["config"].get("mode"), "steps": _redact_stand_in(tl["steps"]) if rehearsal else tl["steps"],
            "errors": tl["errors"], "screenshots": sorted(p.name for p in d.glob("step-*.png"))}


def trial_dir(run: InvestigationRun, trial_name: str) -> Path:
    return run.dir / run.artifact(f"trials/{trial_name}")["trial_dir"]
