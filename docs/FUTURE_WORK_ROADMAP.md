# Agent Readiness — Roadmap & Future Work

**Updated:** 2026-10-29  
**Status:** strategic backlog, not an implementation authorization.  
**Source of truth for current execution:** [STATUS.md](../STATUS.md). Task 015's approved experiment and gates remain governed by [its specification](TASK015_REMEDIATION_EXPERIMENT_SPEC.md) once merged. This roadmap does **not** authorize paid inference, merges, public deployment, or release of private traces.

## Product thesis

Build a developer-facing system that **observes how websites expose information to AI agents, identifies evidence-grounded friction, proposes remediations, and measures whether those remediations improve agent outcomes**. Over time, accumulate a reusable, reproducible knowledge base of website design patterns that help or hinder agents.

Keep three statements separate in every report:
1. **Observed website property** — independently reproducible evidence from the page.
2. **Proposed causal explanation and intervention** — hypothesis, with explicit confidence and possible alternative causes.
3. **Measured agent effect** — independently evaluated outcomes from controlled runs, with scope and uncertainty.

A resolved website finding is not automatically a demonstrated agent improvement. An agent failure is not automatically a website defect.

## Horizon 0 — Complete the core hackathon submission (P0)

- [ ] **Task 015 pilot driver, offline:** connect product-generated audit and recommendation IDs to a frozen experiment schedule, independent oracle, AUD-aware stage ledger, and durable request reservations. Test failures, missing usage, interruption, and provenance.
- [ ] **Separately approved paid pilot:** determine whether the baseline has measurable room for improvement; do not execute without explicit approval. Review pilot before deciding on further runs.
- [ ] **Controlled remediation evaluation:** compare stock-on-listing vs detail-only with SKU and all other factors held constant; include stock-independent negative control. Predefine metrics, stopping conditions and limitations. Do not confuse Task 007 replication with novel discovery.
- [ ] **End-to-end demonstration:** scan → product-generated recommendation → operator change → rescan → attach measured effect (only if actually measured). Show evidence, risks, and uncertainty prominently.
- [ ] **Submission polish:** short credible story, reproducible demo, safe public artifacts, documentation and a 3-minute presentation. Prioritize reliability and clarity over adding features.

**Decision gate:** The demo must work without hardcoded variant labels, manual recommendation selection, or unsupported improvement claims.

## Horizon 1 — Hackathon stretch goals (P1; only after P0 is stable)

| Candidate | Smallest credible slice | Value | Gate |
| --- | --- | --- | --- |
| **Hybrid LLM investigator + rule engine** | Give a model a sanitized agent trace and audit observations; ask for one *candidate* friction hypothesis, supporting evidence references, alternatives and a verification plan. Deterministic checks verify evidence references; never auto-promote to a proven recommendation. | Demonstrates discovery beyond two prewritten rules. | Offline prototype first; separate paid approval if model calls required. |
| **Second, genuinely distinct remediation** | Validate a SKU-visibility or structured-specification issue on a task where it matters, rather than only repeating stock placement. | Shows the engine is reusable across issue classes. | Require a clear objective, independent oracle, controlled intervention and sufficient time. |
| **Recommendation evidence registry v1** | Persist rule ID, finding fingerprint, site/task/agent scope, supporting trace references, intervention, risks, validation state and linked experiment results. | Makes credibility visible and lays groundwork for learning across audits. | No unsupported cross-site generalization. |
| **Better before/after UI** | Side-by-side observation counts, cited evidence, original recommendation, resolved/persisting/indeterminate status, and separately measured outcomes. | Strong demo communication with little new inference cost. | Must not render mock outcomes as live measurements. |
| **Agent-friction discovery candidates** | Surface recurring list→detail→list navigation and similar trace patterns as *hypotheses*, not proven site problems. | Bridges diagnostics and autonomous discovery. | Attribute cause only after verification. |

**Stretch selection rule:** Choose at most one or two that demonstrably strengthen the core story. No stretch goal should delay P0 or silently consume the A$50 programme ceiling.

## Horizon 2 — Post-hackathon product roadmap (P2)

### Hybrid evidence-first recommendation architecture
- **Deterministic rules:** versioned, inspectable detectors for known properties; explicit coverage, thresholds, evidence pointers, and reproducible tests.
- **LLM investigation:** propose novel failure modes and remediation hypotheses from observed traces and page data; cite exact evidence, list competing explanations, and specify falsification tests.
- **Evidence validator:** independently check cited URLs, elements, counts, and trace spans; reject unsupported claims or mark them as unresolved.
- **Provisional rule authoring:** convert promising hypotheses into candidate detectors; test against multiple markup families and negative cases before promoting.
- **Human governance:** review rule changes, audit false positives, preserve version history and roll back regressions. Do not let model-generated prose masquerade as verified evidence.

