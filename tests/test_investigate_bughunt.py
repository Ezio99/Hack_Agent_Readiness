"""Regression tests for the adversarial bug hunt (collaboration/reports/016f-bug-hunt.md). Each test reproduces a counterexample that previously produced a convincing but FALSE (or lost) result."""
import asyncio
import json
import os
import random

import pytest

from agent_readiness.investigate import flow, zoo
from agent_readiness.investigate.evaluate import design
from agent_readiness.investigate.evaluate import stage as ev
from agent_readiness.investigate.inspect.profile import build_profile, observations
from agent_readiness.investigate.investigator import verifiers as V
from agent_readiness.investigate.investigator.loop import investigate
from agent_readiness.investigate.investigator.stage import investigate_stage
from agent_readiness.investigate.llm import ScriptedClient
from agent_readiness.investigate.models import Hypothesis, Observation, Provenance
from agent_readiness.investigate.pipeline import Context
from agent_readiness.investigate.sitemodel.patch import apply_patch
from agent_readiness.investigate.store import EvidenceStore
from agent_readiness.investigate.taskgen import freeze as freezer
from agent_readiness.investigate.taskgen import gate
from agent_readiness.investigate.taskgen.candidates import candidates
from agent_readiness.investigate.taskgen.criteria import answer_match, compile_criterion, grade, norm_answer
from agent_readiness.investigate.trials import stage as trials_stage
from agent_readiness.investigate.trials.attribution import attribute
from agent_readiness.investigate.trials.trace import analyze, trace_stage
from agent_readiness.suite.core import Observation as SuiteObs
from agent_readiness.suite.core import evaluate as core_eval

from . import test_investigate_fix_eval as F
from . import test_investigate_investigator as T

P = {sid: build_profile(zoo.snapshot(sid)) for sid in zoo.ids()}


# ---- 1. evaluation integrity: grading -------------------------------------------------------------------------------------------------------------------------------------------
def test_a_hedged_answer_that_names_several_candidates_is_not_correct():
    c = compile_criterion({"kind": "page_fact", "page": "/workshops/pottery-basics", "label": "date"}, P["site-1"])
    assert grade(c, "12 Nov")[0] and grade(c, "It is 12 Nov.")[0]
    for hedge in ("12 Nov or 14 Nov", "14 Nov, 12 Nov", "either 12 Nov or 19 Nov", "12 Nov / 3 Dec"):
        ok, d = grade(c, hedge)
        assert not ok, hedge
    e = compile_criterion({"kind": "extremum", "listing": "/workshops", "label": "price", "direction": "max"}, P["site-1"])
    assert grade(e, "Silver Ring Making")[0] and not grade(e, "Silver Ring Making, Pottery Basics")[0] and not grade(e, "Pottery Basics or Silver Ring Making")[0]
    r = compile_criterion({"kind": "reach_page", "target": "/faq"}, P["site-1"])
    assert grade(r, "Frequently asked questions")[0] and not grade(r, "Frequently asked questions or About")[0] and not grade(r, "Frequently asked questions or About Fieldhouse")[0]


@pytest.mark.parametrize("sid", zoo.ids())
def test_property_the_truth_passes_every_other_offered_answer_fails_and_no_pairing_with_one_passes(sid):
    rng = random.Random(7)
    accepted = []
    for d in candidates(P[sid]):
        r = gate.evaluate(d, P[sid], accepted)
        if isinstance(r, gate.Accepted):
            accepted.append(r)
    assert accepted
    for a in accepted:
        c = a.compiled
        if c.style != "string":
            continue
        assert grade(c, c.truth)[0] and grade(c, c.truth + ".")[0] and grade(c, c.truth.upper())[0]
        for dis in c.distractors:
            assert not grade(c, dis)[0], (c.truth, dis)
            joiner = rng.choice([" or ", ", ", " / ", " and "])
            assert not grade(c, c.truth + joiner + dis)[0], (c.truth, dis, joiner)
            assert not grade(c, dis + joiner + c.truth)[0]


