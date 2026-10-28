"""electronics-v1 catalogue: deterministic, immutable synthetic fixtures (no randomness, no external data, no personal data).

48 products across four categories, built so that answers need navigation and multi-constraint checks: cheaper decoys fail exactly one
criterion each, some eligible products are out of stock, eligible items are spread over listing pages and similar product names exist.
Brands are fictional. Prices are integer Australian cents. ``featured_rank`` is the default (non-price) listing order."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ...suite.core import canonical_hash

ENVIRONMENT_ID = "electronics-v1"
CATEGORIES = {"headphones": "Headphones", "laptops": "Laptops", "monitors": "Monitors", "accessories": "Accessories"}
SHIPPING_CLASS = {"headphones": "standard", "laptops": "standard", "monitors": "bulky", "accessories": "standard"}


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    brand: str
    category: str
    price_cents: int
    in_stock: bool
    featured_rank: int
    rating: float
    specs: tuple[tuple[str, object], ...] = field(default_factory=tuple)   # ordered (key, value) facts; presentation is a variant concern

    @property
    def slug(self) -> str:
        return re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-")

    @property
    def path(self) -> str:
        return f"/p/{self.slug}"

    @property
    def shipping_class(self) -> str:
        return SHIPPING_CLASS[self.category]

    def spec(self, key: str, default=None):
        return dict(self.specs).get(key, default)


def _p(sku, name, brand, cat, dollars, stock, rank, rating, **specs):
    return Product(sku, name, brand, cat, int(round(dollars * 100)), stock, rank, rating, tuple(specs.items()))


# headphones: anc, form, wireless, battery_hours (None when wired)
HEADPHONES = (
    _p("HP-1001", "Aurel Quiet 700", "Aurel", "headphones", 399, True, 2, 4.7, anc=True, form="over-ear", wireless=True, battery_hours=30),
    _p("HP-1002", "Nordwave Silence Pro", "Nordwave", "headphones", 349, False, 5, 4.6, anc=True, form="over-ear", wireless=True, battery_hours=35),
    _p("HP-1003", "Kestrel Calm ANC", "Kestrel", "headphones", 299, True, 8, 4.4, anc=True, form="over-ear", wireless=True, battery_hours=28),
    _p("HP-1004", "Lumio Hush 3", "Lumio", "headphones", 249, True, 10, 4.3, anc=True, form="over-ear", wireless=True, battery_hours=24),
    _p("HP-1005", "Brevik Drift ANC", "Brevik", "headphones", 229, False, 11, 4.2, anc=True, form="in-ear", wireless=True, battery_hours=10),
    _p("HP-1006", "Tessera Whisper", "Tessera", "headphones", 199, True, 13, 4.1, anc=True, form="in-ear", wireless=True, battery_hours=9),
    _p("HP-1007", "Aurel Pulse Buds", "Aurel", "headphones", 179, True, 14, 4.0, anc=True, form="in-ear", wireless=True, battery_hours=7),
    _p("HP-1008", "Lumio Hush Lite", "Lumio", "headphones", 129, False, 12, 3.9, anc=True, form="over-ear", wireless=True, battery_hours=20),
    _p("HP-1009", "Nordwave Beat 200", "Nordwave", "headphones", 89, True, 1, 4.0, anc=False, form="over-ear", wireless=True, battery_hours=40),
    _p("HP-1010", "Kestrel Run Sport", "Kestrel", "headphones", 99, True, 4, 4.1, anc=False, form="in-ear", wireless=True, battery_hours=12),
    _p("HP-1011", "Brevik Studio Monitor", "Brevik", "headphones", 149, True, 6, 4.5, anc=False, form="over-ear", wireless=False, battery_hours=None),
    _p("HP-1012", "Tessera Daily", "Tessera", "headphones", 59, True, 9, 3.8, anc=False, form="in-ear", wireless=True, battery_hours=6),
    _p("HP-1013", "Aurel Core", "Aurel", "headphones", 119, False, 7, 4.2, anc=False, form="over-ear", wireless=True, battery_hours=32),
    _p("HP-1014", "Lumio Spark Kids", "Lumio", "headphones", 39, True, 3, 3.7, anc=False, form="over-ear", wireless=True, battery_hours=15),
)
# laptops: cpu, ram_gb, storage_gb, screen_in, battery_hours (advertised), weight_kg, charger_w
LAPTOPS = (
    _p("LT-2001", "Kestrel Air 14", "Kestrel", "laptops", 1299, True, 1, 4.6, cpu="Helix 5", ram_gb=16, storage_gb=512, screen_in=14.0, battery_hours=18, weight_kg=1.2, charger_w=65),
    _p("LT-2002", "Kestrel Air 14 Plus", "Kestrel", "laptops", 1499, True, 3, 4.7, cpu="Helix 7", ram_gb=32, storage_gb=1024, screen_in=14.0, battery_hours=16, weight_kg=1.3, charger_w=65),
    _p("LT-2003", "Nordwave ProBook 15", "Nordwave", "laptops", 1699, True, 2, 4.5, cpu="Helix 7", ram_gb=32, storage_gb=1024, screen_in=15.6, battery_hours=11, weight_kg=1.9, charger_w=100),
    _p("LT-2004", "Nordwave ProBook 15 Lite", "Nordwave", "laptops", 1199, False, 6, 4.2, cpu="Helix 5", ram_gb=16, storage_gb=512, screen_in=15.6, battery_hours=12, weight_kg=1.8, charger_w=65),
    _p("LT-2005", "Aurel Slate 13", "Aurel", "laptops", 1099, True, 4, 4.3, cpu="Helix 3", ram_gb=8, storage_gb=256, screen_in=13.3, battery_hours=20, weight_kg=1.1, charger_w=45),
    _p("LT-2006", "Aurel Slate 16", "Aurel", "laptops", 1399, True, 5, 4.4, cpu="Helix 5", ram_gb=16, storage_gb=512, screen_in=16.0, battery_hours=14, weight_kg=1.7, charger_w=65),
    _p("LT-2007", "Tessera Studio 16", "Tessera", "laptops", 2199, True, 9, 4.8, cpu="Helix 9", ram_gb=64, storage_gb=2048, screen_in=16.0, battery_hours=9, weight_kg=2.1, charger_w=140),
    _p("LT-2008", "Lumio Go 14", "Lumio", "laptops", 899, True, 7, 4.0, cpu="Helix 3", ram_gb=8, storage_gb=256, screen_in=14.0, battery_hours=15, weight_kg=1.4, charger_w=45),
    _p("LT-2009", "Brevik Craft 14", "Brevik", "laptops", 1249, False, 10, 4.1, cpu="Helix 5", ram_gb=16, storage_gb=1024, screen_in=14.0, battery_hours=13, weight_kg=1.5, charger_w=65),
    _p("LT-2010", "Lumio Pro 14", "Lumio", "laptops", 1599, True, 8, 4.5, cpu="Helix 7", ram_gb=32, storage_gb=512, screen_in=14.0, battery_hours=17, weight_kg=1.4, charger_w=65),
)
# monitors: size_in, resolution, refresh_hz, usb_c, panel
MONITORS = (
    _p("MN-3001", "Lumio View 24", "Lumio", "monitors", 179, True, 1, 4.0, size_in=24, resolution="1920x1080", refresh_hz=75, usb_c=False, panel="IPS"),
    _p("MN-3002", "Tessera Desk 24C", "Tessera", "monitors", 249, True, 2, 4.2, size_in=24, resolution="1920x1080", refresh_hz=144, usb_c=True, panel="IPS"),
    _p("MN-3003", "Kestrel Core 27", "Kestrel", "monitors", 329, True, 3, 4.3, size_in=27, resolution="2560x1440", refresh_hz=75, usb_c=True, panel="IPS"),
    _p("MN-3004", "Nordwave Rapid 27", "Nordwave", "monitors", 379, True, 4, 4.4, size_in=27, resolution="2560x1440", refresh_hz=144, usb_c=False, panel="IPS"),
    _p("MN-3005", "Aurel Vision 27C", "Aurel", "monitors", 399, False, 5, 4.5, size_in=27, resolution="2560x1440", refresh_hz=144, usb_c=True, panel="IPS"),
    _p("MN-3006", "Lumio Pro 27C", "Lumio", "monitors", 449, True, 6, 4.4, size_in=27, resolution="2560x1440", refresh_hz=120, usb_c=True, panel="IPS"),
    _p("MN-3007", "Brevik Edge 27C", "Brevik", "monitors", 529, True, 7, 4.6, size_in=27, resolution="2560x1440", refresh_hz=165, usb_c=True, panel="IPS"),
    _p("MN-3008", "Kestrel Wide 34C", "Kestrel", "monitors", 699, True, 8, 4.7, size_in=34, resolution="3440x1440", refresh_hz=144, usb_c=True, panel="VA"),
    _p("MN-3009", "Nordwave Studio 32", "Nordwave", "monitors", 599, True, 9, 4.5, size_in=32, resolution="3840x2160", refresh_hz=60, usb_c=True, panel="IPS"),
    _p("MN-3010", "Aurel Vision 32C", "Aurel", "monitors", 649, True, 10, 4.5, size_in=32, resolution="3840x2160", refresh_hz=60, usb_c=True, panel="IPS"),
    _p("MN-3011", "Tessera Pixel 32", "Tessera", "monitors", 479, True, 11, 4.1, size_in=32, resolution="3840x2160", refresh_hz=60, usb_c=False, panel="VA"),
    _p("MN-3012", "Lumio Vista 32C", "Lumio", "monitors", 549, False, 12, 4.2, size_in=32, resolution="3840x2160", refresh_hz=60, usb_c=True, panel="IPS"),
)
# accessories: kind, output_w / connector where relevant
ACCESSORIES = (
    _p("AC-4001", "Kestrel GaN Charger 65W", "Kestrel", "accessories", 59, True, 1, 4.5, kind="charger", output_w=65, connector="USB-C"),
    _p("AC-4002", "Nordwave GaN Charger 100W", "Nordwave", "accessories", 89, True, 2, 4.6, kind="charger", output_w=100, connector="USB-C"),
    _p("AC-4003", "Aurel Travel Charger 45W", "Aurel", "accessories", 39, True, 3, 4.1, kind="charger", output_w=45, connector="USB-C"),
    _p("AC-4004", "Lumio USB-C Cable 2m", "Lumio", "accessories", 19, True, 4, 4.0, kind="cable", output_w=100, connector="USB-C"),
    _p("AC-4005", "Brevik Dock 8-in-1", "Brevik", "accessories", 149, True, 5, 4.4, kind="dock", output_w=None, connector="USB-C"),
    _p("AC-4006", "Tessera Laptop Sleeve 14", "Tessera", "accessories", 35, True, 6, 4.2, kind="sleeve", output_w=None, connector=None),
    _p("AC-4007", "Tessera Laptop Sleeve 16", "Tessera", "accessories", 39, False, 7, 4.2, kind="sleeve", output_w=None, connector=None),
    _p("AC-4008", "Kestrel Wireless Mouse", "Kestrel", "accessories", 45, True, 8, 4.3, kind="mouse", output_w=None, connector="2.4 GHz"),
    _p("AC-4009", "Nordwave Monitor Arm", "Nordwave", "accessories", 119, True, 9, 4.5, kind="stand", output_w=None, connector=None),
    _p("AC-4010", "Aurel USB-C Hub 4-port", "Aurel", "accessories", 49, True, 10, 4.0, kind="hub", output_w=None, connector="USB-C"),
    _p("AC-4011", "Lumio Headphone Stand", "Lumio", "accessories", 29, True, 11, 3.9, kind="stand", output_w=None, connector=None),
    _p("AC-4012", "Brevik Replacement Ear Tips", "Brevik", "accessories", 15, True, 12, 4.0, kind="ear-tips", output_w=None, connector=None),
)
PRODUCTS: tuple[Product, ...] = HEADPHONES + LAPTOPS + MONITORS + ACCESSORIES
BY_SKU = {p.sku: p for p in PRODUCTS}
BY_SLUG = {p.slug: p for p in PRODUCTS}
assert len(BY_SKU) == len(PRODUCTS) == len(BY_SLUG) == 48

# Policies (A$). One source for both the policy pages and the oracle's expected values.
RETURNS = {  # category -> (window days, opened-item restocking fee %, return shipping paid by)
    "headphones": (30, 0, "retailer"), "laptops": (14, 15, "customer"), "monitors": (30, 10, "customer"), "accessories": (30, 0, "retailer"),
}
DELIVERY = {  # shipping class -> (cost cents, free-delivery threshold cents, min business days, max business days)
    "standard": (995, 10000, 2, 4), "bulky": (2900, 50000, 4, 7),
}


def delivery_cost_cents(product: Product) -> int:
    cost, threshold, _, _ = DELIVERY[product.shipping_class]
    return 0 if product.price_cents >= threshold else cost


def data_snapshot() -> dict:
    return {"environment": ENVIRONMENT_ID, "products": [[p.sku, p.name, p.brand, p.category, p.price_cents, p.in_stock, p.featured_rank, p.rating,
                                                       [[k, v] for k, v in p.specs]] for p in PRODUCTS],
            "returns": RETURNS, "delivery": DELIVERY, "shipping_class": SHIPPING_CLASS}


DATA_HASH = canonical_hash(data_snapshot())
DATA_VERSION = f"{ENVIRONMENT_ID}+{DATA_HASH[:12]}"
