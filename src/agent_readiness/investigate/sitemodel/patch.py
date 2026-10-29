"""Constrained declarative patches over a Snapshot (plan D9). A patch can only change the MIRROR; it is data, validated before and re-checked while applying.

Closed operation set:
  set_attribute         set an allow-listed attribute (aria-label, alt, title, lang) on elements matched by a CSS selector
  insert_text           insert a short text node (span/p/small/strong) next to / inside matched elements
  add_link              insert a link whose target is a page that EXISTS in the snapshot
  copy_field_to_listing for each repeated listing item, copy a labelled fact from the item's detail page into the item (general "show it where the choice is made")

Safety rules (each one tested): no scripts / handlers / HTML markup in values (text only); bounded op count, text length and total inserted bytes; every inserted string must have
PROVENANCE — it is taken from the site's own visible text, from a small fixed vocabulary of interface words, or from the page's own title; link targets must exist; every op must
match something (a patch that does nothing is rejected, not silently accepted); only HTML pages change, never assets; the result is a new Snapshot (parent hash recorded), the
original is untouched. Because inserted text must already exist on the site, a patch cannot invent a task answer; copying existing content to a more discoverable place is the
intended kind of change."""
from __future__ import annotations

import fnmatch
import re
from typing import Annotated, Literal, Union

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, field_validator

from ...suite.core import canonical_hash
from ..inspect.pagemodel import accessible_name, internal_path, norm, parse_page, visible_text
from .snapshot import Resource, Snapshot

MAX_OPS, MAX_TEXT, MAX_INSERTED_BYTES, MAX_PAGES_PER_OP = 40, 200, 20_000, 30
ALLOWED_ATTRS = ("aria-label", "alt", "title", "lang")
ALLOWED_TAGS = ("span", "p", "small", "strong", "li")
VOCAB = frozenset({"Skip to main content", "Search", "Menu", "Open menu", "Close menu", "Home", "Contact", "Contact us", "Submit", "Next", "Previous", "Back", "Close", "Opening hours"})
BAD_TEXT = re.compile(r"[<>]|javascript:|data:|on\w+\s*=", re.I)


class PatchError(ValueError):
    pass


def _text(v: str) -> str:
    v = norm(v)
    if not v or len(v) > MAX_TEXT or BAD_TEXT.search(v):
        raise ValueError("text must be 1-200 characters of plain text (no markup, no javascript:/data: URLs)")
    return v


class _Op(BaseModel):
    pages: list[str] = Field(min_length=1, max_length=MAX_PAGES_PER_OP)
    css: str = Field(min_length=1, max_length=200)

    @field_validator("pages")
    @classmethod
    def _pages(cls, v):
        for p in v:
            if not p.startswith("/") or len(p) > 120 or "\n" in p:
                raise ValueError("page globs are root-relative paths")
        return v


class SetAttribute(_Op):
    op: Literal["set_attribute"] = "set_attribute"
    attr: Literal["aria-label", "alt", "title", "lang"]
    value: str
    only_unnamed: bool = False                    # apply only to elements that currently have NO accessible name (never overrides an existing name)

    @field_validator("value")
    @classmethod
    def _v(cls, v):
        return _text(v)


class InsertText(_Op):
    op: Literal["insert_text"] = "insert_text"
    position: Literal["before", "after", "append", "prepend"] = "after"
    tag: Literal["span", "p", "small", "strong", "li"] = "span"
    text: str

    @field_validator("text")
    @classmethod
    def _v(cls, v):
        return _text(v)


class AddLink(_Op):
    op: Literal["add_link"] = "add_link"
    position: Literal["before", "after", "append", "prepend"] = "after"
    href: str
    text: str

    @field_validator("text")
    @classmethod
    def _v(cls, v):
        return _text(v)


class CopyFieldToListing(_Op):
    """`css` selects each repeated item on the listing page(s); the item's first same-origin link leads to its detail page; `source_label` names a labelled fact there."""
    op: Literal["copy_field_to_listing"] = "copy_field_to_listing"
    source_label: str = Field(min_length=1, max_length=40)
    tag: Literal["span", "p", "small", "strong", "li"] = "p"


Op = Annotated[Union[SetAttribute, InsertText, AddLink, CopyFieldToListing], Field(discriminator="op")]


class Patch(BaseModel):
    description: str = Field(default="", max_length=300)
    ops: list[Op] = Field(min_length=1, max_length=MAX_OPS)

    @property
    def sha256(self) -> str:
        return canonical_hash(self.model_dump())


def _site_text(snap: Snapshot) -> str:
    return " ".join(visible_text(BeautifulSoup(r.text(), "html.parser")) for r in snap.pages())


def _targets(snap: Snapshot, globs: list[str]) -> list[Resource]:
    out = [r for r in snap.pages() if any(fnmatch.fnmatchcase(r.path.split("?")[0], g) for g in globs)]
    if not out:
        raise PatchError(f"no page matches {globs}")
    return out


