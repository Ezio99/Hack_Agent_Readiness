"""One fact model, two presentations (structured table vs fragmented prose). Every fact in ``facts()`` must appear in both; tests enforce it."""
from __future__ import annotations

from .catalog import Product

YN = {True: "Yes", False: "No"}


def facts(p: Product) -> list[tuple[str, str]]:
    """(label, value) pairs in display order: the single source of truth for specification text."""
    s = p.spec
    if p.category == "headphones":
        battery = f"up to {s('battery_hours')} hours" if s("battery_hours") else "not applicable (wired)"
        return [("Active noise cancelling", YN[s("anc")]), ("Type", s("form").capitalize()), ("Wireless", YN[s("wireless")]), ("Battery life (advertised)", battery)]
    if p.category == "laptops":
        return [("Processor", s("cpu")), ("Memory (RAM)", f"{s('ram_gb')} GB"), ("Storage", f"{s('storage_gb')} GB"), ("Display", f"{s('screen_in'):.1f} inch"),
                ("Battery life (advertised)", f"up to {s('battery_hours')} hours"), ("Weight", f"{s('weight_kg')} kg"), ("Charger", f"{s('charger_w')} W USB-C")]
    if p.category == "monitors":
        return [("Screen size", f"{s('size_in')} inch"), ("Resolution", s("resolution")), ("Refresh rate", f"{s('refresh_hz')} Hz"),
                ("USB-C input", YN[s("usb_c")]), ("Panel", s("panel"))]
    parts = [("Type", s("kind").replace("-", " ").capitalize())]
    if s("output_w"):
        parts.append(("Output power", f"{s('output_w')} W"))
    if s("connector"):
        parts.append(("Connector", s("connector")))
    return parts


def prose(p: Product) -> list[str]:
    """The same facts as running text. Wording differs from the table labels on purpose (that is the factor); every value is present."""
    s, n = p.spec, p.name
    if p.category == "headphones":
        anc = ("Adaptive active noise cancelling keeps commutes and open offices quiet." if s("anc")
               else "This model does not include active noise cancelling.")
        bat = (f"Expect up to {s('battery_hours')} hours of listening on a charge." if s("battery_hours") else "It plugs in with a cable, so there is no battery to charge.")
        conn = "Connects wirelessly to phones and laptops." if s("wireless") else "It is a wired design for studio and desk use."
        return [f"The {n} is an {s('form')} headphone from {p.brand}. {anc}", f"{conn} {bat}"]
    if p.category == "laptops":
        return [f"The {n} pairs a {s('cpu')} processor with {s('ram_gb')} GB of memory and a {s('storage_gb')} GB drive behind a {s('screen_in'):.1f}-inch display.",
                f"{p.brand} quotes up to {s('battery_hours')} hours of battery life. At {s('weight_kg')} kg it is easy to carry, and a {s('charger_w')} W USB-C charger is supplied."]
    if p.category == "monitors":
        usb = ("A USB-C input with power delivery connects a laptop with a single cable." if s("usb_c") else "There is no USB-C input; connect over HDMI or DisplayPort.")
        return [f"The {n} is a {s('size_in')}-inch {s('panel')} monitor with a {s('resolution')} resolution.",
                f"It refreshes at {s('refresh_hz')} Hz for smooth motion. {usb}"]
    bits = [f"The {n} is a {s('kind').replace('-', ' ')} from {p.brand}."]
    if s("output_w"):
        bits.append(f"It delivers up to {s('output_w')} W.")
    if s("connector"):
        bits.append(f"Connector: {s('connector')}.")
    return [" ".join(bits)]


def chips(p: Product) -> list[str]:
    """Key attributes shown on listing cards in the structured presentation only."""
    s = p.spec
    if p.category == "headphones":
        return [("ANC" if s("anc") else "No ANC"), s("form").capitalize()]
    if p.category == "laptops":
        return [f"{s('screen_in'):.1f} inch", f"{s('storage_gb')} GB storage"]
    if p.category == "monitors":
        return [f"{s('size_in')} inch", f"{s('refresh_hz')} Hz"]
    return [s("kind").replace("-", " ").capitalize()]
