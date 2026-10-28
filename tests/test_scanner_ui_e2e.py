"""Local end-to-end: dashboard UI -> scanner API -> real Browser Use agent (mock model) -> real storefront -> independent evaluator -> UI result.
Builds the dashboard with a loopback API URL into a temp dir (never into dashboard/dist). Skipped when node/npm is unavailable. Screenshots go to
$SCANNER_E2E_SHOTS if set (kept local, never committed)."""
import functools
import http.server
import os
import shutil
import socket
import subprocess
import threading
from pathlib import Path

import pytest
import uvicorn
from playwright.sync_api import sync_playwright

from agent_readiness.scanner.service.api import create_scanner_app
from agent_readiness.scanner.service.config import ScannerConfig

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "dashboard"
pytestmark = [pytest.mark.browser, pytest.mark.skipif(not shutil.which("npm") or not (DASH / "node_modules").exists(), reason="dashboard toolchain not installed")]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_invited_developer_runs_a_scan_and_reads_diagnostics(tmp_path):
    api_port, ui_port = free_port(), free_port()
    dist = tmp_path / "dist"
    subprocess.run(["npm", "run", "build", "--", "--outDir", str(dist), "--emptyOutDir"], cwd=DASH, check=True, capture_output=True,
                   env={**os.environ, "VITE_SCANNER_API_URL": f"http://127.0.0.1:{api_port}"})
    cfg = ScannerConfig(data_dir=tmp_path / "data", secret="e2e-secret", cors_origins=(f"http://127.0.0.1:{ui_port}",), rate_limit_per_minute=2000)
    app = create_scanner_app(cfg)
    _, code = app.state.store.create_invitation("e2e", scan_quota=3)
    api = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=api_port, log_level="error"))
    threading.Thread(target=api.run, daemon=True).start()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(dist))
    handler.log_message = lambda *a, **k: None
    ui = http.server.ThreadingHTTPServer(("127.0.0.1", ui_port), handler)
    threading.Thread(target=ui.serve_forever, daemon=True).start()
    shots = Path(os.environ["SCANNER_E2E_SHOTS"]) if os.environ.get("SCANNER_E2E_SHOTS") else None
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(args=["--no-sandbox"])
            page = b.new_page(viewport={"width": 1100, "height": 1000})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{ui_port}/#/scanner")
            page.get_by_label("Invitation code").fill("AR-WRONG-WRONG-WRONG")
            page.get_by_role("button", name="Start session").click()
            page.get_by_role("alert").wait_for()
            assert "Invalid" in page.get_by_role("alert").inner_text()
            page.get_by_label("Invitation code").fill(code)
            page.get_by_role("button", name="Start session").click()
            page.get_by_label("Task").select_option("t3-cheapest-monitor-27in-usbc-120hz")
            page.get_by_role("button", name="Run mock scan").click()
            page.get_by_role("region", name="Scan result").wait_for(timeout=120000)
            body = page.inner_text("main")
            assert "PASS" in body and "MOCK" in body and "not billed" in body and "What the agent did" in body
            if shots:
                shots.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(shots / "scanner-pass.png"), full_page=True)
            # a second scan with the tool-visibility persona -> agent/tool-interface finding, then compare with the baseline
            page.get_by_role("button", name="Use this scan as baseline").click()
            page.get_by_label("Task").select_option("t1-anc-headphones-under-250-all")
            page.get_by_label("Mock agent scenario").select_option("loop")
            page.get_by_role("button", name="Run mock scan").click()
            page.get_by_text("Agent–tool interface").first.wait_for(timeout=120000)
            assert "FAIL" in page.inner_text("main")
            if shots:
                page.screenshot(path=str(shots / "scanner-loop.png"), full_page=True)
            assert not errors, errors
            page.get_by_role("button", name="End session").click()
            page.get_by_label("Invitation code").wait_for()
            b.close()
    finally:
        api.should_exit = True
        ui.shutdown()
