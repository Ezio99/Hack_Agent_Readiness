"""Domain vocabulary for goal grounding on the registered rental/shop demo sites: what a goal word like "price" or "available" means in terms of fact labels and pages. Injected into the (domain-neutral)
goal-relevance verifier. Small and explicit on purpose; what it cannot ground is reported as a limitation."""
RENTAL = {
    "price": {"terms": {"price", "prices", "pricing", "cost", "costs", "rate", "rates", "fee", "fees", "charge", "charges", "cheap", "cheapest", "cheaper", "expensive", "afford", "affordable"},
              "labels": {"price", "rate", "cost", "fee", "charge", "daily", "weekly", "day", "week"}, "path_suffix": None,
              "unsupported_note": "no labelled price or rate fact exists on the goal's pages in the captured site (hire rates are not extracted as labelled facts), so price tasks cannot be expressed or verified by the task criteria"},
    "availability": {"terms": {"availability", "available", "free", "booked", "booking", "stock", "calendar", "vacant"}, "labels": {"availability", "available", "booked", "calendar"}, "path_suffix": "/availability",
                     "unsupported_note": "no availability page was found for the goal's entities"},
}
