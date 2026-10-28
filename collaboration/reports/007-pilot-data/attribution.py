"""Run from the repository root. Splits each run's model requests into three sources, from per-run-reconciled.json:
  website-induced   : the deterministic navigation the page design forces = required requests (A: 2; B: 2*rank: a click and a go-back
                      per higher-priced candidate, then the answer click and done). Arm B's *extra* required navigation vs arm A is 2*(rank-1).
  tool-interface    : requests spent in agent<->tool interface failures = all `find_elements` calls in the 3 loop runs (>= 3 consecutive),
                      whose output (hrefs) reached the harness but not the model-visible history.
  agent-induced     : everything else above the required path (re-opened pages, 'thoroughness' detours, filter steps, backtracking, a
                      stray non-looping find_elements call).
Cost shares are prorated by request share and are therefore approximate (later requests carry longer histories)."""
import json, statistics as ST
R = json.load(open("collaboration/reports/007-pilot-data/per-run-reconciled.json"))
for r in R:
    req_required = 2 if r["arm"] == "A" else 2 * r["rank"]
    loop = len(r["find_elements"]) if len(r["find_elements"]) >= 3 else 0
    r["_req_required"], r["_req_tool"] = req_required, loop
    r["_req_agent"] = r["requests"] - req_required - loop
    r["_cost_per_req"] = r["cost"] / r["requests"]
print("per run: id arm required tool-interface agent-induced total | agent-induced may be negative when a run is shorter than the minimal path")
for r in R:
    print(r["id"], r["arm"], r["_req_required"], r["_req_tool"], r["_req_agent"], r["requests"], "" if r["passed"] else "FAILED (shortfall run)")
print("\nMEANS per run, requests: arm | required | tool-interface | agent-induced | total ; prorated cost US$: required | tool | agent")
for arm in "AB":
    X = [r for r in R if r["arm"] == arm]
    m = lambda f: ST.mean(f(r) for r in X)
    print(arm, round(m(lambda r: r["_req_required"]), 2), round(m(lambda r: r["_req_tool"]), 2), round(m(lambda r: r["_req_agent"]), 2), round(m(lambda r: r["requests"]), 2),
          "|", round(m(lambda r: r["_req_required"] * r["_cost_per_req"]), 4), round(m(lambda r: r["_req_tool"] * r["_cost_per_req"]), 4), round(m(lambda r: r["_req_agent"] * r["_cost_per_req"]), 4))
print("\nB - A mean requests: required %.2f, tool-interface %.2f, agent-induced %.2f, total %.2f" % tuple(
    ST.mean(r[k] for r in R if r["arm"] == "B") - ST.mean(r[k] for r in R if r["arm"] == "A") for k in ("_req_required", "_req_tool", "_req_agent", "requests")))
print("\nPER SCOPE B-A requests: scope | website-induced (required diff) | tool-interface diff | agent-induced diff | total")
for seed, name in ((4, "Kitchen"), (3, "Bags"), (0, "Home"), (1, "Outdoors"), (2, "Fern")):
    d = lambda k: ST.mean(r[k] for r in R if r["seed"] == seed and r["arm"] == "B") - ST.mean(r[k] for r in R if r["seed"] == seed and r["arm"] == "A")
    print(name, round(d("_req_required"), 2), round(d("_req_tool"), 2), round(d("_req_agent"), 2), round(d("requests"), 2))
print("\nTool-interface loop runs:", [(r["id"], r["arm"], len(r["find_elements"]), round(r["_req_tool"] * r["_cost_per_req"], 4)) for r in R if r["_req_tool"]])
print("Tool-interface requests total", sum(r["_req_tool"] for r in R), "of", sum(r["requests"] for r in R), "; prorated cost US$", round(sum(r["_req_tool"] * r["_cost_per_req"] for r in R), 4), "of", round(sum(r["cost"] for r in R), 4))
