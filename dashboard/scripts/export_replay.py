#!/usr/bin/env python3
"""Deterministic, sanitized export of three recorded Task 007 runs for the dashboard's "Recorded experiment replay".

DEVELOPMENT-ONLY OUTPUT: files are written to dashboard/public/replays/ which is Git-ignored. Do not commit or publish them until the exact
files and fields have been reviewed and approved. Stdlib only. No model calls, no network, no changes to runs/.

    python3 dashboard/scripts/export_replay.py            # write the export
    python3 dashboard/scripts/export_replay.py --check    # regenerate in memory and compare with the files on disk
    python3 dashboard/scripts/export_replay.py --audit    # export + sanitization audit and field/size inventory (exit 1 on any finding)

The exporter emits an allow-list of fields only. Excluded: model thinking/memory/next-goal/evaluation text, prose prefixes, free-text action
descriptions, system prompts and complete model requests, raw HTTP bodies, request IDs, screenshots, history.json, private task truth,
absolute paths and localhost ports."""
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "dashboard" / "public" / "replays"
STATE = ROOT / "runs" / "pilot-task007" / "pilot-state.json"
RECONCILED = ROOT / "collaboration" / "reports" / "007-pilot-data" / "per-run-reconciled.json"
RUNS = {"fern-A-25-s02-A1": "25-s02-A1", "fern-B-26-s02-B1": "26-s02-B1", "fern-B-27-s02-B2": "27-s02-B2"}
SCHEMA = "task008-replay-v1"
PRICE_IN, PRICE_OUT = 1.25, 4.25          # USD per million tokens (published prices; calculated estimate, not a bill)
EXCERPT_CHARS = 600
# Action parameters that may be published (everything else is dropped). Free-text fields such as `description`, `thinking`,
# `memory` are never allowed.
ALLOWED_PARAMS = {
    "click": ["index"], "navigate": ["url", "new_tab"], "go_back": [], "select_dropdown": ["index", "text"], "dropdown_options": ["index"],
    "find_elements": ["selector", "attributes", "include_text", "max_results"], "wait": ["seconds"], "scroll": ["down", "pages"],
    "done": ["data", "success"],
}
DONE_DATA = ["product_id", "price_cents", "available"]
FORBIDDEN_KEYS = {"thinking", "memory", "next_goal", "evaluation_previous_goal", "description", "request_id", "content", "prose_prefix",
                  "system_prompt", "messages", "screenshot", "expected", "artifact_path", "history"}


def scrub(text):
    """Remove localhost ports and local identifiers from page/harness text."""
    if text is None:
        return None
    text = re.sub(r"https?://127\.0\.0\.1:\d+", "http://localhost", text)
    text = re.sub(r"127\.0\.0\.1:\d+", "localhost", text)
    return text


def path_of(url):
    parts = urlsplit(url or "")
    return (parts.path or "/") + (f"?{parts.query}" if parts.query else "")


def page_kind(url):
    path = urlsplit(url or "").path
    if path.startswith("/products/"):
        return "product detail"
    return "filtered listing" if urlsplit(url or "").query else "listing"


def sanitize_action(action):
    """One proposed action dict -> {name, params} with allow-listed params only."""
    name = next(iter(action))
    params = action[name] or {}
    allowed = ALLOWED_PARAMS.get(name)
    if allowed is None:
        return {"name": name, "params": {}, "params_omitted": True}
    out = {}
    for key in allowed:
        if key in params and params[key] is not None:
            value = params[key]
            if key == "url":
                value = path_of(value)
            if name == "done" and key == "data":
                value = {k: value[k] for k in DONE_DATA if k in value}
            out[key] = value
    return {"name": name, "params": out}


def history_last_result(request_event):
    """The text the model saw as the previous step's result: the last 'Result' block of <agent_history>, excluding the model-written
    goal/memory lines that precede it."""
    for message in request_event["messages"]:
        if message["role"] != "user":      # the system prompt documents <agent_history> but contains no run history
            continue
        content = message["content"]
        parts = content if isinstance(content, list) else [{"type": "text", "text": content}]
        for part in parts:
            text = part.get("text") or ""
            if "<agent_history>" not in text or "</agent_history>" not in text:
                continue
            history = text[text.index("<agent_history>"): text.index("</agent_history>")]
            block = history.split("<step>")[-1]
            marker = block.rfind("\nResult\n")
            if marker < 0:
                return None
            return scrub(block[marker + len("\nResult\n"):].strip())
    return None


