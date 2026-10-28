"""Bounded, single-slot scan execution. One scan runs at a time (enforced atomically in the store); a failure is recorded and never retried automatically."""
from __future__ import annotations

import asyncio
import json
import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor

from ...agent import ModelConfig
from ...suite import core
from ..execute import execute_scan
from .config import ScannerConfig
from .store import Store

PER_SCAN_LIVE_RESERVATION_USD = 0.48        # worst-case ESTIMATE for one 12-request scan (12 x US$0.04); an estimate, not a guarantee of billed spend


class ScanManager:
    def __init__(self, store: Store, config: ScannerConfig, runner=execute_scan):
        self.store, self.config, self.runner = store, config, runner
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scan")
        self._handles: dict[str, tuple[asyncio.AbstractEventLoop, asyncio.Task]] = {}
        self._lock = threading.Lock()

    def killed(self) -> bool:
        return self.config.kill_switch_path.exists()

    def submit(self, scan_id: str, task_id: str, variant: core.Variant, mode: str, behavior: str | None) -> Future:
        return self.pool.submit(self._run, scan_id, task_id, variant, mode, behavior or "correct")

    def _run(self, scan_id, task_id, variant, mode, behavior):
        if self.killed() or not self.store.mark_running(scan_id):
            self.store.finish_scan(scan_id, "cancelled", None, "kill switch active before the scan started" if self.killed() else "scan was not queued")
            return
        loop = asyncio.new_event_loop()
        try:
            key = os.environ.get(self.config.live_api_key_env) if mode == "live" else None
            coro = self.runner(task_id, variant, provider=mode, mock_behavior=behavior, output=self.store.result_path(scan_id), model_config=ModelConfig(), api_key=key)
            task = loop.create_task(coro)
            with self._lock:
                self._handles[scan_id] = (loop, task)
            record = loop.run_until_complete(asyncio.wait_for(task, timeout=None))
            record.pop("artifact_path", None)                                   # never expose server paths
            self.store.result_path(scan_id).mkdir(parents=True, exist_ok=True)
            (self.store.result_path(scan_id) / "result.json").write_text(json.dumps(record, indent=1))
            self.store.finish_scan(scan_id, "complete", record["metrics"]["calculated_cost_usd"] if mode == "live" else 0.0, None)
        except asyncio.CancelledError:
            self.store.finish_scan(scan_id, "cancelled", None, "cancelled")
        except Exception as exc:                                               # recorded, never retried; message is generic (no stack, path or secret)
            self.store.finish_scan(scan_id, "error", None, f"{type(exc).__name__}")
        finally:
            with self._lock:
                self._handles.pop(scan_id, None)
            loop.close()

    def cancel_all(self) -> int:
        with self._lock:
            handles = list(self._handles.values())
        for loop, task in handles:
            loop.call_soon_threadsafe(task.cancel)
        return len(handles)

    def private_result(self, scan_id: str) -> dict | None:
        path = self.store.result_path(scan_id) / "result.json"
        return json.loads(path.read_text()) if path.exists() else None
