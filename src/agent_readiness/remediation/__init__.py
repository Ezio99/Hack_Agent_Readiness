"""Autonomous, evidence-grounded diagnosis and remediation guidance (Task 015).

Pipeline: black-box site probe (observed website properties) -> findings -> recommendation library (rule based) -> optional agent-execution evidence from a scan ->
re-audit lifecycle (resolved / persisting / new) -> measured effects ONLY when an experiment supplies them. Nothing in this package reads an experimental-arm label, a
variant id or a demo outcome: every conclusion is derived from what the probe actually observed on the site (or from recorded agent traces)."""