def excerpt(text):
    if text is None:
        return None, False
    text = scrub(text)
    return (text[:EXCERPT_CHARS] + "…", True) if len(text) > EXCERPT_CHARS else (text, False)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    state = json.loads(STATE.read_text())
    reconciled = {r["id"]: r for r in json.loads(RECONCILED.read_text())}
    out, sources = {}, {}
    for name, entry_id in RUNS.items():
        entry = next(e for e in state["entries"] if e["entry_id"] == entry_id)
        d = Path(entry["result"]["artifact_path"])
        if not d.is_absolute():
            d = ROOT / d
        run = json.loads((d / "run.json").read_text())
        trace = [json.loads(l) for l in (d / "trace.jsonl").read_text().splitlines()]
        observations = [t for t in trace if t["kind"] == "observation"]
        results = [t for t in trace if t["kind"] == "step_result"]
        requests = [t for t in trace if t["kind"] == "model_request"]
        http_requests = [t for t in trace if t["kind"] == "model_http_request"]
        rec = reconciled[entry_id]
        assert len(observations) == len(results) == len(requests) == len(http_requests) == rec["requests"], entry_id
        steps = []
        for i, (obs, res, req, hreq) in enumerate(zip(observations, results, requests, http_requests), 1):
            response = json.loads((d / f"model-response-{i:02d}.json").read_text())
            usage = response["usage"]
            proposed = [sanitize_action(a) for a in obs["proposed_actions"]]
            executed = []
            for j, result in enumerate(res["result"]["result"]):
                text, truncated = excerpt(result.get("extracted_content"))
                executed.append({"action": proposed[j]["name"] if j < len(proposed) else None, "result_excerpt": text, "result_truncated": truncated,
                                 "error": scrub(result.get("error")), "is_done": bool(result.get("is_done"))})
            nxt = history_last_result(requests[i]) if i < len(requests) else None
            steps.append({
                "step": i, "page": page_kind(obs["url"]), "path": path_of(obs["url"]), "title": scrub(obs.get("title")),
                "model_visible_dom": scrub(obs["dom"]),
                "model_visible_last_result": history_last_result(req),
                "actions": proposed, "tool_results": executed,
                "result_visible_to_model_next_request": nxt,
                "protocol": "raw_valid" if response.get("raw_protocol_compliant") else "recovered",
                "guard": {"schema": "done_only" if hreq["fidelity"]["schema_narrowed"] else "full",
                          "budget_warning": "BUDGET WARNING" in json.dumps(req["messages"]), "final_step": bool(hreq["fidelity"]["schema_narrowed"])},
                "usage": {"prompt_tokens": usage["prompt_tokens"], "completion_tokens": usage["completion_tokens"],
                          "reasoning_tokens": response.get("reasoning_tokens")},
                "latency_s": round(response["elapsed_seconds"], 3), "finish_reason": response["finish_reason"],
                "estimated_cost_usd": round(usage["prompt_tokens"] * PRICE_IN / 1e6 + usage["completion_tokens"] * PRICE_OUT / 1e6, 6),
            })
        total_tokens = sum(s["usage"]["prompt_tokens"] for s in steps), sum(s["usage"]["completion_tokens"] for s in steps)
        att_required = 2 if rec["arm"] == "A" else 2 * rec["rank"]
        att_tool = len(rec["find_elements"]) if len(rec["find_elements"]) >= 3 else 0
        out[name] = {
            "schema": SCHEMA, "label": "Recorded experiment replay — not live inference",
            "run": {"id": entry_id, "scope": rec["scope"], "arm": rec["arm"], "rank": rec["rank"], "task": run["task"]["prompt"],
                    "evaluator": {"passed": rec["passed"], "reasons": run["evaluation"]["reasons"]},
                    "answer_submitted": {k: rec["answer"][k] for k in ("product_id", "price_cents", "available")},
                    "required_visits": rec["required_visits"], "observed_visits": len(rec["visits_trace"]),
                    "overhead": rec["overhead"], "verification_shortfall": rec["shortfall"],
                    "attribution": {"required_path_requests": att_required, "tool_loop_requests": att_tool,
                                    "residual_requests": rec["requests"] - att_required - att_tool, "total_requests": rec["requests"]},
                    "totals": {"requests": rec["requests"], "prompt_tokens": total_tokens[0], "completion_tokens": total_tokens[1],
                               "estimated_cost_usd": round(sum(s["estimated_cost_usd"] for s in steps), 6), "elapsed_s": round(run["elapsed_seconds"], 1)}},
            "steps": steps,
            "notes": {"cost": "calculated from provider-reported tokens at published prices (US$1.25/M input, US$4.25/M output); not a bill",
                      "excluded": "model reasoning/memory/next-goal text, prose prefixes, free-text action descriptions, system prompts, full requests, "
                                  "raw HTTP bodies, request IDs, screenshots, private task truth, local paths and ports"},
        }
        sources[name] = {"entry_id": entry_id, **{f: sha(d / f) for f in ["run.json", "trace.jsonl"]},
                         "model_responses": {p.name: sha(p) for p in sorted(d.glob("model-response-*.json"))}}
    files = {f"{k}.json": json.dumps(v, indent=1, sort_keys=True, ensure_ascii=False) + "\n" for k, v in out.items()}
    manifest = {"schema": SCHEMA, "label": "Recorded experiment replay — not live inference", "development_only": True,
                "replays": [{"file": f, "id": k, "entry_id": RUNS[k], "sha256": hashlib.sha256(files[f].encode()).hexdigest(), "bytes": len(files[f].encode())}
                            for k, f in zip(out, files)],
                "schedule_sha256": state["schedule_sha256"], "execution_commit": state["fingerprint"]["git_commit"][:7],
                "exporter_sha256": sha(__file__), "source_sha256": sources}
    files["manifest.json"] = json.dumps(manifest, indent=1, sort_keys=True) + "\n"
    return files


