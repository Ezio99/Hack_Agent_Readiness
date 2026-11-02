"""Stage A / Stage B boundary. Stage A (task-suite design and selection) must never see agent evaluation outcomes.

Enforced three ways:
  imports    Stage A modules may not import anything that executes agents or reads their results (`forbidden_imports`)
  schemas    Stage A records accept inputs only of STAGE_A_INPUT_KINDS (records.InputRef validation)
  store      a Stage A record may not reference a stored object whose kind is a Stage B outcome (store.WriteOnceStore._check_stage_a_refs)
"""
from __future__ import annotations

import ast
from pathlib import Path

STAGE_A_INPUT_KINDS = ("catalogue", "context", "site", "snapshot", "generator", "evaluator", "proposals", "suite", "task")
STAGE_B_INPUT_KINDS = ("frozen_suite", "suite", "task", "site", "snapshot", "profile", "jail_policy", "plan")
STAGE_B_OUTCOME_KINDS = ("run_result", "manifest")          # store kinds a Stage A record must never reference

FORBIDDEN_FOR_STAGE_A = (
    "agent_readiness.investigate.trials",     # trial execution and trial records
    "agent_readiness.hosted",                 # live service, jobs, results
    "agent_readiness.diagnostics",            # behavioural diagnostics read trials
    "agent_readiness.grading.rescore",        # reads trial answers
    "agent_readiness.provenance",             # reads trial records and traces
    "agent_readiness.research.pilot",         # paid trial runner
    "agent_readiness.framework.evaluate",     # trial execution
    "agent_readiness.evalruns",               # Stage B (future)
    "agent_readiness.live",                   # live jobs and runners
    "agent_readiness.scanner",                # scan execution
    "agent_readiness.agent",                  # the browser agent
)
STAGE_A_MODULES = ("records.py", "store.py", "boundary.py")   # files of agent_readiness/suites that belong to Stage A (plus suites/stage_a/** when it exists)


def _resolve(module: str | None, level: int, here: str) -> str:
    if level == 0:
        return module or ""
    base = here.split(".")[: -level]
    return ".".join(base + ([module] if module else []))


def imports_of(path: Path, module_name: str) -> set[str]:
    tree = ast.parse(Path(path).read_text())
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            base = _resolve(node.module, node.level, module_name)
            out.add(base)
            out |= {f"{base}.{a.name}" for a in node.names}
    return out


def forbidden_imports(package_dir: Path) -> list[str]:
    """Violations in the Stage A files of `package_dir` (agent_readiness/suites) and its stage_a/ subpackage."""
    package_dir = Path(package_dir)
    files = [package_dir / f for f in STAGE_A_MODULES if (package_dir / f).exists()] + sorted((package_dir / "stage_a").rglob("*.py"))
    bad = []
    for f in files:
        rel = f.relative_to(package_dir.parent.parent).with_suffix("")
        mod = ".".join(rel.parts)
        for imp in imports_of(f, mod):
            if any(imp == p or imp.startswith(p + ".") for p in FORBIDDEN_FOR_STAGE_A):
                bad.append(f"{f.name}: imports {imp}")
    return bad
