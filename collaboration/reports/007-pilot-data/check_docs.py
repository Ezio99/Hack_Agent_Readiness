"""Run from the repository root (no model calls, no network). Recomputes the headline figures, protocol counts and bootstrap intervals
from per-run-reconciled.json and checks that Report 007 states them. Exit status 1 and a list of mismatches on failure."""
import json, random, re, statistics as ST, sys
DOC = open("collaboration/reports/007-availability-placement-pilot.md").read()
R = json.load(open("collaboration/reports/007-pilot-data/per-run-reconciled.json"))
mean = ST.mean; sd = ST.stdev
fails, checked = [], 0
def need(label, text):
    global checked
    checked += 1
    if text not in DOC:
        fails.append(f"{label}: expected {text!r}")
A = [r for r in R if r["arm"] == "A"]; B = [r for r in R if r["arm"] == "B"]
need("pass A/B", "arm A 15/15, arm B 14/15"); assert sum(r["passed"] for r in R) == 29 and sum(r["passed"] for r in A) == 15 and sum(r["passed"] for r in B) == 14
for name, X in (("A", A), ("B", B)):
    need(f"requests {name}", f"{mean(r['requests'] for r in X):.2f} (SD {sd([r['requests'] for r in X]):.2f})")
    need(f"prompt {name}", f"{round(mean(r['prompt'] for r in X)):,}")
    need(f"cost total {name}", f"US${sum(r['cost'] for r in X):.4f}")
    need(f"cost mean {name}", f"US${mean(r['cost'] for r in X):.4f} (SD {sd([r['cost'] for r in X]):.4f})")
    need(f"per-request s {name}", f"{sum(r['model_s'] for r in X) / sum(r['requests'] for r in X):.2f}")
need("run time", f"| Run time (s) | {mean(r['elapsed'] for r in A):.1f} | {mean(r['elapsed'] for r in B):.1f} |")
need("pilot total", f"**US${sum(r['cost'] for r in R):.4f}**")
# overhead run IDs (successful runs only) and revisits
pos = sorted(r["id"] for r in R if r["overhead"] and r["overhead"] > 0)
assert len(pos) == 10 and pos == sorted(r["id"] for r in R if r["revisits"] > 0)
for i in pos: need("overhead run id", i)
need("extra openings", "14 extra openings"); assert sum(r["revisits"] for r in R) == 14
fail = [r for r in R if not r["passed"]]; assert [r["id"] for r in fail] == ["27-s02-B2"]
s = fail[0]["shortfall"]; need("shortfall", f"required {s['required_visits']}, actual {s['actual_visits']}, shortfall {s['detail_visit_shortfall']}")
need("run 27 answer", "AR-7573, 4800 cents"); assert fail[0]["answer"]["product_id"] == "AR-7573" and fail[0]["answer"]["price_cents"] == 4800
# protocol
from collections import Counter
c = Counter(x for r in R for x in r["categories"]); need("protocol", f"| Raw-valid (strict JSON, no recovery needed) | **{c['raw_valid']}** |"); need("protocol rec", f"**{c['recovered']}**")
assert (c["raw_valid"], c["recovered"], c.get("rejected", 0), sum(c.values())) == (50, 132, 0, 182)
# by scope deltas
for seed, name in ((4, "Kitchen"), (3, "Bags"), (0, "Home"), (1, "Outdoors"), (2, "Fern")):
    a = [r for r in A if r["seed"] == seed]; b = [r for r in B if r["seed"] == seed]
    d = mean(r["cost"] for r in b) - mean(r["cost"] for r in a)
    need(f"cost delta {name}", f"{'+' if d >= 0 else '−'}US${abs(d):.3f}")
# bootstrap: same algorithm and seed as aggregate.py
random.seed(7)
def boot(seeds, key, successful=False, n=5000):
    res = []
    for _ in range(n):
        ds = []
        for s_ in seeds:
            f = (lambda r: r["passed"]) if successful else (lambda r: True)
            g = (lambda r: len(r["visits_trace"])) if key == "visits" else (lambda r, k=key: r[k])
            a = [g(r) for r in R if r["seed"] == s_ and r["arm"] == "A" and f(r)]; b = [g(r) for r in R if r["seed"] == s_ and r["arm"] == "B" and f(r)]
            ds.append(mean(random.choices(b, k=len(b))) - mean(random.choices(a, k=len(a))))
        res.append(mean(ds))
    res.sort(); return round(mean(res), 3), round(res[int(.025 * n)], 3), round(res[int(.975 * n)], 3)
fmt = lambda x, p: ("−" if x < 0 else "") + f"{abs(x):.{p}f}"
out = {}
for name, seeds in (("rank3", (0, 1, 2)), ("bags", (3,)), ("kitchen", (4,))):
    out[name] = {k: boot(seeds, k, k == "visits_succ") if False else boot(seeds, k) for k in ("cost", "requests", "elapsed")}
    out[name]["visits"] = boot(seeds, "visits"); out[name]["visits_succ"] = boot(seeds, "visits", True)
m, lo, hi = out["rank3"]["cost"]; need("boot rank3 cost", f"US${m:.3f} [{lo:.3f}, {hi:.3f}]")
m, lo, hi = out["rank3"]["requests"]; need("boot rank3 req", f"+{m:.1f} [{lo:.1f}, {hi:.1f}]")
m, lo, hi = out["rank3"]["elapsed"]; need("boot rank3 time", f"+{m:.1f} s [{lo:.1f}, {hi:.1f}]")
m, lo, hi = out["rank3"]["visits"]; need("boot rank3 visits", f"+{m:.2f} [{lo:.2f}, {hi:.2f}]")
m, lo, hi = out["rank3"]["visits_succ"]; need("boot rank3 visits succ", f"+{m:.2f} [{lo:.2f}, {hi:.2f}]")
m, lo, hi = out["bags"]["cost"]; need("boot bags cost", f"+US${m:.3f} [{lo:.3f}, {hi:.3f}]")
m, lo, hi = out["kitchen"]["cost"]; need("boot kitchen cost", f"−US${abs(m):.3f} [{fmt(lo, 3)}, {hi:.3f}]")
m, lo, hi = out["kitchen"]["requests"]; need("boot kitchen req", f"{fmt(m, 1)} [{fmt(lo, 1)}, {hi:.1f}]")
print(f"{checked} statements checked against the reconciled data;", "ALL MATCH" if not fails else f"{len(fails)} MISMATCH(ES)")
for f in fails: print(" -", f)
sys.exit(1 if fails else 0)
