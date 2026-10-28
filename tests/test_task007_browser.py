"""Task 007 Stage 1 in real Chromium: Browser Use observations, accessibility trees, screenshots, oracle-vs-browsing and limits."""
import json
import re
import httpx
import pytest
from openai import DefaultAsyncHttpxClient
from agent_readiness import oracle, runner
from agent_readiness.capture import DONE_ONLY_SCHEMA_SHA256, FULL_AGENT_SCHEMA_SHA256, estimate_cost_usd
from agent_readiness.evaluator import evaluate
from agent_readiness.inventory import PRODUCTS
from agent_readiness.storefront import VARIANT_AVAIL_ID, VARIANT_B_ID, VARIANT_D0_ID, VARIANT_ID
from agent_readiness.tasks import generate
from tests.test_step_aware_guard import DONE, reply
from tests.test_task007 import SCOPE_RANKS, truth
from tests.test_variants_browser import cards, link_index, observe

pytestmark = pytest.mark.browser
SENTINEL = "sentinel-model-credential-0123456789-not-real"
STOCK = lambda p: "In stock" if p.available else "Out of stock"
VARIANT_STRINGS = (VARIANT_AVAIL_ID, VARIANT_ID, VARIANT_B_ID, VARIANT_D0_ID, "variant", "diagnostic")


async def test_browser_use_observations_accessibility_and_screenshots_differ_only_by_availability_lines():
    a, b = await observe(VARIANT_AVAIL_ID), await observe(VARIANT_ID)
    names = [p.name for p in PRODUCTS]
    stock_lines = lambda rep: [l.strip() for l in cards(rep).splitlines() if l.strip() in ("In stock", "Out of stock")]
    # Arm A: availability is in what the model receives, once per card, in card order, equal to inventory truth
    assert stock_lines(a["agent_dom"]) == [STOCK(p) for p in PRODUCTS]
    # Arm B: no availability wording anywhere in the listing observation, accessibility tree, HTML or URL
    for blob in (b["agent_dom"], b["ax_json"], b["html"], b["url"]):
        assert not re.search(r"stock|availab", blob, re.I), blob[:80]
    assert stock_lines(b["agent_dom"]) == []
    # accessibility tree: identical link names; A adds exactly the 20 static-text stock nodes, B none
    assert a["ax_links"] == b["ax_links"] == names
    assert len(re.findall(r'"value": ?"(?:In stock|Out of stock)"', a["ax_json"])) >= 20 and "stock" not in b["ax_json"].lower()
    # nothing else differs in the agent view: remove the stock lines from A and the views coincide after index/URL normalisation
    strip = lambda rep: re.sub(r"\[\d+\]|\*", "[]", re.sub(r"\n(?:In stock|Out of stock)(?=\n)", "", cards(rep)))
    assert strip(a["agent_dom"]) == strip(b["agent_dom"])
    # screenshots differ (taller cards); observation size delta is bounded and recorded
    assert a["screenshot"] != b["screenshot"]
    delta = len(cards(a["agent_dom"])) - len(cards(b["agent_dom"]))
    assert 100 < delta < 1200, delta
    # no product ID, route-derived stock signal or variant identity leaks in either arm's initial observation
    for view in (a, b):
        blob = view["agent_dom"] + view["ax_json"] + view["html"] + view["url"]
        assert not any(p.product_id in blob for p in PRODUCTS) and not any(s in blob for s in VARIANT_STRINGS)


async def test_detail_page_observations_are_identical_in_both_arms():
    route = next(p for p in PRODUCTS if not p.available).route
    a, b = await observe(VARIANT_AVAIL_ID, f"products/{route}"), await observe(VARIANT_ID, f"products/{route}")
    # element indices are a session-wide counter (the preceding listing differs by the stock lines), so they are normalised
    norm = lambda s: re.sub(r"\[\d+\]", "[]", re.sub(r"127\.0\.0\.1:\d+", "H", s))
    assert norm(a["agent_dom"]) == norm(b["agent_dom"]) and norm(a["html"]) == norm(b["html"]) and a["screenshot"] == b["screenshot"]
    assert "Out of stock" in a["agent_dom"] and "AR-" in a["agent_dom"]    # the information B hides on the listing is here, in both arms