def _node(soup: BeautifulSoup, container: str, wanted: str, text: str, href: str | None = None):
    """Create the inserted node so the markup stays valid where it lands: a browser's HTML parser would move a <p> or <a> placed directly inside <tr>/<ul>/<ol> OUT of the row/list (foster
    parenting), so the fix would not appear where the static check saw it. Rows get a <td>, lists an <li>."""
    inner = soup.new_tag("a", href=href) if href else soup.new_tag(wanted)
    inner.string = text
    wrap = {"tr": "td", "ul": "li", "ol": "li"}.get(container)
    if wrap is None:
        return inner
    outer = soup.new_tag(wrap)
    outer.append(inner)
    return outer


def _container(el, position: str) -> str:
    return (el.name if position in ("append", "prepend") else getattr(el.parent, "name", "")) or ""


def apply_patch(snap: Snapshot, patch: Patch | dict) -> tuple[Snapshot, dict]:
    """Return (new snapshot, report). Raises PatchError on any rule violation; the input snapshot is never modified."""
    patch = patch if isinstance(patch, Patch) else Patch.model_validate(patch)
    corpus = _site_text(snap)
    pages: dict[str, BeautifulSoup] = {}
    inserted_bytes, report_ops = 0, []

    def soup_of(r: Resource) -> BeautifulSoup:
        if r.path not in pages:
            pages[r.path] = BeautifulSoup(r.text(), "html.parser")
        return pages[r.path]

    def provenance_ok(text: str, soup: BeautifulSoup) -> bool:
        return text in VOCAB or norm(text) in corpus or (soup.title is not None and norm(text) == norm(soup.title.get_text()))

    def place(el, new, position):
        {"before": el.insert_before, "after": el.insert_after, "append": el.append, "prepend": lambda n: el.insert(0, n)}[position](new)

    for i, op in enumerate(patch.ops):
        changed, texts = 0, []
        for r in _targets(snap, op.pages):
            soup = soup_of(r)
            try:
                els = soup.select(op.css)
            except Exception as exc:
                raise PatchError(f"op {i}: invalid selector ({type(exc).__name__})") from None
            if isinstance(op, SetAttribute):
                for el in els:
                    if not provenance_ok(op.value, soup):
                        raise PatchError(f"op {i}: value {op.value!r} has no provenance on the site (not site text, page title or interface vocabulary)")
                    if op.only_unnamed and accessible_name(el, soup)[0]:
                        continue
                    el[op.attr] = op.value
                    changed += 1
                    texts.append(op.value)
            elif isinstance(op, InsertText):
                if els and not provenance_ok(op.text, soup):
                    raise PatchError(f"op {i}: text {op.text!r} has no provenance on the site (not site text, page title or interface vocabulary)")
                for el in els:
                    place(el, _node(soup, _container(el, op.position), op.tag, op.text), op.position)
                    changed += 1
                    texts.append(op.text)
            elif isinstance(op, AddLink):
                target = internal_path(op.href, r.path)
                if target is None or snap.get(target) is None or not snap.get(target).is_html:
                    raise PatchError(f"op {i}: link target {op.href!r} is not a page of this snapshot")
                if els and not provenance_ok(op.text, soup):
                    raise PatchError(f"op {i}: link text {op.text!r} has no provenance on the site")
                for el in els:
                    place(el, _node(soup, _container(el, op.position), "a", op.text, href=target), op.position)
                    changed += 1
                    texts.append(op.text)
            else:                                                            # copy_field_to_listing
                for el in els:
                    anchor = el if el.name == "a" and el.get("href") else el.find("a", href=True)
                    href = internal_path(anchor["href"], r.path) if anchor is not None else None
                    detail = snap.get(href) if href else None
                    if detail is None or not detail.is_html:
                        continue
                    facts = parse_page(detail.path, detail.text())["facts"]
                    fact = next((f for f in facts if f["label"] == op.source_label.lower()), None)
                    if fact is None:
                        continue
                    label_shown = norm(op.source_label)
                    text = f"{label_shown[:1].upper()}{label_shown[1:]}: {fact['value']}"
                    if norm(visible_text(el)).find(fact["value"]) >= 0:
                        continue                                              # already shown on the card
                    el.append(_node(soup, el.name, op.tag, text))
                    changed += 1
                    texts.append(text)
        if changed == 0:
            raise PatchError(f"op {i} ({op.op}) changed nothing: its selector/labels matched no element or no item had the field")
        inserted_bytes += sum(len(t.encode()) for t in texts) if not isinstance(op, SetAttribute) else 0
        if inserted_bytes > MAX_INSERTED_BYTES:
            raise PatchError("patch inserts more than the allowed volume of text")
        report_ops.append({"op": op.op, "elements_changed": changed, "inserted_texts": texts[:20]})
    res, changed_pages = dict(snap.resources), []
    for path, soup in pages.items():
        old = res[path]
        body = soup.decode().encode("utf-8")
        if body != old.body:
            res[path] = Resource(path, old.status, old.content_type, body, old.location)
            changed_pages.append(path)
    new = snap.derive(res, patch_sha256=patch.sha256, patch_description=patch.description)
    return new, {"patch_sha256": patch.sha256, "parent_sha256": snap.sha256, "new_sha256": new.sha256, "pages_changed": sorted(changed_pages), "ops": report_ops, "inserted_bytes": inserted_bytes}
