# Future architecture (documented 2026-11-02; NOT implemented before the 2026-11-04 feature freeze)

**Positioning (owner decision).** Agent Readiness is primarily a **testing and observability platform** for AI agents interacting with websites. A **public benchmark** and a **capability registry** will be separate products built on the same evaluation infrastructure.

## Target entities

| Entity | What it is | Today (closest existing piece) |
|---|---|---|
| **Site** | a versioned target: definition, versions (frozen snapshots), and for controlled sites an oracle | `framework.site.SiteDefinition`, snapshots, `RecordOracle` |
| **Task / workflow** (first-class) | a stable id, the question or workflow steps, a criterion, a verifiability class, provenance (generated / owner / LLM-proposed), and a validation record; reusable across evaluations | frozen tasks inside a `tasks-manifest` (per run), `framework.generate` classes |
| **Agent profile** | model, endpoint, parameters (e.g. reasoning_effort), prompts and parser, identified by hash | `profiles/*.json` + profile hash; `provenance.model_provenance` |
| **Grader** | versioned; an official version per evaluation, post-hoc rescoring allowed but labelled | grader_v1 (official), grader_v2 (`grading/`), derivation ids |
| **Evaluation** | a **versioned configuration**: site version(s) × task set × agent profile × grader × repetitions × comparison rule, frozen by hash before execution | the hosted runner's manifest (Ironbark-specific), `framework.evaluate.prepare` provenance |
| **Run / trial** | an execution of an evaluation, with evidence, a ledger and results | investigation-run layout (trials, trace, ledger) |
| **Finding** | diagnostics with status and evidence references | `diagnostics.model.Finding` |

## Private evaluations vs public benchmarks (must stay distinct)

- **Private evaluation** (the product): the owner's site and tasks, possibly owner-authored or generated from private context; results visible to the owner; recommendations and diagnostics; exploratory analysis is allowed if it is labelled.
- **Public benchmark** (separate product):
  - task selection is fixed and published in advance;
  - only deterministic, oracle-validated tasks;
  - held-out tasks never shown to agent developers;
  - pre-registered comparison rules and repetition counts with adequate power;
  - publication requires reproducibility (hashes of site versions, tasks, profile and grader), and the private-truth / public-question separation is enforced;
  - no owner-selected changes are presented as findings.
- **Capability registry:** aggregates benchmark results per agent profile. It is never fed by private evaluations.

## Migration path (post-freeze)

1. **Task store.** Promote frozen tasks to stored entities keyed by criterion hash and site version, with their verifiability class and oracle validation.
2. **Evaluation configuration.** Make it an explicit, hash-frozen document (site versions, task ids, profile hash, grader version, repetitions, rule). The hosted Ironbark manifest becomes one instance of it.
3. **Generic hosted executor.** Generalise the executor over evaluation configurations (admission, budget, jail unchanged), so Larkspur or any controlled site can run without Ironbark-specific pinning.
4. **Separate publication pipeline for benchmarks**, with its own task selection and review gate.
