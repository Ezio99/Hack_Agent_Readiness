"""Generic page model: what a page offers to a reader or an agent, extracted without any e-commerce (or any domain) assumption.

Records FACTS only — structure, links, forms, controls with their computed accessible names, label/value facts, repeated item groups, structured data. Judgement (what is
friction, what is the cause) is never made here; later stages form hypotheses from these facts."""
from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

ORIGIN = "http://mirror.invalid"
SKIP_TEXT = ("script", "style", "noscript", "template", "head")
LANDMARKS = {"nav": "nav", "header": "header", "footer": "footer", "main": "main", "aside": "aside", "search": "search"}
INTERACTIVE_ROLES = {"button", "link", "tab", "menuitem", "checkbox", "switch", "radio", "combobox", "textbox", "searchbox"}


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _hidden(el: Tag) -> bool:
    style = (el.get("style") or "").replace(" ", "").lower()
    return el.has_attr("hidden") or "display:none" in style or "visibility:hidden" in style


def visible_text(node) -> str:
    out = []
    for s in node.find_all(string=True):
        if any(p.name in SKIP_TEXT or (isinstance(p, Tag) and _hidden(p)) for p in s.parents if isinstance(p, Tag)):
            continue
        out.append(str(s))
    return norm(" ".join(out))


def locator(el: Tag) -> str:
    parts = []
    for n in [el, *el.parents][:4]:
        if not isinstance(n, Tag) or n.name == "[document]":
            break
        cls = ".".join((n.get("class") or [])[:2])
        parts.append(n.name + (f"#{n['id']}" if n.get("id") else "") + (f".{cls}" if cls else ""))
    return " < ".join(parts)


def landmark_of(el: Tag) -> str | None:
    for p in [el, *el.parents]:
        if isinstance(p, Tag):
            role = p.get("role")
            if p.name in LANDMARKS:
                return LANDMARKS[p.name]
            if role in ("navigation", "banner", "contentinfo", "main", "search"):
                return {"navigation": "nav", "banner": "header", "contentinfo": "footer"}.get(role, role)
    return None


def accessible_name(el: Tag, soup: BeautifulSoup) -> tuple[str | None, str | None]:
    """Simplified accessible-name computation (aria-labelledby, aria-label, native label, content, alt, title, placeholder). Returns (name, source) or (None, None)."""
    ids = (el.get("aria-labelledby") or "").split()
    if ids:
        t = norm(" ".join(visible_text(x) for i in ids if (x := soup.find(id=i))))
        if t:
            return t, "aria-labelledby"
    if norm(el.get("aria-label") or ""):
        return norm(el["aria-label"]), "aria-label"
    if el.name in ("input", "select", "textarea"):
        typ = (el.get("type") or "text").lower()
        if typ in ("submit", "button", "reset") and norm(el.get("value") or ""):
            return norm(el["value"]), "value"
        if typ == "image" and norm(el.get("alt") or ""):
            return norm(el["alt"]), "alt"
        lab = soup.find("label", attrs={"for": el.get("id")}) if el.get("id") else None
        lab = lab or el.find_parent("label")
        if lab is not None and visible_text(lab):
            return visible_text(lab), "label"
        if norm(el.get("title") or ""):
            return norm(el["title"]), "title"
        if norm(el.get("placeholder") or ""):
            return norm(el["placeholder"]), "placeholder"
        return None, None
    t = visible_text(el)
    if t:
        return t, "content"
    for img in el.find_all(["img", "svg"]):
        if img.name == "img" and norm(img.get("alt") or ""):
            return norm(img["alt"]), "img-alt"
        if img.name == "svg":
            ti = img.find("title")
            if ti is not None and norm(ti.get_text()):
                return norm(ti.get_text()), "svg-title"
            if norm(img.get("aria-label") or ""):
                return norm(img["aria-label"]), "svg-aria-label"
    if norm(el.get("title") or ""):
        return norm(el["title"]), "title"
    return None, None


def internal_path(href: str | None, base_path: str) -> str | None:
    """Root-relative path(+query) of a same-origin link, or None for external / non-navigational links."""
    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
        return None
    u = urlsplit(urljoin(ORIGIN + base_path, href))
    if u.scheme + "://" + u.netloc != ORIGIN:
        return None
    return (u.path or "/") + (f"?{u.query}" if u.query else "")


