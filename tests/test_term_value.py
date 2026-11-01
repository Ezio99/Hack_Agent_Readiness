"""`term_value`: the fifth criterion kind (documentation-style lookups). Offline: a Sphinx-style fixture, an independent generic fixture (headings / table / policy page), and the Ironbark control
snapshot, whose requests and schemas must stay byte-identical unless a run opts in."""
import json

import pytest

from agent_readiness.exp2 import snapshot as ironbark_snapshot
from agent_readiness.investigate.inspect.crawl import Limits, MappingFetcher, crawl
from agent_readiness.investigate.inspect.profile import build_profile
from agent_readiness.investigate.llm import ScriptedClient, request_sha256
from agent_readiness.investigate.taskgen import gate, goal, propose, termvalue
from agent_readiness.live.targets import SAMPLE_CONTEXT
from agent_readiness.investigate.taskgen.criteria import CriterionError, compile_criterion, grade

NAV = '<nav><a href="/">Home</a> <a href="/cfg/">Config</a> <a href="/cli">CLI</a> <a href="/plans">Plans</a> <a href="/policy">Policy</a> <a href="/other">Other</a></nav>'


def pg(title, body):
    return f"<!doctype html><html><head><title>{title} | Docs</title></head><body>{NAV}<main>{body}</main></body></html>"


def sphinx_item(name, default, prose=""):
    return (f'<dl class="py data"><dt class="sig" id="{name}"><span class="pre">{name}</span><a class="headerlink" href="#{name}">¶</a></dt>'
            f"<dd><p>{prose or 'Controls ' + name.lower() + '.'}</p><p>Default: <code>{default}</code></p></dd></dl>")


SPHINX_PAGE = pg("Configuration Handling", "<h1>Configuration</h1>" + "".join(sphinx_item(n, d) for n, d in [
    ("SESSION_COOKIE_NAME", "'session'"), ("PREFERRED_URL_SCHEME", "'http'"), ("MAX_FORM_MEMORY_SIZE", "500_000"), ("MAX_FORM_PARTS", "1_000"), ("PERMANENT_LIFETIME", "31 days"),
    ("TRAP_ONE", "None"), ("TRAP_TWO", "None"), ("TRAP_THREE", "None"), ("TRAP_FOUR", "None"), ("TRAP_FIVE", "None"), ("TRAP_SIX", "None"), ("FLAG_DEBUG", "False"),
    ("LONG_ONE", "Use the configured value, which may be overridden in several ways described elsewhere in the manual.")]) + sphinx_item("MAX_FORM_PARTS", "2_000"))

OPT = lambda n, t, d: f"<h3>{n}</h3><p>Type: {t}</p><p>Default: {d}</p>"
GENERIC = {
    "/": pg("Zephyr", "<h1>Zephyr</h1><p>Reference.</p>"),
    "/cfg/": SPHINX_PAGE,
    "/cli": pg("Command line options", "<h1>Options</h1>" + OPT("--timeout", "integer", "30 seconds") + OPT("--retries", "integer", "5") + OPT("--region", "string", "eu-west-1")
               + OPT("--format", "string", "json") + OPT("--quiet", "string", "None") + OPT("--trace", "string", "None") + OPT("--proxy", "string", "None") + OPT("--cache", "string", "None")),
    "/plans": pg("Plans", "<h1>Plans</h1><table><tr><th>Plan</th><th>Projects</th><th>Support</th></tr><tr><td>Free</td><td>3</td><td>Community</td></tr>"
                 "<tr><td>Pro</td><td>20</td><td>Email</td></tr><tr><td>Team</td><td>100</td><td>Chat</td></tr></table>"),
    "/policy": pg("Policy", "<h1>Policy</h1><h2>Cancellations</h2><p>Notice period: 7 days</p><h2>Changes</h2><p>Notice period: 30 days</p><h2>Termination</h2><p>Notice period: 14 days</p>"),
    "/other": pg("Other", "<h1>Other</h1><h3>--timeout</h3><p>Type: integer</p><p>Default: 45 seconds</p>"),
}


@pytest.fixture(scope="module")
def prof():
    return json.loads(json.dumps(build_profile(crawl(MappingFetcher(GENERIC), Limits(max_pages=20)))))          # as a stored profile artifact: JSON round-trip


def tv(page, term, label):
    return {"kind": "term_value", "page": page, "term": term, "label": label}


# --- derivation and rejection ---------------------------------------------------------------------------------------------------------------------------------------------------
def test_answers_are_derived_from_the_snapshot_never_supplied(prof):
    assert compile_criterion(tv("/cfg/", "PREFERRED_URL_SCHEME", "default"), prof).truth == "'http'"
    assert compile_criterion(tv("/cfg/", "MAX_FORM_MEMORY_SIZE", "default"), prof).truth == "500_000"
    assert compile_criterion(tv("/cli", "--region", "default"), prof).truth == "eu-west-1"
    assert compile_criterion(tv("/plans", "Pro", "projects"), prof).truth == "20"
    assert compile_criterion(tv("/policy", "Changes", "notice period"), prof).truth == "30 days"


