"""Task 014: scripted (no-LLM) WebArena Verified shopping validation against a REAL local Magento container. Not a model run; nothing paid.
usage: uv run --extra webarena python scripts/webarena_validate.py <scenario> <out_dir> [--base http://localhost:7770]
scenarios: direct (known-good product page), wrong (negative control: other product page)."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "tests"))
from agent_readiness.webarena.adapter import WebArenaShopping
from agent_readiness.webarena.runner import run_task

OK = {"task_type": "NAVIGATE", "status": "SUCCESS", "retrieved_data": None, "error_details": None}


def script_for(scenario: str, target_path: str, other_path: str):
    path = {"direct": target_path, "wrong": other_path}[scenario]

    def make(task, base_url):
        from agent_readiness.scanner import mock
        n = {"n": 0}

        def handler(request):
            n["n"] += 1
            act = {"navigate": {"url": base_url + path, "new_tab": False}} if n["n"] == 1 else {"done": {"data": OK, "success": True}}
            return mock._reply(n["n"], act)
        return handler
    return make


async def main(a):
    shop = WebArenaShopping(a.base)
    task = shop.task(286)
    ev = next(e for e in shop.wa.get_task(286).model_dump(mode="json")["eval"] if e["evaluator"] == "NetworkEventEvaluator")
    target = ev["expected"]["url"].replace("__SHOPPING__", "")
    r = await run_task(shop, task, output=Path(a.out), handler_factory=script_for(a.scenario, target, a.other), profile_id="suite-v2-compat1")
    r["scenario"] = a.scenario
    Path(a.out, "result.json").write_text(json.dumps(r, indent=1, default=str))
    print(json.dumps({k: r[k] for k in ("scenario", "run_status", "har_entries", "model_requests", "official_verdict")}, indent=1, default=str))

p = argparse.ArgumentParser()
p.add_argument("scenario", choices=["direct", "wrong"])
p.add_argument("out")
p.add_argument("--base", default="http://localhost:7770")
p.add_argument("--other", default="/catalogsearch/result/?q=ssd")
asyncio.run(main(p.parse_args()))
