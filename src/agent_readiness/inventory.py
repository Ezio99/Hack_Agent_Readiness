"""Fresh synthetic source inventory. Never served as a file or bulk API."""
from dataclasses import asdict, dataclass
import hashlib
import json


@dataclass(frozen=True)
class Product:
    product_id: str
    name: str
    brand: str
    category: str
    price_cents: int
    available: bool

    @property
    def route(self) -> str:
        # Independent of answer-bearing ID and stock state; stable ordinary links.
        return hashlib.sha256(("shop-route-v1:" + self.name).encode()).hexdigest()[:20]

    def listing(self) -> dict:
        return {"name": self.name, "brand": self.brand, "category": self.category,
                "price_cents": self.price_cents, "route": self.route}


_ROWS = (
    ("Trail Daypack", "Fern", "Bags", 3900, True),
    ("City Tote", "Fern", "Bags", 2400, False),
    ("Commuter Sling", "Harbor", "Bags", 3200, True),
    ("Weekend Duffel", "Harbor", "Bags", 6900, False),
    ("Pocket Pouch", "Ember", "Bags", 1500, True),
    ("Stone Mug", "Fern", "Kitchen", 1800, True),
    ("Travel Tumbler", "Fern", "Kitchen", 2800, False),
    ("Glass Carafe", "Harbor", "Kitchen", 3400, True),
    ("Lunch Container", "Harbor", "Kitchen", 2200, False),
    ("Bamboo Tray", "Ember", "Kitchen", 2600, True),
    ("Reading Lamp", "Fern", "Home", 4500, False),
    ("Linen Cushion", "Fern", "Home", 2900, True),
    ("Woven Basket", "Harbor", "Home", 3700, True),
    ("Cotton Throw", "Harbor", "Home", 5900, False),
    ("Desk Clock", "Ember", "Home", 3100, True),
    ("Yoga Mat", "Fern", "Outdoors", 3500, True),
    ("Picnic Blanket", "Fern", "Outdoors", 4800, False),
    ("Water Bottle", "Harbor", "Outdoors", 2100, True),
    ("Camp Stool", "Harbor", "Outdoors", 4200, False),
    ("Sun Hat", "Ember", "Outdoors", 2700, True),
)
PRODUCTS = tuple(Product(f"AR-{7301 + i * 17}", *row) for i, row in enumerate(_ROWS))
INVENTORY_VERSION = "synthetic-v1"
INVENTORY_HASH = hashlib.sha256(json.dumps([asdict(p) for p in PRODUCTS], sort_keys=True).encode()).hexdigest()
