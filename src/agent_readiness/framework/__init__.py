"""Reusable website-evaluation framework (Phase 3; isolated).

Separates what is site-specific (a `SiteDefinition`: variants, start page, an independent `Oracle` over the site's own source data) from the
evaluation engine (profile -> rule-based task candidates -> acceptance gate -> oracle cross-check -> verifiability class -> frozen manifest for the
existing trial/grading pipeline). Only DETERMINISTIC, independently validated tasks are eligible for readiness scores.

Isolation: nothing in `hosted/` imports this package; the production Ironbark evaluation is unchanged until this is validated and reviewed.
See docs/FRAMEWORK.md.
"""
