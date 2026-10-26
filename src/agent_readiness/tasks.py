"""Seeded generation; private specification stays in the runner/evaluator process."""
from dataclasses import dataclass
import random
import hashlib
from .contracts import PublicTask
from .inventory import PRODUCTS, Product, INVENTORY_VERSION


@dataclass(frozen=True)
class PrivateTask:
    public: PublicTask
    seed: int
    expected_id: str
    category: str | None = None
    brand: str | None = None
    max_price_cents: int | None = None
    name: str | None = None

    def matches(self, product: Product) -> bool:
        return ((self.category is None or product.category == self.category)
                and (self.brand is None or product.brand == self.brand)
                and (self.max_price_cents is None or product.price_cents <= self.max_price_cents)
                and (self.name is None or product.name == self.name))


def generate(seed: int = 0, kind: str = "discovery", available: bool | None = None) -> PrivateTask:
    rng = random.Random(seed)
    if kind == "discovery":
        candidates = [p for p in PRODUCTS if sum(
            q.category == p.category and q.brand == p.brand and q.price_cents <= p.price_cents
            for q in PRODUCTS) == 1]
        p = rng.choice(candidates)
        prompt = (f"Find the {p.brand} product in {p.category} costing at most ${p.price_cents / 100:.2f} AUD. "
                  "Return its product ID, price in integer cents, and whether it is available.")
        constraints = dict(category=p.category, brand=p.brand, max_price_cents=p.price_cents)
    elif kind == "availability":
        p = rng.choice([p for p in PRODUCTS if available is None or p.available == available])
        prompt = (f"Locate {p.name}. Return its product ID, price in integer cents, "
                  "and whether it is currently available.")
        constraints = dict(name=p.name)
    else:
        raise ValueError("Unknown task kind")
    suffix = hashlib.sha256(prompt.encode()).hexdigest()[:10]
    public = PublicTask(task_id=f"{INVENTORY_VERSION}-{kind}-{seed}-{suffix}", kind=kind, prompt=prompt)
    return PrivateTask(public, seed, p.product_id, **constraints)