### Recommendation maturity and provenance
Track **diagnostic confidence** separately from **intervention effectiveness**. Useful statuses include hypothesis, observed/reproducible diagnosis, site/task-specific experimental support, and cross-site/agent replication. Also record contradictory evidence and null results. A strong diagnosis may still have an unproven fix.

### Real-world website coverage
- JavaScript-rendered sites and SPA navigation through browser instrumentation, while preserving the cheaper HTTP probe when adequate.
- More robust product-card extraction, schema.org/JSON-LD, accessibility-tree cues, dynamic stock and variant selection.
- Safe, permissioned scanning: strict origin and network boundaries, robots/terms awareness, bounded traffic, sensitive-data redaction, no unauthorized checkout/account actions.
- Calibration and abstention when coverage is insufficient; distinguish scanner/tool failures from website issues.

### Wider evaluation
- More shopping tasks and agents; compare success, correctness, tool calls, navigation, latency, cost, and robustness.
- Controlled website interventions with matched tasks and frozen configurations; replication across sites and agent families.
- Counterfactuals and negative controls to separate website effects from agent strategy, browser tooling, or model variation.
- Developer-facing API, CI integration, and regression checks after site changes.

## Horizon 3 — Ambitious research and platform bets (P3)

### Shared Agent Readiness registry / API
A reusable public catalogue of website readiness findings, test coverage, timestamps, evidence summaries and confidence levels, so agents and developers need not repeatedly audit the same site. Requires freshness policies, owner opt-out/corrections, permissions, and a defensible methodology. **Do not reduce this to an opaque composite score before the underlying metrics are validated.**

### Agent-aware website design and standards
Investigate whether websites should offer dedicated machine-readable agent interfaces alongside human pages, or eventually agent-first surfaces. Compare ordinary HTML, structured metadata, APIs, and explicit agent-facing routes under equivalent tasks. Study discoverability, content parity, authorization, provenance and abuse resistance. Avoid assuming one architecture will win.

### Recommendation-inclusion and commercial impact
Test whether poor agent accessibility causes a product or site to be missed, misrepresented, or excluded from an AI shopping agent's shortlist. Use a controlled consumer-side shopping agent and independent catalogue ground truth; separate agent recommendation bias from website discoverability. Longer-term commercial value may lie here, but evidence must precede claims about revenue or rankings.

### Self-improving remediation knowledge base
Aggregate intervention outcomes across sites, tasks, agent versions and time; learn when particular fixes help, do nothing or backfire. Surface calibrated recommendations with explicit transfer limits, drift detection and counterexamples. Preserve original evidence and failed experiments.

### Automated remediation assistant
Generate candidate website changes (e.g., structured product attributes, filters, accessibility fixes), preview diffs, and run sandboxed before/after evaluation. Human approval remains required for changes to production websites. Consider integrations with developer workflows and CI.

### Beyond e-commerce
Extend the measurement framework to travel, services, documentation, public information, and authenticated workflows only where safe and permissioned. Define domain-specific oracles rather than pretending that one shopping score generalizes universally.

## Non-goals and guardrails

- Do **not** present a generic LLM-generated SEO checklist as evidence-grounded diagnosis.
- Do **not** equate a website property's resolution with measured improvement.
- Do **not** automatically promote an LLM hypothesis into a validated rule.
- Do **not** conflate the single successful WebArena Magento run with a reliability estimate or a proven causal website defect.
- Do **not** expand scope or spend merely because implementation is fast or budget remains.
- Keep raw private traces, credentials and replay data out of public artifacts unless separately reviewed and approved.

## Prioritization principle

Optimize for **decision-relevant information gained per unit of time and spend**, not for exhausting the budget or minimizing cost at all costs. Before any paid experiment, state the uncertainty, the decision it will inform, the cheapest credible design, predeclared stop conditions, and the applicable per-request/run/stage/programme limits. The A$50 budget is a ceiling, **not spending authorization**.

## Development velocity log (reported; not a performance benchmark)

- **2026-10-29 — Task 015b:** owner reports approximately **35 minutes** for the offline experiment driver and associated work: PR #22 security/integration review and fixes, frozen pilot manifest, dry run, and **32 additional Python tests** (590 → 622). PR #24 opened; paid pilot not run at the time of this record. This is an owner-reported elapsed time, not independently timed or a claim of scientific validity.