@pytest.mark.parametrize("crit,reason", [
    (tv("/cfg/", "MAX_FORM_PARTS", "default"), "more than once"),                      # the term is repeated with a different value
    (tv("/cfg/", "LONG_ONE", "default"), "long"),
    (tv("/cfg/", "FLAG_DEBUG", "default"), "boolean"),
    (tv("/cli", "--quiet", "default"), "guessable"),                                   # None answers half of this page's options
    (tv("/cli", "--timeout", "default"), "inconsistent"),                              # 30 seconds here, 45 seconds on /other
    (tv("/cli", "--retries", "type"), "closed vocabulary"),
    (tv("/policy", "Changes", "refund window"), "no 'refund window'"),
    (tv("/cli", "--nope", "default"), "no term"),
    (tv("/missing", "x", "default"), "not part of the snapshot")])
def test_ambiguous_long_boolean_guessable_inconsistent_and_unsupported_candidates_are_rejected(prof, crit, reason):
    with pytest.raises(CriterionError) as e:
        compile_criterion(crit, prof)
    assert reason.split()[0] in str(e.value) or reason in str(e.value)
    assert "500_000" not in str(e.value) and "eu-west-1" not in str(e.value)           # reasons never reveal answers


def test_permalink_is_not_part_of_the_term_and_grading_is_the_existing_short_value_rule(prof):
    c = compile_criterion(tv("/cfg/", "SESSION_COOKIE_NAME", "default"), prof)
    assert c.kind == "term_value" and c.evidence_paths == ["/cfg/"] and c.style == "string" and "¶" not in c.detail["term"]
    c = compile_criterion(tv("/cli", "--region", "default"), prof)
    assert grade(c, "eu-west-1")[0] and grade(c, "It is eu-west-1.")[0]
    assert not grade(c, "eu-west-1 or json")[0] and not grade(c, "json")[0] and not grade(c, "(not sure)")[0]


# --- the real gate ------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def run_gate(drafts, prof):
    acc, rej = [], []
    for d in drafts:
        r = gate.evaluate(d, prof, acc, first_page="tag")
        (acc if isinstance(r, gate.Accepted) else rej).append(r)
    return acc, rej


def test_generated_drafts_pass_the_unchanged_gate_on_the_sphinx_style_and_the_independent_fixtures(prof):
    acc, rej = run_gate(termvalue.drafts(prof, limit=30), prof)
    pages = {a.criterion["page"] for a in acc}
    assert len(acc) >= 10 and {"/cfg/", "/cli", "/plans", "/policy"} <= pages
    cfg = [a for a in acc if a.criterion["page"] == "/cfg/"]
    assert len(cfg) >= 3 and all(a.compiled.truth not in a.draft.question for a in cfg)
    truths = {a.criterion["term"]: a.compiled.truth for a in cfg}
    assert truths["MAX_FORM_MEMORY_SIZE"] == "500_000" and "TRAP_ONE" not in truths and "MAX_FORM_PARTS" not in truths and "LONG_ONE" not in truths


def test_the_gate_requires_the_question_to_name_the_term_and_the_field(prof):
    c = tv("/cfg/", "PREFERRED_URL_SCHEME", "default")
    ok = gate.evaluate(gate.Draft("In Configuration Handling, what is the default for PREFERRED_URL_SCHEME?", "/", c, "owner"), prof, [], first_page="tag")
    no_term = gate.evaluate(gate.Draft("In Configuration Handling, what is the default scheme?", "/", c, "owner"), prof, [], first_page="tag")
    no_field = gate.evaluate(gate.Draft("In Configuration Handling, what does PREFERRED_URL_SCHEME mean for urls?", "/", c, "owner"), prof, [], first_page="tag")
    assert isinstance(ok, gate.Accepted)
    assert isinstance(no_term, gate.Rejected) and "term" in no_term.reason and isinstance(no_field, gate.Rejected) and "field" in no_field.reason


def test_answer_on_the_start_page_still_needs_navigation(prof):
    r = gate.evaluate(gate.Draft("On the Configuration Handling page, what is the default listed for PREFERRED_URL_SCHEME?", "/cfg/", tv("/cfg/", "PREFERRED_URL_SCHEME", "default"), "owner"), prof, [], first_page="tag")
    assert isinstance(r, gate.Rejected)                                                 # existing rule: no navigation needed


# --- the proposer: opt-in only ------------------------------------------------------------------------------------------------------------------------------------------------
def test_default_requests_do_not_mention_term_value_and_the_default_schema_refuses_it(prof):
    for reqs in (propose.batch_requests(prof), propose.batch_requests(prof, "goal text", True)):
        assert all("term_value" not in json.dumps(r.messages) + json.dumps(r.response_schema) for r in reqs)
    bad = {"tasks": [{"question": "q", "start_path": "/", "criterion": {"kind": "term_value", "page": "/cfg/", "label": "default", "target": None, "listing": None, "direction": None, "conditions": None}, "rationale": "r"}]}
    with pytest.raises(Exception):
        propose.TaskProposals.model_validate(bad)