@pytest.mark.parametrize("seed", range(5))
async def test_filtered_scope_listing_in_chromium_matches_truth_in_arm_a_and_hides_it_in_arm_b(seed):
    scope, rank = SCOPE_RANKS[seed]
    t = generate(seed, "instock_max")
    query = f"?brand={scope}" if t.brand else f"?category={scope}"
    members = oracle.scope_products(t)
    a, b = await observe(VARIANT_AVAIL_ID, query), await observe(VARIANT_ID, query)
    assert f"{len(members)} products" in a["agent_dom"] and f"{len(members)} products" in b["agent_dom"]
    listed = [l.strip() for l in a["agent_dom"].splitlines() if l.strip() in ("In stock", "Out of stock")]
    order = [p for p in PRODUCTS if p in members]                       # listing order within the scope
    assert listed == [STOCK(p) for p in order]
    assert not re.search(r"stock|availab", b["agent_dom"] + b["ax_json"] + b["html"], re.I)


@pytest.mark.parametrize("variant", [VARIANT_AVAIL_ID, VARIANT_ID])
async def test_browsing_in_chromium_matches_the_oracle_minimum_for_every_scope(tmp_path, variant):
    for seed in range(5):
        path, record = await runner.run(mode="smoke", kind="instock_max", seed=seed, output=tmp_path, storefront_variant=variant,
                                        max_steps=12, timeout_seconds=240)
        t = generate(seed, "instock_max")
        assert record["status"] == "completed" and record["evaluation"]["passed"], (seed, record.get("errors"))
        nav = record["metrics"]["navigation_overhead"]
        minimum = oracle.minimum_detail_visits(t, variant == VARIANT_AVAIL_ID)
        assert (nav["detail_visits_actual"], nav["detail_visits_minimum"], nav["navigation_overhead"]) == (minimum, minimum, 0), seed
        assert nav["answer_is_target"] is True and nav["verification_complete"] is True
        assert nav["scope_rank_of_answer"] == SCOPE_RANKS[seed][1]


async def mocked_run(tmp_path, monkeypatch, handler, **kwargs):
    monkeypatch.setenv("META_MODEL_API_KEY", SENTINEL)
    original = runner.create_model

    def make(config, effective):
        model = original(config, effective)
        model.http_client = DefaultAsyncHttpxClient(transport=httpx.MockTransport(handler))
        sdk = model.get_client()
        sdk._platform = "Linux"
        model.get_client = lambda: sdk
        return model
    monkeypatch.setattr(runner, "create_model", make)
    return await runner.run(mode="live", allow_model_calls=True, output=tmp_path, kind="instock_max", timeout_seconds=240,
                            profile_id="natural-shopping-v3-compat1", expect_schema_sha256=FULL_AGENT_SCHEMA_SHA256,
                            max_estimated_cost_usd=0.04, max_cumulative_estimated_cost_usd=0.48, max_steps=12,
                            max_model_requests=12, **kwargs)


@pytest.mark.parametrize("variant", [VARIANT_AVAIL_ID, VARIANT_ID])
async def test_scripted_model_end_to_end_records_zero_overhead_for_the_minimal_path(tmp_path, monkeypatch, variant):
    t = generate(0, "instock_max")                      # Home: Cotton Throw (out), Reading Lamp (out), Woven Basket (answer)
    members = oracle.scope_products(t)
    answer = next(p for p in members if p.product_id == t.expected_id)
    path_names = [p.name for p in members[:3]] if variant == VARIANT_ID else [answer.name]
    steps, calls = [], []
    for name in path_names:
        steps += [("click", name)] + ([("go_back", None)] if name != answer.name else [])
    steps.append(("done", None))

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        kind, name = steps[min(len(calls), len(steps)) - 1]
        user = body["messages"][1]["content"][0]["text"]
        action = ({"click": {"index": link_index(user, name, VARIANT_ID)}} if kind == "click" else
                  {"go_back": {}} if kind == "go_back" else {"done": {"data": truth(answer)}})
        return reply(len(calls), action)
    path, record = await mocked_run(tmp_path, monkeypatch, handler, seed=0, storefront_variant=variant)
    assert record["status"] == "completed" and record["evaluation"]["passed"], record.get("errors")
    nav = record["metrics"]["navigation_overhead"]
    assert nav["detail_visits_actual"] == nav["detail_visits_minimum"] == (3 if variant == VARIANT_ID else 1)
    assert nav["navigation_overhead"] == 0 and nav["verification_complete"] and nav["answered_product_page_visited"]
    assert len(calls) == len(steps) and record["fidelity_violations"] is None
    assert record["limits"] == {"max_steps": 12, "timeout_seconds": 240.0, "max_model_requests": 12}
    assert record["metrics"]["task_success"]["evaluator_passed"] is True and record["metrics"]["protocol"]["raw_protocol_compliant"] == len(calls)


