"""Sanitized, versioned lifecycle datasets (M8): the preloaded M7 experiment, derived from the REAL git-ignored run artefacts.

A dataset is exactly what the product's API would serve for that evaluation: the projection (`projection.project`, the same function the API uses
for evaluations launched in the product), the per-trial public timelines, the Stage A views (generation run, suite review packets with their
approval and freeze state) and the recorded browser screenshots (re-encoded to WebP; pixels are not edited). Nothing is invented: every document is
recomputed from the source by `build`, and `validate --source` recomputes it again and requires byte-equal documents and the same screenshot
source hashes.

    python -m agent_readiness.lifecycle.dataset build --store STORE --run RUN_DIR [--run ...] --generation GEN_DIR --out DIR --id ID --version N
    python -m agent_readiness.lifecycle.dataset validate DIR [--store STORE --run RUN_DIR ... --generation GEN_DIR]

DATASET.json lists every file with its SHA-256, the source identities (run ids, manifest, frozen suite, RunResult evidence hashes, the SHA-256 of
every source trial record and screenshot) and the builder's code hashes. Withheld by construction (and checked by `audit`): expected answers and
other oracle data, criteria, required evidence paths, authorisation records, ledgers, credentials, raw model inputs and responses, local paths."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
from pathlib import Path

from . import audit, projection as P, stage_a as SA

SCHEMA = "lifecycle-dataset-v1"
SCREENSHOT = re.compile(r"step-(\d{3})\.png")
WEBP_WIDTH, WEBP_QUALITY = 1024, 72
CODE = ("projection.py", "audit.py", "dataset.py", "stage_a.py", "../grading/contrast.py", "../grading/evidence_ranked.py", "../hosted/telemetry.py",
        "../diagnostics/hypotheses.py", "../diagnostics/behavioral.py", "../diagnostics/run.py")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _dump(obj) -> bytes:
    return (json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode()


def code_hashes() -> dict:
    here = Path(__file__).parent
    return {c.split("/")[-1]: _sha((here / c).resolve().read_bytes()) for c in CODE}


def _webp(png: bytes) -> bytes:
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGB")
    if im.width > WEBP_WIDTH:
        im = im.resize((WEBP_WIDTH, round(im.height * WEBP_WIDTH / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=WEBP_QUALITY, method=6)
    return buf.getvalue()


def documents(store_root: Path, run_dirs: list[Path], generation_dir: Path | None, *, evaluation_id: str, title: str | None = None,
              context: dict | None = None) -> tuple[dict[str, dict], dict[str, Path], dict]:
    """The dataset's JSON documents (by relative path), the screenshot sources (relative webp path -> source png) and the source record."""
    from ..evalruns import runner as RN
    from ..suites.store import WriteOnceStore
    store = WriteOnceStore(Path(store_root))
    runs = P.load_runs([Path(d) for d in run_dirs])
    ev = P.project(store, runs, evaluation_id=evaluation_id, title=title, context=context)
    answers = RN._answers(store, ev["frozen_suite"]["sha256"])
    docs: dict[str, dict] = {"evaluation.json": ev}
    shots: dict[str, Path] = {}
    trials_src = {}
    for cond, run in runs.items():
        for path in sorted((run.dir / "artifacts" / "trials").glob("*.json")):
            name = path.stem
            trials_src[f"{run.state['id']}/{name}"] = _sha(path.read_bytes())
            tl = P.trial_timeline(run, name)
            d = P.trial_dir(run, name)
            for s in tl["steps"]:
                if s.get("screenshot"):
                    s["screenshot"] = s["screenshot"].replace(".png", ".webp")
            tl["screenshots"] = [x.replace(".png", ".webp") for x in tl["screenshots"]]
            for x in tl["screenshots"]:
                shots[f"screenshots/{name}/{x}"] = d / x.replace(".webp", ".png")
            docs[f"trials/{name}.json"] = tl
    frozen = store.get("frozen_suite", ev["frozen_suite"]["sha256"])
    suite = store.get("suite", frozen.suite_sha256)
    suite_shas = [frozen.suite_sha256] + [i.sha256 for i in suite.provenance.inputs if i.kind == "suite"]
    for sha in suite_shas:
        if store.kind_of(sha) == "suite":
            docs[f"suites/{sha}.json"] = SA.suite(store, sha)
    if generation_dir is not None:
        docs["generation.json"] = SA.generation(Path(generation_dir), generation_id=Path(generation_dir).name)
    problems = []
    for rel, doc in docs.items():
        if rel == "evaluation.json":
            problems += audit.check_evaluation(doc, answers, where=rel)
        elif rel.startswith("suites/"):
            problems += audit.check_evaluation(doc, answers, where=rel)
        elif rel == "generation.json":
            problems += audit.check(doc, None, where=rel)                          # proposals are other tasks: structural and pattern checks
        else:
            problems += audit.check(doc, [a for v in answers.values() for a in v], where=rel)
    if problems:
        raise ValueError("the sanitized documents failed the leak audit; nothing written:\n  " + "\n  ".join(problems[:20]))
    rr = []
    rdir = store.root / "objects" / "run_result"
    for p in sorted(rdir.glob("*.json")) if rdir.exists() else []:
        r = store.get("run_result", p.stem)
        if r.manifest_sha256 == ev["manifest"]["sha256"] and any(f"run {run.state['id']}" == r.provenance.notes for run in runs.values()):
            rr.append({"sha256": p.stem, "variant": r.variant, "condition": r.condition, "evidence_dir_sha256": r.evidence_dir_sha256})
    source = {"runs": sorted(r.state["id"] for r in runs.values()), "mode": ev["mode"], "manifest_sha256": ev["manifest"]["sha256"],
              "frozen_suite_sha256": ev["frozen_suite"]["sha256"], "run_results": rr, "trial_records_sha256": trials_src,
              "generation": Path(generation_dir).name if generation_dir else None}
    return docs, shots, source


