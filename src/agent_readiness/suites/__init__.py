"""Two-stage evaluation lifecycle (collaboration/proposals/two-stage-evaluation-lifecycle.md). M1: immutable records, a write-once content-addressed
store, canonical hashes and provenance, public/private separation, and the Stage A / Stage B boundary.

  records.py   frozen record types: TaskRecord, PrivateOutcome, SuiteRecord, Approval, FrozenSuite, EvaluationManifest, RunResult
  store.py     WriteOnceStore: content-addressed, read-only files, tamper detection on read, private outcomes in a separate 0700 directory
  boundary.py  Stage A isolation: forbidden imports and forbidden input kinds (Stage A may never see agent outcomes)

Isolated research work: nothing in hosted/, the frozen experiments or the release candidate imports this package.
"""
