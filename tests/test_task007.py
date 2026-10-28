"""Task 007 Stage 1 (offline, no browser): task kind, evaluator, oracle, solvers, leakage, isolation, metrics, schedule."""
import dataclasses
import hashlib
import json
import re
import pytest
from fastapi.testclient import TestClient
from agent_readiness import oracle, pilot
from agent_readiness.evaluator import evaluate
from agent_readiness.inventory import PRODUCTS
from agent_readiness.metrics import run_metrics
from agent_readiness.pilot import PilotError
from agent_readiness.storefront import VARIANT_AVAIL_ID, VARIANT_ID, create_app
from agent_readiness.tasks import INSTOCK_SCOPES, generate
from tests.test_pilot import Fake, live
from tests.test_variants import BASELINE_GOLDEN, TASKS_GOLDEN, queries, sha

SCOPE_RANKS = {0: ("Home", 3), 1: ("Outdoors", 3), 2: ("Fern", 3), 3: ("Bags", 2), 4: ("Kitchen", 1)}   # seed -> scope, rank
STOCK_LINE = '<p class="availability">{}</p>'
price_line = lambda p: f'<p class="price">${p.price_cents / 100:.2f}</p>'
clients = {v: TestClient(create_app(v)) for v in (VARIANT_ID, VARIANT_AVAIL_ID)}
A, B = clients[VARIANT_AVAIL_ID], clients[VARIANT_ID]
byid = {p.product_id: p for p in PRODUCTS}


def task(seed):
    return generate(seed, "instock_max")


# ---- task kind, determinism and the unchanged evaluator -------------------------------------------------------

def test_new_task_kind_is_deterministic_and_existing_kinds_are_untouched():
    rows = [[kind, s, t.public.task_id, t.public.prompt, t.expected_id]
            for kind in ("discovery", "availability") for s in range(60) for t in [generate(s, kind)]]
    assert sha(json.dumps(rows).encode()) == TASKS_GOLDEN
    assert sha(open("src/agent_readiness/evaluator.py", "rb").read()) == "47b960c9356bc0b26ca04a459f9f7d25e1bb795145f3b9510450cc8d8cb7c4de"
    assert len(INSTOCK_SCOPES) == 5
    for seed, (scope, rank) in SCOPE_RANKS.items():
        t = task(seed)
        assert t.public.kind == "instock_max" and scope in t.public.prompt
        assert t.public.prompt == (f"Find the most expensive {scope} product that is currently in stock. "
                                   "Return its product ID, price in integer cents, and whether it is available.")
        assert task(seed + 5).public.prompt == t.public.prompt and task(seed).public == t.public       # seeds wrap deterministically
        assert not hasattr(t.public, "expected_id")
    assert [task(s).expected_id for s in range(5)] == ["AR-7505", "AR-7556", "AR-7301", "AR-7301", "AR-7420"]


def truth(p):
    return {"product_id": p.product_id, "price_cents": p.price_cents, "available": p.available}


@pytest.mark.parametrize("seed", range(5))
def test_evaluator_accepts_only_the_most_expensive_in_stock_product_in_scope(seed):
    t = task(seed)
    members = oracle.scope_products(t)
    assert evaluate(truth(byid[t.expected_id]), t).passed
    for p in PRODUCTS:
        verdict = evaluate(truth(p), t)
        assert verdict.passed == (p.product_id == t.expected_id), (seed, p.name)       # out-of-scope, out-of-stock, lower-priced all fail
    assert evaluate({**truth(byid[t.expected_id]), "available": False}, t).passed is False
    assert evaluate({**truth(byid[t.expected_id]), "price_cents": 1}, t).passed is False
    assert evaluate({"product_id": "AR-0000", "price_cents": 1, "available": True}, t).passed is False
    assert members[0].product_id != t.expected_id or SCOPE_RANKS[seed][1] == 1


# ---- independent oracle: expected minimum detail visits, find vs verify ----------------------------------------

def test_oracle_is_independent_of_the_storefront_agent_and_pilot():
    source = open(oracle.__file__).read()
    assert not re.search(r"^\s*(from|import)\s+.*\b(storefront|agent|pilot|runner|metrics)\b", source, re.M)


