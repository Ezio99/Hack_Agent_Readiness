"""Per-run metrics extracted from a scan result record + its private trace. Pure functions; no network. Partial accuracy uses the evaluator's PRIVATE truth
(offline analysis side only; the grading contract is unchanged)."""
from __future__ import annotations

from collections import Counter

from ..suite import core, registry


def partial_accuracy(instance, answer) -> dict:
    """Fraction of independently checkable fields correct (0 when no valid answer). Returns {'score','fields': {name: bool}}."""
    t = instance.truth
    fields: dict[str, bool] = {}
    tid = instance.spec.template_id
    if not isinstance(answer, dict):
        return {"score": 0.0, "fields": {}}
    try:
        if tid.startswith("t1"):
            eligible = dict(t["eligible"])
            got = answer.get("products", [])
            good = [p for p in got if eligible.get(p.get("sku")) == p.get("price_cents")]
            denom = max(len(eligible) if t["mode"] == "set" else 1, len(got), 1)
            if t["mode"] == "set":
                score = len({p["sku"] for p in good}) / denom
            else:
                score = 1.0 if len(got) == 1 and len(good) == 1 else 0.0
            fields = {"correct_items": len(good), "reported_items": len(got), "eligible_items": len(eligible)}
            return {"score": round(score, 4), "fields": fields,
                    "precision": round(len(good) / len(got), 4) if got else 0.0, "recall": round(len({p["sku"] for p in good}) / len(eligible), 4) if eligible else 1.0}
        if tid.startswith("t2"):
            for side in ("a", "b"):
                for k in ("sku", "ram_gb", "battery_hours"):
                    fields[f"{side}.{k}"] = answer.get(side, {}).get(k) == t[side][k]
            fields["more_ram"] = answer.get("more_ram") == t["more_ram"]
            fields["longer_battery"] = answer.get("longer_battery") == t["longer_battery"]
        elif tid.startswith("t3"):
            from ..environments.electronics.catalog import BY_SKU
            sku = answer.get("sku")
            fields = {"eligible": sku in t["eligible"], "cheapest_eligible": sku == t["answer_sku"], "price": sku in BY_SKU and answer.get("price_cents") == BY_SKU[sku].price_cents}
        elif tid.startswith("t4"):
            fields = {k: answer.get(k) == v for k, v in t.items()}
        else:
            return {"score": 0.0, "fields": {}}
    except (KeyError, AttributeError, TypeError):
        return {"score": 0.0, "fields": fields}
    return {"score": round(sum(fields.values()) / len(fields), 4), "fields": fields}


def trace_events(artifact_dir) -> list[dict]:
    import json
    from pathlib import Path
    p = Path(artifact_dir) / "trace.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


def observations(events: list[dict]) -> list[core.Observation]:
    out = []
    for e in events:
        if e["kind"] == "observation":
            from urllib.parse import urlsplit
            out.append(core.Observation(urlsplit(e.get("url", "")).path or "/", e.get("dom") or ""))
    return out


def visit_taxonomy(instance, obs: list[core.Observation]) -> list[dict]:
    """Rule-based, pre-registered: each page load is 'required' (shows a needed fact not yet observed), 're_verification' (shows only needed facts already observed)
    or 'navigation' (no needed fact). Re-verification is agent behaviour unless it differs systematically between variants - it is never labelled friction here."""
    all_req = set(core.evidence_gaps(instance, []))
    seen: set[str] = set()
    out = []
    for o in obs:
        page_facts = all_req - set(core.evidence_gaps(instance, [o]))
        new = page_facts - seen
        kind = "required" if new else ("re_verification" if page_facts else "navigation")
        seen |= page_facts
        out.append({"path": o.path, "kind": kind, "new_facts": len(new), "facts_on_page": len(page_facts)})
    return out


def extract(record: dict, events: list[dict], instance, *, run: dict | None = None) -> dict:
    """The flat per-run row used by the analysis. `record` is a scanner result record (mock or live)."""
    ev, out, m = record["evaluation"], record["outcome"], record["metrics"]
    obs = observations(events)
    tax = visit_taxonomy(instance, obs) if obs else []
    total_req = len(core.evidence_gaps(instance, []))
    missing = len(ev["missing_evidence"])
    journey = record["journey"]
    paths = [(j["path"], j["query"]) for j in journey]
    action_counts = Counter(a["name"] for j in journey for a in j["actions"])
    seen, revisits = set(), 0
    for p in paths:
        revisits += p in seen
        seen.add(p)
    failed_calls = sum(1 for j in journey for x in j["executed"] if x["error"])
    findings = record.get("diagnostics", {}).get("findings", [])
    attribution = sorted({f["category"] for f in findings if f["category"] != "task_outcome"}) or (["none"] if ev["passed"] else ["undetermined"])
    pa = partial_accuracy(instance, out.get("answer"))
    row = {
        "run_id": (run or {}).get("run_id"), "stage": (run or {}).get("stage"), "block": (run or {}).get("block"), "task_code": (run or {}).get("task_code"), "variant_code": (run or {}).get("variant_code"),
        "task_id": record["task"]["task_id"], "variant_id": record["variant"]["id"], "mode": record["scan"]["mode"], "run_status": out["run_status"], "stop_reason": out["stop_reason"],
        "answer_valid": ev["answer_valid"], "passed": ev["passed"], "evidence_backed": ev["evidence_backed"], "success": bool(ev["passed"] and ev["evidence_backed"]),
        "partial_accuracy": pa["score"], "partial_fields": pa["fields"], "evidence_coverage": round(1 - missing / total_req, 4) if total_req else 1.0, "evidence_missing": missing,
        "model_requests": m["model_requests"], "steps": m.get("steps"), "actions": sum(action_counts.values()), "action_counts": dict(action_counts), "page_loads": len(paths),
        "unique_pages": len(seen), "revisits": revisits, "backtracks": action_counts.get("go_back", 0), "failed_tool_calls": failed_calls,
        "detail_page_loads": sum(1 for p, _ in paths if p.startswith("/p/")), "visit_kinds": dict(Counter(t["kind"] for t in tax)),
        "elapsed_seconds": m["elapsed_seconds"], "prompt_tokens": m["prompt_tokens"], "completion_tokens": m["completion_tokens"], "calculated_cost_usd": m["calculated_cost_usd"],
        "protocol": {k: v for k, v in (record.get("protocol") or {}).items() if k != "parser"}, "attribution": attribution,
        "finding_titles": [f["title"] for f in findings],
    }
    return row
