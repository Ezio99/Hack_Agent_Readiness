# Report 015a — security and integration review of PR #22 (website audit API), with fixes

**Date:** 2026-10-29. Reviewer: the implementing agent (self-review; not an independent audit). Scope: URL handling and data flow of `POST /api/audits`, the probe, the managed targets, stored reports, the dashboard panel, and integration with existing code. **No model call, no spend.**

## Data flow in one paragraph
A session holder sends `{target_id, objective?, task_id?, with_scan?, previous_audit_id?}` (`extra="forbid"`, 4 KB body limit, global rate limit, kill switch honoured). `target_id` must be a **registered** target (operator-configured loopback demo servers); the probe is constructed from the registered target's own address, never from request data. The probe fetches ≤ 24 pages + ≤ 6 detail pages (GET, same origin, no JS), builds a report, and the report (not the fetched HTML) is stored as JSON under the service data dir and returned. `previous_audit_id` is resolved through the database and ownership-checked before any file is read. `with_scan` runs the existing **mock** scanner only.

## Findings and what was done
| # | Issue (severity) | Status |
|---|---|---|
| 1 | **SSRF via the probe if it were ever pointed at user-supplied URLs** (high, latent): the library `SiteProbe` accepted any http(s) URL, followed redirects automatically, and the CLI audited any host. The API itself cannot reach it (registered ids only), but a future "register my site" feature or CLI misuse could hit cloud metadata / internal hosts. | **Fixed.** `SiteProbe` refuses by default any host resolving to loopback, private, link-local (incl. 169.254.169.254), reserved, multicast or unspecified addresses, checked at construction and on every hop; URLs with credentials and non-http(s) schemes are rejected. Loopback/private is allowed only with an explicit `allow_private_hosts=True` (used for the operator's registered demo targets) or the CLI flag `--allow-private`. Tests: 8 private/metadata hosts, credentials, schemes. |
| 2 | **Off-origin redirects** (medium): `follow_redirects=True` could have been bounced to another host/internal address. | **Fixed.** Redirects are followed manually, only within the audited origin, max 3 hops, and the public-address check is applied per hop; an off-origin redirect or link is recorded as an error and never requested. Tests: the other origin receives 0 hits; redirect loops are bounded. |
| 3 | **Unbounded response body** (medium): the whole body was read before truncation. | **Fixed.** Streamed with a 1 MB cap; non-HTML is skipped without reading. Test with a 3 MB page. |
| 4 | **Internal address disclosure** (medium): evidence URLs and probe errors in the stored/returned report contained the fetched address (`http://127.0.0.1:<port>/…`). | **Fixed.** Evidence URLs are relativised to the audited site; errors keep only the path; the report's `target` is the registered id. Test asserts the internal base URL never appears in an API response. |
| 5 | **Retrospective rewriting of recommendations** (integrity, per owner requirement): `attach_measured_effects` mutated the audit report and overwrote `validation`. | **Fixed.** It now returns a derived view (`original_report_sha256`, `measured_validation`), leaves the original and `validation` as issued, requires the effect to reference the report's own audit id and one of its recommendation ids, and rejects non-LIVE (mock/dry-run) results. |
| 6 | **Path traversal via ids** (checked): `GET /api/audits/{id}` and `previous_audit_id` are looked up in SQLite first; file paths are built only from ids the server generated. Traversal strings return 404/422 (tested). | OK |
| 7 | **Cross-session access** (checked): audits are owned by the invitation; other sessions get 404, including as `previous_audit_id`. | OK (tested) |
| 8 | **Admin change endpoint** (checked): requires the admin token (constant-time compare), only library-defined change ids, only registered targets; it mutates a demo target, not a real site. | OK; disabled unless an admin token is configured and `--demo-target` is used |
| 9 | **Untrusted page text** in evidence excerpts / objective (checked): rendered as React text nodes, never as HTML; not sent to any model. | OK |
| 10 | **Resource use** (low): one audit = ≤ 30 sequential GETs with 10 s timeouts; a mock scan takes the existing single browser slot (asyncio lock); per-session cap of 50 audits; global rate limit. | Accepted; a per-IP audit quota is future work if the service is ever exposed |

## Residual risks (not fixed)
- **DNS rebinding / TOCTOU:** the public-address check resolves the host before the request; a hostile DNS server could answer differently at connect time. Mitigation if user URLs are ever accepted: pin the resolved IP into the connection (custom transport). Not needed while only registered targets are audited.
- **Accepting user URLs is still out of scope** and needs the above plus an ownership/consent step (the probe's user agent states it is a site owner's test, but nothing verifies ownership).
- The probe sees plain HTTP HTML only (no JavaScript, no authentication); results on JS-rendered sites are `insufficient_coverage`, not wrong findings.
- `budget.LEDGER_PATH` assumes the repository layout (fine for the dev tooling it serves; not for a pip-installed package).
- This was a self-review by the author; an independent review is advisable before any public exposure.

## Integration review
- `capture.py` hook and `execute_scan(request_gate=…)` are optional with default `None`; all pre-existing tests still pass (full suite below). `webarena/live.py` now imports the gate from `spend_gate.py` and re-exports it; its 16 gate tests are unchanged and green.
- `Store` gained an `audits` table via `CREATE TABLE IF NOT EXISTS` (safe on existing databases); no existing table or endpoint changed. The scanner's no-URL design (`NewScan` has no URL field) is unchanged and the new `NewAudit` follows the same rule.
- Dashboard: the panel renders only when `/api/targets` returns targets; the public build (no scanner API) is unchanged; `check:dist` hygiene tests still hold.

## Tests
`tests/test_remediation_security.py` (8 groups, 13 cases), plus the updated `tests/test_remediation.py` and `tests/test_remediation_api.py`: **33 passed**. Full suite (after the driver was added): 622 passed.
