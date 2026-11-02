"""Source of truth for the fictional Larkspur Community College short-course catalogue.

Every page is rendered from these records (`render.py`), and the framework's independent oracle reads the same records, so pages and ground truth
cannot silently diverge without the cross-check noticing. Deterministic: no clock, no randomness. Larkspur Community College is fictional."""
from __future__ import annotations

from dataclasses import dataclass

COLLEGE = {"name": "Larkspur Community College", "tagline": "Evening and weekend short courses for adults", "suburb": "Larkspur Heights",
           "phone": "(03) 5550 8820", "email": "courses@larkspur.example"}


@dataclass(frozen=True)
class Course:
    slug: str
    name: str
    category: str
    summary: str
    fee: int                  # AUD, whole course
    weeks: int                # duration in weeks
    level: str                # Beginner | Intermediate | Advanced
    day: str                  # weekly class day
    seats_left: int
    campus: str               # Northside | Riverside
    materials: str            # "Included" | "Bring your own"


COURSES = [
    Course("watercolour-foundations", "Watercolour foundations", "Arts", "Washes, layering and colour mixing for complete beginners.", 260, 6, "Beginner", "Tuesday", 7, "Riverside", "Included"),
    Course("life-drawing-studio", "Life drawing studio", "Arts", "Weekly untutored sessions with a short warm-up demonstration.", 210, 8, "Intermediate", "Thursday", 3, "Northside", "Bring your own"),
    Course("wheel-thrown-pottery", "Wheel-thrown pottery", "Arts", "Centre, throw and trim simple forms on the wheel.", 395, 8, "Beginner", "Saturday", 2, "Riverside", "Included"),
    Course("intro-to-python", "Introduction to Python", "Technology", "Variables, loops and functions with small practical projects.", 340, 10, "Beginner", "Monday", 11, "Northside", "Included"),
    Course("spreadsheets-for-small-business", "Spreadsheets for small business", "Technology", "Budgets, invoices and simple dashboards in a spreadsheet.", 180, 4, "Beginner", "Wednesday", 9, "Riverside", "Included"),
    Course("web-pages-from-scratch", "Web pages from scratch", "Technology", "Write HTML and CSS by hand and publish a personal page.", 290, 6, "Intermediate", "Tuesday", 5, "Northside", "Bring your own"),
    Course("conversational-italian-1", "Conversational Italian 1", "Languages", "Everyday Italian for travel: greetings, food and directions.", 230, 10, "Beginner", "Monday", 6, "Riverside", "Included"),
    Course("japanese-for-travellers", "Japanese for travellers", "Languages", "Polite phrases, numbers and reading signs.", 245, 8, "Beginner", "Wednesday", 0, "Northside", "Included"),
    Course("spanish-conversation-2", "Spanish conversation 2", "Languages", "Build fluency with role plays and short readings.", 230, 10, "Intermediate", "Thursday", 8, "Riverside", "Bring your own"),
    Course("beginners-yoga", "Beginners yoga", "Wellbeing", "Gentle flow, breathing and relaxation for stiff bodies.", 150, 6, "Beginner", "Saturday", 12, "Northside", "Bring your own"),
    Course("mindful-meditation", "Mindful meditation", "Wellbeing", "Short guided practices you can continue at home.", 120, 4, "Beginner", "Sunday", 15, "Riverside", "Included"),
    Course("home-electrical-basics", "Home electrical basics", "Trades", "Safe isolation, fittings and what must be left to a licensed electrician.", 310, 5, "Beginner", "Saturday", 4, "Northside", "Included"),
    Course("furniture-restoration", "Furniture restoration", "Trades", "Strip, repair and refinish a small piece you bring in.", 420, 8, "Intermediate", "Sunday", 1, "Riverside", "Bring your own"),
    Course("advanced-joinery", "Advanced joinery", "Trades", "Dovetails, mortise and tenon, and hand-cut drawer fronts.", 480, 10, "Advanced", "Tuesday", 3, "Northside", "Bring your own"),
]
BY_SLUG = {c.slug: c for c in COURSES}
CATEGORIES = sorted({c.category for c in COURSES})

REFUNDS = [("More than 7 days before the first class", "Full refund less a $20 administration fee"), ("2 to 7 days before the first class", "50 % refund"),
           ("Less than 2 days before the first class", "No refund; transfer to a later course"), ("If the college cancels", "Full refund")]
CONCESSION = 15               # percent off the course fee for concession card holders


def money(n: int) -> str:
    return f"${n}"


def weeks(n: int) -> str:
    return f"{n} week" + ("" if n == 1 else "s")
