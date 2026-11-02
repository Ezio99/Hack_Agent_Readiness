"""Task-generation evaluator (versioned, code-only): judges candidate tasks before they enter the browser-agent evaluation workflow.

Hard deterministic gates (any failure excludes the candidate; nothing soft can override them) reuse the unchanged engine: proposal schema, grounding
in the verified catalogue, the criterion language, compile_criterion against the frozen snapshot, the acceptance gate, the site's record oracle,
grader v1 and grader v2, cross-version fairness and evidence pages. Soft judgments (persona and journey relevance, realism, specificity of the
customer wording, novelty) follow explicit, reproducible criteria recorded in a fingerprinted configuration. No LLM judge is used in this version.

Research-stage component (branch research/llm-task-planning): it imports the research planner's verifier; not wired into production.
"""
