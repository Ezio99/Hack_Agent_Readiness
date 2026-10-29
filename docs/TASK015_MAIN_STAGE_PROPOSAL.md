# Task 015 — main-stage experiment PROPOSAL (offline; nothing here is approved or executed)

Status 2026-10-29. Prepared offline after the owner approved a corrected proposal. **No model call, no key use, no spend.** The original pilot (manifest, results, frozen gate decision `stop`) is preserved byte-for-byte (pinned by tests) and is not reinterpreted: see [GATE-ERRATUM](../collaboration/experiments/task015/pilot/results/GATE-ERRATUM.md). **Revised after verification (Report 015e):** the earlier proposed manifest `ee2f6e06…` was never approved or run and is superseded by the hash below because verification found defects in the driver (see 015e). Frozen proposed manifest: [`collaboration/experiments/task015/main/manifest.json`](../collaboration/experiments/task015/main/manifest.json), **SHA-256 `<<NEW_HASH>>`**. Validation: [Report 015d](../collaboration/reports/015d-main-stage-offline-validation.md).

## 1. What we learned from the pilot (and what we did not)
One pair: with the recommendation applied the agent passed in 4 requests (using the in-stock filter), without it the agent failed in 11 requests with recall 0.33 after checking stock page by page and running out of its own step budget. Learned: the mechanism is *plausible and observable* (stock invisible on cards ⇒ per-product lookups ⇒ budget exhaustion), the infrastructure (audit → manifest → gated live run → re-audit) works end to end at A$0.32, and the pilot gate was mis-specified. **Not** learned: whether the difference is systematic (n = 1), which part of the bundle matters (the modified run used the filter), or anything about other tasks, sites or models. Structural remediation (the property changed — independently re-audited), observed behaviour (what the agent did) and measured effect (paired outcomes over blocks) remain three separate things; the pilot supplies only the first two.

## 2. The original gate flaw and the corrected prospective gate (`room-to-act-v2`)
**Flaw:** the frozen pilot rule continued only if the unmodified run made ≥ 4 product-page visits or reported an ineligible product. The unmodified run did neither (3 visits, no extra item) yet **failed** on recall — the rule measured visit count, not the oracle-visible signature of the mechanism, and labelled a budget-exhausted failure a "ceiling effect". Recorded: original result `stop`, interpretation wrong; unchanged on disk.
**Corrected rule** (applies only to the `unmodified` T1 runs, non-void, and only prospectively; every criterion is independently measurable from the oracle verdict, request counts, page visits and tool-loop flags):
| id | fires when | independent measure |
|---|---|---|
| R1 | the answer misses ≥ 1 eligible product (recall < 1) | oracle |
| R2 | oracle verdict FAIL and recall < 1 | oracle |
| R3 | ≥ 75 % of the request limit used (≥ 9 of 12) or stop reason `request_limit`, **and** products are missing | request counter + oracle |
| R4 | ≥ 9 requests or ≥ 5 product-page visits **and** no repeated-action loop / tool-visibility gap in the run | counters + trace flags |
| R5 | the answer includes an ineligible (e.g. out-of-stock) product | oracle |
Void runs (budget stop, provider failure, ambiguous timeout, guard violation, interruption) **never** count as room and never as a website result. **Use:** an *interim check* once the unmodified T1 runs of blocks 1 and 2 exist: continue if ≥ 1 shows room; halt as `halt_no_room` (a ceiling finding, reported as such) only if **both** baseline runs are valid and neither shows room; halt as inconclusive if both are void, or one is void and the other shows no room (no replacement, no ceiling claim). It only decides continue/halt — the effect verdict never depends on it.
**Justification:** it keys on what the mechanism predicts and the oracle can check (incomplete or wrong answers, budget exhaustion), not on a proxy. **False positives** (room but not website-related): the agent stops early or misreads the task; its own strategy burns the budget; it verifies exhaustively by temperament; a hallucinated inclusion (R5); tool overhead below the loop detector (e.g. tab switches, repeated `find_elements`). **False negatives:** a lucky complete baseline in both blocks. **Disclosure:** the thresholds (75 %, 5 visits) were chosen after seeing the pilot, so they are post-hoc; they are frozen in the manifest before any main-stage run and are used only for the stop decision. Tests: the pilot's incomplete-answer scenario (now shows room via R1–R4 while the original gate still reads `stop`), 8 parametrised cases, void classes, and the interim decisions.

