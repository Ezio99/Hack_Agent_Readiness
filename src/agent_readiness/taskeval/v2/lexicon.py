"""gate-nl-1 lexicon (versioned; part of the evaluator-v2 configuration fingerprint).

The lexicon maps customer phrasing to ATTRIBUTE CLASSES, COMPARATORS and DIRECTIONS. It never maps phrasing to a VALUE, with one documented
exception: the availability idiom ("still has places", "not full") means "more than 0 left", which is definitional, not an invented threshold.
Vague quantities ("affordable", "a few weeks", "several places") are listed so that they are DETECTED and preserved as unresolved; they are
never converted into numbers.

Attribute classes are derived from the verified catalogue view (kind, unit, label, value domain), so the lexicon is site-agnostic: a class
cue resolves to the catalogue attributes of that class, and a cue that resolves to more than one attribute is ambiguous."""
from __future__ import annotations

VERSION = "nl-lexicon-1"

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
# definitional value sets (a phrase that names exactly these values of a weekday-class domain)
VALUE_SETS = {"weekend": ("saturday", "sunday"), "weekends": ("saturday", "sunday"),
              "weekday": WEEKDAYS[:5], "weekdays": WEEKDAYS[:5]}

NUMBER_WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "twenty": 20, "thirty": 30}

# comparator phrases immediately BEFORE a number (nearest wins) and immediately AFTER it (takes precedence)
PREFIX_COMPARATORS = (("less than", "lt"), ("fewer than", "lt"), ("under", "lt"), ("below", "lt"), ("cheaper than", "lt"), ("shorter than", "lt"),
                      ("at most", "le"), ("no more than", "le"), ("not more than", "le"), ("up to", "le"), ("maximum of", "le"), ("max", "le"),
                      ("no longer than", "le"), ("within", "le"), ("budget of", "le"), ("budget is", "le"),
                      ("more than", "gt"), ("over", "gt"), ("above", "gt"), ("greater than", "gt"), ("longer than", "gt"),
                      ("at least", "ge"), ("no less than", "ge"), ("not less than", "ge"), ("minimum of", "ge"), ("exactly", "eq"))
SUFFIX_COMPARATORS = (("or less", "le"), ("or fewer", "le"), ("or under", "le"), ("or below", "le"), ("or cheaper", "le"), ("or shorter", "le"),
                      ("at most", "le"), ("max", "le"), ("maximum", "le"), ("tops", "le"),
                      ("or more", "ge"), ("or over", "ge"), ("or longer", "ge"), ("and up", "ge"), ("plus", "ge"), ("at least", "ge"), ("minimum", "ge"))

# phrases that identify which attribute CLASS a question or a number refers to (field names themselves always count too)
CLASS_CUES = {
    "money": ("how much", "cost", "costs", "price", "priced", "pricing", "fee", "fees", "pay", "spend", "charge", "rate", "dollars"),
    "duration": ("how long", "how many weeks", "how many days", "how many hours", "how many months", "last", "lasts", "run for", "runs for",
                 "duration", "length", "weeks", "days"),
    "weekday": ("what day", "which day", "which days", "what days", "day of the week", "when does it meet", "when does it run", "when is it on",
                "when is it held"),
    "location": ("where", "which campus", "what campus", "location", "which branch"),
    "availability": ("how many seats", "how many places", "how many spots", "how many spaces", "seats", "places", "spots", "spaces", "availability"),
    "level": ("what level", "which level", "how hard", "how difficult", "difficulty"),
}
# the availability idiom: "> 0 left" (definitional); recorded as an interpretation decision whenever it is used
AVAILABILITY_IDIOMS = ("still have seats", "still has seats", "still have places", "still has places", "still have spots", "still have space",
                       "still available", "places left", "seats left", "spots left", "spaces left", "seats available", "places available",
                       "have places", "has places", "have seats", "has seats", "not full", "not yet full", "not sold out", "still open")

# vague quantities: detected and preserved as unresolved, NEVER converted into a number
VAGUE = {
    "money": ("cheap", "cheaper", "inexpensive", "affordable", "afford", "low cost", "low-cost", "budget", "money is tight", "cost too much",
              "costs too much", "cost much", "too expensive", "not expensive", "expensive", "pricey", "reasonably priced", "reasonable price",
              "good value", "won't break the bank"),
    "duration": ("short", "shorter", "quick", "brief", "long", "longer", "a few weeks", "few weeks", "not much time", "fit in quickly"),
    "availability": ("several", "plenty", "lots of", "a few places", "a few seats", "many places", "many seats", "a couple of", "enough places"),
}

# superlatives: self-contained (class, direction) and compositional words that need an attribute cue right after (or before: "costs the least")
SUPERLATIVE_PHRASES = (("least expensive", "money", "min"), ("most affordable", "money", "min"), ("lowest priced", "money", "min"),
                       ("lowest-priced", "money", "min"), ("cheapest", "money", "min"), ("most expensive", "money", "max"), ("priciest", "money", "max"),
                       ("longest", "duration", "max"), ("shortest", "duration", "min"), ("quickest", "duration", "min"))
SUPERLATIVE_WORDS = {"highest": "max", "most": "max", "largest": "max", "biggest": "max", "greatest": "max", "maximum": "max",
                     "lowest": "min", "least": "min", "fewest": "min", "smallest": "min", "minimum": "min"}

# a stated value within this many tokens AFTER one of these words is a negative mention ("I work Monday to Friday", "not on Sundays")
NEGATIVE_CUES = ("work", "works", "working", "busy", "not", "never", "except", "unavailable", "avoid", "can't", "cannot", "don't", "won't")
NEGATIVE_WINDOW = 4
JUDGMENT_CUES = ("best", "ideal", "recommend", "suit", "suitable", "right for me", "worth it", "should i")
LABEL_STOPWORDS = {"per", "and", "the", "of", "left", "for", "a", "an"}


def snapshot() -> dict:
    """Everything above, for the configuration fingerprint (sets as sorted lists: a fingerprint must not depend on hash randomisation)."""
    return {k: (sorted(v) if isinstance(v, (set, frozenset)) else v) for k, v in globals().items() if k.isupper()}