@pytest.mark.parametrize("seed,expected", [(s, v) for s, v in SCOPE_RANKS.items()])
def test_oracle_minimum_visits_and_find_versus_verify(seed, expected):
    scope, rank = expected
    t = task(seed)
    a = oracle.analysis(t, listing_shows_availability=True)
    b = oracle.analysis(t, listing_shows_availability=False)
    assert a["rank"] == b["rank"] == rank and a["answer_id"] == t.expected_id
    # arm A: availability is on the listing, so nothing needs to be opened to find or to verify; the answer's page gives the ID
    assert (a["min_visits_to_find"], a["min_visits_to_verify_no_higher"], a["min_detail_visits"]) == (0, 0, 1)
    # arm B: every higher-priced candidate must be opened (verification), then the answer itself (finding + ID)
    assert (b["min_visits_to_find"], b["min_visits_to_verify_no_higher"], b["min_detail_visits"]) == (rank, rank - 1, rank)
    assert len(b["higher_priced_candidate_ids"]) == rank - 1 and not any(byid[i].available for i in b["higher_priced_candidate_ids"])
    assert "first in-stock" in b["stopping_condition"]
    assert oracle.minimum_detail_visits(t, True) == 1 and oracle.minimum_detail_visits(t, False) == rank
    for kind in ("discovery", "availability"):
        assert oracle.minimum_detail_visits(generate(0, kind), False) == oracle.minimum_detail_visits(generate(0, kind), True) == 1


@pytest.mark.parametrize("variant", [VARIANT_AVAIL_ID, VARIANT_ID])
def test_scripted_solvers_confirm_correctness_minimum_visits_and_stopping(variant):
    client, shows = clients[variant], variant == VARIANT_AVAIL_ID
    for seed, (scope, rank) in SCOPE_RANKS.items():
        t = task(seed)
        minimum = oracle.minimum_detail_visits(t, shows)
        best = oracle.solve_descending(client, t)
        assert evaluate(best["answer"], t).passed and len(best["detail_visits"]) == minimum    # exactly the minimum, then stops
        members = oracle.scope_products(t)
        assert best["detail_visits"][-1] == t.expected_id
        if not shows:
            assert best["detail_visits"] == [p.product_id for p in members[:rank]]              # top-down, no lower-priced page opened
        # finding without verifying: the cheapest in-stock product is found but is not the maximum -> wrong
        unverified = oracle.solve_ascending_unverified(client, t)
        assert not evaluate(unverified["answer"], t).passed
        # answering with the top price unchecked is right only when the top product happens to be in stock (rank 1)
        guess = oracle.solve_top_price_guess(client, t)
        assert evaluate(guess["answer"], t).passed == (rank == 1) and len(guess["detail_visits"]) == 1
        # exhaustive browsing is correct but pays navigation overhead = scope size - minimum
        exhaustive = oracle.solve_exhaustive(client, t)
        assert evaluate(exhaustive["answer"], t).passed and len(exhaustive["detail_visits"]) == len(members)


# ---- leakage and isolation --------------------------------------------------------------------------------------

def test_route_ids_and_listing_markup_in_arm_b_carry_no_availability_or_id_information():
    for p in PRODUCTS:
        flipped = dataclasses.replace(p, available=not p.available, product_id="AR-0000", price_cents=p.price_cents + 1)
        assert flipped.route == p.route == hashlib.sha256(("shop-route-v1:" + p.name).encode()).hexdigest()[:20]
    for path in queries():
        response = B.get(path)
        blob = response.text + json.dumps(dict(response.headers))
        assert not re.search(r"stock|availab|AR-\d|data-[\w-]+=|hidden|display:\s*none|aria-hidden|visibility", blob, re.I), path
        assert {m for m in re.findall(r'href="([^"]+)"', response.text) if m.startswith("/products/")} <= {f"/products/{p.route}" for p in PRODUCTS}
    for p in PRODUCTS:   # URLs carry nothing but the route
        assert re.fullmatch(r"/products/[0-9a-f]{20}", f"/products/{p.route}")


def test_arm_a_listing_shows_truthful_availability_and_nothing_else_new():
    html = A.get("/").text
    assert re.findall(r'<p class="availability">([^<]+)</p>', html) == ["In stock" if p.available else "Out of stock" for p in PRODUCTS]
    assert not re.search(r"AR-\d|data-[\w-]+=|hidden|display:\s*none|aria-hidden", html + json.dumps(dict(A.get("/").headers)))
    for path in queries():
        a, b = A.get(path), B.get(path)
        assert a.status_code == b.status_code
        transformed = b.text
        for p in PRODUCTS:
            transformed = transformed.replace(price_line(p), price_line(p) + STOCK_LINE.format("In stock" if p.available else "Out of stock"))
        assert transformed == a.text, path                       # A differs from B only by the availability line per card


