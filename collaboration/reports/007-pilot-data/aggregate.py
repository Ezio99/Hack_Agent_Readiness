"""Run from the repository root. Aggregates computed directly from per-run-reconciled.json (itself derived from run artifacts). Unrounded math; rounding only for display."""
import json, random, statistics as ST
R = json.load(open("collaboration/reports/007-pilot-data/per-run-reconciled.json"))
mean = ST.mean; sd = lambda x: ST.stdev(x) if len(x) > 1 else 0.0
out = {}
print("OVERALL per arm (n=15 each): requests, run s, model-request s, s/request, prompt, completion, reasoning, cost mean (SD), cost total")
for arm in "AB":
    X = [r for r in R if r["arm"] == arm]
    print(arm, round(mean(r["requests"] for r in X), 3), round(mean(r["elapsed"] for r in X), 2), round(mean(r["model_s"] for r in X), 2),
          round(sum(r["model_s"] for r in X) / sum(r["requests"] for r in X), 3), round(mean(r["prompt"] for r in X)), round(mean(r["completion"] for r in X)),
          round(mean(r["reasoning"] for r in X)), round(mean(r["cost"] for r in X), 5), round(sd([r["cost"] for r in X]), 5), round(sum(r["cost"] for r in X), 5),
          "req SD", round(sd([r["requests"] for r in X]), 3), "visits mean(all)", round(mean(len(r["visits_trace"]) for r in X), 3))
print("TOTAL cost", round(sum(r["cost"] for r in R), 5), "sum of rounded metric costs", round(sum(r["cost_metric"] for r in R), 6))
print("scope arm | visits all (successful only) | overhead successful-only | req [min,max] | cost mean [min,max] | run s | prompt")
for seed in (4, 3, 0, 1, 2):
    row = {}
    for arm in "AB":
        X = [r for r in R if r["seed"] == seed and r["arm"] == arm]; S = [r for r in X if r["passed"]]
        row[arm] = X
        print(X[0]["scope"], X[0]["rank"], arm, "|", round(mean(len(r["visits_trace"]) for r in X), 3), "(%s)" % round(mean(len(r["visits_trace"]) for r in S), 3), "| ovh", round(mean(r["overhead"] for r in S), 3),
              "n=%d" % len(S), "| req", round(mean(r["requests"] for r in X), 3), [min(r["requests"] for r in X), max(r["requests"] for r in X)],
              "| cost", round(mean(r["cost"] for r in X), 4), [round(min(r["cost"] for r in X), 4), round(max(r["cost"] for r in X), 4)], "| t", round(mean(r["elapsed"] for r in X), 2), "| prompt", round(mean(r["prompt"] for r in X)))
    A, B = row["A"], row["B"]; rk = A[0]["rank"]
    d = lambda f: mean(f(r) for r in B) - mean(f(r) for r in A)
    ex = lambda X: mean(r["requests"] - (2 if r["arm"] == "A" else 2 * rk) for r in X)
    sA = [r for r in A if r["passed"]]; sB = [r for r in B if r["passed"]]
    print("  B-A:", A[0]["scope"], "visits(all)", round(d(lambda r: len(r["visits_trace"])), 3), "visits(successful only)", round(mean(len(r["visits_trace"]) for r in sB) - mean(len(r["visits_trace"]) for r in sA), 3),
          "req", round(d(lambda r: r["requests"]), 3), "cost", round(d(lambda r: r["cost"]), 4), "time", round(d(lambda r: r["elapsed"]), 2), "| required", 2 * (rk - 1), "extra-req diff", round(ex(B) - ex(A), 3))
random.seed(7)
def boot(seeds, key, successful=False, n=5000):
    res = []
    for _ in range(n):
        ds = []
        for s in seeds:
            f = (lambda r: r["passed"]) if successful else (lambda r: True)
            g = (lambda r: len(r["visits_trace"])) if key == "visits" else (lambda r, k=key: r[k])
            A = [g(r) for r in R if r["seed"] == s and r["arm"] == "A" and f(r)]; B = [g(r) for r in R if r["seed"] == s and r["arm"] == "B" and f(r)]
            ds.append(mean(random.choices(B, k=len(B))) - mean(random.choices(A, k=len(A))))
        res.append(mean(ds))
    res.sort(); return round(mean(res), 3), round(res[int(.025 * n)], 3), round(res[int(.975 * n)], 3)
for name, seeds in (("rank3 pooled (Home,Outdoors,Fern)", (0, 1, 2)), ("Bags", (3,)), ("Kitchen", (4,))):
    print(name, "cost", boot(seeds, "cost"), "req", boot(seeds, "requests"), "time", boot(seeds, "elapsed"), "visits(all)", boot(seeds, "visits"), "visits(successful)", boot(seeds, "visits", True))