AMOUNT = re.compile(r"^[$€£]\s?\d[\d,]*(\.\d{1,2})?$")
DATE = re.compile(r"^\d{1,2} [A-Z][a-z]{2}$")


def _facts(root: Tag) -> list[dict]:
    """Label/value pairs from definition lists, two-column table rows, and 'Label: value' text — in that order of reliability."""
    out = []

    def add(label, value, el, how):
        label, value = norm(label).rstrip(":").strip(), norm(value)
        if label and value and len(label) <= 40 and len(value) <= 200:
            out.append({"label": label.lower(), "value": value, "how": how, "locator": locator(el)})
    for dt in root.find_all("dt"):
        dd = dt.find_next_sibling("dd")
        if dd is not None:
            add(visible_text(dt), visible_text(dd), dt, "dl")
    for tr in root.find_all("tr"):
        cells = tr.find_all(["th", "td"], recursive=False)
        if len(cells) == 2 and cells[0].name == "th":
            add(visible_text(cells[0]), visible_text(cells[1]), tr, "table")
    # Caption-with-amount pairs ("$110" above "Per day") and calendar cells ("14 Nov" beside "Booked"): the page SHOWS these to a browser agent as text, but they are neither dl nor table-row pairs. Only
    # the exact visible text of two sibling elements is recorded (label = the caption/date, value = the amount/status); nothing is computed, inferred or normalised beyond case of the label.
    for el in root.find_all(["div", "td", "li"]):
        kids = [c for c in el.children if isinstance(c, Tag)]
        if len(kids) != 2 or any(c.find(True) for c in kids) or _hidden(el):
            continue
        first, second = visible_text(kids[0]), visible_text(kids[1])
        if AMOUNT.match(first) and 1 <= len(second.split()) <= 3 and not AMOUNT.match(second):
            add(second, first, el, "amount-caption")
        elif DATE.match(first) and 1 <= len(second.split()) <= 3 and not DATE.match(second):
            add(first, second, el, "calendar-cell")
    for strong in root.find_all(["strong", "b"]):                      # a dated status line under a heading: "Today, Mon 2 Nov: <status>." -> label "<heading> today", value "<status>"
        m = re.match(r"^(Today|Tomorrow), [A-Za-z]{3} \d{1,2} [A-Za-z]{3}: (.{3,40})\.$", visible_text(strong))
        h = strong.find_previous(["h2", "h3"])
        if m and h is not None:
            add(f"{visible_text(h)} {m.group(1)}", m.group(2), strong, "dated-status")
    for el in root.find_all(["p", "li", "div", "span"]):
        if el.find(["p", "li", "div", "dl", "table"]):
            continue
        t = visible_text(el)
        m = re.match(r"^([A-Za-z][A-Za-z0-9 /&'-]{1,38}):\s+(.{1,160})$", t)
        if m and not any(f["label"] == m.group(1).lower() and f["value"] == norm(m.group(2)) for f in out):
            add(m.group(1), m.group(2), el, "text")
    return out


def _item_name(item: Tag, anchor: Tag | None, soup: BeautifulSoup) -> str:
    """A repeated item's visible name: its link text, else its first heading, else the first cell of a table row, else the leading words of its text."""
    name = (accessible_name(anchor, soup)[0] or "") if anchor is not None else ""
    if name and name != visible_text(item) or name and not item.find(["h1", "h2", "h3", "h4"]):
        return name[:120]
    h = item.find(re.compile(r"^h[1-6]$"))
    if h is not None and visible_text(h):
        return visible_text(h)[:120]
    if item.name == "tr":
        cell = item.find(["th", "td"])
        if cell is not None and visible_text(cell):
            return visible_text(cell)[:120]
    return (name or visible_text(item)[:60]).strip()


