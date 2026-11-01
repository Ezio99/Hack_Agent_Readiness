"""Second evaluation target (a saved documentation snapshot): registry, per-target configuration, Ironbark identity, and neutral reporting. Offline; browser-free (the end-to-end dev-provider run is
marked `browser` in test_second_target_e2e.py)."""
import json
from types import SimpleNamespace

import pytest

from agent_readiness.agent import ModelConfig
from agent_readiness.investigate.inspect.crawl import Limits, MappingFetcher, crawl
from agent_readiness.investigate.inspect.profile import build_profile, observations
from agent_readiness.investigate.investigator.verifiers import run_verifier
from agent_readiness.investigate.taskgen import gate
from agent_readiness.live import devprovider, mock_investigator, targets, worker
from agent_readiness.live.jobs import JobError, JobManager, LiveSettings
from agent_readiness.live.lexicon import NEUTRAL, RENTAL

NAV = '<nav><a href="/">Home</a></nav>'
SEARCH = ('<search id="searchbox" style="display: none" role="search"><h3 id="searchlabel">Quick search</h3><form action="/search/" method="get">'
          '<input type="text" name="q" aria-labelledby="searchlabel"><input type="submit" value="Go"></form></search>')


def pg(title, body):
    return f"<!doctype html><html><head><title>{title} | Docs</title></head><body>{NAV}{SEARCH}<main>{body}</main></body></html>"


def item(name, default):
    return (f'<dl class="py data"><dt class="sig" id="{name}"><span class="pre">{name}</span><a class="headerlink" href="#{name}">¶</a></dt>'
            f"<dd><p>Controls {name.lower()}.</p><p>Default: <code>{default}</code></p></dd></dl>")


TOC = "".join(f'<li><a href="/{s}/">{s.title()}</a></li>' for s in ("cfg", "intro", "usage", "deploy"))
FILES = {"/": pg("Docs", f"<h1>Docs</h1><ul>{TOC}</ul>"),
         "/cfg/": pg("Configuration", f"<h1>Configuration</h1><ul>{TOC}</ul>" + "".join(item(n, d) for n, d in [("SESSION_NAME", "'session'"), ("URL_SCHEME", "'http'"), ("MAX_MEMORY", "500_000"), ("MAX_PARTS", "1_000"),
                                                                                                                   ("LIFETIME", "31 days"), ("T1", "None"), ("T2", "None"), ("T3", "None"), ("T4", "None"), ("T5", "None"), ("T6", "None")])),
         "/intro/": pg("Intro", f"<h1>Intro</h1><ul>{TOC}</ul>"), "/usage/": pg("Usage", f"<h1>Usage</h1><ul>{TOC}</ul>"), "/deploy/": pg("Deploy", f"<h1>Deploy</h1><ul>{TOC}</ul>")}


@pytest.fixture(scope="module")
def snap():
    return crawl(MappingFetcher(FILES), Limits(max_pages=20))


@pytest.fixture(scope="module")
def prof(snap):
    return json.loads(json.dumps(build_profile(snap)))


# --- registry and per-target configuration ----------------------------------------------------------------------------------------------------------------------------------------
def test_ironbark_keeps_the_rental_vocabulary_and_never_enables_term_value():
    ib = targets.TARGETS["ironbark"]
    assert ib.lexicon() is RENTAL and not ib.term_values and ib.live
    opts = worker.live_options(None, "g goal text here", None, budget=2.0, cfg=ModelConfig(), target=ib)
    default = worker.live_options(None, "g goal text here", None, budget=2.0, cfg=ModelConfig())
    assert opts == default and opts["goal_lexicon"] is RENTAL and "term_values" not in opts, "Ironbark options are exactly the pre-existing ones"


def test_the_documentation_target_uses_a_neutral_vocabulary_and_enables_term_value_for_itself_only():
    f = targets.TARGETS["flask-docs"]
    opts = worker.live_options(None, "find the default of a setting", None, budget=2.0, cfg=ModelConfig(), target=f)
    assert f.lexicon() is NEUTRAL and NEUTRAL == {} and opts["goal_lexicon"] == {} and opts["term_values"] is True
    assert [t.id for t in targets.TARGETS.values() if t.term_values] == ["flask-docs"]
    assert not any(w in json.dumps(NEUTRAL) for w in ("hire", "rent", "deposit", "price"))


def test_a_saved_snapshot_target_is_offered_only_when_its_snapshot_exists_and_there_is_no_url_field(tmp_path, monkeypatch, snap):
    monkeypatch.setenv(targets.SNAPSHOT_ROOT_ENV, str(tmp_path))
    assert "flask-docs" not in [t["id"] for t in targets.listing()] and "flask-docs" not in targets.live_target_ids()
    with pytest.raises(FileNotFoundError, match="capture it with scripts/capture_docs_snapshot.py"):
        targets.TARGETS["flask-docs"].snapshot()
    m = JobManager(tmp_path / "jobs", live=LiveSettings())
    with pytest.raises(JobError) as e:
        m.create("o", "flask-docs", "find the default of a configuration setting", "mock")
    assert e.value.status == 422
    snap.save(tmp_path / "flask-docs")
    assert "flask-docs" in [t["id"] for t in targets.listing()] and "flask-docs" in targets.live_target_ids()
    assert targets.TARGETS["flask-docs"].snapshot().sha256 == snap.sha256
    import inspect
    assert "url" not in " ".join(inspect.signature(JobManager.create).parameters).lower()


