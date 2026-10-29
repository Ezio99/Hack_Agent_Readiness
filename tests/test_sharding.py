"""The CI shard partition: every selected test belongs to exactly one shard."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _ids(tmp_path, n, k):
    out = tmp_path / f"s{k}.txt"
    subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "-m", "not browser and not slow", "tests/test_markers.py", "tests/test_compat_parser.py", "tests/test_probe.py",
                    "--num-shards", str(n), "--shard-id", str(k), "--shard-ids-file", str(out)], cwd=ROOT, check=True, capture_output=True)
    return out.read_text().splitlines()


def test_shards_partition_the_selection(tmp_path):
    full = _ids(tmp_path, 1, 1)
    parts = [_ids(tmp_path, 3, k) for k in (1, 2, 3)]
    assert len(full) > 6
    assert sorted(sum(parts, [])) == sorted(full)                  # union is complete
    assert len({i for p in parts for i in p}) == len(full)         # and disjoint
    assert all(p for p in parts)


def test_invalid_shard_is_rejected(tmp_path):
    r = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "--num-shards", "2", "--shard-id", "3", "tests/test_markers.py"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode != 0
