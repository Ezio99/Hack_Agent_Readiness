"""Turn accepted candidates into `suite.core.TaskInstance`s that the existing trial runner executes unchanged, plus the public/private split.

PUBLIC (agent-facing and manifest-facing): question, start page, answer schema, limits. PRIVATE (private/criteria.json of the run, never given to the agent or the investigator): truth,
expected answer text, options, evidence pages, how the answer was verified. The agent receives only the question text and the answer schema."""
from __future__ import annotations

from pydantic import BaseModel, create_model

from ..suite.core import EvidenceRequirement, Grade, Limits, TaskInstance, TaskSpec
from . import answers as A
from .costs import step_limit
from .tasks import ANAME, PNAME, Candidate

EVALUATOR_ID, EVALUATOR_VERSION, TEMPLATE_ID, VERSION = "exp2-ironbark", "1", "exp2-ironbark-v1", "1"


def private_record(c: Candidate) -> dict:
    return {"kind": c.kind, "truth": c.truth, "expected_text": c.expected_text, "options": list(c.options), "evidence": list(c.evidence), "pages_needed": c.pages_needed, "family": c.family, "template": c.sub,
            "params": c.params, "verified": "data truth == truth recomputed from the rendered control pages"}


def instance(public: dict, priv: dict, data_version: str) -> TaskInstance:
    kind, options = priv["kind"], tuple(priv["options"])
    names = ANAME if kind in ("accessory", "accessories") else PNAME if kind in ("product", "products") else {}
    model: type[BaseModel] = create_model("IronbarkAnswer", answers=(list[str], ...)) if kind in A.SET_KINDS else create_model("IronbarkAnswer", answer=(str, ...))
    lim = public["limits"]
    spec = TaskSpec(task_id=public["task_id"], template_id=TEMPLATE_ID, version=VERSION, environment_id="ironbark-hire", data_version=data_version, objective=public["question"],
                    answer_schema=public["answer_schema"], start_path=public["start_path"], outcome_type="set" if kind in A.SET_KINDS else "unique",
                    evidence_policy="The pages that hold the figures or facts behind the answer must have been shown to the agent.", limits=Limits(max_steps=lim["max_steps"], timeout_seconds=lim["timeout_seconds"], max_model_requests=lim["max_model_requests"]),
                    evaluator_id=EVALUATOR_ID, evaluator_version=EVALUATOR_VERSION)
    evidence = tuple(EvidenceRequirement("visited_path", p, "page behind the answer") for p in priv["evidence"])

    def grader(inst, ans: BaseModel) -> Grade:
        payload = ans.model_dump()
        ok = A.grade(kind, priv["truth"], payload.get("answers" if kind in A.SET_KINDS else "answer"), options=options, names=names)
        return Grade(ok, ("matches the independently derived answer",) if ok else ("does not match the independently derived answer",), {"kind": kind})
    return TaskInstance(spec=spec, truth={"expected": priv["expected_text"]}, answer_model=model, grader=grader, evidence=evidence)