def test_trailing_punctuation_does_not_fail_a_correct_set_or_string():
    s = compile_criterion({"kind": "item_set", "listing": "/workshops", "conditions": [{"label": "level", "op": "eq", "value": "Intermediate"}]}, P["site-1"])
    assert grade(s, ["Screen Printing.", "Japanese Bookbinding.", "Silver Ring Making."])[0]
    assert norm_answer("$4.50.") == "$4.50" and norm_answer("Dr. Smith") == "dr smith" and answer_match("$45", "$45.")


# ---- 2. evaluation integrity: a fix must not be punished for working ---------------------------------------------------------------------------------------------------------
def test_patched_arm_is_graded_with_evidence_requirements_derived_from_the_patched_site(tmp_path):
    run, pid, ctx = F.applied_run(tmp_path, T.smooth)
    m, private = freezer.load(run)
    t = next(t for t in m["tasks"] if t["kind"] == "extremum" and private[t["task_id"]]["evidence_paths"][1:])
    base_priv = private[t["task_id"]]
    from agent_readiness.investigate.sitemodel.snapshot import Snapshot
    ok, excluded, priv_new = ev.still_valid(run, Snapshot.load(run.dir / "patched" / pid))
    assert t["task_id"] in priv_new
    new_priv = priv_new[t["task_id"]]
    assert set(new_priv["evidence_paths"]) < set(base_priv["evidence_paths"]) and new_priv["truth"] == base_priv["truth"]       # same question, same answer; fewer pages needed
    var = freezer.variant_for(m["snapshot_sha256"])
    seen = [SuiteObs("/", "home"), SuiteObs("/workshops", "cards now show the fields: " + base_priv["truth"])]
    answer = {"answer": base_priv["truth"]}
    old = core_eval(freezer.instance(t, base_priv, m["snapshot_sha256"]), answer, var, seen)
    new = core_eval(freezer.instance(t, new_priv, m["snapshot_sha256"]), answer, var, seen)
    assert old.passed and not old.evidence_backed            # the bug: a correct answer read off the improved listing was scored "not evidence-backed"
    assert new.passed and new.evidence_backed
    assert freezer.instance(t, new_priv, m["snapshot_sha256"]).spec.limits == freezer.instance(t, base_priv, m["snapshot_sha256"]).spec.limits and \
        freezer.instance(t, new_priv, m["snapshot_sha256"]).spec.objective == t["question"]


def test_an_overall_improvement_is_withdrawn_when_the_held_out_tasks_get_worse():
    parts = {f"t{i}": ("holdout" if i >= 6 else "investigation") for i in range(8)}
    mk = lambda rows: {k: [{"void": False, "passed": p, "evidence_backed": p, "model_requests": r, "primary": "x", "page_views": r}] for k, (p, r) in rows.items()}
    base = mk({f"t{i}": ((i >= 6), 12) for i in range(8)})
    patched = mk({f"t{i}": ((i < 6), 6) for i in range(8)})
    v = design.compare(base, patched, parts, design.RULE)
    assert v["verdict"] == "inconclusive" and "held-out" in v["reason"] and v["holdout_consistent"] is False
    good = mk({f"t{i}": (True, 6) for i in range(8)})
    assert design.compare(mk({f"t{i}": (False, 12) for i in range(8)}), good, parts, design.RULE)["verdict"] == "improvement"
    worse = design.compare(good, base, parts, design.RULE)
    assert worse["verdict"] in ("regression", "inconclusive")
    assert "holdout_guard" in design.RULE


# ---- 3. attribution / investigation integrity --------------------------------------------------------------------------------------------------------------------------------
def test_requests_the_agent_guessed_are_not_website_errors_but_broken_links_are(tmp_path):
    ws = T.ws_for(tmp_path, T.smooth)
    k = next(iter(ws.trials))
    ws.trials[k]["mirror"]["log"].append({"method": "GET", "path": "/pricing-secret-page", "status": 404})        # the agent typed a URL no page links to
    r = V.run_verifier(ws, "error_response_on_path", {}, "Some paths return errors")
    assert r.result == "refuted" and "not counted" in r.detail
    ws.profile["pages"]["/"]["controls"].append({"tag": "a", "role": None, "type": None, "name": "Old page", "name_source": "content", "href": "/gone", "external_href": None, "landmark": "nav", "locator": "x", "native": True})
    ws.trials[k]["mirror"]["log"].append({"method": "GET", "path": "/gone", "status": 404})                    # a page DOES link there: genuinely broken
    r2 = V.run_verifier(ws, "error_response_on_path", {}, "Some link targets return errors")
    assert r2.result == "supported" and r2.support == [f"trial:{k}"]