def build(store_root: Path, run_dirs: list[Path], out: Path, *, generation_dir: Path | None, dataset_id: str, version: int, title: str | None = None,
          context: dict | None = None, built_at: str) -> dict:
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"{out} is not empty: datasets are versioned and immutable; build a new version into a new directory")
    docs, shots, source = documents(store_root, run_dirs, generation_dir, evaluation_id=dataset_id, title=title, context=context)
    files, shot_src = {}, {}
    for rel, doc in sorted(docs.items()):
        b = _dump(doc)
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_bytes(b)
        files[rel] = _sha(b)
    for rel, src in sorted(shots.items()):
        png = src.read_bytes()
        b = _webp(png)
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_bytes(b)
        files[rel] = _sha(b)
        shot_src[rel] = _sha(png)
    meta = {"schema": SCHEMA, "id": dataset_id, "version": version, "built_at": built_at, "title": docs["evaluation.json"]["title"],
            "mode": docs["evaluation.json"]["mode"], "description": "Sanitized projection of a recorded lifecycle evaluation; derived from the real run artefacts "
            "(git-ignored, local) by agent_readiness.lifecycle.dataset. Screenshots are the recorded browser frames re-encoded to WebP "
            f"(max width {WEBP_WIDTH}px, quality {WEBP_QUALITY}); no pixel is edited.",
            "source": {**source, "screenshots_png_sha256": shot_src}, "code_sha256": code_hashes(), "files": files}
    (out / "DATASET.json").write_bytes(_dump(meta))
    return meta


def validate(d: Path, *, store_root: Path | None = None, run_dirs: list[Path] | None = None, generation_dir: Path | None = None) -> dict:
    """Integrity (every file listed, hashes match, nothing extra), the structural audit, and with `store_root` and `run_dirs` the full re-derivation:
    every document recomputed from the source must equal the stored bytes, each screenshot's source PNG must have its recorded hash, and the expected
    answers audit is repeated."""
    d = Path(d)
    meta = json.loads((d / "DATASET.json").read_text())
    problems = []
    if meta.get("schema") != SCHEMA:
        problems.append("unknown dataset schema")
    present = {str(p.relative_to(d)) for p in d.rglob("*") if p.is_file() and p.name != "DATASET.json"}
    listed = set(meta["files"])
    problems += [f"unlisted file {x}" for x in sorted(present - listed)] + [f"missing file {x}" for x in sorted(listed - present)]
    for rel, sha in sorted(meta["files"].items()):
        p = d / rel
        if p.exists() and _sha(p.read_bytes()) != sha:
            problems.append(f"hash mismatch {rel}")
    for rel in sorted(listed & present):
        if rel.endswith(".json"):
            problems += audit.check(json.loads((d / rel).read_text()), None, where=rel)
    rederived = None
    if store_root and run_dirs:
        ev = json.loads((d / "evaluation.json").read_text())
        docs, shots, source = documents(store_root, run_dirs, generation_dir, evaluation_id=meta["id"], title=ev["title"],
                                        context=ev["dimensions"]["coverage"].get("context"))
        for rel, doc in docs.items():
            if rel not in meta["files"]:
                problems.append(f"re-derived document {rel} is not in the dataset")
            elif _sha(_dump(doc)) != meta["files"][rel]:
                problems.append(f"re-derived {rel} differs from the dataset")
        for rel, src in shots.items():
            if meta["source"]["screenshots_png_sha256"].get(rel) != _sha(src.read_bytes()):
                problems.append(f"screenshot source changed: {rel}")
        if {k: v for k, v in source.items()} != {k: v for k, v in meta["source"].items() if k != "screenshots_png_sha256"}:
            problems.append("source identities differ")
        rederived = not problems
    return {"dataset": meta["id"], "version": meta["version"], "files": len(listed), "problems": problems, "valid": not problems, "rederived_from_source": rederived}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agent_readiness.lifecycle.dataset")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    v = sub.add_parser("validate")
    for p in (b, v):
        p.add_argument("--store", type=Path)
        p.add_argument("--run", type=Path, action="append", default=[])
        p.add_argument("--generation", type=Path)
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--id", required=True)
    b.add_argument("--version", type=int, required=True)
    b.add_argument("--title")
    v.add_argument("dir", type=Path)
    a = ap.parse_args(argv)
    if a.cmd == "build":
        from datetime import datetime, timezone
        from .sites import context_for
        ev_site = json.loads((a.run[0] / "run.json").read_text())["config"]["site"]
        meta = build(a.store, a.run, a.out, generation_dir=a.generation, dataset_id=a.id, version=a.version, title=a.title, context=context_for(ev_site),
                     built_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat())
        print(json.dumps({"id": meta["id"], "version": meta["version"], "files": len(meta["files"])}))
        return 0
    rep = validate(a.dir, store_root=a.store, run_dirs=a.run or None, generation_dir=a.generation)
    print(json.dumps(rep, indent=1))
    return 0 if rep["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
