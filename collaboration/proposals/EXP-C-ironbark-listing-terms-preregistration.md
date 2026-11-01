# EXP-C — Ironbark listing-card terms: pre-registration (OFFLINE PREPARATION; nothing paid has run)

Status: **proposed, not approved.** No model call has been made for this experiment. The hashes below are reproducible with `readiness live ab-experiment` (free) and are what a person would approve before any spend.

## Question
Does showing three facts (`refundable deposit`, `minimum hire`, `delivery and collection`) directly on the Ironbark listing cards reduce the effort an AI agent needs for the four frozen comparison tasks, or improve completion?

## Standing of the change
`EXPERIMENTAL — OWNER-SELECTED change; not an investigator-verified finding.` The investigator never verified a typed claim for this pattern (its replay produced one unverified open-ended hypothesis); the measured site property (0 of 16 cards show these fields, all 16 item pages do) is an observation, not a verified finding. The change was chosen after the owner saw the four baseline failures, so the investigation tasks are favourable by construction and the holdout is not blind to the owner.

## Identities
| item | value |
|---|---|
| source run (real model, archived) | `live-2d58a80e14`: model `muse-spark-1.3`, profile `suite-v2-compat1`, 4 frozen tasks, 4 baseline trials (all failed, 12-13 of 14 requests) |
| original snapshot (baseline, never modified) | `d2824b210ed9e9d85dac527eb0b4eeb519540a70a7c59ff8690c204ff677538f` |
| modified snapshot (mirror only) | `40c5d886963c925a7b99ff721d7971d5ebacbc52d0237d9549febe301d74f1ed` (parent recorded) |
| tasks manifest | `1c0f546ef0b0588cdc6a81ab7abb6d0e70bbe9d01487b4f9856ccd8ed979dd95` |
| proposal / patch | `prp-2f3f998f8a` / patch `406c0240d5a316889d1cbfa7dc819f368778d30d5ea4a099b2b4dfd0e00d940e` |
| `apply_fix` manifest | `ac07d360c349cc73765c99b4d2b30300cd19ebe3d18279b7cf6c81bf72c0d8f2` |
| `post_trials` manifest | `05053088ef81a2ae2c0c4cce34bef74306416ff9b7e978281b7d93cbbf087d8c` |
| exploratory rules (`exploratory-listing-v1`) | `f8c25e461c64eb87c0bd77c5e0a38dce0a5721ddfd471a2d2eb35efc4aa6ea99` |
| frozen rule | `paired-signflip-v1` (unchanged) |

## Intervention (exactly)
One `copy_field_to_listing` patch with three operations. On the 9 listing pages (`/`, `/hire`, four category pages, three sort views) every machine card gains three `<p>` lines: `Refundable deposit: …`, `Minimum hire: …`, `Delivery and collection: …`, each the value on that machine's own detail page. 252 lines, 6,688 bytes, no attributes, classes, ids or markers; after removing the lines each page is byte-identical to the original. Item pages (which state the fields themselves) and `/kits` (bundles) are untouched. Nothing is invented: a patch cannot insert text that does not already exist on the site.

## Design
* Arms: **baseline** (imported, historical), **placebo** (unmodified repeat, same snapshot/instances/limits), **patched** (modified snapshot; criteria re-derived on it, same questions and expected answers — all four verified unchanged).
* One trial per task per arm, K = 1. Order fixed and hashed in the manifest, counterbalanced (placebo-first / patched-first alternately). Control integrity (model, profile, schemas, limits, and for the placebo the snapshot) is checked after every trial against the baseline trial; a mismatch stops the stage.
* All four tasks are *affected* tasks. There is no unaffected control in this frozen set; this is a limitation, not a feature.
* The investigator is not run on any patched or placebo evidence; hypothesis and prediction text exist only in the evidence store, never in an agent prompt.

## Outcomes (all from existing records)
Task success; evidence-supported success (`passed` and `evidence_backed`); model requests; page views; extra page views (page views minus the minimum); step-budget exhaustion (requests at or near the 14-request limit); attribution class; calculated cost.

## Decision rules
* **Frozen `paired-signflip-v1`**, unchanged, reported unchanged. With four pairs the smallest exact sign-flip p is 2/16 = 0.125, above alpha 0.10, so the pass-delta route to `improvement` is closed and the expected verdict is `inconclusive` unless request reductions are uniform enough for p ≤ 0.10 (they cannot be at n = 4). This is known in advance.
* **`exploratory-listing-v1`** (hashed above) is the only rule that can support the hypothesis, and only as `consistent_with_h1`: for every task, patched requests ≤ 75 % of the placebo's, the reduction exceeds the noise estimate (max |placebo − historical|), patched page views < placebo, no evidence-backed pass lost. Any conflict between the placebo and the historical comparison, or a drift flag, yields no claim.
* Allowed wording: "consistent with / not consistent with a reduction in browsing effort for this exploratory change on this site, these tasks and this model". Never "proved" or a general improvement.

## Fold analysis (free, done before this proposal)
Agent profile viewport 1280x960. Model-visible `/hire` view (Browser Use `llm_representation`): original 9 machine names, 0 fields; modified 6 machines with all three fields each (first view). Scrolling one viewport at a time reveals all 16 names by view 3 on the original (still no fields) and all 16 machines' three fields by view 4 on the modified page. Page height 4,203 → 4,636 px (+10 %), card height 514 → 586 px. The penalty (first-view coverage 9 → 6 machines, one more scroll to enumerate) is small against the removed need to open 16 detail pages; the experiment, not this analysis, measures whether the agent uses it.

## Budget (calculated at published prices, not a bill)
Imported spend 0.864825. Arm caps: placebo 0.80, patched 0.80, combined 1.60; per trial 0.50; per request 0.05; ledger ceiling 2.50 (imported + combined, rounded up to 5 cents). Baseline trials cost 0.17-0.20 each. **Expected** about 0.74 (placebo) + 0.12-0.35 (patched) ≈ US$0.9-1.1; **hard maximum** US$1.60 additional. A refused trial is void and halts the stage.

## Confounders and limitations
Model nondeterminism (n = 1 per cell; the placebo estimates drift but cannot remove it); sequential not simultaneous trials; a script-stripped mirror, not a change to a live site; the viewport/scroll interaction above; four tasks of one family, none unaffected; one site, one model, one agent profile; the owner chose the change after seeing the baseline; the dev-provider run of this pipeline is plumbing only and says nothing about an effect.

## Procedure (a person runs the paid step)
```
readiness live ab-experiment --id live-ab-ironbark                                   # free: prints the apply_fix manifest + hash
readiness live ab-experiment --id live-ab-ironbark --approve-hash <apply_fix hash>   # free: records that approval, prints the post_trials manifest + hash
readiness live ab-experiment --id live-ab-ironbark --approve-hash <apply_fix hash> --approve-hash <post_trials hash> --allow-model-calls   # PAID, only after explicit approval
```
