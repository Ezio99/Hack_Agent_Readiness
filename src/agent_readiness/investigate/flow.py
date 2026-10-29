"""The runnable investigation flow (M3 scope): inspect -> taskgen -> freeze -> baseline_trials, in `mock` mode (rule-generated tasks + scripted agent, no key, no network) or `live`
mode (Meta proposes the tasks and Meta is the agent; every spending stage waits for the owner's approval of its exact manifest hash). Later milestones append investigate / recommend /
fix / post-trial / report stages to the same list.

The live model client is built lazily: nothing reads the key or touches the network until a stage has been approved and starts, and then only after the shared `ledger.preflight`."""
from __future__ import annotations

from pathlib import Path

from ..agent import ModelConfig
from ..ledger import Halt
from ..suite.core import canonical_hash
from . import zoo
from .inspect.stage import run_inspect
from .llm import LLMRequest, RecordingClient
from .llm.meta import MetaClient
from .pipeline import Context, Pipeline, Stage
from .run import InvestigationRun
from .investigator import stage as investigator
from .taskgen import propose
from .taskgen.stage import freeze_stage, taskgen_stage
from .trials import stage as trials

STAGES = ("inspect", "taskgen", "freeze", "baseline_trials", "trace", "investigate", "report")
TASKGEN_RUN_CAP_USD = 0.15


class LazyMeta:
    """Defers key lookup and client construction to the first call (i.e. until after approval); records the transcript privately."""
    mode = "live"

    def __init__(self, run: InvestigationRun, cfg: ModelConfig, allow: bool, cap_usd: float, ledger_ceiling_usd: float, *, name: str = "taskgen", max_requests: int = 4, transcript: str = "llm-transcript"):
        self.model, self._run, self._cfg, self._allow, self._cap, self._ceiling, self._client = cfg.model, run, cfg, allow, cap_usd, ledger_ceiling_usd, None
        self._name, self._max_requests, self._transcript = name, max_requests, transcript

    def complete(self, request: LLMRequest):
        if self._client is None:
            inner = MetaClient.live(self._cfg, self._run.ledger(self._ceiling), f"{self._run.state['id']}-{self._name}", allow_model_calls=self._allow, run_cap_usd=self._cap, per_request_cap_usd=0.05, max_requests=self._max_requests)
            self._client = RecordingClient(inner, self._run.dir / "private" / f"{self._transcript}.jsonl")
        return self._client.complete(request)


def taskgen_manifest(ctx: Context) -> dict:
    cfg = ctx.options.get("model_config") or ModelConfig()
    profile = ctx.run.artifact("site-profile")
    n = ctx.options.get("n_tasks", 8)
    return {"stage": "taskgen", "provider": cfg.provider, "model": cfg.model, "endpoint": cfg.base_url.rstrip("/") + "/chat/completions", "max_requests": 4, "retries_per_request": 1,
            "first_prompt_sha256": canonical_hash(propose.build_prompt(profile, n + 2, None)), "snapshot_sha256": ctx.run.artifact("site-profile")["snapshot_sha256"], "run_cap_usd": TASKGEN_RUN_CAP_USD,
            "per_request_cap_usd": 0.05, "cost_basis": "calculated upper bounds at published prices; not a bill"}


def build(root: Path, run_id: str, site: str, *, mode: str, options: dict | None = None) -> tuple[InvestigationRun, Pipeline, Context]:
    opts = dict(options or {})
    d = Path(root) / run_id
    run = InvestigationRun(d) if (d / "run.json").exists() else InvestigationRun.create(root, run_id, target=site, mode=mode, stages=STAGES, config={k: v for k, v in opts.items() if k != "model_config"})
    if run.mode != mode:
        raise Halt(f"investigation {run_id} was created in {run.state['mode']} mode; it cannot be resumed as {mode}")
    cfg = opts.get("model_config") or ModelConfig()
    live = mode == "live"
    ceiling = opts.get("stage_cap_usd", 3.0) + TASKGEN_RUN_CAP_USD + opts.get("investigate_cap_usd", investigator.RUN_CAP_USD)
    llm = LazyMeta(run, cfg, opts.get("allow_model_calls", False), TASKGEN_RUN_CAP_USD, ceiling) if live else None
    if live and "investigator_llm" not in opts:
        opts["investigator_llm"] = LazyMeta(run, cfg, opts.get("allow_model_calls", False), opts.get("investigate_cap_usd", investigator.RUN_CAP_USD), ceiling, name="investigate",
                                            max_requests=opts.get("max_calls", investigator.DEFAULT_MAX_CALLS) + 3, transcript="investigator-llm-transcript")
    snap = zoo.snapshot(site)
    stages = [Stage("inspect", lambda c: run_inspect(c, snap)),
              Stage("taskgen", taskgen_stage, spends=live, manifest=taskgen_manifest if live else None),
              Stage("freeze", freeze_stage),
              Stage("baseline_trials", trials.baseline_trials_stage, spends=True, manifest=trials.manifest),
              Stage("trace", investigator.trace_stage),
              Stage("investigate", investigator.investigate_stage, spends=True, manifest=investigator.manifest),
              Stage("report", investigator.report_stage)]
    return run, Pipeline(stages), Context(run, llm=llm, options=opts)