def test_missing_or_short_trace_data_never_blames_the_site_or_the_interface(tmp_path):
    run = T.frozen(tmp_path, name="trace")
    m, p = freezer.load(run)
    pf = next(t for t in m["tasks"] if t["kind"] == "page_fact")
    page = p[pf["task_id"]]["evidence_paths"][0]
    gone = T.fake_trial(run, pf, p[pf["task_id"]], passed=False, backed=False, visited=["/", page], answer="x", tag="gone")
    short = T.fake_trial(run, pf, p[pf["task_id"]], passed=False, backed=False, visited=["/", page], answer="x", tag="short")
    os.remove(run.dir / run.artifact(f"trials/baseline-{gone}")["trial_dir"] / "observations.json")
    f = run.dir / run.artifact(f"trials/baseline-{short}")["trial_dir"] / "observations.json"
    f.write_text(json.dumps(json.loads(f.read_text())[:1]))
    ok = T.fake_trial(run, pf, p[pf["task_id"]], passed=False, backed=False, visited=["/", page], shown=False, tag="complete")
    att = analyze(run)
    assert att[gone]["primary"] == "undetermined" and att[short]["primary"] == "undetermined" and "incomplete" in att[gone]["why"]
    assert att[ok]["primary"] == "tool_interface"                                                                 # with a complete trace the same shape is still recognised


def test_repeats_of_one_task_are_not_independent_support_and_screenshot_blind_findings_are_not_promoted(tmp_path):
    run = T.frozen(tmp_path, name="rep")
    m, p = freezer.load(run)
    pf = next(t for t in m["tasks"] if t["kind"] == "page_fact" and t["partition"] == "investigation")
    for tag in ("r1", "r2", "r3"):
        T.fake_trial(run, pf, p[pf["task_id"]], passed=False, backed=False, visited=["/", p[pf["task_id"]]["evidence_paths"][0]], shown=False, tag=tag)
    trace_stage(Context(run))
    ws = T.Workspace(run)
    r = V.run_verifier(ws, "observation_missing_dom_content", {}, "x")
    assert r.result == "supported" and len(r.support) == 1                                                         # three trials of ONE task are one piece of support
    h = run.evidence.add_hypothesis(Hypothesis(tier="verifiable", statement="x", claim_kind="observation_missing_dom_content", citations=[next(iter(run.evidence.observations))], provenance=Provenance(mode="scripted", source="t")))
    row = V.verify_and_promote(ws, h)
    assert row["finding_id"] is None and not run.evidence.findings and "not promoted" in row["promotion"]
    assert V.ATTRIBUTION["observation_missing_dom_content"] == "undetermined"                                       # the screenshot is not inspected: never a finding on its own


# ---- 4. experiment execution -------------------------------------------------------------------------------------------------------------------------------------------------------
def test_every_arm_shares_the_baselines_frozen_configuration(tmp_path):
    run, pid, ctx = F.applied_run(tmp_path, T.smooth, name="arm")
    frozen = run.artifact("arm-config")
    assert frozen["repeats"] == 1 and frozen["model"] == "muse-spark-1.3"
    assert ev.post_manifest(ctx)["repeats"] == 1
    with pytest.raises(ValueError, match="differs from the baseline"):
        ev.post_manifest(Context(run, options={"fix": pid, "repeats": 3}))
    with pytest.raises(ValueError, match="differs from the baseline"):
        ev.post_manifest(Context(run, options={"fix": pid, "mock_behavior": "wrong"}))
    from agent_readiness.investigate.run import ArtifactExists
    with pytest.raises(ArtifactExists):
        run.write_artifact("arm-config", {**frozen, "repeats": 2})                                                  # resuming the baseline with other options cannot overwrite it


