> **Provenance:** Pre-hackathon design specification, retained as reference. No Gate 1 review or acceptance criterion has been completed in this hackathon repository. Reassess the gate sequence after the new Task 001 implementation.

# Task 002 — Interaction-Dependent Shopping Benchmark

**Project:** Agent Readiness  
**Status:** Proposed — Gate 1 pending  
**Implementation owner:** Codex  
**Approval authority:** User

## 1. Intent

Task 001 established an end-to-end browser-agent benchmark. However, the initial storefront exposed enough information for agents to answer tasks without meaningful navigation.

Task 002 will make the benchmark capable of testing genuine website navigation rather than merely extracting information from an initial observation.

The goal is to strengthen experimental validity, not optimize agent performance or demonstrate that one website design is superior.

## 2. Approved scope

Extend the existing controlled storefront while preserving Task 001's architecture and approximately 20 synthetic products.

- Introduce navigable product-detail pages.
- Limit listing-page information to product name, brand, category, price, and detail links.
- Reserve product ID and stock availability for detail pages.
- Preserve feasible discovery and availability tasks.
- Preserve independent inventory-based evaluation.
- Record evidence of navigation and interaction.
- Maintain existing functionality wherever practical.

## 3. Information boundary

The initial listing must not reveal product IDs or stock availability through visible text, hidden DOM, accessible labels, embedded JSON, data attributes, or equivalent browser-agent-accessible content.

Detail pages must expose the required fields through ordinary navigation.

Avoid URLs that directly reveal answer-bearing product IDs. Do not degrade accessibility artificially.

Verify the boundary using the actual observation mechanisms available to the reference agent.

## 4. Task and evaluation design

Availability tasks should require locating a named product and retrieving its ID and availability from its detail page.

Discovery tasks should require identifying eligible candidates from listing information and obtaining the missing answer fields through further interaction.

Keep seeded task generation deterministic and independently feasible.

Continue evaluating structured answers against inventory truth. Do not require particular UI actions to pass; legitimate alternative navigation paths remain valid.

Track outcome correctness separately from interaction behaviour.

## 5. Evidence and instrumentation

Saved artifacts should allow reviewers to determine:

- Pages visited and detail-page access
- Search and filter usage where applicable
- Action count, step count, elapsed time, and reported token usage
- Execution status, stop reason, and errors
- Final structured answer and independent evaluation result

Reuse existing instrumentation where sufficient. Add only what is necessary to make navigation evidence inspectable.

## 6. Acceptance checklist

### A. Functional correctness

- [ ] A1 — Product-detail pages are accessible through normal browser navigation.
- [ ] A2 — Listing pages do not directly expose product IDs or stock availability.
- [ ] A3 — Listing, detail pages, task generation, and evaluator use consistent inventory truth.
- [ ] A4 — Discovery and availability tasks remain feasible and unambiguous.
- [ ] A5 — Existing evaluation behaviour and relevant Task 001 functionality remain intact.

### B. Information-boundary verification

- [ ] B1 — Automated tests check for answer leakage in initial listing observations.
- [ ] B2 — Tests cover browser-agent-accessible content, not only visible HTML.
- [ ] B3 — At least one generated task cannot be fully answered from the initial listing.
- [ ] B4 — No unintended page payload or exposed endpoint makes the complete answer available without further interaction.

### C. Experimental validation

- [ ] C1 — Credential-free browser smoke test demonstrates detail-page navigation.
- [ ] C2 — At least one approved live reference-agent trial completes an interaction-dependent task.
- [ ] C3 — Saved trace demonstrates access to information beyond the initial listing.
- [ ] C4 — Independent evaluator correctly grades the live result.
- [ ] C5 — All attempted live runs, including failures, are preserved and reported.

### D. Reproducibility and engineering quality

- [ ] D1 — Seeded task generation remains deterministic.
- [ ] D2 — Run artifacts retain task, inventory, configuration, model, and execution provenance.
- [ ] D3 — Existing and new automated tests pass.
- [ ] D4 — CI and credential-free smoke checks pass.
- [ ] D5 — Changes to schemas, task IDs, and baseline comparability are documented.
- [ ] D6 — No credentials, secrets, or raw sensitive artifacts are committed.

**Completion rule:** All 20 acceptance criteria must be verified with evidence before Task 002 can be marked complete. Unverified items remain unchecked. An exception requires explicit user approval and a documented reason.

## 7. Exclusions and constraints

Task 002 does not authorize external website crawling, checkout, purchases, accounts, public registries, dashboards, composite scores, additional agent profiles, model comparisons, accessible-label A/B interventions, large-scale trials, or broad architectural rewrites.

Prefer the smallest coherent changes to the existing codebase. Do not alter independent evaluation to accommodate agent behaviour.

## 8. Execution gates

### Gate 1 — Read-only design review

- [ ] G1.1 — Read collaboration instructions, project status, decisions, and Task 001 report.
- [ ] G1.2 — Inspect storefront, task generator, evaluator, adapter, and recorder.
- [ ] G1.3 — Identify current information leaks.
- [ ] G1.4 — Propose minimal file-level changes.
- [ ] G1.5 — Identify compatibility and reproducibility risks.
- [ ] G1.6 — Propose boundary tests and verification commands.
- [ ] G1.7 — Submit findings and obtain explicit approval.

**Stop after the review. No file changes or paid experiments.**

### Gate 2 — Implementation

- [ ] G2.1 — Work on a dedicated Task 002 branch.
- [ ] G2.2 — Implement approved changes only.
- [ ] G2.3 — Add focused automated tests.
- [ ] G2.4 — Run credential-free checks.
- [ ] G2.5 — Document changes and limitations.
- [ ] G2.6 — Obtain approval for live validation.

### Gate 3 — Experimental validation

- [ ] G3.1 — Run approved live trials.
- [ ] G3.2 — Preserve complete run evidence.
- [ ] G3.3 — Inspect navigation traces.
- [ ] G3.4 — Verify independent evaluation.
- [ ] G3.5 — Report failures and limitations.
- [ ] G3.6 — Obtain approval for final review.

### Gate 4 — Review and handoff

- [ ] G4.1 — Complete the acceptance checklist with supporting evidence.
- [ ] G4.2 — Update task report and project status.
- [ ] G4.3 — Open a pull request for review.
- [ ] G4.4 — Obtain user approval before merge.
- [ ] G4.5 — Record merge and final task status.

## 9. Definition of done

Task 002 is complete when all acceptance criteria are verified, all execution gates are satisfied, and the user has approved the final result.

The deliverable is an independently inspectable benchmark demonstrating that an agent can navigate to obtain information unavailable in its initial storefront observation.