def test_arm_b_is_the_unchanged_baseline_byte_for_byte_and_detail_pages_are_identical():
    for path, golden in BASELINE_GOLDEN.items():
        assert sha(B.get(path).content) == golden
    for p in PRODUCTS:
        assert A.get(f"/products/{p.route}").content == B.get(f"/products/{p.route}").content
    assert sha(open("src/agent_readiness/templates/listing.html", "rb").read()) == "18c7e3fbb7c49129a377b31d19b3d77d06140c3f3ed60d18a054661c856f39d5"
    base = open("src/agent_readiness/templates/listing.html").read()
    assert open("src/agent_readiness/templates/listing_avail.html").read().replace(
        '<p class="availability">{% if p.available %}In stock{% else %}Out of stock{% endif %}</p>', "") == base


# ---- metrics: navigation overhead -------------------------------------------------------------------------------

def obs(step, url, actions=None):
    return {"kind": "observation", "step": step, "url": url, "proposed_actions": actions or []}


def trace(*products):
    base, events = "http://127.0.0.1:1", [obs(1, "http://127.0.0.1:1/")]
    for i, p in enumerate(products):
        events += [obs(2 + 2 * i, f"{base}/products/{p.route}"), obs(3 + 2 * i, f"{base}/")]
    return events


def test_navigation_overhead_reports_actual_minimum_and_difference_without_judging_correctness():
    t = task(0)                                                      # Home: Cotton Throw (n), Reading Lamp (n), Woven Basket (answer)
    members = oracle.scope_products(t)
    record = {"evaluation": {"passed": True}, "status": "completed", "answer": truth(byid[t.expected_id])}
    exact = run_metrics(trace(*members[:3]), record, t.expected_id, t, False)["navigation_overhead"]
    assert (exact["detail_visits_actual"], exact["detail_visits_minimum"], exact["navigation_overhead"]) == (3, 3, 0)
    assert exact["verification_complete"] is True and exact["higher_priced_candidates_checked"] == 2 and exact["answered_product_page_visited"]
    extra = run_metrics(trace(members[4], *members[:3]), record, t.expected_id, t, False)["navigation_overhead"]
    assert (extra["detail_visits_actual"], extra["navigation_overhead"], extra["distinct_detail_pages"]) == (4, 1, 4)
    guess = run_metrics(trace(members[2]), {**record, "evaluation": {"passed": True}}, t.expected_id, t, False)["navigation_overhead"]
    assert guess["navigation_overhead"] == -2 and guess["verification_complete"] is False and guess["higher_priced_candidates_checked"] == 0
    in_a = run_metrics(trace(members[2]), record, t.expected_id, t, True)["navigation_overhead"]
    assert (in_a["detail_visits_minimum"], in_a["navigation_overhead"], in_a["verification_basis"]) == (1, 0, "listing availability")
    wrong = run_metrics(trace(members[0]), {"evaluation": {"passed": False}, "status": "completed",
                                            "answer": truth(members[0])}, t.expected_id, t, False)
    assert wrong["task_success"]["evaluator_passed"] is False and wrong["navigation_overhead"]["answer_is_target"] is False
    assert run_metrics(trace(), {"evaluation": None, "status": "step_limit"}, t.expected_id, t, False)["navigation_overhead"]["detail_visits_actual"] == 0
    discovery = run_metrics(trace(byid["AR-7318"]), {"evaluation": {"passed": True}, "status": "completed", "answer": None},
                            "AR-7318", generate(2, "discovery"), False)["navigation_overhead"]
    assert (discovery["detail_visits_minimum"], discovery["navigation_overhead"]) == (1, 0)


# ---- pre-registered, deterministic 30-run schedule and frozen limits ------------------------------------------

