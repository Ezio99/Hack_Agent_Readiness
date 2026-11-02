"""SYNTHETIC business context for the fictional Larkspur Community College.

Every goal, persona, need, journey and weight below is an ILLUSTRATIVE ASSUMPTION written for this experiment. None of it is customer research,
analytics or survey data, and none of it adds catalogue facts: course facts come only from sites/larkspur/data.py through catalogue.py."""
from __future__ import annotations

from ...suite.core import canonical_hash

LABEL = "SYNTHETIC - illustrative assumptions for a fictional college; not customer research"

CONTEXT = {
    "label": LABEL,
    "business": "Larkspur Community College (fictional): evening and weekend short courses for adults at two campuses.",
    "goals": [
        "Help adults find a course that fits their budget, schedule and level without phoning the office.",
        "Fill places in courses with seats left before the term starts.",
        "Make fees, duration and level easy to compare across courses.",
        "Reduce enquiries about refunds and concessions.",
    ],
    "personas": [
        {"id": "career_switcher", "name": "Career switcher", "needs": "a practical first course in a new field; works weekdays, so the class day matters",
         "constraints": "beginner level; moderate budget; prefers courses that include materials"},
        {"id": "recent_graduate", "name": "Recent graduate", "needs": "an affordable course to add a skill to a CV",
         "constraints": "low budget; flexible on day; short duration preferred"},
        {"id": "budget_learner", "name": "Budget-conscious learner", "needs": "the cheapest suitable option and certainty about refunds",
         "constraints": "fee is the deciding factor; may hold a concession card"},
        {"id": "professional_upskiller", "name": "Professional upskiller", "needs": "an intermediate or advanced course that fits around work",
         "constraints": "level above beginner; specific campus or day; wants to know seats are available"},
    ],
    "journeys": [
        {"id": "find_affordable", "name": "Find a course within budget", "attributes": ["course fee"], "weight": 0.30},
        {"id": "fit_schedule", "name": "Find a course on a day or campus that fits", "attributes": ["class day", "campus"], "weight": 0.25},
        {"id": "match_level", "name": "Find a course at the right level", "attributes": ["level"], "weight": 0.15},
        {"id": "check_availability", "name": "Check that places are still available", "attributes": ["seats left"], "weight": 0.15},
        {"id": "plan_commitment", "name": "Judge the time commitment and what to bring", "attributes": ["duration", "materials"], "weight": 0.10},
        {"id": "understand_policies", "name": "Understand refunds and concessions", "attributes": [], "weight": 0.05},
    ],
    "weights_note": "Journey weights are illustrative priorities chosen for the experiment, not measured traffic or demand.",
}


def fingerprint() -> str:
    return canonical_hash(CONTEXT)


def journeys_for(attributes: set[str]) -> set[str]:
    """Journeys an attribute set touches (the same mapping is applied to rule-based and LLM tasks)."""
    return {j["id"] for j in CONTEXT["journeys"] if set(j["attributes"]) & attributes}
