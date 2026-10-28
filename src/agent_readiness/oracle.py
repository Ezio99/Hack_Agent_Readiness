"""Offline oracle and scripted solvers for Task 007 (no browser, no model).

The oracle derives, from inventory truth alone, the correct answer and the *minimum* number of detail pages any
correct agent must open for each scope and arm. It separates two things an agent can do:
  * finding the answer - identifying the most expensive in-stock product; and
  * verifying it - establishing that no higher-priced product in scope is in stock.
With availability on the listing (arm A) both need no detail page and only the answer's page is opened (to read the
product ID, which exists only there). Without it (arm B) every higher-priced candidate's page must be opened, so the
minimum is the answer's rank when scope products are ordered by descending price."""
import re
from .inventory import PRODUCTS, Product
from .tasks import PrivateTask


def scope_products(task: PrivateTask) -> list[Product]:
    """Scope members ordered by descending price (prices are distinct within every Task 007 scope)."""
    members = [p for p in PRODUCTS if (task.category is None or p.category == task.category)
               and (task.brand is None or p.brand == task.brand)]
    members.sort(key=lambda p: -p.price_cents)
    assert len({p.price_cents for p in members}) == len(members)
    return members


def analysis(task: PrivateTask, listing_shows_availability: bool) -> dict:
    members = scope_products(task)
    answer = next(p for p in members if p.available)
    higher = [p for p in members[:members.index(answer)]]
    assert not any(p.available for p in higher)
    rank = len(higher) + 1
    return {
        "answer_id": answer.product_id, "scope_size": len(members), "rank": rank,
        "higher_priced_candidate_ids": [p.product_id for p in higher],
        # visits needed to *find* which product it is, and to *verify* nothing higher-priced qualifies
        "min_visits_to_find": 0 if listing_shows_availability else rank,
        "min_visits_to_verify_no_higher": 0 if listing_shows_availability else len(higher),
        "min_detail_visits": 1 if listing_shows_availability else rank,
        "min_detail_visits_basis": ("availability on the listing: only the answer's page is needed for its product ID"
                                    if listing_shows_availability else
                                    "availability on detail pages only: every higher-priced candidate, then the answer"),
        "stopping_condition": "stop at the first in-stock product in descending price order; lower-priced products need not be opened",
    }


def minimum_detail_visits(task: PrivateTask, listing_shows_availability: bool) -> int:
    """Existing task kinds need exactly one detail page (the product ID is only there) in every arm."""
    if task.public.kind != "instock_max":
        return 1
    return analysis(task, listing_shows_availability)["min_detail_visits"]


# ---- scripted solvers over HTTP (anything with .get(path, params=None) -> .text) -------------------------------

CARD = re.compile(r"<article>(.*?)</article>", re.S)


def parse_listing(html: str) -> list[dict]:
    cards = []
    for body in CARD.findall(html):
        stock = re.search(r'<p class="availability">(In stock|Out of stock)</p>', body)
        cards.append({"href": re.search(r'href="(/products/[0-9a-f]+)"', body).group(1),
                      "price_cents": round(float(re.search(r'\$([\d.]+)</p>', body).group(1)) * 100),
                      "in_stock": None if stock is None else stock.group(1) == "In stock"})
    return cards


def parse_detail(html: str) -> dict:
    return {"product_id": re.search(r'id="product-id">([^<]+)<', html).group(1),
            "price_cents": round(float(re.search(r'id="price">\$([\d.]+)<', html).group(1)) * 100),
            "available": "In stock" in re.search(r'id="availability">([^<]+)<', html).group(1)}


class Solver:
    def __init__(self, client, task: PrivateTask):
        self.client, self.task, self.visits = client, task, []

    def listing(self):
        params = {"category": self.task.category} if self.task.category else {"brand": self.task.brand}
        return sorted(parse_listing(self.client.get("/", params=params).text), key=lambda c: -c["price_cents"])

    def open(self, card) -> dict:
        detail = parse_detail(self.client.get(card["href"]).text)
        self.visits.append(detail["product_id"])
        return detail

    def result(self, answer):
        return {"answer": answer, "detail_visits": list(self.visits)}


def solve_descending(client, task):
    """The minimal correct strategy: walk down by price; use listing availability when present."""
    solver, cards = Solver(client, task), None
    cards = solver.listing()
    for card in cards:
        if card["in_stock"] is False:
            continue
        detail = solver.open(card)       # B: reveals availability; A: the page is opened only for the product ID
        if detail["available"]:
            return solver.result(detail)
    raise AssertionError("no in-stock product in scope")


def solve_ascending_unverified(client, task):
    """Finds *an* in-stock product from the cheapest end and stops: found, but never verified as the maximum."""
    solver = Solver(client, task)
    for card in reversed(solver.listing()):
        if card["in_stock"] is False:
            continue
        detail = solver.open(card)
        if detail["available"]:
            return solver.result(detail)
    raise AssertionError("no in-stock product in scope")


def solve_top_price_guess(client, task):
    """Answers with the most expensive product without regard to availability."""
    solver = Solver(client, task)
    return solver.result(solver.open(solver.listing()[0]))


def solve_exhaustive(client, task):
    """Opens every product in scope and answers with the best in-stock one (maximum overhead)."""
    solver = Solver(client, task)
    details = [solver.open(card) for card in solver.listing()]
    return solver.result(next(d for d in details if d["available"]))
