"""Reproducible block-randomized schedule with matrix validation. Same (stage, seed) -> identical schedule and hash."""
from __future__ import annotations

import random

from ..suite import core
from . import design

SCHEDULE_VERSION = "task012-schedule-v1"
DEFAULT_SEEDS = {1: 20261028, 2: 20261029}      # recorded; any change changes the hash and needs re-approval


def build_schedule(stage: int, seed: int | None = None) -> dict:
    cfg = design.STAGES[stage]
    seed = DEFAULT_SEEDS[stage] if seed is None else seed
    rng = random.Random(f"{design.EXPERIMENT_ID}/stage{stage}/{seed}")
    remaining = {(t, v): n for t, vs in cfg["cells"].items() for v, n in vs.items()}
    blocks = []
    # Stage 1 is a paired design: per block each task appears once; the leading variant alternates between blocks and is balanced across tasks.
    lead = {}
    if stage == 1:
        tasks = sorted(cfg["cells"])
        flips = [0, 0, 1, 1]
        rng.shuffle(flips)
        lead = dict(zip(tasks, flips))
    for b in range(cfg["blocks"]):
        block = []
        for (t, v), n in sorted(remaining.items()):
            if n <= 0:
                continue
            if stage == 1:
                order = ["V0", "V3"] if lead[t] == 0 else ["V3", "V0"]
                if v != order[b]:
                    continue
            block.append((t, v))
        for key in block:
            remaining[key] -= 1
        rng.shuffle(block)
        blocks.append(block)
    assert all(n == 0 for n in remaining.values()), remaining
    entries, i = [], 0
    for b, block in enumerate(blocks, 1):
        for t, v in block:
            i += 1
            entries.append({"index": i, "run_id": f"s{stage}-{i:02d}-{t.lower()}-{v.lower()}", "stage": stage, "block": b, "task_code": t, "task_id": design.PRIMARY_TASKS[t],
                            "variant_code": v, "variant_id": design.variant_id(v)})
    sched = {"schedule_version": SCHEDULE_VERSION, "experiment_id": design.EXPERIMENT_ID, "stage": stage, "seed": seed, "purpose": cfg["purpose"], "blocks": cfg["blocks"], "entries": entries}
    sched["schedule_hash"] = core.canonical_hash({k: v for k, v in sched.items()})
    validate(sched)
    return sched


def validate(sched: dict) -> None:
    """Exact matrix check: cell counts equal the pre-registered design; ids unique; each block has no repeated (task, variant) beyond the design."""
    cfg = design.STAGES[sched["stage"]]
    want = {(t, v): n for t, vs in cfg["cells"].items() for v, n in vs.items()}
    got: dict = {}
    for e in sched["entries"]:
        key = (e["task_code"], e["variant_code"])
        got[key] = got.get(key, 0) + 1
        if e["task_id"] != design.PRIMARY_TASKS[e["task_code"]] or e["variant_id"] != design.variant_id(e["variant_code"]):
            raise ValueError(f"entry {e['run_id']} does not match the design")
    if got != want:
        raise ValueError(f"schedule cells {got} differ from the pre-registered matrix {want}")
    if len({e["run_id"] for e in sched["entries"]}) != len(sched["entries"]):
        raise ValueError("duplicate run ids")
    body = {k: v for k, v in sched.items() if k != "schedule_hash"}
    if sched.get("schedule_hash") and sched["schedule_hash"] != core.canonical_hash(body):
        raise ValueError("schedule hash does not match its contents")