@pytest.mark.parametrize("variant", [VARIANT_AVAIL_ID, VARIANT_ID])
async def test_twelve_step_limits_guard_final_step_and_cost_caps_hold_in_both_arms(tmp_path, monkeypatch, variant):
    calls, estimates = [], []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        estimates.append(estimate_cost_usd(body)["usd"])
        return reply(len(calls), {"wait": {"seconds": 1}} if len(calls) < 12 else DONE)
    path, record = await mocked_run(tmp_path, monkeypatch, handler, seed=2, storefront_variant=variant)
    assert record["status"] == "completed" and record["fidelity_violations"] is None, record.get("errors")
    assert len(calls) == 12 and record["model_request_count"] == 12                       # the 12-request gate and 12-step budget
    shas = [json.dumps(c["response_format"]["json_schema"]["schema"], sort_keys=True, separators=(",", ":")) for c in calls]
    import hashlib
    digests = [hashlib.sha256(s.encode()).hexdigest() for s in shas]
    assert digests[:11] == [FULL_AGENT_SCHEMA_SHA256] * 11 and digests[11] == DONE_ONLY_SCHEMA_SHA256
    assert all("BUDGET WARNING" in json.dumps(calls[i]["messages"]) for i in (8, 9, 10)) and "BUDGET WARNING" not in json.dumps(calls[7]["messages"])
    assert max(estimates) < 0.04 and sum(estimates) <= 0.48                                # per-request ceiling and per-run cap
    cost = record["estimated_cost"]
    assert (cost["per_request_ceiling_usd"], cost["cumulative_cap_usd"], cost["requests_blocked_before_network"]) == (0.04, 0.48, 0)
    assert cost["cumulative_estimated_sent_usd"] <= 0.48 and record["limits"]["timeout_seconds"] == 240.0


async def test_cumulative_cap_of_0_48_blocks_a_thirteenth_dollar_of_estimated_spend_before_the_network(tmp_path, monkeypatch):
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return reply(len(calls), {"wait": {"seconds": 1}})
    monkeypatch.setenv("META_MODEL_API_KEY", SENTINEL)
    original = runner.create_model

    def make(config, effective):
        model = original(config, effective)
        model.http_client = DefaultAsyncHttpxClient(transport=httpx.MockTransport(handler))
        sdk = model.get_client()
        sdk._platform = "Linux"
        model.get_client = lambda: sdk
        return model
    monkeypatch.setattr(runner, "create_model", make)
    path, record = await runner.run(mode="live", allow_model_calls=True, output=tmp_path, kind="instock_max", seed=0,
                                    storefront_variant=VARIANT_ID, timeout_seconds=240, profile_id="natural-shopping-v3-compat1",
                                    expect_schema_sha256=FULL_AGENT_SCHEMA_SHA256, max_estimated_cost_usd=0.04,
                                    max_cumulative_estimated_cost_usd=0.07, max_steps=12, max_model_requests=12)
    assert record["status"] == "estimated_cost_limit" and 1 <= len(calls) <= 2
    assert record["estimated_cost"]["requests_blocked_before_network"] >= 1 and record["estimated_cost"]["cumulative_estimated_sent_usd"] <= 0.07