def test_there_is_one_total_spend_ceiling_not_per_stage_caps_that_disagree(tmp_path, monkeypatch):
    run = F.with_finding(tmp_path, name="cap")
    m = trials_stage.manifest(Context(run, options={"total_cap_usd": 2.05}))
    assert m["ledger_ceiling_usd"] == 2.05 and "stage_cap_usd" not in m and m["retries"] == 0
    run_l, pipe, ctx = flow.build(tmp_path, "capflow", "site-5", mode="live", options={"total_cap_usd": 1.75})
    assert ctx.llm._ceiling == 1.75 and ctx.options["investigator_llm"]._ceiling == 1.75
    from agent_readiness.ledger import Ledger
    led = Ledger(tmp_path / "led", 1.75)
    led.reserve("taskgen:req01", 0.15)
    led.reserve("baseline:req01", 1.45)
    from agent_readiness.ledger import Halt
    with pytest.raises(Halt):
        led.reserve("post:req01", 0.30)                                                                              # one ledger, one ceiling, enforced across all stages


def test_a_truncated_last_event_line_after_a_crash_does_not_make_the_run_unloadable(tmp_path):
    p = tmp_path / "e.jsonl"
    s = EvidenceStore(p)
    prov = Provenance(mode="scripted", source="t")
    s.add_observation(Observation(kind="k", summary="first", provenance=prov))
    with p.open("a") as f:
        f.write('{"schema": "evidence-v1", "ts": "x", "event": "obser')
    r = EvidenceStore(p)
    assert len(r.observations) == 1
    r.add_observation(Observation(kind="k", summary="second", provenance=prov))                                       # appending after repair stays well-formed
    assert len(EvidenceStore(p).observations) == 2
    lines = p.read_text().splitlines()
    p.write_text("\n".join([lines[0][:30]] + lines[1:]) + "\n")
    with pytest.raises(ValueError):
        EvidenceStore(p)                                                                                             # corruption anywhere but the final line is still an error


def test_a_duplicate_hypothesis_or_a_provider_failure_does_not_discard_a_paid_investigation(tmp_path):
    ws = T.ws_for(tmp_path)
    obs = next(iter(ws.run.evidence.observations))
    dup = T.hyp("The price is only on detail pages, not on the listing", [obs], claim_kind="info_absent_on_template", label="price")
    res = investigate(ws, ScriptedClient(T.scripted_model([T.step("finish", hyps=[dup, dup])])), max_calls=3)
    assert res["finished"] and len(res["verification"]) == 1 and any("duplicate" in r["reason"] for r in res["rejected_hypotheses"])

    class Flaky:
        mode, model, n = "live", "m", 0

        def complete(self, req):
            Flaky.n += 1
            if Flaky.n == 3:
                raise RuntimeError("provider down")
            return ScriptedClient(T.scripted_model([T.step("list_trials")])).complete(req)
    ws2 = T.ws_for(tmp_path, name="flaky")
    res2 = investigate(ws2, Flaky(), max_calls=6)
    assert not res2["finished"] and "aborted after 2 model request(s)" in res2["incomplete"] and res2["tool_calls"] == 2 and res2["transcript"]
    out = investigate_stage(Context(ws2.run, options={"investigator_llm": type("L", (), {"mode": "live", "model": "m", "complete": lambda self, r: Flaky().complete(r)})()}))
    assert ws2.run.has_artifact("investigation") and (ws2.run.dir / "private" / "investigator-transcript.json").exists() and out["incomplete"]


# ---- 5. browser / mirror fidelity ---------------------------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("sid", zoo.ids())
def test_every_internal_link_and_asset_of_every_zoo_site_resolves_in_its_snapshot(sid):
    snap = zoo.snapshot(sid)
    broken = []
    for pg, rec in P[sid]["pages"].items():
        for c in rec["controls"]:
            if c["href"] and snap.get(c["href"]) is None:
                broken.append((pg, c["href"]))
        broken += [(pg, i["src"]) for i in rec["images"] if i["src"] and i["src"].startswith("/") and snap.get(i["src"]) is None]
    assert broken == [] or all(q.startswith(("/catalogue?", "/rooms/book")) for _, q in broken), broken


