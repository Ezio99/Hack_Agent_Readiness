"""Stage B of the two-stage lifecycle: evaluation of an APPROVED, FROZEN suite (lifecycle M5).

  manifest.py   EvaluationManifest builder (frozen suite by hash, variants with snapshot hashes, conditions, oracle and graders, agent configuration,
                repetitions, seed, pre-registered plan, worst-case budget) and regression manifests on new snapshots with a diff
  runner.py     prepare (one standard investigation run per wording condition; snapshot-specific validity per variant) -> execute (jailed Chromium,
                reserve-before-send gate, counterbalanced from the seed, no retries, halt on void or bound violation) -> results (official grader v1,
                post-hoc grader v2, pre-registered / exploratory / diagnostics sections, RunResult records) -> public-artifact leak audit
  rehearse.py   zero-cost end-to-end rehearsal on Larkspur and Ironbark (fixture generators, a SYNTHETIC approval, the loopback dev provider)

Stage A never imports this package (suites.boundary). Paid execution is refused: it needs a separate owner approval mechanism (M6)."""
