"""Versioned answer graders for frozen generated-criteria tasks.

grader_v1 is `investigate.taskgen.criteria.grade` (unchanged; it produced every recorded grade and pre-registered verdict).
grader_v2 (`grading.v2`) is a separate, deterministic grader that accepts a correct answer carrying supporting detail that is consistent with
the site's own ground truth, and still refuses wrong, ambiguous, contradictory, hedged or multiple-candidate answers. `grading.rescore` applies
v2 to recorded answers post hoc, writing labelled documents beside (never over) the original evidence.
"""
