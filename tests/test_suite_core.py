"""Task 010: domain-extensible contract tests (core independence, toy non-electronics domain, evidence semantics) and historical reproducibility pins."""
import hashlib
import re
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from agent_readiness import pilot
from agent_readiness.suite import core

SRC = Path(__file__).resolve().parents[1] / "src" / "agent_readiness"
sha = lambda p: hashlib.sha256((SRC / p).read_bytes()).hexdigest()


def imports_of(path: Path) -> list[str]:
    return re.findall(r"^\s*(?:from|import)\s+([\w.]+)", path.read_text(), re.M)


def test_core_contract_does_not_import_any_environment_or_domain_module():
    for rel in ("suite/core.py", "suite/__init__.py"):
        bad = [m for m in imports_of(SRC / rel) if "environments" in m or "electronics" in m]
        assert not bad, (rel, bad)
    assert "electronics" not in (SRC / "suite" / "core.py").read_text().lower().replace("electronics-v1", "")


def test_oracles_and_graders_do_not_import_the_web_app_query_layer_or_presentation_and_navigators_never_import_the_oracle():
    mods = " ".join(imports_of(SRC / "environments" / "electronics" / "tasks.py"))
    assert not re.search(r"\b(app|query|presentation|scripted)\b", mods), mods
    scripted_mods = " ".join(imports_of(SRC / "environments" / "electronics" / "scripted.py"))
    assert not re.search(r"\b(tasks|oracle)\b", scripted_mods), scripted_mods          # catalogue-only helper import is allowed (public product URLs)


# ---- a toy non-shopping domain proves the contract is not electronics-shaped -------------------------------------------------------

class CityAnswer(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    city: str
    population: int


def toy_instance(truth_city="Aldra", evidence=()):
    spec = core.TaskSpec("toy-capital", "toy-lookup", "0.1", "atlas-v0", "atlas-v0+x", "Report the capital of Veria and its population.", CityAnswer.model_json_schema(), "/", "unique",
                         "The capital page should have been opened.", core.Limits(), "toy-grader", "0.1")
    grade = lambda inst, a: core.Grade(a.city == inst.truth["city"] and a.population == inst.truth["population"], ("ok",) if a.city == inst.truth["city"] else ("wrong city",))
    return core.TaskInstance(spec, {"city": truth_city, "population": 120000}, CityAnswer, grade, tuple(evidence))


VARIANT = core.Variant("atlas-v0", (("map", "plain"),))


def test_contract_is_domain_neutral_and_versioned():
    inst = toy_instance(evidence=[core.EvidenceRequirement("visited_path", "/city/aldra", "capital page")])
    ok = core.evaluate(inst, {"city": "Aldra", "population": 120000}, VARIANT, ["/", "/city/aldra"])
    assert ok.passed and ok.evidence_backed and ok.answer_valid
    assert (ok.task_id, ok.template_id, ok.task_version, ok.environment_id, ok.data_version, ok.variant_id, ok.evaluator_id, ok.evaluator_version, ok.contract_version) == (
        "toy-capital", "toy-lookup", "0.1", "atlas-v0", "atlas-v0+x", "atlas-v0/map-plain", "toy-grader", "0.1", core.CONTRACT_VERSION)


def test_correct_answer_without_required_evidence_is_correct_but_not_evidence_backed():
    inst = toy_instance(evidence=[core.EvidenceRequirement("visited_path", "/city/aldra", "capital page"), core.EvidenceRequirement("visited_prefix", "/atlas", "any atlas page")])
    r = core.evaluate(inst, {"city": "Aldra", "population": 120000}, VARIANT, ["/"])
    assert r.passed and not r.evidence_satisfied and not r.evidence_backed and len(r.missing_evidence) == 2
    unknown = core.evaluate(inst, {"city": "Aldra", "population": 120000}, VARIANT, None)      # no observation record at all
    assert unknown.passed and not unknown.evidence_backed
    wrong = core.evaluate(inst, {"city": "Beta", "population": 1}, VARIANT, ["/", "/city/aldra"])
    assert not wrong.passed and not wrong.evidence_backed


@pytest.mark.parametrize("raw", [None, {}, {"city": "Aldra"}, {"city": "Aldra", "population": "120000"}, {"city": "Aldra", "population": 1, "extra": 1}, "Aldra", [1]])
def test_malformed_answers_fail_with_a_schema_reason_not_an_exception(raw):
    r = core.evaluate(toy_instance(), raw, VARIANT, ["/"])
    assert not r.answer_valid and not r.passed and not r.evidence_backed and "Malformed answer" in r.reasons[0]


def test_public_spec_never_carries_truth_or_concrete_evidence_pages():
    inst = toy_instance(evidence=[core.EvidenceRequirement("visited_path", "/city/aldra", "capital page")])
    public = str(inst.spec.public())
    assert "Aldra" not in public and "/city/aldra" not in public and "truth" not in public and "120000" not in public
    assert set(core.OUTCOME_TYPES) == {"unique", "set", "any_valid"}


# ---- historical reproducibility: Task 005-007 code, data and schedules are byte-pinned -------------------------------------------

def test_legacy_experiment_code_and_templates_are_unchanged():
    pins = {"storefront.py": "bea00155f3a335c2d0f27799dddb7ef364b0ec62930f9abd09480e4eb93034f4", "inventory.py": "1fdcdf8945af13a1748e1009dda7c6cdfa4d1da3bb160f03c9f046e70c05305d",
            "tasks.py": "4f9330ad9ae8421dc7021c2aed137b60c6e1d0546f524a8b8ebd0fd35b32d8ff", "evaluator.py": "47b960c9356bc0b26ca04a459f9f7d25e1bb795145f3b9510450cc8d8cb7c4de",
            "contracts.py": "4f4a9031453b603bb964241d72db9be3a60e136f777e333ff7c521ace511ed88", "oracle.py": "71f98fe89e647bd61e1f9f5fc22e5f6b30df995db318802d59b6fcfbabf0170a",
            "templates/base.html": "b2bdec3b61db1dbf54f5aff1523bfef7fd69e1230b4fb10ee0007b962c2c81cb", "templates/detail.html": "4daa6705a31d71f3fa8854c73b0884c6e204f54caedfdbc73901fcf31bf5a107",
            "templates/listing.html": "18c7e3fbb7c49129a377b31d19b3d77d06140c3f3ed60d18a054661c856f39d5"}
    assert {k: sha(k) for k in pins} == pins


def test_historical_pilot_schedules_and_profiles_are_unchanged():
    assert pilot.schedule_sha256() == "bb660b0c0f1f7a6a1215ea2bfff6beda0a2124a95201f8c93c1214254fa3dcf4"                     # Task 006
    assert pilot.schedule_sha256(experiment="007") == "a2cf749c809e9a905d445d06b87fdb3411fda30978f01c291c74824a656f5eaa"     # Task 007
