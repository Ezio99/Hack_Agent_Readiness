"""Freeze accepted tasks into an immutable manifest + private criteria, partition them, and turn them back into independent `suite.core.TaskInstance`s.

PUBLIC  `tasks-manifest` artifact (write-once, hashed): question, start page, kind, partition, limits, answer schema, snapshot hash, criteria hash. No truth, no criterion locators.
PRIVATE `private/criteria.json` (mode 0600, write-once): criterion spec, expected answer, evidence requirements. Never read by prompt builders or investigator tools.
Partition: `investigation` tasks may be shown to the investigator (with their traces); `holdout` tasks are never shown to it and serve only the before/after evaluation."""
from __future__ import annotations

import hashlib
from dataclasses import asdict

from pydantic import BaseModel, create_model

from ...suite.core import EvidenceRequirement, Grade, Limits, TaskInstance, TaskSpec, Variant, canonical_hash
from ..run import InvestigationRun
from .criteria import Compiled, grade
from .gate import Accepted

SCHEMA = "tasks-manifest-v1"
EVALUATOR_ID, EVALUATOR_VERSION, TEMPLATE_ID, VERSION = "generated-criteria", "1", "generated-v1", "1"
HOLDOUT_FRACTION = 1 / 3


def task_id(fingerprint: str) -> str:
    return "gen-" + fingerprint[:10]


def partition(accepted: list[Accepted], seed: int = 0, fraction: float = HOLDOUT_FRACTION) -> dict[str, str]:
    """Deterministic, kind-spread assignment: tasks are ordered by a seeded hash and holdout slots are dealt round-robin over kinds. With >= 3 tasks there is at least one holdout and one investigation task."""
    n = len(accepted)
    k = 0 if n < 3 else max(1, round(n * fraction))
    k = min(k, n - 1) if n else 0
    by_kind: dict[str, list[Accepted]] = {}
    for a in sorted(accepted, key=lambda a: hashlib.sha256(f"{seed}:{a.fingerprint}".encode()).hexdigest()):
        by_kind.setdefault(a.compiled.kind, []).append(a)
    hold: list[str] = []
    while len(hold) < k and any(by_kind.values()):
        for kind in sorted(by_kind):
            if by_kind[kind] and len(hold) < k:
                hold.append(by_kind[kind].pop(0).fingerprint)
    return {a.fingerprint: ("holdout" if a.fingerprint in hold else "investigation") for a in accepted}


def _limits(hops: dict[str, int]) -> Limits:
    steps = min(16, 8 + 3 * max(hops.values(), default=1))
    return Limits(max_steps=steps, timeout_seconds=240, max_model_requests=steps)


def _answer_schema(style: str) -> dict:
    return ({"type": "object", "properties": {"answers": {"type": "array", "items": {"type": "string"}, "description": "every matching name, one string each"}}, "required": ["answers"]}
            if style == "set" else {"type": "object", "properties": {"answer": {"type": "string", "description": "the answer, stated briefly"}}, "required": ["answer"]})


def build(accepted: list[Accepted], *, snapshot_sha256: str, generator: dict, agent_profile: str, seed: int = 0, rejections: list[dict] | None = None) -> tuple[dict, dict]:
    part = partition(accepted, seed)
    tasks, private = [], {}
    for a in accepted:
        tid = task_id(a.fingerprint)
        lim = _limits(a.hops)
        tasks.append({"task_id": tid, "question": a.draft.question, "start_path": a.draft.start_path, "kind": a.compiled.kind, "source": a.draft.source, "partition": part[a.fingerprint],
                      "outcome_type": "set" if a.compiled.style == "set" else "unique", "answer_schema": _answer_schema(a.compiled.style), "limits": asdict(lim), "criterion_sha256": canonical_hash(a.criterion)})
        private[tid] = {"criterion": a.criterion, "kind": a.compiled.kind, "style": a.compiled.style, "truth": a.compiled.truth, "evidence_paths": a.compiled.evidence_paths,
                        "evidence_texts": [list(t) for t in a.compiled.evidence_texts], "detail": a.compiled.detail, "min_hops": max(a.hops.values(), default=0)}
    tasks.sort(key=lambda t: t["task_id"])
    manifest = {"schema": SCHEMA, "snapshot_sha256": snapshot_sha256, "agent_profile": agent_profile, "generator": generator, "seed": seed, "tasks": tasks,
                "counts": {"investigation": sum(t["partition"] == "investigation" for t in tasks), "holdout": sum(t["partition"] == "holdout" for t in tasks)},
                "rejections": rejections or [], "criteria_sha256": canonical_hash(private)}
    return manifest, private


