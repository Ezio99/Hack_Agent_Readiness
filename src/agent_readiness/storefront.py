from pathlib import Path
from decimal import Decimal, InvalidOperation
from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates
from .inventory import PRODUCTS

VARIANT_ID = "baseline-detail-v1"

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@app.get("/")
async def listing(request: Request, q: str = "", category: str = "", brand: str = "",
            max_price: str = ""):
    try:
        limit = Decimal(max_price) * 100 if max_price else None
        if limit is not None and (not limit.is_finite() or limit < 0 or limit != limit.to_integral_value()):
            raise ValueError("Price must be nonnegative with at most two decimal places")
    except (InvalidOperation, ValueError):
        raise HTTPException(422, "Invalid maximum price")
    products = [p.listing() for p in PRODUCTS
                if (not q or q.casefold() in f"{p.name} {p.brand} {p.category}".casefold())
                and (not category or p.category == category)
                and (not brand or p.brand == brand)
                and (limit is None or p.price_cents <= limit)]
    return templates.TemplateResponse(request=request, name="listing.html", context={
        "products": products, "categories": sorted({p.category for p in PRODUCTS}),
        "brands": sorted({p.brand for p in PRODUCTS}), "q": q, "category": category,
        "brand": brand, "max_price": max_price})


@app.get("/products/{route}")
async def detail(request: Request, route: str):
    product = next((p for p in PRODUCTS if p.route == route), None)
    if product is None:
        raise HTTPException(404, "Product not found")
    return templates.TemplateResponse(request=request, name="detail.html", context={"product": product})