def test_patches_into_table_rows_and_lists_keep_the_markup_valid():
    new, rep = apply_patch(zoo.snapshot("site-2"), {"ops": [{"op": "copy_field_to_listing", "pages": ["/rooms"], "css": "tr", "source_label": "booking limit"}]})
    html = new.get("/rooms").text()
    assert "</td><p>Booking limit" not in html and "<td><p>Booking limit: 2 hours per day</p></td></tr>" in html.replace("\n", "")      # a new cell INSIDE the row, never a bare <p> in <tr>
    n2, _ = apply_patch(zoo.snapshot("site-5"), {"ops": [{"op": "insert_text", "pages": ["/tools"], "css": "ul", "position": "append", "text": "Tools"}]})
    assert "<li><span>Tools</span></li></ul>" in n2.get("/tools").text().replace("\n", "")


@pytest.mark.browser
def test_real_chromium_shows_the_patched_field_inside_the_table_row_and_matches_the_profile_text():
    from playwright.sync_api import sync_playwright
    from agent_readiness.investigate.sitemodel.server import Mirror
    from agent_readiness.scanner.serve import serve_app
    patched, _ = apply_patch(zoo.snapshot("site-2"), {"ops": [{"op": "copy_field_to_listing", "pages": ["/rooms"], "css": "tr", "source_label": "booking limit"}]})

    async def go():
        out = {}
        async with serve_app(Mirror(patched)) as base:
            def work():
                with sync_playwright() as p:
                    b = p.chromium.launch()
                    pg = b.new_page()
                    pg.goto(base + "/rooms")
                    out["rows"] = pg.eval_on_selector_all("tr", "rs => rs.map(r => r.innerText)")
                    out["outside"] = pg.evaluate("[...document.querySelectorAll('main > p, body > p')].map(x => x.innerText)")
                    b.close()
            await asyncio.get_running_loop().run_in_executor(None, work)
        return out
    out = asyncio.run(go())
    assert sum("Booking limit: 2 hours per day" in r for r in out["rows"]) == 6 and not any("Booking limit" in x for x in out["outside"])


@pytest.mark.browser
@pytest.mark.parametrize("sid", zoo.ids())
def test_what_chromium_renders_contains_the_text_the_inspector_believes_is_visible_and_no_request_fails(sid):
    from playwright.sync_api import sync_playwright
    from agent_readiness.investigate.sitemodel.server import Mirror
    from agent_readiness.scanner.serve import serve_app
    snap, mirror = zoo.snapshot(sid), None
    mirror = Mirror(snap)

    async def go():
        bad = []
        async with serve_app(mirror) as base:
            def work():
                with sync_playwright() as p:
                    b = p.chromium.launch()
                    pg = b.new_page()
                    for rec in snap.pages():
                        pg.goto(base + rec.path)
                        shown = norm_answer(pg.inner_text("body")).replace(" ", "")                 # innerText glues adjacent inline elements ("ingredientSearch"); compare without spaces
                        missing = [w for w in set(norm_answer(P[sid]["pages"][rec.path]["text"]).split()) if w not in shown]
                        if missing:
                            bad.append((rec.path, sorted(missing)[:5]))
                    b.close()
            await asyncio.get_running_loop().run_in_executor(None, work)
        return bad
    bad = asyncio.run(go())
    assert bad == [] and not [e for e in mirror.log if e["status"] >= 400]


# ---- 6. model integration -------------------------------------------------------------------------------------------------------------------------------------------------------
def test_prompts_stay_bounded_on_large_sites_and_say_how_many_items_exist():
    from agent_readiness.investigate.taskgen import propose
    prof = json.loads(json.dumps(P["site-1"]))
    g = prof["pages"]["/workshops"]["item_groups"][0]
    g["items"] = [{**g["items"][i % 8], "name": f"Item {i}"} for i in range(500)]
    s = propose.site_summary(prof)
    assert len(s["listings"][0]["items"]) == propose.MAX_ITEMS_SHOWN and s["listings"][0]["items_total"] == 500


