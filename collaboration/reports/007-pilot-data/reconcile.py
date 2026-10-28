"""Read-only reconciliation of Task 007 against raw artifacts (run.json, trace.jsonl, history.json, model-response-NN.json).
No model calls, no writes into the checkout. Run from the repository root (needs runs/pilot-task007/): PYTHONPATH=src python collaboration/reports/007-pilot-data/reconcile.py collaboration/reports/007-pilot-data/per-run-reconciled.json"""
import glob, json, statistics as ST, sys
from urllib.parse import urlsplit
from agent_readiness.inventory import PRODUCTS
from agent_readiness import oracle
from agent_readiness.tasks import generate

PRICE_IN, PRICE_OUT = 1.25, 4.25
ROUTE = {p.route: p for p in PRODUCTS}
SC = {0: "Home", 4: "Kitchen", 1: "Outdoors", 3: "Bags", 2: "Fern"}
st = json.load(open("runs/pilot-task007/pilot-state.json"))


def product_of(url):
    path = urlsplit(url or "").path
    return ROUTE.get(path[len("/products/"):].strip("/")) if path.startswith("/products/") else None


def arrivals(urls):
    out, last = [], None
    for u in urls:
        if u == last or not u:
            continue
        last = u
        p = product_of(u)
        if p:
            out.append(p.name)
    return out


runs = []
for e in st["entries"]:
    d = e["result"]["artifact_path"]
    rj = json.load(open(d + "/run.json"))
    tr = [json.loads(l) for l in open(d + "/trace.jsonl")]
    hist = json.load(open(d + "/history.json"))["history"]
    task = generate(e["seed"], "instock_max")
    shows = e["arm"] == "A"
    info = oracle.analysis(task, shows)
    obs_urls = [t["url"] for t in tr if t["kind"] == "observation"]
    hist_urls = [h["state"]["url"] for h in hist]
    v_trace, v_hist = arrivals(obs_urls), arrivals(hist_urls)
    v_metric = rj["metrics"]["navigation_overhead"]["detail_visits_actual"]
    last_actions = [list(a)[0] for a in (hist[-1]["model_output"] or {}).get("action", [])]
    # tokens/cost recomputed from run.json usage (unrounded)
    pt = sum(u["prompt_tokens"] for u in rj["usage"]); ct = sum(u["completion_tokens"] for u in rj["usage"])
    cost = pt * PRICE_IN / 1e6 + ct * PRICE_OUT / 1e6
    caps = rj["http_captures"]
    resp_files = sorted(glob.glob(d + "/model-response-*.json"))
    cats = []
    for f in resp_files:
        r = json.load(open(f))
        rec = (r.get("recovery") or {}).get("status")
        cats.append("raw_valid" if r.get("raw_protocol_compliant") is True else
                    "recovered" if rec == "recovered" else "rejected" if rec == "rejected" else "other")
    fe = [t for t in tr if t["kind"] == "step_result"]
    fe_calls = []
    mreq = [t for t in tr if t["kind"] == "model_request"]
    for i, t in enumerate(fe):
        for x in t["result"]["result"]:
            c = x.get("extracted_content") or ""
            if c.startswith("Found") and "elements matching" in c:
                nxt = json.dumps(mreq[i + 1]["messages"]) if i + 1 < len(mreq) else ""
                fe_calls.append({"step": i + 1, "tool_output_contains_product_hrefs": 'href="/products/' in c,
                                 "next_model_request_shows_hrefs": 'href="/products/' in nxt or "{href=" in nxt,
                                 "next_model_request_shows_count_line": "elements matching" in nxt})
    runs.append(dict(
        id=e["entry_id"], run_id=e["result"]["run_id"], seed=e["seed"], scope=SC[e["seed"]], arm=e["arm"], rep=e["repetition"],
        passed=bool(e["result"]["evaluator_passed"]), status=rj["status"], stop_reason=rj["stop_reason"],
        required_visits=info["min_detail_visits"], rank=info["rank"], higher_ids=info["higher_priced_candidate_ids"],
        visits_trace=v_trace, visits_history=v_hist, visits_metric=v_metric,
        sources_agree=(len(v_trace) == len(v_hist) == v_metric and v_trace == v_hist),
        last_action=last_actions, answer=rj["answer"], expected=task.expected_id,
        requests=e["result"]["model_request_count"], resp_files=len(resp_files), http200=rj["protocol_compliance"]["http_200_responses"],
        categories=cats, finish=sorted({c["finish_reason"] for c in caps}),
        prompt=pt, completion=ct, reasoning=sum(c["reasoning_tokens"] or 0 for c in caps), cost=cost, cost_metric=rj["metrics"]["cost"]["calculated_actual_usd"],
        elapsed=rj["elapsed_seconds"], model_s=sum(c["elapsed_seconds"] for c in caps), per_req_s=[c["elapsed_seconds"] for c in caps],
        worst_sent=(rj["estimated_cost"] or {})["cumulative_estimated_sent_usd"], narrowed=rj["schema_narrowing_detected"], violations=rj["fidelity_violations"],
        find_elements=fe_calls, find_elements_params_href=[a.get("find_elements", {}).get("attributes") for h in hist for a in ((h["model_output"] or {}).get("action") or []) if "find_elements" in a],
        state_summary_cost=e["result"]["calculated_actual_usd"], state_summary_requests=e["result"]["model_request_count"]))

