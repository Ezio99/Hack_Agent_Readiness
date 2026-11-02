"""Phase 4 diagnostics (isolated; nothing in hosted/ imports this package).

Three layers over the same finding schema (`model.Finding`):
  structural   reproducible observations of page semantics, accessible names, navigation, forms, structured data, listing information
  behavioral   observations from recorded trajectories: revisits, loops, retries, dead ends, unnecessary navigation, budget exhaustion,
               unsupported and incorrect answers
  hypotheses   links between the two, with an explicit status: a suspected contributor is a HYPOTHESIS; it is SUPPORTED only when a paired
               comparison of a version without the structural issue was run on a real model and a recorded rule agreed. Nothing is causal by default.
See docs/DIAGNOSTICS.md.
"""
