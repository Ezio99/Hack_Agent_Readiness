# EXP-C-S1 — executed scroll-tolerance sensitivity stage, 2026-11-01

Exactly one authorized paid stage completed, all eight trials retained. Code `b6d7534`, branch `live-m1-llm-evaluation`. No retries, further experiments, merge, push or deployment. Results belong to S1 alone and are not pooled with EXP-C/R1.

Approval manifest: `99f493d1558db5d925069e5ae8ea66fc21e2927e1364a69ddb45ec9ae3a550f8`. Pre-execution assertions verified the current generated manifest against the approved stored manifest, model, original/patched snapshots, four frozen tasks/truths, execution order, zero retries and each cap; verified the fork/imports; required clean tracked code at the reviewed commit and no prior S1 paid approval/reservation. All 2,239 protected historical files matched before and after execution. Untracked superseded prototypes were left alone.

Both contemporary arms used `muse-spark-1.3` and `suite-v2-compat2`, with the declared hashed scroll-only successor policy. Grader, task inputs and both preregistered decision rules were unchanged.

## Outcomes

Passes below are strict independent oracle passes; every pass was also evidence-supported. Every trial ended `completed`, with zero tool errors and zero terminal tool failures.

| Frozen task | Placebo pass | Patched pass | Requests placebo / patched | Patched fallbacks | Cost placebo / patched (US$) |
|---|---|---|---|---:|---|
| Highest refundable deposit (`gen-0a0d1f9340`) | fail | pass | 12 / 6 | 1 | 0.172989 / 0.081314 |
| Deposit below threshold (`gen-4336e8b32f`) | fail | fail | 12 / 11 | 1 | 0.180831 / 0.157896 |
| Delivery required (`gen-660570f215`) | pass | pass | 13 / 7 | 2 | 0.195256 / 0.095398 |
| Two-day minimum (`gen-bbf4a34af3`) | pass | pass | 13 / 5 | 0 | 0.186812 / 0.066993 |
| Total | **2/4** | **3/4** | **50 / 29** | **4** | **0.735888 / 0.401601** |

Four fallback events, all patched, all requested index `1`, all absent from the current map. Each executed the ordinary page scroll with `index=None`, retaining the requested direction/pages; all returned without error. Two of the three tasks that used fallbacks passed; the below-threshold task still produced an incorrect answer. Placebo had no fallbacks. There were no voids, retries or new model-output/tool errors.

## Costs and limits

Additional calculated spend **US$1.137487**; imported history **US$0.864825**; total committed **US$2.002312** of US$2.50. No outstanding reservations and no request settled above its reservation. Calculated cost is not a bill.

Both arms stayed below US$0.80, combined below US$1.60, every trial below US$0.50. Largest settled request cost US$0.019285, below US$0.05; reservations were subject to the unchanged US$0.05 gate. All trials used at most 13 of their 14 frozen model requests. No further spending is authorized.

## Verdicts and interpretation

- Stored frozen `paired-signflip-v1`: **inconclusive**, p(pass)=0.25, p(requests)=0.125. This pipeline result compares the imported compat1 historical baseline against patched compat2, so it is explicitly a sensitivity comparison that changes agent version as well as site.
- Stored preregistered `exploratory-listing-v1`: **not_supported**. The below-threshold task's 12→11 request change misses the 25% floor and does not exceed the noise estimate of one request. No rules were changed.
- Separately archived free descriptive application of the SAME frozen `paired-signflip-v1` to the contemporary placebo vs patched arms: **inconclusive**, p(pass)=1.0, p(requests)=0.125. This supplementary calculation does not replace the stored frozen verdict. At four pairs the minimum request-test p is 0.125.

**Tool reliability:** four observed invalid-index actions were tolerated and useful trials continued; no terminal tool failures occurred. This supports the mechanism working on these encounters. It does not establish a general failure-rate improvement: hosted-model trials are stochastic, there was no paired compat1 counterfactual within S1, and different tool results change the subsequent trajectory.

**Website readiness:** under the same compat2 instrument, patched had 3/4 evidence-supported passes versus placebo 2/4, and used 29 versus 50 requests (42% fewer in aggregate). Those descriptive differences do not meet the frozen or exploratory evidence standard for a website improvement. The owner-selected intervention, one site, four related tasks, n=1 per cell and no unaffected controls limit interpretation. Placebo now passed two tasks that failed in the historical runs; historical differences must not be attributed solely to the scroll correction. No pooling with EXP-C/R1.

## Separate archive and verification

Local, git-ignored S1 root: `scanner-data/live/live-ab-ironbark-s1/`.

- Original paid-stage artifacts: `artifacts/trials/`, `trial-data/`, `artifacts/evaluation.json`, `artifacts/report-final.json`, `approvals.jsonl`, `spend/ledger.jsonl`.
- Read-only derived summary: `archive/s1-results-summary.json`, including the supplementary contemporary frozen-rule calculation.
- Preservation index: `archive/s1-artifact-sha256.json`, covering 700 non-archive S1 files.

EXP-C, R1, source, replay, related live run and compat1 remained byte-identical across 2,239 protected files. Original EXP-C/R1 approval hashes are unchanged. No private truths or raw traces were committed; the programme ledger was not rewritten. No implementation changed, so no new code tests were needed for this execution. The prior offline checks are in Report 016n.

Stopped for owner review. No additional paid call is authorized.
