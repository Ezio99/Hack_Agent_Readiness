"""Evaluator v2 (taskeval-2): evaluator v1 unchanged plus the natural-wording gate gate-nl-1, the four wording categories, intent preservation,
ambiguity classification, coverage and diversity (lifecycle M2), and the ranked_subset / either_of kinds (M2b).

  lexicon.py    versioned phrase lexicon (attribute classes, comparators, vague quantities, superlatives); never maps phrasing to an invented value
  nl.py         gate-nl-1: traces every specification component to the customer wording and every stated value back to the specification
  evaluator.py  TaskEvaluatorV2 (checks=False reproduces evaluator v1 exactly), public(), distribution(), coverage()
  coverage.py   persona x journey x capability matrix, diversity, provisional targets and gaps
  (suites/stage_a/taskrecords.py maps these records one-to-one onto suites.records; taskeval never imports suites)
  kinds.py      M2b: ranked_subset and either_of through compile, oracle, gate, grader v1 and grader v2

Research-stage (branch research/llm-task-planning); nothing in production imports this package."""