def test_task007_schedule_is_the_deterministic_counterbalanced_30_run_design():
    entries = pilot.build_schedule("007")
    assert entries == pilot.build_schedule("007") and len(entries) == 30
    assert [e["seed"] for e in entries[::6]] == [0, 4, 1, 3, 2]
    by_seed = {}
    for e in entries:
        by_seed.setdefault(e["seed"], []).append(e)
    for seed, rows in by_seed.items():
        assert len(rows) == 6 and sorted((r["arm"], r["repetition"]) for r in rows) == [("A", 1), ("A", 2), ("A", 3), ("B", 1), ("B", 2), ("B", 3)]
        assert "".join(r["arm"] for r in rows) in ("ABBAAB", "BAABBA")
        positions = {"A": [r["slot"] for r in rows if r["arm"] == "A"], "B": [r["slot"] for r in rows if r["arm"] == "B"]}
        assert abs(sum(positions["A"]) - sum(positions["B"])) == 1 and sum(positions["A"]) + sum(positions["B"]) == 21
    firsts = ["".join(r["arm"] for r in rows)[0] for rows in by_seed.values()]
    assert sorted(firsts) == ["A", "A", "A", "B", "B"]
    assert {e["storefront_variant"] for e in entries if e["arm"] == "A"} == {VARIANT_AVAIL_ID}
    assert {e["storefront_variant"] for e in entries if e["arm"] == "B"} == {VARIANT_ID}
    assert sum(e["arm"] == "A" for e in entries) == 15


def test_task007_frozen_configuration_documents_every_deviation_from_task_005_006():
    f, base = pilot.FROZEN_007, pilot.FROZEN
    diff = {k: (base[k], f[k]) for k in f if base.get(k) != f[k]}
    assert diff == {"kind": ("discovery", "instock_max"), "max_steps": (6, 12), "max_model_requests": (6, 12),
                    "timeout_seconds": (120, 240), "max_cumulative_estimated_cost_usd": (0.25, 0.48)}
    assert (f["profile_id"], f["model"], f["max_estimated_cost_usd"], f["expect_schema_sha256"]) == (
        base["profile_id"], base["model"], 0.04, base["expect_schema_sha256"])
    assert pilot.LIMITS_007 == {"pilot_estimated_cap_usd": 15.0, "review_halt_actual_usd": 4.0, "max_consecutive_model_output_errors": 2}
    assert pilot.schedule_sha256() == "bb660b0c0f1f7a6a1215ea2bfff6beda0a2124a95201f8c93c1214254fa3dcf4"      # Task 006 hash unchanged
    assert pilot.schedule_sha256(experiment="007") != pilot.schedule_sha256()
    assert 12 * f["max_estimated_cost_usd"] == f["max_cumulative_estimated_cost_usd"]                     # per-request ceiling x gate == per-run cap


async def test_task007_driver_uses_the_new_limits_and_keeps_all_safeguards(tmp_path):
    state = pilot.plan(tmp_path, "live", "007")
    assert state["task"] == "007" and len(state["entries"]) == 30 and state["limits"] == pilot.LIMITS_007
    fake = Fake(tmp_path)
    done = await live(tmp_path, fake, max_runs=3)
    for call in fake.calls:
        assert (call["kind"], call["max_steps"], call["max_model_requests"], call["timeout_seconds"]) == ("instock_max", 12, 12, 240)
        assert (call["max_estimated_cost_usd"], call["max_cumulative_estimated_cost_usd"], call["profile_id"]) == (0.04, 0.48, "natural-shopping-v3-compat1")
        assert call["allow_model_calls"] is True and call["mode"] == "live"
    assert [c["storefront_variant"] for c in fake.calls] == [VARIANT_AVAIL_ID, VARIANT_ID, VARIANT_ID]
    # no live execution without the flag and the exact hash; a different experiment's hash is refused
    with pytest.raises(PilotError):
        await pilot.drive(tmp_path, fake, mode="live", allow_model_calls=True,
                          approved_schedule_sha256=pilot.schedule_sha256())
    # a failure still halts and the halted run is not repeated; resume needs an approval note
    fake2 = Fake(tmp_path / "x", mutate={2: {"status": "estimated_cost_limit"}})
    pilot.plan(tmp_path / "x", "live", "007")
    halted = await live(tmp_path / "x", fake2)
    assert halted["halt"]["kind"] == "cost_cap_block" and len(fake2.calls) == 2
    with pytest.raises(PilotError):
        await live(tmp_path / "x", fake2)


async def test_task007_drift_in_the_frozen_configuration_blocks_execution(tmp_path, monkeypatch):
    pilot.plan(tmp_path, "live", "007")
    monkeypatch.setitem(pilot.FROZEN_007, "max_steps", 13)
    with pytest.raises(PilotError):
        await live(tmp_path, Fake(tmp_path))


def test_the_two_experiments_cannot_share_a_state_directory(tmp_path):
    pilot.plan(tmp_path, "live", "007")
    with pytest.raises(PilotError):
        pilot.plan(tmp_path, "live", "006")
