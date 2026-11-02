"""Research experiment: LLM-generated, business-context-aware task planning for Larkspur, with independent deterministic verification.

context.py     SYNTHETIC business profile (goals, personas, needs, journeys, illustrative weights): assumptions, not customer research
catalogue.py   the verified catalogue view the planner may use (from the site's source records and oracle fields), with a fingerprint
schema.py      the structured proposal format; no expected-answer field is trusted
planner.py     prompt (versioned), clients (fixture | Meta behind an explicit approval), per-item schema validation
verify.py      independent verification with the existing oracle, gate, grader_v2 key and cross-variant check; explicit rejection categories
experiment.py  batch run, comparison with the rule-based generator, preserved artefacts
See docs/research/LLM_TASK_PLANNING.md."""