def freeze(run: InvestigationRun, accepted: list[Accepted], **kw) -> dict:
    manifest, private = build(accepted, **kw)
    run.write_private("criteria", private)
    run.write_artifact("tasks-manifest", manifest)
    return manifest


def load(run: InvestigationRun) -> tuple[dict, dict]:
    """Manifest + private criteria, verified against each other and the frozen snapshot (any edit after freezing is detected)."""
    from ..inspect.stage import load_snapshot
    manifest, private = run.artifact("tasks-manifest"), run.private("criteria")
    if canonical_hash(private) != manifest["criteria_sha256"]:
        raise ValueError("private criteria no longer match the frozen manifest (edited after freezing)")
    if load_snapshot(run).sha256 != manifest["snapshot_sha256"]:
        raise ValueError("the snapshot is not the one the tasks were frozen against")
    return manifest, private


def variant_for(snapshot_sha256: str) -> Variant:
    return Variant("generated-site", (("snapshot", snapshot_sha256[:12]),))


def instance(entry: dict, priv: dict, snapshot_sha256: str) -> TaskInstance:
    comp = Compiled(priv["kind"], priv["style"], priv["truth"], priv["evidence_paths"], [tuple(t) for t in priv["evidence_texts"]], detail=priv["detail"])
    model: type[BaseModel] = (create_model("GeneratedAnswer", answers=(list[str], ...)) if comp.style == "set" else create_model("GeneratedAnswer", answer=(str, ...)))
    spec = TaskSpec(task_id=entry["task_id"], template_id=TEMPLATE_ID, version=VERSION, environment_id="generated-site", data_version=snapshot_sha256[:12], objective=entry["question"],
                    answer_schema=entry["answer_schema"], start_path=entry["start_path"], outcome_type=entry["outcome_type"], evidence_policy="The pages that contain the answer must have been shown to the agent.",
                    limits=Limits(**entry["limits"]), evaluator_id=EVALUATOR_ID, evaluator_version=EVALUATOR_VERSION)
    evidence = tuple(EvidenceRequirement("visited_path", p, "page that holds or leads to the answer") for p in comp.evidence_paths) \
        + tuple(EvidenceRequirement("observed_text", t, "the answer text must have been shown", path=p) for p, t in comp.evidence_texts)

    def grader(inst, ans: BaseModel) -> Grade:
        ok, details = grade(comp, ans.model_dump().get("answers" if comp.style == "set" else "answer"))
        return Grade(ok, ("matches the independently derived answer",) if ok else ("does not match the independently derived answer",), details)
    return TaskInstance(spec=spec, truth={"expected": comp.truth}, answer_model=model, grader=grader, evidence=evidence)


def instances(run: InvestigationRun, partition_name: str | None = None) -> list[TaskInstance]:
    manifest, private = load(run)
    return [instance(t, private[t["task_id"]], manifest["snapshot_sha256"]) for t in manifest["tasks"] if partition_name in (None, t["partition"])]


def investigator_view(run: InvestigationRun) -> list[dict]:
    """What an investigator may see about tasks: PUBLIC specs of investigation-partition tasks only. Holdout tasks and all criteria/truth are excluded."""
    manifest = run.artifact("tasks-manifest")
    return [{k: t[k] for k in ("task_id", "question", "start_path", "kind", "limits")} for t in manifest["tasks"] if t["partition"] == "investigation"]
