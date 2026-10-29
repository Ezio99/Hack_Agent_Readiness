#!/usr/bin/env python3
"""CI coverage check: the shard files written by `--shard-ids-file` must partition a full collection exactly.

usage: ci_check_shards.py LOGIC_DIR BROWSER_DIR   (each holds shard-*.ids from the matrix jobs)
Fails when a selected test is in no shard, in two shards, or a shard file is missing/empty; prints counts. Stdlib + the project's pytest only."""
import subprocess
import sys
from pathlib import Path

SUITES = {"logic": ('not browser', 2), "browser": ("browser", 4)}


def collect(marker: str) -> set[str]:
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "-m", marker], capture_output=True, text=True, check=True).stdout
    return {l for l in out.splitlines() if "::" in l}


def main(dirs: dict[str, str]) -> int:
    bad = 0
    for suite, (marker, count) in SUITES.items():
        full = collect(marker)
        files = sorted(Path(dirs[suite]).glob("shard-*.ids"))
        got = [l for f in files for l in f.read_text().splitlines() if l]
        dup, missing, extra = len(got) - len(set(got)), full - set(got), set(got) - full
        ok = len(files) == count and not dup and not missing and not extra and full
        print(f"{suite}: full={len(full)} shards={len(files)}/{count} selected={len(got)} duplicates={dup} missing={len(missing)} unexpected={len(extra)} -> {'OK' if ok else 'FAIL'}")
        for m in sorted(missing)[:10]:
            print("  missing:", m)
        bad += not ok
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main({"logic": sys.argv[1], "browser": sys.argv[2]}))