def test_unnamed_control_evidence_counts_distinct_controls_not_page_repetitions():
    obs = [o for o in observations(P["site-2"]) if o.kind == "controls_without_accessible_name"]
    d = obs[0].data
    assert all(o.data["distinct_no_name"] <= o.data["count_no_name"] for o in obs) and any(o.data["distinct_no_name"] < o.data["count_no_name"] for o in obs)
    assert "distinct" in obs[0].summary and "occurrences" in obs[0].summary


# ---- 7. property / fuzz: no patch the DSL accepts can break the mirror's safety invariants --------------------------------------------------------------------------------------
def test_fuzz_random_patches_never_escape_the_safety_invariants():
    import re
    from pydantic import ValidationError
    from agent_readiness.investigate.sitemodel.patch import PatchError
    rng = random.Random(2026)
    safe_texts = ["Home", "Search", "Skip to main content", "Menu", "Contact us", "Opening hours", "Frequently asked questions"]
    bad_texts = ["<script>x</script>", "javascript:alert(1)", "onclick=x()", "https://evil.invalid/x", "a" * 300, "", "data:text/html,x", "Pottery Basics and invented claims"]
    good_css = ["a", "h1", "nav a", "main", "p", "h2", "header", "footer", "li", "ul", "td", "dd"]
    bad_css = ["[[", "", "x" * 300, "script", ".nothing-here"]
    good_href, bad_href = ["/", "/faq", "/workshops", "/contact", "/about"], ["/nope", "https://evil.invalid/", "//evil.invalid", "javascript:alert(1)"]
    pick = lambda good, bad, p=0.8: rng.choice(good) if rng.random() < p else rng.choice(bad)
    attempted = accepted = 0
    for _ in range(600):
        sid = rng.choice(zoo.ids())
        snap = zoo.snapshot(sid)
        before = snap.sha256
        ops = []
        for _ in range(1 if rng.random() < 0.6 else rng.randint(2, 4)):
            kind = rng.choice(["set_attribute", "insert_text", "add_link", "copy_field_to_listing"])
            base = {"op": kind, "pages": [pick(["/*", "/", "/*"], ["/nope/*", "/img/*"], 0.9)], "css": pick(good_css, bad_css)}
            if kind == "set_attribute":
                base |= {"attr": pick(["aria-label", "title", "alt", "lang"], ["href", "onclick"], 0.85), "value": pick(safe_texts, bad_texts), "only_unnamed": rng.random() < 0.5}
            elif kind == "insert_text":
                base |= {"text": pick(safe_texts, bad_texts), "position": rng.choice(["before", "after", "append", "prepend"]), "tag": pick(["span", "p", "li", "strong"], ["script"], 0.9)}
            elif kind == "add_link":
                base |= {"href": pick(good_href, bad_href), "text": pick(safe_texts, bad_texts), "position": rng.choice(["before", "after", "append", "prepend"])}
            else:
                base |= {"pages": ["/workshops"], "css": "li.card", "source_label": pick(["price", "date", "seats left"], ["x", ""], 0.8)}
            ops.append(base)
        attempted += 1
        try:
            new, rep = apply_patch(snap, {"ops": ops})
        except (PatchError, ValidationError):
            assert snap.sha256 == before
            continue
        accepted += 1
        assert snap.sha256 == before and new.meta["parent_sha256"] == before
        for r in new.pages():
            t = r.text()
            assert "<script" not in t.replace('type="application/ld+json"', "") and not re.search(r"\son\w+\s*=", t) and "evil.invalid" not in t and "javascript:" not in t.lower()
        assert all(new.get(p).body == r.body for p, r in snap.resources.items() if not r.is_html)
        assert apply_patch(snap, {"ops": ops})[0].sha256 == new.sha256
    assert attempted == 600 and accepted >= 40, accepted