def test_opt_in_requests_carry_the_kind_the_rule_and_a_bounded_candidate_list_without_values(prof):
    for reqs in (propose.batch_requests(prof, term_values=True), propose.batch_requests(prof, "goal text", True, None, True)):
        text = reqs[0].messages[1]["content"]
        assert "term_value{page,term,label}" in text and "term_value" in json.dumps(reqs[0].response_schema) and '"term_values"' in text
        summary = json.loads(text.split("Website summary (JSON):\n", 1)[1].split("\n\nRules:", 1)[0])
        tvs = summary["term_values"]
        assert 3 <= len(tvs) <= propose.MAX_TERM_VALUES and all(set(x) == {"page", "term", "label"} for x in tvs)
        assert "'http'" not in json.dumps(tvs) and all(compile_criterion({"kind": "term_value", **x}, prof) for x in tvs)       # every listed candidate compiles; none carries its value
        assert all(r.purpose in ("taskgen", "taskgen-goal") for r in reqs)


def test_a_scripted_model_proposal_with_term_value_is_parsed_and_passes_the_gate(prof):
    task = {"question": "In Configuration Handling, what is the default for MAX_FORM_PARTS_X?", "start_path": "/", "rationale": "r", "criterion": {"kind": "term_value", "page": "/cfg/", "term": "MAX_FORM_MEMORY_SIZE", "label": "default",
            "target": None, "listing": None, "direction": None, "conditions": None}}
    task["question"] = "In Configuration Handling, what is the default for MAX_FORM_MEMORY_SIZE?"
    req = propose.build_request(prof, 1, term_values=True)
    drafts, meta = propose.propose(ScriptedClient([json.dumps({"tasks": [task]})]), prof, request=req, retries=0)
    assert drafts[0].criterion == tv("/cfg/", "MAX_FORM_MEMORY_SIZE", "default")
    assert isinstance(gate.evaluate(drafts[0], prof, [], first_page="tag"), gate.Accepted)
    broken = dict(task, criterion=dict(task["criterion"], term=None))
    drafts, _ = propose.propose(ScriptedClient([json.dumps({"tasks": [broken]})]), prof, request=req, retries=0)
    assert isinstance(gate.evaluate(drafts[0], prof, [], first_page="tag"), gate.Rejected)               # malformed: recorded as a rejection, never a crash


def test_goal_grounding_reads_the_label_of_a_term_value_task():
    assert goal._labels_of(tv("/cfg/", "X", "default")) == ["default"]


# --- Ironbark stays byte-identical -------------------------------------------------------------------------------------------------------------------------------------------------
IRONBARK_FOCUS = "Can an AI agent compare the refundable deposit, minimum hire period, and delivery requirements across the hire machines?"
# Request hashes recorded from the commit BEFORE term_value existed (521532a): a change means an Ironbark taskgen approval hash changed.
FROZEN = {"plain": ["67421d83839a44c66c0fe24493fefde360c7026133afd1448ac67ac5af0193b1", "e8b30e50ab346305e39f9be92f5b5cada570b2b9265f94c49afd20b396e73569", "2bcb619e650103b2596b41f00fd08af9e2d12ee0d1c68f2762659251fcd33169"],
          "bound": ["e4d3e3fcf8ffce8b8ea7fcd15ed346efe7276417afa4156a0a770e674471ed6e", "4fcb202f9b34c5e2aa6a4a4cc24a9775e4e4ceb01c1462c34f730a125aa2541b", "e5d791982909f41f70c6e7bfa9306ae8992879fe86fcc59edf241ea01649f4b6"]}


@pytest.fixture(scope="module")
def ib():
    return json.loads(json.dumps(build_profile(ironbark_snapshot.snapshot("control"))))


def test_ironbark_requests_schemas_and_rules_are_byte_identical_by_default(ib):
    plain, bound = propose.batch_requests(ib), propose.batch_requests(ib, IRONBARK_FOCUS, True)
    assert plain == propose.batch_requests(ib, None, False, None, False) and bound == propose.batch_requests(ib, IRONBARK_FOCUS, True, None, False)
    assert all("term_value" not in json.dumps(r.messages) + json.dumps(r.response_schema) for r in plain + bound)
    assert [request_sha256(r) for r in plain] == FROZEN["plain"]
    ctx = propose.batch_requests(ib, IRONBARK_FOCUS, True, SAMPLE_CONTEXT["ironbark"])
    assert [request_sha256(r) for r in ctx] == FROZEN["bound"]
    assert "term_value" not in propose.RULES and propose.CriterionDraft.model_json_schema()["properties"]["kind"]["enum"] == ["page_fact", "reach_page", "item_set", "extremum"]


def test_enabling_the_option_changes_ironbark_requests_so_it_cannot_happen_silently(ib):
    assert [request_sha256(r) for r in propose.batch_requests(ib)] != [request_sha256(r) for r in propose.batch_requests(ib, term_values=True)]
