"""Deterministic test sharding for CI (no extra dependency).

``--num-shards N --shard-id K`` (K = 1..N) keeps every N-th test of the *already selected* collection (after ``-m`` filtering), taken from the sorted node ids so that
neighbouring tests of one file land on different shards. Each test therefore belongs to exactly one shard by construction. ``--shard-ids-file PATH`` writes the node ids
kept by this run; CI's gate job compares the union of those files with a full collection so a shard can never silently lose a test. Without the options nothing changes."""
from pathlib import Path

import pytest


def pytest_addoption(parser):
    g = parser.getgroup("sharding")
    g.addoption("--num-shards", type=int, default=1, help="split the selected tests into N deterministic shards")
    g.addoption("--shard-id", type=int, default=1, help="which shard (1..N) this run executes")
    g.addoption("--shard-ids-file", default=None, help="write the node ids selected by this run to this file")


def shard_of(index: int, num_shards: int) -> int:
    return index % num_shards + 1


@pytest.hookimpl(trylast=True)       # run after the `-m` marker deselection so shards partition the selected tests
def pytest_collection_modifyitems(config, items):
    n, k = config.getoption("--num-shards"), config.getoption("--shard-id")
    if n < 1 or not 1 <= k <= n:
        raise SystemExit(f"invalid shard: --shard-id {k} --num-shards {n}")
    if n > 1:
        order = {it.nodeid: shard_of(i, n) for i, it in enumerate(sorted(items, key=lambda it: it.nodeid))}
        kept = [it for it in items if order[it.nodeid] == k]
        config.hook.pytest_deselected(items=[it for it in items if order[it.nodeid] != k])
        items[:] = kept
    out = config.getoption("--shard-ids-file")
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text("".join(f"{it.nodeid}\n" for it in sorted(items, key=lambda it: it.nodeid)))