def test_live_trials_share_one_spend_ledger_with_the_single_ceiling_and_per_trial_caps(tmp_path, monkeypatch):
    """Mutation-driven: nothing previously proved that live trials reserve against the run-wide ceiling. Uses a live-mode run dir and a stub trial runner (no model, no browser, no network)."""
    import shutil
    src = F.with_finding(tmp_path, name="src")
    live = type(src).create(tmp_path, "livearm", target="site-1", mode="live", stages=flow.STAGES)
    for d in ("artifacts", "private", "snapshot"):
        shutil.copytree(src.dir / d, live.dir / d, dirs_exist_ok=True)
    seen = []

    async def fake(inst, snap, **kw):
        seen.append(kw["request_gate"])
        return {"trial": {"mode": "live"}, "task": {}, "outcome": {"run_status": "completed", "answer": {"answer": "x"}, "errors": []}, "evaluation": {"passed": False, "evidence_backed": False, "answer_valid": True, "missing_evidence": [], "reasons": [], "details": {}},
                "metrics": {"model_requests": 1, "page_views": 1, "limits": {"max_steps": 10}}, "journey": [], "mirror": {"log": [], "blocked": []}, "artifact_path": str(live.dir / "trial-data" / f"x{len(seen)}")}
    monkeypatch.setattr(trials_stage, "run_trial", fake)
    monkeypatch.setattr(trials_stage, "preflight", lambda cfg, allow: "test-key-not-real")
    (live.dir / "trial-data").mkdir(exist_ok=True)
    for i in range(1, 8):
        (live.dir / "trial-data" / f"x{i}").mkdir(exist_ok=True)
    ctx = Context(live, options={"total_cap_usd": 1.75, "allow_model_calls": True, "run_cap_usd": 0.31, "per_request_cap_usd": 0.02})
    manifest_, insts = freezer.load(live)[0], {i.spec.task_id: i for i in freezer.instances(live)}
    trials_stage.run_arm(ctx, label="baseline", snap=zoo.snapshot("site-1"), tasks=manifest_["tasks"][:3], insts=insts, prefix="armtest", manifest_=trials_stage.manifest(ctx), repeats=1)
    assert len(seen) == 3 and all(g.ledger.ceiling == 1.75 and g.run_cap == 0.31 and g.per_request_cap == 0.02 for g in seen)
    assert len({str(g.ledger.path) for g in seen}) == 1 and len({g.run_id for g in seen}) == 3                      # one ledger file, one gate id per trial


# ---- 8. provider behaviour that scripted tests do not represent -----------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("content,finish", [(None, "stop"), ([{"type": "text", "text": '{"a": 1}'}], "stop"), ('```json\n{"a": 1}\n```', "stop"), ('{"a": 1', "length"), ("I cannot help with that.", "stop"), ('{"a": 1}\n{"a": 2}', "stop")])
def test_odd_provider_responses_fail_cleanly_without_losing_or_inventing_anything(tmp_path, content, finish):
    import httpx
    from pydantic import BaseModel
    from agent_readiness.agent import ModelConfig
    from agent_readiness.investigate.llm import LLMRequest, StructuredOutputError, complete_structured
    from agent_readiness.investigate.llm.meta import MetaClient
    from agent_readiness.ledger import Ledger
    from agent_readiness.spend_gate import RequestGate

    class Out(BaseModel):
        a: int

    def handler(request):
        return httpx.Response(200, json={"choices": [{"finish_reason": finish, "message": {"content": content}}], "usage": {"prompt_tokens": 100, "completion_tokens": 20}})
    led = Ledger(tmp_path / "s", 1.0)
    client = MetaClient(ModelConfig(), "k-test", RequestGate(led, "r", run_cap=0.5, per_request_cap=0.05, max_requests=4), transport=httpx.MockTransport(handler))
    req = LLMRequest(messages=[{"role": "user", "content": "x"}], purpose="p", max_tokens=100, response_schema=Out.model_json_schema())
    with pytest.raises(StructuredOutputError):
        complete_structured(client, req, Out, retries=1)
    kinds = [e["kind"] for e in led.entries()]
    assert kinds == ["reserve", "settle", "reserve", "settle"]                  # both attempts were reserved BEFORE sending and settled from provider usage: no hidden or double spend
    assert led.committed() < 0.01
