# Report 016a — Task 016 M1: investigation foundations

Branch `task016-m1-foundations`. Plan: [docs/TASK016_IMPLEMENTATION_PLAN.md](../../docs/TASK016_IMPLEMENTATION_PLAN.md) (rev 2, approved). **No paid call, network call, deployment or frozen-file edit.**

## What was built (`src/agent_readiness/investigate/`, new, ~900 lines)
| module | purpose |
|---|---|
| `models.py` | `evidence-v1`: Observation, Hypothesis (`tier` verifiable / novel), Verification, Finding, Proposal (`basis` verified_finding / unverified_hypothesis; always `validation: unvalidated`; EXPERIMENTAL label), Effect (only `mode == live` counts as measured). Content-derived ids; the closed claim grammar names (verifiers come in M5) |
| `store.py` | append-only `evidence.jsonl` with the rules enforced **in code**: citations must exist; hypotheses arrive unverified; only `record_verification` (verifiable tier only) and `promote` (the sole way to make a Finding: verifier-supported + website/tool_interface attribution + ≥2 independent support refs or a structural proof) change status; a novel hypothesis can never be verified/promoted; proposals need the right basis; approval precedes apply; manual changes are not auto-applicable; replay rebuilds identical state; `outcome()` = findings / experimental_only / no_supported_issue |
| `run.py` | `investigations/<id>/` (git-ignored): `run.json` stage status, write-once artifacts, `approvals.jsonl` bound to the SHA-256 of an exact manifest (changed manifest ⇒ new approval), evidence store, spend `Ledger` (existing class) |
| `pipeline.py` | stage machine: ordered, resumable; failed spending stage never re-run automatically; spending stage in `live` mode runs only after approval of its manifest hash (else `awaiting_approval`, nothing runs); `gate=True` stages need approval in every mode (e.g. applying a fix) |
| `llm/` | `LLMClient` protocol; `ScriptedClient`; `RecordingClient`/`RecordedClient` (offline replay keyed by request hash); `complete_structured` (strict JSON or the existing byte-preserving prose-prefix recovery, bounded retry); `MetaClient` (OpenAI-compatible; only reachable through `MetaClient.live`, which runs the existing `ledger.preflight` and uses the existing `spend_gate.RequestGate` to reserve before send; failures keep the full reservation; key never in errors) |
| `report.py`, `demo.py`, `cli.py` | `investigation-report-v1` (observations / hypotheses by tier / findings / proposals with labels / effects measured-vs-pipeline-check); scripted end-to-end demo; `readiness investigate demo|status|approve` |

Reused unchanged: `ledger.Ledger/preflight/cost_of`, `spend_gate.RequestGate`, `capture.GateRefused`, `compat.recover`, `agent.ModelConfig`, `suite.core.canonical_hash`. Edited outside the new package: `cli.py` (+2 lines: registers the group, not frozen), `.gitignore` (+`investigations/`), STATUS/COLD_START.

## Tests (all offline, no key)
`tests/test_investigate_{evidence,run_pipeline,llm,demo}.py`: **35 tests**, covering the rules above, the reserve-before-send ordering (the request handler observes the reservation already on disk), refusal paths (no flag/key/https/transport ⇒ nothing reserved or sent), a source scan that only `llm/meta.py` may import a network library, durable replay, and the CLI.
Results run locally: fast suite `scripts/dev-tests.sh` **569 passed** (534 before + 35); frozen/pin guard tests (`test_remediation_main_design`, `test_suite_core`, `test_experiment_infra`, `test_profile_v3`, `test_remediation`, `test_remediation_security`, `test_markers`) **136 passed**. Full regression (including browser tests) is left to CI on the PR. `git diff` shows no change to `remediation/`, `scanner/`, `spend_gate.py`, `capture.py`, the budget ledger or any pinned artifact.

## A bug found by the tests
The approved manifest was first stored write-once under the stage name, so a *changed* manifest raised `ArtifactExists` instead of requiring a new approval. Manifests are now stored per content hash (`manifests/<stage>-<hash16>`), and a test pins the behaviour.

## Deviations from the plan
1. `models.py`/`store.py`/`run.py` sit flat in `investigate/` as planned, but the "evidence graph" has no separate `verify.py`/`promote.py` yet: promotion lives in the store (it must, to be enforceable); verifiers arrive in M5.
2. `demo.py` includes a *toy* verifier and a toy site fixture, clearly labelled `scripted`; they are not product features and do not count as verification of anything real.
3. No `LLMCallGate` class: `spend_gate.RequestGate` already accepts any chat body, so `MetaClient` uses it directly (less code, same guarantees).
4. The apply-fix and post-trial stages exist in `pipeline.STAGES` as names only; M1's demo pipeline runs inspect → investigate → recommend → report.

## Not verified / risks
- `MetaClient` has **never contacted the hosted API**. Its request shape follows the public docs and mock-transport tests; real behaviour (strict JSON-schema output, prose-prefix rate, usage reporting, latency) is exactly what the proposed L0 probe would establish. **L0 is not run and needs the owner's approval of the exact probe and cap.**
- The call-count/cost caps and prompt sizes for the investigator are placeholders until M5 measures real prompts.
- CI for this PR runs on the old (serial, ~14 min) workflow because #33 is not merged.

## Next
M2 — generic `inspect` + mirror/snapshot server + patch DSL + site zoo (including the three sealed demonstration sites and the blindness tests). Before M5 the L0 probe is wanted; the first live end-to-end slice (L1) follows M5.