# --- the dev-provider stand-in proposes term_value tasks that the unchanged gate accepts --------------------------------------------------------------------------------------------
def test_the_documentation_stand_in_proposes_gate_acceptable_term_value_tasks(prof):
    analysis, tasks = devprovider.follow_goal_docs(prof, 12)
    assert tasks and all(t["criterion"]["kind"] == "term_value" and set(t["criterion"]) == {"kind", "page", "term", "label", "target", "listing", "direction", "conditions"} for t in tasks)
    acc = []
    for t in tasks:
        r = gate.evaluate(gate.Draft(t["question"], t["start_path"], {k: v for k, v in t["criterion"].items() if v is not None}, "model"), prof, acc, first_page="tag")
        if isinstance(r, gate.Accepted):
            acc.append(r)
    truths = {a.criterion["term"]: a.compiled.truth for a in acc}
    assert len(acc) >= 3 and truths["MAX_MEMORY"] == "500_000" and not any(k.startswith("T") and len(k) == 2 for k in truths)


# --- neutral reporting: navigation and hidden controls are never product-listing or accessibility claims -------------------------------------------------------------------------------
def test_a_table_of_contents_is_reported_as_navigation_not_as_a_listing(prof):
    obs = {o.kind: o for o in observations(prof)}
    assert all(l.get("classification") != "catalogue" for l in prof["listings"]) and "navigation_link_groups" in obs
    assert "controls_without_accessible_name" not in obs and "form_fields_without_label" not in obs                 # the hidden, labelled search box is not a defect
    assert "listing_detail_fields" not in obs or all("UNCERTAIN" in o.summary for o in observations(prof) if o.kind == "listing_detail_fields")


def test_no_listing_friction_can_be_derived_from_an_uncertain_or_navigation_group(prof):
    from agent_readiness.investigate.insights import _site_properties
    uncertain = {**prof, "listings": [{"listing": "/", "group": "ul", "items": 4, "detail_template": "/{}", "classification": "uncertain", "classification_basis": "x",
                                       "fields": {"default": {"detail_pages": 3, "in_listing_item": 0, "of": 4, "distinct_pages": 3}}}]}
    assert _site_properties(uncertain, {"default"}) == []
    ws = SimpleNamespace(profile=uncertain)
    r = run_verifier(ws, "info_absent_on_template", {"label": "default"})
    assert r.result == "unverifiable"
    assert mock_investigator._label(uncertain) is None
    catalogue = {**uncertain, "listings": [{**uncertain["listings"][0], "classification": "catalogue"}]}
    assert len(_site_properties(catalogue, {"default"})) == 1 and mock_investigator._label(catalogue) == "default"


# --- end to end against the zero-spend dev provider (real worker process and browser; no model) ---------------------------------------------------------------------------------------
import socket
import threading
import time

import uvicorn

KEY = "dev-key-not-a-real-key-0123456789"
DOC_GOAL = "Can an AI agent find the default values of the configuration settings, such as the URL scheme and the memory and parts limits?"


@pytest.fixture
def dev_provider(tmp_path):
    started = []

    def start():
        prov = devprovider.DevProvider(tmp_path / "live")
        s = socket.create_server(("127.0.0.1", 0))
        srv = uvicorn.Server(uvicorn.Config(devprovider.make_app(prov), log_level="error", lifespan="off"))
        threading.Thread(target=lambda: srv.run(sockets=[s]), daemon=True).start()
        started.append(srv)
        return prov, f"http://127.0.0.1:{s.getsockname()[1]}/v1"
    yield start
    for srv in started:
        srv.should_exit = True


@pytest.mark.browser
def test_a_documentation_target_runs_end_to_end_offline_with_term_value_tasks_and_a_neutral_report(tmp_path, monkeypatch, snap, dev_provider):
    monkeypatch.setenv("META_MODEL_API_KEY", KEY)
    monkeypatch.setenv(targets.SNAPSHOT_ROOT_ENV, str(tmp_path / "snaps"))
    snap.save(tmp_path / "snaps" / "flask-docs")
    prov, url = dev_provider()
    m = JobManager(tmp_path / "live", live=LiveSettings(enabled=True, cap_usd=2.0, global_budget_usd=10.0, base_url=url, allow_dev_provider=True))
    j = m.create("o", "flask-docs", DOC_GOAL, "live", 2.0)
    t0, v = time.time(), None
    while time.time() - t0 < 420:
        v = m.get(j["id"], "o")
        if v["state"] not in ("queued", "running"):
            break
        time.sleep(2)
    assert v["state"] == "completed", (v["error"], v["stop"])
    d = m.export(j["id"], "o")
    assert d["notices"][0].startswith("DEV PROVIDER") and len(d["tasks"]) >= 3 and all(t["kind"] == "term_value" and t["source"] == "model" for t in d["tasks"])
    assert len(v["trials"]) >= 3 and "term_value" in json.dumps(prov.taskgen_prompts[0])
    ins = d["insights"]
    assert ins["site_properties"] == [] and "listing" not in ins["summary"].lower() and not ins["suggestions"]
    assert not any(c.get("claim_kind") == "info_absent_on_template" for c in ins["possible_causes"])
    assert all("SUGGESTED" in s["label"] or "POSSIBLE" in s["label"] for s in ins["suggestions"] + ins["possible_causes"])
