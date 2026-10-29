"""Stage machine for an investigation (plan §5). Stages are plain functions registered in order; the machine owns ordering, resume, failure recording and the approval gates.

Behaviour that matters:
  * completed stages are skipped on resume; a FAILED spending stage is never silently re-run (the owner must look first);
  * a stage that `spends` and runs in `live` mode must present a manifest; it runs only if the owner has approved that manifest's SHA-256 (otherwise the run stops with
    `awaiting_approval` and nothing is spent);
  * a stage may also declare `gate` = a callable that returns a manifest needing approval in ANY mode (e.g. applying a proposed fix);
  * no network or model access happens here: stages receive a context with the (injected) LLM client."""
from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from typing import Callable

from .run import InvestigationRun, NeedsApproval

STAGES = ("inspect", "taskgen", "freeze", "baseline_trials", "investigate", "recommend", "apply_fix", "post_trials", "report")


@dataclass
class Context:
    run: InvestigationRun
    llm: object | None = None                  # an LLMClient (scripted / recorded / meta); None for stages that make no model calls
    options: dict = field(default_factory=dict)

    @property
    def evidence(self):
        return self.run.evidence


@dataclass(frozen=True)
class Stage:
    name: str
    fn: Callable[[Context], dict | None]
    spends: bool = False                                           # makes paid model calls or browser trials
    manifest: Callable[[Context], dict] | None = None              # what the owner approves (required when `spends` and mode == live, or when `gate` is set)
    gate: bool = False                                             # needs approval of `manifest` in every mode
    skip: Callable[[Context], str | None] | None = None            # returns a reason to skip the stage entirely (no approval, nothing runs)


@dataclass
class Result:
    status: str                                                    # done | awaiting_approval | failed
    stage: str | None = None
    manifest_sha256: str | None = None
    error: str | None = None


class Pipeline:
    def __init__(self, stages: list[Stage]):
        names = [s.name for s in stages]
        if len(set(names)) != len(names):
            raise ValueError("duplicate stage names")
        self.stages = stages

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(s.name for s in self.stages)

    def run(self, ctx: Context, *, until: str | None = None) -> Result:
        run = ctx.run
        for stage in self.stages:
            st = run.status(stage.name)
            if st == "done":
                continue
            if st == "failed" and stage.spends:
                return Result("failed", stage.name, error="a failed spending stage is not re-run automatically; inspect it and create a new investigation or reset deliberately")
            needs_gate = stage.gate or (stage.spends and run.mode == "live")
            if stage.skip is not None and (why := stage.skip(ctx)):
                run.set_status(stage.name, "done", summary={"skipped": True, "reason": why})
                continue
            if needs_gate:
                if stage.manifest is None:
                    raise ValueError(f"stage {stage.name!r} needs approval but defines no manifest")
                try:
                    run.require_approval(stage.name, stage.manifest(ctx))
                except NeedsApproval as exc:
                    run.set_status(stage.name, "awaiting_approval", manifest_sha256=exc.manifest_sha256)
                    return Result("awaiting_approval", stage.name, exc.manifest_sha256)
            run.set_status(stage.name, "running")
            try:
                out = stage.fn(ctx) or {}
            except NeedsApproval as exc:
                run.set_status(stage.name, "awaiting_approval", manifest_sha256=exc.manifest_sha256)
                return Result("awaiting_approval", stage.name, exc.manifest_sha256)
            except Exception as exc:                               # recorded, never swallowed silently
                run.set_status(stage.name, "failed", error=f"{type(exc).__name__}: {exc}"[:500], trace=traceback.format_exc()[-1500:])
                return Result("failed", stage.name, error=f"{type(exc).__name__}: {exc}")
            run.set_status(stage.name, "done", summary=out)
            if until == stage.name:
                break
        return Result("done")