def audit(files):
    findings = []
    secret = os.environ.get("META_MODEL_API_KEY", "")
    envfile = ROOT / ".env"
    if not secret and envfile.exists():
        for line in envfile.read_text().splitlines():
            if line.startswith("META_MODEL_API_KEY="):
                secret = line.split("=", 1)[1].strip()
    blob = "\n".join(files.values())
    if secret and secret in blob:
        findings.append("credential value present")
    for pattern, label in ((r"/home/|/tmp/|/Users/|runs/pilot", "local path"), (r"127\.0\.0\.1:\d+|localhost:\d+", "localhost port"),
                           (r"\bsk-[A-Za-z0-9]{10,}", "key-like token"), (r"[\w.+-]+@[\w-]+\.[\w.]+", "email address"), (r"browser_use_agent_|target_id", "internal id")):
        if re.search(pattern, blob):
            findings.append(f"{label} pattern found")

    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k
                yield from keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from keys(v)
    for name, text in files.items():
        bad = FORBIDDEN_KEYS & set(keys(json.loads(text)))
        if bad:
            findings.append(f"{name}: forbidden keys {sorted(bad)}")
    # model-generated text must not leak: no model-written string of >= 20 chars may appear anywhere in the export
    state = json.loads(STATE.read_text()) if STATE.exists() else {"entries": []}
    for entry_id in RUNS.values():
        if not state["entries"]:
            break  # no local artifacts (e.g. CI): the model-text leak check needs them and is skipped
        d = Path(next(e for e in state["entries"] if e["entry_id"] == entry_id)["result"]["artifact_path"])
        d = d if d.is_absolute() else ROOT / d
        for response_file in d.glob("model-response-*.json"):
            content = json.loads(response_file.read_text())["content"]
            i = content.find("{")
            strings = [content[:i].strip()] if i > 0 else []
            try:
                body = json.loads(content[i:])
                strings += [str(body.get(k) or "") for k in ("thinking", "memory", "next_goal", "evaluation_previous_goal")]
                strings += [str(v.get("description")) for a in body.get("action", []) for v in a.values() if isinstance(v, dict) and v.get("description")]
            except ValueError:
                findings.append(f"{response_file.name}: unparsable model content")
            for s in strings:
                if len(s) >= 20 and s in blob:
                    findings.append(f"model-generated text leaked from {entry_id}/{response_file.name}: {s[:40]!r}")
    inventory = {}
    for name, text in files.items():
        data = json.loads(text)
        inventory[name] = {"bytes": len(text.encode()), "top_level_fields": sorted(data)}
        if "steps" in data:
            inventory[name]["run_fields"] = sorted(data["run"])
            inventory[name]["step_fields"] = sorted(data["steps"][0]) if data["steps"] else []
            inventory[name]["steps"] = len(data["steps"])
    return findings, inventory


def main(argv):
    files = build()
    if "--check" in argv:
        bad = [n for n, t in files.items() if not (OUT / n).exists() or (OUT / n).read_text() != t]
        print("export matches files on disk" if not bad else f"MISMATCH: {bad}")
        return 1 if bad else 0
    OUT.mkdir(parents=True, exist_ok=True)
    for n, t in files.items():
        (OUT / n).write_text(t)
    print(f"wrote {len(files)} files to {OUT.relative_to(ROOT)} (Git-ignored, development-only)")
    if "--audit" in argv:
        findings, inventory = audit(files)
        print(json.dumps(inventory, indent=1))
        print("AUDIT:", "no findings" if not findings else f"{len(findings)} finding(s)")
        for f in findings:
            print(" -", f)
        return 1 if findings else 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
