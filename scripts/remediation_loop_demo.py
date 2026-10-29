"""Offline end-to-end demonstration of the diagnose -> recommend -> modify -> rescan loop through the PRODUCT INTERFACES ONLY: the `readiness` CLI starts the scanner
service with a managed demo target and creates an invitation, then this script behaves like any API client (httpx). All logic lives in the product; this script contains no
rules, no thresholds and no expected outcomes. No model call, no key, no cost. usage: uv run python scripts/remediation_loop_demo.py [--scan]"""
import argparse
import os
import re
import subprocess
import sys
import tempfile
import time

import httpx

ADMIN = "demo-admin-token"
OBJECTIVE = "List every in-stock ANC headphone at or below A$250.00 with SKU and price"


def show(title, report):
    print(f"\n=== {title}  (audit {report['audit_id']}, target '{report['target']}')")
    for f in report["findings"]:
        print(f"  [{f['category']}] {f['fingerprint']}: {f['summary']}")
    for r in report["recommendations"]:
        print(f"  RECOMMENDATION [{r['validation']}, {r['confidence']['level']}] {r['title']}\n     change: {r['change']}\n     why: {r['rationale'][:230]}…\n     expected benefit: {r['expected_benefit']}\n     confidence: {r['confidence']['statement']}")
    if report["agent_execution"]:
        ex = report["agent_execution"]
        print(f"  AGENT EXECUTION ({ex['scan_mode']} scan): " + "; ".join(i["summary"] for i in ex["items"][:3]))
        for c in ex["corroborates"]:
            print(f"     inferred: {c['statement'][:160]}…")
    if report["lifecycle"]:
        for i in report["lifecycle"]["items"]:
            print(f"  LIFECYCLE {i['fingerprint']}: {i['status'].upper()} — {i['current_summary']}")
        print(f"  note: {report['lifecycle']['statement']}")
    print(f"  measured effects: {report['measured_effects']['status']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true", help="also run a MOCK agent scan with each audit (needs Chromium)")
    ap.add_argument("--port", type=int, default=8791)
    a = ap.parse_args()
    data = tempfile.mkdtemp(prefix="ar-demo-")
    env = {**os.environ, "SCANNER_DATA_DIR": data, "SCANNER_SECRET": "demo-secret", "SCANNER_ADMIN_TOKEN": ADMIN}
    out = subprocess.run(["uv", "run", "readiness", "scanner", "invite", "--label", "demo"], env=env, capture_output=True, text=True, check=True).stdout
    code = re.search(r"code: (\S+)", out).group(1)
    srv = subprocess.Popen(["uv", "run", "readiness", "scanner", "serve", "--demo-target", "--port", str(a.port)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{a.port}"
    try:
        for _ in range(100):
            try:
                if httpx.get(base + "/api/health", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.3)
        with httpx.Client(base_url=base, timeout=180) as c:
            h = {"Authorization": "Bearer " + c.post("/api/session", json={"code": code}).json()["token"]}
            body = {"target_id": "demo-shop", "objective": OBJECTIVE}
            if a.scan:
                body.update(task_id="t1-anc-headphones-under-250-all", with_scan=True)
            first = c.post("/api/audits", headers=h, json=body).json()
            show("1. BASELINE AUDIT", first)
            rec = next(r for r in first["recommendations"] if r["change_id"] == "availability-on-listing-cards")
            print(f"\n--- operator applies the recommended change '{rec['change_id']}' to the managed site ---")
            print(c.post("/api/admin/targets/demo-shop/changes", headers={"X-Admin-Token": ADMIN}, json={"change_id": rec["change_id"]}).json())
            second = c.post("/api/audits", headers=h, json={**body, "previous_audit_id": first["audit_id"]}).json()
            show("2. INDEPENDENT RESCAN", second)
    finally:
        srv.terminate()
        srv.wait(10)


main()