## 3. Hypothesis, treatment, control, negative control
**Causal question:** does applying the product's recommendation as issued (stock labels on listing cards **plus** an in-stock filter) change the outcome of the frozen stock-dependent set-collection task for the frozen agent on this storefront, and how much is due to the labels alone versus the added filter?
**Isolation (implemented, small):** a new optional website factor `stockfilter` (`off` = labels on cards, no filter). Original variants, ids and pages are unchanged (tests). Three arms, all other factors fixed (catalogue, `specs`, `sku=listing`, task text, oracle, model, `suite-v2-compat1`, limits):
| arm | stock labels on cards | in-stock filter |
|---|---|---|
| `unmodified` (the audited site) | no | no |
| `labels_only` | yes | no |
| `modified` (recommendation as issued; the pilot's treatment) | yes | yes |
**H1 (confirmatory):** `modified` vs `unmodified`: fewer model requests per T1 run with completeness not worse. **H2/H3 (exploratory):** `labels_only` vs `unmodified` and `modified` vs `labels_only`. **Negative control:** T4 (return/delivery policy, stock-independent) in 2 blocks × 3 arms: no arm-related shift (|mean Δ requests| < 2). **It is a coarse diagnostic for LARGE unrelated shifts only** (two blocks per arm): passing it does **not** show that confounding, drift or unrelated effects are absent, and failing it only prevents a `supports` verdict. The product itself recognises the intermediate state: auditing `labels_only` reports `attribute_detail_only:availability` **resolved**, `filter_absent:availability` **persisting**, and recommends the remaining change (`in-stock-filter`) — the iterative loop the dashboard can show.

## 4. Schedule, sample size, stopping rules
24 runs, sequential, frozen in the manifest with seed 20261030: 6 blocks × 3 arms for T1 (18 runs) + 2 control blocks × 3 arms for T4 (6 runs). Block ordering uses **all six permutations of the three arms exactly once**, randomly assigned to blocks, so each arm occupies each position equally often (order and time drift are balanced, not just randomised). **Why 6 blocks:** the smallest number at which a perfectly consistent effect can reach a two-sided exact sign-flip p of 2/64 = 0.031; with one lost block (5 pairs) the best attainable is 0.0625, which still meets the pre-declared ≤ 0.07; with ≤ 4 valid pairs the verdict is forced to *inconclusive*. Fewer blocks cannot support a defensible claim; more would add cost without changing the decision. **Stopping rules (frozen):** stage hard cap A$6.00 (US$4.00); halt on any budget stop, guard/bound violation, two void runs, two parser rejections in a block, or the interim gate (`halt_no_room` / inconclusive baseline); never retry or replace; an attempted run id is never repeated; **a halt is final** — it is persisted (`halt.json`) and re-running the command is refused (continuing needs a new approval); a run that left a ledger marker but no result (driver crash) is recorded as void and halts the stage.

## 5. Metrics and interpretation framework
**Primary (H1):** model requests per T1 run, paired by block (modified − unmodified). **Co-primary safety:** oracle pass-rate/completeness not worse in `modified`. **Secondary:** recall, product-page visits, latency, calculated cost, evidence-backed rate, protocol compliance (raw-valid vs parser-recovered). **Outcome classes:** `completed` and `agent_limit` are analysed; `budget_stop`, `provider_failure`, `ambiguous_timeout`, `guard_violation` are **void** — listed, excluded from estimates, never attributed to the website; the effect record states how many pairs survived. **Pre-declared verdict (H1 only):** *supports* iff ≥ 5 valid pairs, mean Δ requests ≤ −3, mean Δ product-page visits ≤ −2, `modified` pass-rate ≥ `unmodified`, exact two-sided sign-flip p ≤ 0.07 and the negative control within ±2; *not supported* iff mean Δ requests ≥ −1 (≥ 5 pairs); otherwise *inconclusive*. Report per-block deltas (not just means), the count of blocks in which `modified` used fewer requests, and the decomposition descriptively with no multiplicity claims. **Statistic:** exact two-sided sign-flip (randomisation) test over all 2^n sign assignments, zeros and ties handled by the enumeration, unrounded (6 consistent pairs: 0.03125; 5: 0.0625; verified against an independent exact enumeration); p ≤ 0.07 is an exploratory decision criterion, not a conventional 5 % significance claim; with < 5 valid pairs the verdict is *inconclusive* whatever p is. **Uncertainty:** n = 6 pairs; we report effect sizes and per-block values, never "proved"; costs are calculated, not billed.

## 6. Cost in AUD (rate 1 USD = 1.50 AUD, calculated)
| | USD | AUD |
|---|---|---|
| Expected (low – mid – high) | 1.62 – 2.40 – 3.18 | 2.43 – 3.60 – 4.77 |
| Worst case = ledger stage cap (no further request can be reserved above it) | 4.00 | **6.00** |
| Per request / per run caps | 0.05 / 0.50 | 0.075 / 0.75 |
| If the interim gate halts after block 2 (ceiling at baseline) | ≈ 0.8 – 1.2 | ≈ 1.2 – 1.8 |
Basis: pilot actuals (unmodified US$0.161, modified US$0.053), earlier T4 runs (US$0.065–0.095), `labels_only` unobserved (assumed US$0.05–0.15). Programme: spent **A$6.21**, remaining **A$43.79**; after the expected main stage ≈ A$9.8 spent; at the cap A$12.21 spent, **A$37.79 remaining**. The pilot is in the committed programme ledger and is not double-counted. The A$50 ceiling is a limit, not an authorization.

## 7. Risks, confounders, remaining uncertainty
Run-to-run variability dominates at n = 6 (the main risk; blocks and position balance help, not cure). The agent's fixed 12-step limit shapes outcomes (a design constant; results do not transfer to other limits). The `labels_only` arm's behaviour and cost are unobserved. T4 control has only 2 blocks (detects gross shifts only). Gate thresholds are post-hoc (disclosed). Parser recovery (≈ 80 % of responses) is part of the frozen agent. Provider-side drift over the ~25-minute stage is possible. One catalogue, one task family, one model: no generality. The scripted/mock results prove plumbing only. Possible agent learning across runs is excluded (fresh browser/session each run; no memory), but cannot be proven absent in a hosted model.

## 8. The decision this enables
*Supports* ⇒ record the stock-visibility recommendation as **measured on the synthetic store (n = 6 blocks, one model)** and use it as the demo's measured loop; the decomposition tells us whether to keep the bundle or lead with the filter. *Not supported* ⇒ demote the recommendation to "no effect measured" and present the pilot honestly as a favourable single pair that did not replicate — a valid product outcome. *Inconclusive* ⇒ make no effect claim; a further stage would need its own proposal (not automatic). *Halt: no room* ⇒ report that the baseline agent does not struggle on this task and choose a harder task. In every case the autonomous audit → recommendation → resolution loop stands independently of the effect verdict.

## 9. What this experiment cannot establish
Generality across sites, models or tasks; business impact (traffic, revenue); long-run reliability; that every agent behaves like Muse Spark; the cause of individual run differences beyond the logged traces; or that resolution of a finding implies improvement (that is exactly what H1 tests).

## 10. Approval requested (not authorized)
Reviewing this proposal. If approved, the exact command is:
```
uv run readiness remediation-experiment run \
  --manifest collaboration/experiments/task015/main/manifest.json \
  --audit collaboration/experiments/task015/main/audit-baseline.json \
  --root runs/task015 --mode live \
  --approve-manifest-sha256 <<NEW_HASH>> --allow-model-calls
```
valid only while the frozen source files are unchanged (the run halts on drift; any change requires re-planning and re-approval). **No paid call is authorized by this document.**
