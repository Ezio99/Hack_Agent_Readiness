# Agent Readiness — submission pitch draft

2026-11-01 · owner review required · demonstrated product baseline `1c66a1d` (accepted CI repair), packaging `7df69ce`, recorded demo `018f9fb`. No claim that this documentation commit has completed CI.

## Opening and positioning

**Personal agents need a web they can use reliably. Agent Readiness gives developers evidence about whether an agent can use their site—and a controlled way to test proposed changes.**

Meta's personal-agent vision includes software acting on people's goals across apps and browsers. We ask the complementary infrastructure question: how does a developer know whether that interaction will work on their website? Agent Readiness is a diagnostic layer for the emerging agentic web. We use Muse Spark as a reference instrument to observe tasks, check outcomes and investigate friction. We do not integrate with Meta's production Muse personal agent, represent its exact behavior, claim endorsement, or compete to become a person's assistant. Connection to that vision is our positioning, not a deployed Meta partnership. [Official Muse introduction](https://about.fb.com/news/2026/09/introducing-muse-personal-ai-agent/).

## Project description — draft for the form

Agent Readiness helps website developers understand how AI agents interact with a site. It combines a Muse Spark-powered reference browser agent with independently graded tasks, inspectable evidence, an investigation workflow and controlled retesting of proposed changes. The recorded Ironbark demonstration shows actual actions, a browser-tool fallback and an owner-selected listing intervention. On four frozen tasks, the contemporary unmodified and patched arms had 2/4 and 3/4 evidence-supported passes and used 50 and 29 model requests. These are descriptive differences: website improvement was not established. The frozen verdict is inconclusive and the preregistered exploratory verdict is not supported. The dashboard runs without a model or backend during playback and distinguishes recorded real-model, fixture and unknown provenance. Our longer-term vision is reusable diagnostic infrastructure for the agentic web; general website coverage, a readiness registry and commercial impact remain unvalidated.

## Original vision reconciled with the delivered product

| Vision / original pitch | Implemented or observed now | Boundary to state |
|---|---|---|
| Developer evidence → recommendation → site change → retest | Investigation pipeline, independent criteria/grading, hypothesis verification, patch templates, retests and recorded reports | S1's demonstrated intervention is owner-selected, not an independently verified recommendation |
| Automatic task generation across domains | Muse candidate-generation path plus deterministic answerability/goal gates; optional documentation term-value criteria | S1's four tasks are **owner-authored**. An earlier real taskgen smoke exposed relevance problems; later generator changes were tested offline. Do not claim that smoke validates the current entire generator or that S1 demonstrates autonomous task generation |
| Explain where agents struggle | Captured actions/observations, independent outcomes, investigation loop, safe nine-event storyboard | A tool error, an incorrect output and website friction are different. Not every failure has an established cause |
| Controlled before/after measurement | Separate placebo and patched compat2 arms, frozen truths/order/model/grader; original verdicts preserved | n=1 per task per arm, four related tasks, owner-selected intervention; no general or statistically established website improvement |
| General web infrastructure | Registered Ironbark and saved Flask documentation targets; reusable pipeline abstractions | No arbitrary-URL product flow. Flask evidence is dev-provider plumbing; long-page evidence support is unresolved, not validated real-model success |
| Registry / readiness API / universal score | Future vision only | No shipped registry, integration with personal-agent platforms, validated ROI, customers or universal score |

## Muse Spark: essential measurement roles

| Role | What Muse Spark does | What independent code does | Evidence and limitation |
|---|---|---|---|
| Task generation | Proposes structured tasks using captured site context and the requested goal | Compiles criteria, derives expected values, gates answerability/relevance and freezes accepted tasks separately from truth | `investigate/taskgen/propose.py`, `gate.py`, `goal.py`; [real earlier smoke](LIVE_SMOKE_TEST.md). S1 instead uses four frozen owner-authored tasks |
| Reference browsing | Chooses browser actions from page/DOM and screenshot observations using `muse-spark-1.3` | Executes through Browser Use, records events, enforces limits and grades strict correctness plus required evidence | `agent.py`, `investigate/trials/runner.py`; [S1 results](../collaboration/reports/016o-exp-c-s1-results.md). This is our reference configuration, not production Muse |
| Investigation | Chooses evidence tools, forms hypotheses and decides when to finish | Executes read-only tools, checks citations and supported claim types; promotion needs independent support | `investigate/investigator/loop.py`, `verifiers.py`; archived source/replay investigator records confirm real Muse requests. In the demonstrated S1 case there are zero verified findings; its change is not an autonomous verified diagnosis |

S1 imported prior tasks/investigation; it did not rerun task generation or the investigator. The current video demonstrates recorded browser behavior and retest evidence, with the wider pipeline explained accurately. Model self-assessment never determines a pass. Protocol compatibility, spending gates and sanitized export are application engineering, not new Meta model capabilities.

## Rubric alignment and candid assessment

Weights below are the owner's supplied rubric, corroborated by the October 28 pitch's account of participant screenshots. The separate `Meta_Global_Hackathon_2026_Reference.md` and original screenshots were not found in this checkout/local search; current participant-form wording is unverified. This is a positioning assessment, not a predicted judge score.

| Criterion | Weight | Judge-facing argument / evidence | Remaining limitation / presentation choice |
|---|---:|---|---|
| Impact | 30% | Developers need to know whether agents can find and verify information. Evidence helps decide what to investigate or test, including when a proposed improvement is not supported | Commercial demand, ROI and broad generality unproven. Explain the developer decision; do not invent adoption numbers or promise lower costs |
| Meta AI Tooling | 25% | Muse Spark is in the measurement loop: candidate generation, actual browser decisions and evidence investigation, with independent checks around it | Distinguish implemented generator from S1 owner tasks and imported investigator; no production personal-agent integration claim. Spend meaningful narration time on this rather than just displaying a logo |
| Demo | 25% | Reliable backend-free recorded S1 opening; nine actual event summaries; strict/evidence-supported labels; 2/4→3/4 and 50→29 contemporary comparison with original verdicts | This public asset intentionally omits captured pages, so do not promise a visual page diff or click a nonexistent diff button. Recorded demo is not a fresh run or full raw replay |
| Technical Depth & Execution | 20% | Frozen tasks/truths, separate reference configuration, independent evaluator, control-integrity checks, durable spending gates, safe export, complete sharded CI at `1c66a1d` | Historical compat1 baseline vs compat2 patched is confounded; contemporary arms share compat2. CI tests plumbing/behavior, not broad scientific validity. Show developer trust rather than recite infrastructure |

## What the S1 result means

Contemporary unmodified repeat (placebo): **2/4 evidence-supported and strict passes; 50 requests**. Patched: **3/4 evidence-supported and strict passes; 29 requests**. All eight trials completed; four successful scroll fallbacks occurred in patched trials, no terminal tool failures. Additional US$1.137487 is calculated from reported usage, not a bill.

Stored frozen rule: **inconclusive**. Preregistered exploratory rule: **not_supported**. A supplementary application of the unchanged frozen rule to the contemporary pair is also inconclusive. The stored frozen comparison uses an imported compat1 baseline, unlike both contemporary compat2 arms; do not conflate them. EXP-C/R1 remain separate experiments. Do not describe 50→29 as a proven effect of the site change or pool the trials into a larger sample.

Verification vocabulary: a structural observation can be independently checked; a verified finding can support a proposed recommendation; the recommendation's effect is still unvalidated until adequate controlled evidence supports it. **S1 has no verified findings and no established beneficial intervention.** The owner selected the three-field listing change after seeing baseline failures. Independent grading verifies outcomes, not that the recommendation was correct.

## Hackathon work versus pre-existing components

| Category | Provenance / exact claim |
|---|---|
| Fresh hackathon implementation in this repository | Application storefronts, task/evaluator contracts, Meta adapter and compatibility handling, snapshots/mirrors, investigation/generation/verification pipeline, controlled experiment drivers, dashboard, safe storyboard/export, profile succession, packaging and tests were implemented here starting 2026-10-27 Sydney. Historical within-event experiments are preserved, not newly rerun for this pitch |
| New within-event evidence | Real Muse browser trials and investigations, including separate EXP-C/R1/S1; latest demo packages already recorded S1. No experiment was run for the video or pitch |
| Pre-event planning/prototype | `Ezio99/Agent_Readiness` supplied planning/design context and historical specification documents. [HACKATHON-START](../collaboration/reports/HACKATHON-START.md) records no executable source, tests, CI/configuration or old run artifacts copied into this fresh implementation. Do not change creation dates or represent pre-event results as event work |
| Existing third-party technology | Meta Muse Spark/model service, Browser Use 0.11.13, Chromium/Playwright, Python/FastAPI, React/TypeScript/Vite and other locked dependencies. We built the integration/application, not these models, browser engine or frameworks |
| Existing third-party content | Flask documentation/build tooling is external open-source material, identified as BSD-3 in target documentation. We added saved-snapshot capture/configuration, not Flask or its documentation. Preserve applicable notices; no paid Flask capability claim |
| Future work | Multi-site/platform generality, registry/API, production-agent integration, commercial validation. Not delivered or promised by this submission |

An event-start timestamp, final reuse/license policy and contributor eligibility still need confirmation against participant rules. The repository's record of development dates is evidence, not an organizer eligibility ruling.

## Only essential remaining work

1. Confirm participant form/rules, video limit, links, team disclosures and deadline; see [submission plan](SUBMISSION_PLAN.md).
2. Rehearse and record the [three-minute script](THREE_MINUTE_DEMO_SCRIPT.md), then review narration/links/captions. No experiments needed.
3. Confirm exact repository commit/access/license and contributor list. Keep ignored truths/traces out; the submitted branch remains unmerged until separately authorized.
4. If a live public URL is required, seek explicit hosting approval and use the validated static package; no model/backend deployment is needed for the recorded demo.

No product feature, new evidence run, benchmark change or generalization claim is essential to finish this submission.
