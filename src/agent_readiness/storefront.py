from pathlib import Path
from decimal import Decimal, InvalidOperation
from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates
from .inventory import PRODUCTS

VARIANT_ID = "baseline-detail-v1"          # Arm A / control: the original storefront, unchanged
VARIANT_B_ID = "link-info-placement-b-v1"  # Arm B: visible generic "View details" link, name as a plain heading
VARIANT_D0_ID = "diagnostic-aria-generic-v1"  # offline diagnostic only: generic aria-label, visible name unchanged
VARIANT_AVAIL_ID = "listing-availability-v1"  # Task 007 arm A: availability line on each listing card (detail pages unchanged)
LISTING_TEMPLATES = {VARIANT_ID: "listing.html", VARIANT_B_ID: "listing_b.html", VARIANT_D0_ID: "listing_d0.html",
                     VARIANT_AVAIL_ID: "listing_avail.html"}
EXPERIMENTAL_ARMS = (VARIANT_ID, VARIANT_B_ID, VARIANT_AVAIL_ID)   # variants that may be used in live trials
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def create_app(variant: str = VARIANT_ID) -> FastAPI:
    """One storefront per variant. The variant is chosen by the server's configuration only: it never appears in a
    URL, header, title or page, and the inventory, routes, order, detail pages and filters are shared."""
    if variant not in LISTING_TEMPLATES:
        raise ValueError(f"Unknown storefront variant {variant!r}")
    listing_template = LISTING_TEMPLATES[variant]
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/")
    async def listing(request: Request, q: str = "", category: str = "", brand: str = "",
                max_price: str = ""):
        try:
            limit = Decimal(max_price) * 100 if max_price else None
            if limit is not None and (not limit.is_finite() or limit < 0 or limit != limit.to_integral_value()):
                raise ValueError("Price must be nonnegative with at most two decimal places")
        except (InvalidOperation, ValueError):
            raise HTTPException(422, "Invalid maximum price")
        products = [(p.listing() | {"available": p.available}) if variant == VARIANT_AVAIL_ID else p.listing()
                    for p in PRODUCTS
                    if (not q or q.casefold() in f"{p.name} {p.brand} {p.category}".casefold())
                    and (not category or p.category == category)
                    and (not brand or p.brand == brand)
                    and (limit is None or p.price_cents <= limit)]
        return templates.TemplateResponse(request=request, name=listing_template, context={
            "products": products, "categories": sorted({p.category for p in PRODUCTS}),
            "brands": sorted({p.brand for p in PRODUCTS}), "q": q, "category": category,
            "brand": brand, "max_price": max_price})

    @app.get("/products/{route}")
    async def detail(request: Request, route: str):
        product = next((p for p in PRODUCTS if p.route == route), None)
        if product is None:
            raise HTTPException(404, "Product not found")
        return templates.TemplateResponse(request=request, name="detail.html", context={"product": product})

    return app


app = create_app(VARIANT_ID)   # default / baseline application object (unchanged import path)
