"""Task 014 follow-up: guarded LIVE steps for WebArena shopping task 286. NOTHING HERE RUNS UNLESS YOU PASS --allow-model-calls, and the owner has not authorized any live call yet.
usage:
  uv run --extra webarena python scripts/webarena_live.py status                                   # ledger totals (no network)
  uv run --extra webarena python scripts/webarena_live.py probe --allow-model-calls               # <= US$0.04, 1 request   (needs separate approval)
  uv run --extra webarena python scripts/webarena_live.py run   --allow-model-calls               # exactly 1 run           (needs separate approval)
Private outputs go under runs/webarena-014/live/ (Git-ignored). The key is read from META_MODEL_API_KEY / repo .env and never printed."""
import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

from agent_readiness.agent import ModelConfig
from agent_readiness.scanner.live import Halt, Ledger
from agent_readiness.webarena import live
from agent_readiness.webarena.adapter import WebArenaShopping

DOCKER = "/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe"
ROOT = Path("runs/webarena-014/live")


def container_info(name="wav-shopping"):
    try:
        out = subprocess.run([DOCKER, "inspect", name, "--format", "{{.Image}} {{.State.Status}} {{.State.StartedAt}}"], capture_output=True, text=True, timeout=20).stdout.split()
        return {"image_id": out[0], "state": out[1], "started_at": out[2]} if len(out) >= 3 else None
    except Exception:
        return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["status", "probe", "run"])
    p.add_argument("--allow-model-calls", action="store_true")
    p.add_argument("--base", default="http://localhost:7770")
    p.add_argument("--ctrl", default="http://localhost:7771")
    a = p.parse_args()
    ledger = Ledger(ROOT, ceiling=live.LEDGER_CEILING_USD)
    if a.command == "status":
        print(json.dumps({"ledger_committed_usd": ledger.committed(), "ceiling_usd": ledger.ceiling, "probe_ok": ledger.probe_succeeded(), "entries": len(ledger.entries())}, indent=1))
        return
    try:
        if a.command == "probe":
            rec = live.run_schema_probe(ModelConfig(), ledger, ROOT / "probe", allow_model_calls=a.allow_model_calls)
            print(json.dumps({k: rec.get(k) for k in ("success", "failure_class", "http_status", "finish_reason", "usage", "calculated_cost_usd", "elapsed_seconds", "error")}, indent=1, default=str))
        else:
            shop = WebArenaShopping(a.base)
            health = live.check_site(a.base, a.ctrl)
            health["container"] = container_info()
            rec = asyncio.run(live.run_live(shop, ledger, ROOT / "run", allow_model_calls=a.allow_model_calls, health=health))
            print(json.dumps({k: rec[k] for k in ("mode", "run_status", "stop_reason", "model_requests", "official_verdict", "spend", "guard_halt", "leak_scan")}, indent=1, default=str))
    except Halt as exc:
        print(f"HALT (nothing was sent): {exc}")
        sys.exit(2)


main()
