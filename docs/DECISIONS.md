# Decisions

> **Implementation checkpoint — 2026-10-26:** This log preserves decisions and
> uncertainties as recorded. Statements below about pending initial framework,
> model, profile and artifact choices describe the earlier planning state.
> Task 001 subsequently implemented Browser Use with one versioned natural-shopping
> profile and verified an OpenAI-backed configuration. See [current status](../STATUS.md)
> and the [Task 001 evidence report](../collaboration/reports/001-first-agent-run.md)
> for actual choices, tested versions and limitations. Meta access/compatibility
> remains unverified. This checkpoint records implementation progress, not a new
> architectural or experimental decision.

Record accepted decisions separately from proposals. Entries below capture the
direction in `Initial_prompt.md`; implementation choices remain open.

## D001 — Evidence before scoring

Status: accepted at kickoff.

Collect raw traces, outcomes, failures, resource use, and environmental metadata
before defining readiness metrics or weighting criteria. Candidate dimensions
are hypotheses, not validated scoring inputs.

## D002 — Begin with e-commerce

Status: accepted at kickoff.

Use shopping tasks as the initial domain because outcomes can be defined and
checked. This does not limit the project's eventual scope. Controlled storefronts
are a candidate starting method; real-site comparisons can follow later.

## D003 — Version the experimental configuration

Status: accepted at kickoff.

Freeze model configuration, instructions, tools, and execution limits within an
experiment. Version benchmark definitions, repeat trials, and evaluate against
independent ground truth. Report agent and environment limitations explicitly.

## D004 — Keep the foundation small

Status: accepted at kickoff.

Prioritize working experiments and diagnostics. Reference agent, runner, recorder,
evaluation, and analysis are logical responsibilities, not required services.
Defer a composite score, registry, polished dashboard, and unnecessary infrastructure.

## Pending decisions

- First controlled intervention and exact task fixtures.
- Model/provider and any hackathon requirements.
- Browser observation mode and tool permissions.
- Language, browser library, execution limits, and artifact format.
- Evaluation contract and pilot repetition count.

See `PROJECT.md` for a concrete first-experiment proposal. It is not yet an
accepted architectural or experimental decision.

## D005 — Configurable agent behaviour profiles

Status: accepted on 2026-10-26.

Design the experiment harness so agent behaviour can be selected through versioned configuration rather than hardcoded into the runner. Keep model, agent implementation/adapter, behaviour policy, task, website variant, limits, and recording configuration conceptually separate. This permits later comparisons of natural-shopping, constrained, visual, or semantic interaction styles without requiring a new harness.

A behaviour profile may specify instructions, tool permissions, observation mode, interaction strategy, and execution limits. Enforce restrictions through tool availability when necessary; prompting alone does not guarantee compliance. Record the effective configuration and freeze it within each experiment.

For the MVP, implement only one behaviour profile. Additional profiles and cross-profile comparisons are future experiments, not immediate scope. The initial agent framework, model, and first profile remain undecided pending available Meta resources and technical validation.

## D006 — Automatic, domain-extensible task generation

Status: accepted in principle on 2026-10-26; detailed implementation design pending.

Treat automatic task generation as a core architectural capability rather than relying on manually authored task lists. The system should be extensible beyond e-commerce without requiring a new hardcoded task catalogue for every domain.

Separate website/capability exploration, task generation, task feasibility validation, reference-agent execution, and independent outcome evaluation. Generated tasks are candidates until validated. Do not confuse plausible LLM-generated tasks with feasible, independently verifiable ones; avoid leaking ground truth or evaluator state to the tested agent.

For the initial MVP, a constrained generator using a controlled storefront and known fixtures is acceptable as a first implementation step, but should not become a shopping-specific architectural assumption. Scope, validation oracles, and support for real websites remain open for discussion.