# derived navigation metrics: overhead only on SUCCESSFUL runs; failed runs get a verification shortfall instead
for r in runs:
    visited = r["visits_trace"]
    higher_checked = len({p.name for p in PRODUCTS if p.product_id in r["higher_ids"]} & set(visited)) if r["arm"] == "B" else None
    if r["passed"]:
        r["overhead"] = len(visited) - r["required_visits"]
        r["shortfall"] = None
    else:
        r["overhead"] = None
        r["shortfall"] = {"required_visits": r["required_visits"], "actual_visits": len(visited),
                          "detail_visit_shortfall": max(0, r["required_visits"] - len(visited)),
                          "higher_priced_candidates": len(r["higher_ids"]), "higher_priced_checked": higher_checked,
                          "higher_priced_unchecked": (len(r["higher_ids"]) - higher_checked) if higher_checked is not None else None}
    r["revisits"] = len(visited) - len(set(visited))
json.dump(runs, open(sys.argv[1], "w"), indent=1, default=str)
print("runs", len(runs), "sources agree on every run:", all(r["sources_agree"] for r in runs))
print("disagreements:", [r["id"] for r in runs if not r["sources_agree"]])
print("all runs end with done:", all(r["last_action"] == ["done"] for r in runs))
print("responses: files", sum(r["resp_files"] for r in runs), "http200", sum(r["http200"] for r in runs), "requests", sum(r["requests"] for r in runs), "state-summary requests", sum(r["state_summary_requests"] for r in runs))
from collections import Counter
c = Counter(x for r in runs for x in r["categories"]); print("categories", dict(c), "finish", Counter(f for r in runs for f in r["finish"]))
print("first step", Counter(r["categories"][0] for r in runs), "later", Counter(x for r in runs for x in r["categories"][1:]))
for arm in "AB":
    print(arm, dict(Counter(x for r in runs if r["arm"] == arm for x in r["categories"])))
print("max |cost recompute - metrics| =", max(abs(r["cost"] - r["cost_metric"]) for r in runs), "| vs driver summary =", max(abs(r["cost"] - r["state_summary_cost"]) for r in runs))
print("positive overhead (successful runs):", [(r["id"], r["arm"], r["overhead"]) for r in runs if r["overhead"] and r["overhead"] > 0])
print("zero overhead:", Counter(r["arm"] for r in runs if r["overhead"] == 0), "failed:", [(r["id"], r["shortfall"]) for r in runs if not r["passed"]])
print("revisit runs:", [(r["id"], r["arm"], r["scope"], r["revisits"], Counter(r["visits_trace"]).most_common(1)[0]) for r in runs if r["revisits"]])
print("find_elements runs:", [(r["id"], len(r["find_elements"]), r["find_elements_params_href"][:2], [ (c["tool_output_contains_product_hrefs"], c["next_model_request_shows_hrefs"]) for c in r["find_elements"]][:2]) for r in runs if r["find_elements"]])
