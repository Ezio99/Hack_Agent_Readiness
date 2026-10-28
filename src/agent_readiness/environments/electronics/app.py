"""FastAPI storefront for electronics-v1. One application per variant; the variant never appears in any response."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ...suite.core import Variant
from . import query
from .catalog import BY_SLUG, CATEGORIES, DELIVERY, PRODUCTS, RETURNS, SHIPPING_CLASS
from .presentation import chips, facts, prose
from .variants import DEFAULT_VARIANT

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
BRANDS = sorted({p.brand for p in PRODUCTS})


def money(cents: int) -> str:
    return f"A${cents / 100:,.2f}"


templates.env.filters["money"] = money


def create_app(variant: Variant = DEFAULT_VARIANT) -> FastAPI:
    show_stock_on_listing = variant.factor("availability") == "listing"
    structured = variant.factor("specs") == "structured"
    show_sku = variant.factor("sku", "hidden") == "listing"
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    def ctx(request: Request, **extra):
        return {"request": request, "categories": CATEGORIES, "brands": BRANDS, "show_stock": show_stock_on_listing, "structured": structured,
                "chips": chips, "show_sku": show_sku, "sorts": query.SORTS, **extra}

    def render(request, name, status=200, **extra):
        return templates.TemplateResponse(request=request, name=name, context=ctx(request, **extra), status_code=status)

    def listing(request: Request, category: str, title: str, heading: str):
        try:
            f = query.parse(request.query_params, category=category, allow_in_stock=show_stock_on_listing)
        except query.BadQuery as exc:
            return render(request, "notfound.html", 422, message=f"Those filters could not be applied: {exc}.")
        items, total, pages = query.run(f)
        keep = {k: v for k, v in request.query_params.items() if k != "page" and v}
        qs = lambda n: urlencode({**keep, "page": n})
        first = (min(f.page, pages) - 1) * query.PAGE_SIZE + 1 if total else 0
        return render(request, "listing.html", title=title, heading=heading, items=items, total=total, pages=pages, page=min(f.page, pages), f=f, category=category or f.category,
                      first=first, last=first + len(items) - 1 if total else 0, prev_qs=qs(f.page - 1) if f.page > 1 else None,
                      next_qs=qs(f.page + 1) if f.page < pages else None, path=request.url.path, values=request.query_params)

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request):
        featured = sorted((p for p in PRODUCTS if p.featured_rank == 1), key=lambda p: p.sku)
        return render(request, "home.html", featured=featured)

    @app.get("/c/{category}", response_class=HTMLResponse)
    async def category_page(request: Request, category: str):
        if category not in CATEGORIES:
            raise HTTPException(404, "Category not found")
        return listing(request, category, CATEGORIES[category], CATEGORIES[category])

    @app.get("/search", response_class=HTMLResponse)
    async def search(request: Request):
        q = (request.query_params.get("q") or "").strip()
        return listing(request, "", "Search", f"Search results for “{q}”" if q else "All products")

    @app.get("/p/{slug}", response_class=HTMLResponse)
    async def detail(request: Request, slug: str):
        product = BY_SLUG.get(slug)
        if product is None:
            raise HTTPException(404, "Product not found")
        return render(request, "detail.html", p=product, rows=facts(product), paragraphs=prose(product), category_name=CATEGORIES[product.category])

    @app.get("/help", response_class=HTMLResponse)
    async def help_index(request: Request):
        return render(request, "help.html", page="index")

    @app.get("/help/returns", response_class=HTMLResponse)
    async def returns(request: Request):
        rows = [(CATEGORIES[c], days, fee, "Free for the customer" if who == "retailer" else "Paid by the customer") for c, (days, fee, who) in RETURNS.items()]
        return render(request, "help.html", page="returns", rows=rows)

    @app.get("/help/delivery", response_class=HTMLResponse)
    async def delivery(request: Request):
        rows = [(cls, cost, threshold, lo, hi, ", ".join(CATEGORIES[c] for c, k in SHIPPING_CLASS.items() if k == cls)) for cls, (cost, threshold, lo, hi) in DELIVERY.items()]
        return render(request, "help.html", page="delivery", rows=rows)

    @app.exception_handler(404)
    async def not_found(request: Request, exc):
        return render(request, "notfound.html", 404, message="We couldn’t find that page.")

    return app
