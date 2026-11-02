"""Evidence-linked hypotheses: a structural observation becomes a suspected contributor only when evaluated tasks depend on it and recorded behaviour on
those tasks is consistent with it. Status rules (never causal by default):
  unverified             no evaluated task depends on the structural issue
  hypothesis             tasks depend on it and their behaviour is cited; untested (or tested only with fixture behaviour, which cannot support it)
  supported_exploratory  a version WITHOUT the issue was run on a real model, behaviour on the dependent tasks improved without losing passes, and the
                         recorded exploratory rule agreed (the pre-registered rule did not establish it)
  supported              as above, and the pre-registered comparison rule established an improvement
When one tested change resolved several issues together, support applies to that combined change, not to each issue separately (stated)."""
from __future__ import annotations

from statistics import mean

from .behavioral import item_page_visits
from .model import Evidence, Finding, stable_id


def _criterion_labels(c: dict) -> tuple[str | None, set[str]]:
    if c.get("kind") == "extremum":
        return c.get("listing"), {c.get("label")}
    if c.get("kind") == "item_set":
        return c.get("listing"), {x.get("label") for x in c.get("conditions", [])}
    return None, set()


def link(*, site: str, versions: list[dict], structural: dict[str, list[Finding]], behavioral: dict[str, list[Finding]], comparison: dict | None, origin: str,
         tasks_alias: dict[str, str] | None = None) -> list[Finding]:
    """versions: [{name, sha256, profile, private, trials}] (first = the baseline version)."""
    base = versions[0]
    out = []
    ids_by_version = {v["name"]: {f.id for f in structural[v["name"]]} for v in versions}
    gaps = [g for g in structural[base["name"]] if g.rule == "listing-fact-gap"]
    for g in gaps:
        listing, label = g.detail["listing"], g.detail["label"]
        tasks = sorted(tid for tid, p in base["private"].items() if (lambda l, ls: l == listing and label in ls)(*_criterion_labels(p["criterion"])))
        if not tasks:
            out.append(Finding(stable_id("H", "listing-fact-gap", site, listing, label), "hypothesis", "listing-fact-gap", f"Risk only: no evaluated task compares items by '{label}'",
                               site, base["name"], base["sha256"], "info", "a structural risk indicator; nothing measured either way", "unverified",
                               [Evidence("finding", g.id, g.title)], g.recommendation, "Add a task that compares items by this fact, then evaluate.", evidence_origin=origin))
            continue
        item_pages = {i["href"] for gr in base["profile"]["pages"][listing]["item_groups"] for i in gr["items"]}
        per_version = {}
        for v in versions:
            ts = [t for t in v["trials"].values() if t["task_id"] in tasks and t["outcome"]["run_status"] == "completed"]
            if ts:
                per_version[v["name"]] = {"trials": len(ts), "item_pages_opened_mean": round(mean(item_page_visits(t, item_pages) for t in ts), 2),
                                          "requests_mean": round(mean(t["metrics"]["model_requests"] for t in ts), 2),
                                          "evidence_backed": sum(bool(t["evaluation"]["evidence_backed"]) for t in ts), "resolved_here": g.id not in ids_by_version[v["name"]]}
        cited = [b for b in behavioral.get(base["name"], []) if set(b.tasks) & set(tasks)]
        ev = [Evidence("finding", g.id, g.title)] + [Evidence("finding", b.id, b.title) for b in cited[:8]] + \
             [Evidence("trial", f"{n}: {m['trials']} trials", f"item pages opened {m['item_pages_opened_mean']}, requests {m['requests_mean']}, evidence-supported {m['evidence_backed']}/{m['trials']}") for n, m in per_version.items()]
        status, note = "hypothesis", "untested: no version without this issue has been evaluated"
        resolved = [n for n, m in per_version.items() if m["resolved_here"]]
        if resolved:
            b0, r = per_version[base["name"]], per_version[resolved[0]]
            improved = r["item_pages_opened_mean"] < b0["item_pages_opened_mean"] and r["requests_mean"] < b0["requests_mean"] and r["evidence_backed"] >= b0["evidence_backed"]
            together = sorted(x.detail["label"] for x in gaps if x.id not in ids_by_version[resolved[0]])
            if origin != "real_model":
                note = f"a version without this issue ({resolved[0]}) was run, but only with {origin} behaviour, which cannot support a hypothesis about agents"
            elif not improved:
                note = f"on {resolved[0]} (issue resolved) behaviour on the dependent tasks did not improve on every measure; not supported"
            elif comparison and comparison.get("frozen") == "improvement":
                status, note = "supported", f"pre-registered rule {comparison.get('frozen_rule_id')}: improvement"
            elif comparison and comparison.get("exploratory") == "consistent_with_h1":
                status = "supported_exploratory"
                note = (f"exploratory rule {comparison.get('exploratory_rule_id')}: consistent_with_h1; pre-registered rule {comparison.get('frozen_rule_id')}: "
                        f"{comparison.get('frozen')}; the tested change resolved {', '.join(together)} together, so support applies to that combined change")
            else:
                note = f"behaviour improved on {resolved[0]}, but no recorded comparison rule supports it"
            if comparison:
                ev.append(Evidence("comparison", f"{comparison.get('frozen_rule_id')} / {comparison.get('exploratory_rule_id')}", f"frozen {comparison.get('frozen')}, exploratory {comparison.get('exploratory')}"))
        labels = [(tasks_alias or {}).get(t, t) for t in tasks]
        out.append(Finding(stable_id("H", "listing-fact-gap", site, listing, label), "hypothesis", "listing-fact-gap",
                           f"Listing cards omit '{label}': suspected contributor to item-page navigation on task(s) {', '.join(labels)}", site, base["name"], base["sha256"],
                           "high" if status.startswith("supported") else "medium", f"tasks {', '.join(labels)} compare items by {label}", status, ev, g.recommendation,
                           g.verify, tasks=tasks, evidence_origin=origin, detail={"per_version": per_version, "status_basis": note}))
    return out