def _item_groups(main: Tag, base_path: str, soup: BeautifulSoup) -> list[dict]:
    """Repeated sibling elements with the same tag/class signature that each carry a link to a distinct same-origin page (cards, list rows, table rows)."""
    groups = []
    for parent in main.find_all(True):
        buckets: dict[tuple, list[Tag]] = {}
        for c in parent.find_all(True, recursive=False):
            if c.name in ("li", "div", "article", "tr", "section", "a"):
                buckets.setdefault((c.name, tuple(sorted(c.get("class") or []))), []).append(c)
        for sig, els in buckets.items():
            items = []
            for e in els:
                anchors = ([e] if e.name == "a" and e.get("href") else []) + e.find_all("a", href=True)
                hrefs = [h for a in anchors if (h := internal_path(a["href"], base_path))]
                if hrefs:
                    first = next((a for a in anchors if internal_path(a["href"], base_path)), None)
                    items.append({"href": hrefs[0], "name": _item_name(e, first, soup), "text": visible_text(e)[:300], "facts": _facts(e), "locator": locator(e)})
            if len(items) >= 3 and len({i["href"] for i in items}) >= 3 and landmark_of(parent) not in ("nav", "header", "footer"):
                groups.append({"locator": locator(parent), "signature": f"{sig[0]}.{'.'.join(sig[1])}", "items": items})
    # keep outermost non-overlapping groups: drop a group whose item hrefs are a subset of an earlier larger one
    groups.sort(key=lambda g: -len(g["items"]))
    kept = []
    for g in groups:
        hs = {i["href"] for i in g["items"]}
        if not any(hs <= {i["href"] for i in k["items"]} for k in kept):
            kept.append(g)
    return kept


def parse_page(path: str, html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup.find(attrs={"role": "main"}) or soup.body or soup
    controls = []
    for el in soup.find_all(True):
        role = el.get("role")
        interactive = (el.name in ("button", "select", "textarea", "summary") or (el.name == "a" and el.get("href") is not None) or (el.name == "input" and (el.get("type") or "text").lower() != "hidden")
                       or role in INTERACTIVE_ROLES)
        if not interactive or _hidden(el):
            continue
        name, source = accessible_name(el, soup)
        controls.append({"tag": el.name, "role": role, "type": el.get("type"), "name": name, "name_source": source, "href": internal_path(el.get("href"), path) if el.name == "a" else None,
                         "external_href": el.get("href") if el.name == "a" and el.get("href") and internal_path(el.get("href"), path) is None else None,
                         "landmark": landmark_of(el), "locator": locator(el), "native": el.name in ("a", "button", "input", "select", "textarea", "summary")})
    forms = []
    for f in soup.find_all("form"):
        fields = []
        for x in f.find_all(["input", "select", "textarea"]):
            if (x.get("type") or "text").lower() in ("hidden", "submit", "button", "reset", "image"):
                continue
            name, source = accessible_name(x, soup)
            fields.append({"tag": x.name, "type": x.get("type"), "name_attr": x.get("name"), "accessible_name": name, "name_source": source, "required": x.has_attr("required"), "locator": locator(x)})
        submits = [accessible_name(b, soup)[0] for b in f.find_all(["button", "input"]) if b.name == "button" or (b.get("type") or "").lower() in ("submit", "image")]
        forms.append({"action": internal_path(f.get("action") or path, path), "method": (f.get("method") or "get").lower(), "fields": fields, "locator": locator(f), "submit_names": submits})
    jsonld = []
    for s in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            jsonld.append(json.loads(s.string or ""))
        except ValueError:
            pass
    links = []
    for a in main.find_all("a", href=True):
        p = internal_path(a["href"], path)
        if p:
            links.append({"href": p, "text": visible_text(a)[:120], "name": accessible_name(a, soup)[0], "landmark": landmark_of(a)})
    nav_links = [{"href": p, "name": accessible_name(a, soup)[0]} for a in soup.find_all("a", href=True) if landmark_of(a) in ("nav", "header") and (p := internal_path(a["href"], path))]
    desc = soup.find("meta", attrs={"name": "description"})
    return {
        "path": path, "title": norm(soup.title.get_text()) if soup.title else "", "lang": (soup.html.get("lang") if soup.html else None), "description": norm(desc.get("content", "")) if desc else "",
        "headings": [{"level": int(h.name[1]), "text": visible_text(h)} for h in soup.find_all(re.compile(r"^h[1-6]$")) if visible_text(h)],
        "landmarks": sorted({landmark_of(x) for x in soup.find_all(True) if landmark_of(x)}),
        "text": visible_text(main)[:4000], "text_len": len(visible_text(soup)), "links": links, "nav_links": nav_links, "controls": controls, "forms": forms,
        "images": [{"src": i.get("src"), "alt": i.get("alt") if i.has_attr("alt") else None} for i in soup.find_all("img")],
        "tables": [{"headers": [visible_text(h) for h in t.find_all("th")][:10], "rows": len(t.find_all("tr"))} for t in soup.find_all("table")],
        "facts": _facts(main), "item_groups": _item_groups(main, path, soup), "structured_data": jsonld[:3],
    }
