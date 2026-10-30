"""Original SVG illustrations for the Ironbark storefront, drawn procedurally for this project (no photographs, no third-party artwork, no external references).

They are deliberately illustrations, not photography: the repository has no licensed photo library. Every image is generated from `data.py` plus the drawing functions here, so the output is
deterministic. Text inside the SVGs repeats facts from `data.py` only; the HTML pages always carry the same facts as real text and give each image its own alt text.
"""
from __future__ import annotations

from html import escape

from . import data as D

MAKER_COLORS = {"Kestrel": ("#e0561a", "#a93a0c"), "Marlow": ("#2f8f5b", "#1f6340"), "Torvald": ("#f0b323", "#b98307")}
INK, STEEL, STEEL_D, RUBBER = "#1f2a30", "#aab4bd", "#6c7882", "#2a3036"


def R(x, y, w, h, fill, rx=0, extra=""):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" {extra}/>'


def E(cx, cy, rx, ry, fill, extra=""):
    return f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}" {extra}/>'


def C(cx, cy, r, fill, extra=""):
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" {extra}/>'


def PATH(d, fill="none", extra=""):
    return f'<path d="{d}" fill="{fill}" {extra}/>'


def LINE(x1, y1, x2, y2, stroke, w, extra=""):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{w}" stroke-linecap="round" {extra}/>'


def gloss(x, y, w, h, rx=0):
    return R(x, y, w, h, "#fff", rx, 'opacity=".16"')


def wheel(cx, cy, r):
    return C(cx, cy, r, RUBBER) + C(cx, cy, r * 0.55, STEEL) + C(cx, cy, r * 0.18, STEEL_D)


# --- product drawings: each returns SVG elements for an 800×600 canvas with the ground line at about y=500 ---------------------------------------------------------------------------------
def d_drill(c, k):
    return (R(560, 235, 60, 90, k, 28) + R(290, 225, 290, 120, c, 44) + gloss(310, 235, 250, 30, 14) + R(230, 252, 70, 66, STEEL_D, 10) + R(185, 262, 52, 46, STEEL, 8) + R(110, 280, 80, 10, STEEL_D, 4)
            + PATH("M385 340 L475 340 L452 475 L372 475 Z", RUBBER) + R(380, 345, 18, 44, k, 6) + R(352, 472, 140, 52, "#2d343b", 10) + R(352, 472, 140, 14, c, 6)
            + R(620, 430, 120, 80, "#2d343b", 10) + R(620, 430, 120, 16, c, 6) + R(645, 456, 70, 8, STEEL_D, 3))


def d_rotary(c, k):
    return (R(250, 215, 330, 125, c, 38) + gloss(268, 225, 290, 28, 14) + R(190, 235, 80, 85, STEEL_D, 14) + R(130, 262, 70, 36, STEEL, 8) + R(40, 276, 100, 10, STEEL_D, 4)
            + PATH("M565 235 q95 -12 92 82 q-4 84 -92 74", "none", f'stroke="{RUBBER}" stroke-width="30" stroke-linecap="round"') + R(375, 335, 22, 52, k, 7)
            + PATH("M275 335 L240 470", "none", f'stroke="{STEEL_D}" stroke-width="12" stroke-linecap="round"') + R(212, 450, 60, 40, RUBBER, 14, 'transform="rotate(-14 242 470)"'))


def d_breaker(c, k):
    return (R(270, 90, 260, 40, RUBBER, 20) + R(340, 125, 120, 255, c, 28) + gloss(352, 135, 96, 80, 14) + R(350, 220, 100, 26, k, 8) + R(360, 380, 80, 56, STEEL_D, 10)
            + PATH("M385 436 H415 L408 520 L400 548 L392 520 Z", STEEL) + R(300, 190, 40, 14, RUBBER, 7) + PATH("M530 108 q80 10 90 90 q10 60 60 80", "none", f'stroke="{INK}" stroke-width="7" stroke-linecap="round"')
            + R(250, 280, 90, 22, RUBBER, 11))


def d_core(c, k):
    return (R(230, 505, 340, 26, STEEL_D, 6) + R(290, 100, 28, 410, STEEL, 6) + R(330, 150, 160, 130, c, 20) + gloss(340, 158, 140, 28, 10) + R(320, 140, 30, 150, k, 8)
            + R(360, 280, 100, 30, STEEL_D, 6) + R(360, 308, 100, 190, "#c9d1d8", 6) + E(410, 308, 50, 12, "#dde3e8") + R(360, 470, 100, 28, "#9aa4ad", 6)
            + "".join(R(364 + i * 25, 486, 14, 16, "#4b555e", 2) for i in range(4)) + C(570, 220, 70, "none", f'stroke="{RUBBER}" stroke-width="12"')
            + "".join(LINE(570, 220, 570 + 70 * dx, 220 + 70 * dy, RUBBER, 8) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))) + R(120, 340, 110, 160, "#3b7fbf", 14) + R(120, 340, 110, 30, "#2f628f", 12))


def d_tilesaw(c, k):
    return (R(130, 420, 540, 70, c, 14) + R(150, 440, 500, 30, k, 8) + R(220, 372, 360, 16, STEEL, 4) + R(240, 345, 190, 28, "#e6d7bd", 3) + LINE(260, 359, 410, 359, "#c9b693", 3)
            + PATH("M300 372 A130 128 0 0 1 560 372 Z", "#4a545d") + PATH("M318 372 A112 110 0 0 1 542 372 Z", "#2d343b") + gloss(310, 262, 220, 12, 6)
            + R(540, 250, 110, 120, c, 22) + gloss(548, 258, 94, 26, 10) + R(645, 290, 40, 18, RUBBER, 9) + R(150, 380, 70, 50, "#3b7fbf", 8))


def d_cutoff(c, k):
    rim = "".join(f'<rect x="{228 - 4}" y="{150}" width="8" height="26" fill="#2d343b" transform="rotate({a} 228 360)"/>' for a in range(0, 360, 20))
    return (C(228, 360, 178, STEEL) + rim + C(228, 360, 160, "#c5ced6") + C(228, 360, 36, STEEL_D) + C(228, 360, 12, INK) + PATH("M228 360 L228 182 A178 178 0 0 1 392 300 Z", c, 'opacity=".95"')
            + R(380, 250, 230, 180, c, 42) + gloss(396, 262, 190, 30, 14) + R(405, 300, 60, 24, k, 8) + C(540, 330, 30, "#2d343b") + C(540, 330, 14, STEEL)
            + PATH("M570 260 q80 -20 85 60 q4 70 -70 70", "none", f'stroke="{RUBBER}" stroke-width="28" stroke-linecap="round"') + R(300, 440, 60, 40, "#3b7fbf", 8))


def d_chainsaw(c, k):
    teeth = "".join(R(120 + i * 18, 292, 10, 8, "#2d343b", 2) + R(120 + i * 18, 349, 10, 8, "#2d343b", 2) for i in range(18))
    return (R(110, 298, 330, 54, "#5c6770", 27) + R(122, 308, 306, 34, STEEL, 17) + teeth + R(400, 232, 240, 162, c, 42) + gloss(416, 244, 200, 28, 14) + R(560, 214, 70, 28, k, 10)
            + PATH("M600 250 q110 -20 100 70 q-10 60 -100 70", "none", f'stroke="{RUBBER}" stroke-width="28" stroke-linecap="round"') + R(396, 220, 30, 90, RUBBER, 12) + C(520, 300, 26, "#2d343b") + C(520, 300, 12, STEEL))


def d_hedge(c, k):
    teeth = "".join(PATH(f"M{70 + i * 24} 330 l12 22 l12 -22 Z", STEEL_D) + PATH(f"M{70 + i * 24} 300 l12 -20 l12 20 Z", STEEL_D) for i in range(16))
    return (R(70, 298, 400, 34, STEEL, 6) + teeth + R(450, 262, 170, 120, c, 34) + gloss(462, 270, 150, 28, 12) + PATH("M470 262 q70 -90 150 -4", "none", f'stroke="{RUBBER}" stroke-width="22" stroke-linecap="round"')
            + R(590, 330, 110, 70, "#2d343b", 10) + R(590, 330, 110, 14, c, 6) + R(500, 370, 60, 40, RUBBER, 12))


def d_scarifier(c, k):
    return (R(250, 335, 320, 105, c, 30) + gloss(266, 345, 288, 24, 12) + R(330, 255, 130, 90, "#2d343b", 14) + R(345, 240, 100, 24, STEEL_D, 8) + R(260, 290, 60, 50, k, 10) + wheel(300, 470, 44) + wheel(530, 470, 44)
            + LINE(540, 340, 690, 110, RUBBER, 14) + LINE(690, 110, 690, 110, RUBBER, 14) + R(640, 90, 100, 22, RUBBER, 11) + R(570, 360, 120, 100, "#3c4349", 14) + PATH("M580 380 h100 M580 400 h100 M580 420 h100", "none", 'stroke="#5d676f" stroke-width="3"'))


def d_stump(c, k):
    teeth = "".join(f'<rect x="{150 - 5}" y="{300}" width="10" height="22" fill="#2d343b" transform="rotate({a} 150 390)"/>' for a in range(0, 360, 30))
    return (R(70, 440, 150, 56, "#7a5836", 8) + R(220, 335, 360, 112, c, 22) + gloss(236, 345, 330, 22, 10) + R(420, 270, 130, 74, "#2d343b", 14) + R(440, 250, 90, 24, k, 8)
            + LINE(235, 380, 150, 390, STEEL_D, 24) + C(150, 390, 82, STEEL_D) + teeth + C(150, 390, 54, "#3b444c") + C(150, 390, 14, STEEL) + wheel(310, 478, 52) + wheel(520, 478, 52)
            + LINE(560, 340, 700, 150, RUBBER, 14) + R(650, 128, 100, 22, RUBBER, 11))


def d_chipper(c, k):
    return (PATH("M240 190 H470 L420 330 H290 Z", c) + gloss(255, 196, 200, 24, 8) + R(280, 320, 290, 140, c, 22) + gloss(292, 330, 266, 22, 10) + R(500, 250, 80, 90, k, 14)
            + PATH("M565 270 H640 q50 0 50 -60 V150", "none", f'stroke="{k}" stroke-width="56" stroke-linejoin="round"') + R(650, 118, 80, 28, STEEL_D, 6) + wheel(430, 492, 50)
            + LINE(135, 478, 285, 440, STEEL_D, 14) + C(130, 480, 14, STEEL) + LINE(300, 120, 380, 240, "#7a5836", 12) + LINE(340, 100, 400, 230, "#8a653f", 10) + LINE(260, 150, 330, 250, "#6b4c2e", 9))


def d_ladder(c, k):
    base = "".join(R(-66, 250 + i * 40, 132, 11, STEEL, 3) for i in range(6))
    fly = "".join(R(-52, 40 + i * 40, 104, 11, "#dfe5ea", 3) for i in range(6))
    return (f'<g transform="translate(400 30) rotate(-10)">' + R(-72, 220, 12, 260, c, 5) + R(60, 220, 12, 260, c, 5) + base
            + R(-58, 10, 10, 330, k, 4) + R(48, 10, 10, 330, k, 4) + fly + R(-82, 462, 34, 22, RUBBER, 6) + R(48, 462, 34, 22, RUBBER, 6) + R(-62, 300, 26, 8, STEEL_D, 3) + '</g>'
            + R(560, 480, 130, 14, "#3a434a", 5) + R(580, 400, 12, 90, STEEL_D, 4))


def d_scaffold(c, k):
    parts = [R(280, 140, 14, 370, STEEL, 4), R(506, 140, 14, 370, STEEL, 4), R(340, 170, 10, 340, STEEL_D, 3), R(566, 170, 10, 340, STEEL_D, 3)]
    for y in (220, 320, 420):
        parts += [R(280, y, 240, 10, STEEL, 3), R(340, y - 26, 236, 8, STEEL_D, 3)]
    parts += [LINE(287, 230, 513, 320, c, 8), LINE(513, 230, 287, 320, c, 8), LINE(287, 330, 513, 420, c, 8), LINE(513, 330, 287, 420, c, 8)]
    parts += [R(260, 128, 280, 16, "#c9d1d8", 4), R(260, 110, 280, 8, c, 4), R(268, 60, 8, 60, c, 4), R(524, 60, 8, 60, c, 4), R(260, 60, 280, 8, c, 4)]
    parts += [wheel(287, 530, 22), wheel(513, 530, 22), wheel(347, 530, 20), wheel(573, 530, 20)]
    return "".join(parts)


def d_scissor(c, k):
    arms = "".join(LINE(250 + 0, 440 - lvl * 110, 550, 440 - (lvl + 1) * 110, STEEL_D, 20) + LINE(550, 440 - lvl * 110, 250, 440 - (lvl + 1) * 110, STEEL, 20) for lvl in range(3))
    return (R(190, 440, 420, 56, c, 14) + gloss(200, 448, 400, 14, 6) + R(210, 490, 70, 18, RUBBER, 8) + R(520, 490, 70, 18, RUBBER, 8) + wheel(250, 508, 28) + wheel(550, 508, 28)
            + arms + R(220, 94, 360, 22, c, 6) + R(220, 20, 10, 80, STEEL_D, 4) + R(570, 20, 10, 80, STEEL_D, 4) + R(220, 20, 360, 10, STEEL_D, 4) + R(220, 58, 360, 6, STEEL_D, 3))


def d_compactor(c, k):
    return (R(230, 450, 330, 34, STEEL_D, 6) + R(250, 438, 290, 18, "#7c8791", 4) + R(300, 330, 180, 114, c, 22) + gloss(312, 340, 156, 24, 10) + R(470, 300, 70, 90, k, 12) + R(330, 300, 90, 40, "#2d343b", 10)
            + LINE(520, 380, 680, 120, RUBBER, 16) + R(630, 96, 100, 24, RUBBER, 12) + R(560, 410, 130, 12, STEEL_D, 4) + R(260, 476, 270, 10, "#2d343b", 3) + R(220, 484, 30, 24, "#2d343b", 4))


def d_mixer(c, k):
    return (f'<g transform="rotate(-18 400 300)">' + PATH("M290 170 H510 L545 360 Q545 395 510 395 H290 Q255 395 255 360 Z", c) + gloss(300, 180, 200, 24, 10) + E(400, 170, 110, 30, k) + E(400, 170, 86, 20, "#262d33")
            + R(255, 270, 290, 14, k, 4) + '</g>' + R(260, 360, 24, 140, STEEL_D, 6) + R(520, 360, 24, 140, STEEL_D, 6) + R(260, 480, 290, 16, STEEL_D, 6) + wheel(280, 508, 30) + wheel(540, 508, 30) + R(580, 400, 90, 70, "#2d343b", 10) + R(590, 412, 70, 12, c, 5))


DRAWINGS = {"drill": d_drill, "rotary": d_rotary, "breaker": d_breaker, "core": d_core, "tilesaw": d_tilesaw, "cutoff": d_cutoff, "chainsaw": d_chainsaw, "hedge": d_hedge, "scarifier": d_scarifier,
            "stump": d_stump, "chipper": d_chipper, "ladder": d_ladder, "scaffold": d_scaffold, "scissor": d_scissor, "compactor": d_compactor, "mixer": d_mixer}


# --- accessory icons (centred on 400,300) ---------------------------------------------------------------------------------------------------------------------------------------------------
def a_bits(c, k):
    return "".join(R(220 + i * 80, 150 + i * 14, 18, 300 - i * 20, STEEL, 6) + R(214 + i * 80, 130 + i * 14, 30, 34, STEEL_D, 6) + PATH(f"M{220 + i * 80} {150 + i * 14 + 300 - i * 20} h18 l-9 24 Z", "#e6e9ec") for i in range(5))


def a_chisels(c, k):
    return (PATH("M200 190 h60 v230 l-30 50 l-30 -50 Z", STEEL) + R(196, 150, 68, 44, STEEL_D, 8) + PATH("M360 190 h90 v230 l-20 50 h-50 l-20 -50 Z", STEEL) + R(356, 150, 98, 44, STEEL_D, 8)
            + PATH("M540 190 h60 v200 q0 50 -30 80 q-30 -30 -30 -80 Z", STEEL) + R(536, 150, 68, 44, STEEL_D, 8))


def a_blade(c, k):
    seg = "".join(f'<rect x="394" y="96" width="12" height="40" fill="#2d343b" transform="rotate({a} 400 300)"/>' for a in range(0, 360, 20))
    return C(400, 300, 206, STEEL) + seg + C(400, 300, 190, "#d5dbe0") + C(400, 300, 54, STEEL_D) + C(400, 300, 22, INK) + "".join(PATH(f"M400 300 L400 130", "none", f'stroke="#b6bfc7" stroke-width="3" transform="rotate({a} 400 300)"') for a in range(0, 360, 45))


def a_battery(c, k):
    return R(250, 190, 300, 200, "#2d343b", 24) + R(250, 190, 300, 56, c, 20) + R(300, 400, 70, 30, STEEL_D, 6) + R(430, 400, 70, 30, STEEL_D, 6) + R(300, 270, 200, 24, "#4a545d", 8) + R(300, 312, 120, 14, "#4a545d", 6)


def a_lead(c, k):
    coils = "".join(E(400, 300, 190 - i * 24, 130 - i * 14, "none", f'stroke="{c}" stroke-width="12"') for i in range(6))
    return coils + R(540, 300, 110, 50, "#2d343b", 10) + R(640, 312, 28, 8, STEEL, 2) + R(640, 330, 28, 8, STEEL, 2) + R(150, 300, 70, 30, "#2d343b", 10)


def a_safety(c, k):
    return (PATH("M200 220 q110 -70 220 0", "none", f'stroke="{INK}" stroke-width="14" stroke-linecap="round"') + E(205, 270, 56, 70, "#2d343b") + E(415, 270, 56, 70, "#2d343b") + E(205, 270, 34, 50, "#4a545d") + E(415, 270, 34, 50, "#4a545d")
            + E(560, 400, 110, 38, "#cfe3f0", 'opacity=".8"') + PATH("M450 400 q110 -80 220 0", "none", f'stroke="{INK}" stroke-width="8"') + PATH("M250 420 q-40 80 30 130 h90 q40 -30 20 -100 l-20 -50 Z", c) + C(560, 280, 70, "#e8ecef") + C(560, 280, 44, "#d5dbe0"))


def a_fuel(c, k):
    return R(290, 190, 220, 270, "#c62828", 22) + R(300, 160, 70, 40, "#a01c1c", 10) + R(440, 150, 28, 52, STEEL_D, 6) + PATH("M468 160 l60 -30 l16 30 l-50 30 Z", STEEL) + R(310, 280, 180, 100, "#fff", 8, 'opacity=".9"') + "".join(R(325, 296 + i * 26, 150 - i * 18, 12, "#c62828", 3) for i in range(3))


ACCESSORY_DRAWINGS = {"bits": a_bits, "chisels": a_chisels, "blade": a_blade, "battery": a_battery, "lead": a_lead, "safety": a_safety, "fuel": a_fuel}


# --- SVG assembly ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def _svg(inner: str, title: str, w: int = 800, h: int = 600, bg=("#f4f1ea", "#e4dfd2")) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img"><title>{escape(title)}</title>'
            f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{bg[0]}"/><stop offset="1" stop-color="{bg[1]}"/></linearGradient>'
            f'<filter id="blur" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="9"/></filter></defs>'
            f'<rect width="{w}" height="{h}" fill="url(#bg)"/>{inner}</svg>\n')


def _stage(drawing: str, maker: str | None = None, scale: float = 1.0, dx: float = 0, dy: float = 0, accessory: bool = False) -> str:
    c, k = MAKER_COLORS.get(maker or "", ("#e0561a", "#a93a0c"))
    body = (ACCESSORY_DRAWINGS if accessory else DRAWINGS)[drawing](c, k)
    shadow = "" if accessory else f'<ellipse cx="{400 * scale + dx}" cy="{520 * scale + dy}" rx="{270 * scale}" ry="{22 * scale}" fill="#000" opacity=".22" filter="url(#blur)"/>'
    return f'{shadow}<g transform="translate({dx} {dy}) scale({scale})">{body}</g>'


def product_image_main(p: D.Product) -> str:
    return _svg(_stage(p.drawing, p.maker), f"{p.name} (illustration)")


def _wrap(text: str, width: int) -> list[str]:
    lines, cur = [], ""
    for w in text.split():
        if len(cur) + len(w) + 1 > width and cur:
            lines.append(cur); cur = w
        else:
            cur = f"{cur} {w}".strip()
    return lines + [cur]


def product_image_spec(p: D.Product) -> str:
    """Second view: the same machine on a dark panel with the headline facts, taken from the data, as an at-a-glance card."""
    chips = [("Power", p.power), ("Weight", f"{p.weight_kg:g} kg"), ("Hire from", f"{D.money(p.daily)} / day")]
    name = "".join(f'<text x="470" y="{110 + i * 34}" font-size="28" font-weight="700" fill="#fff" font-family="system-ui,Segoe UI,Roboto,sans-serif">{escape(line)}</text>' for i, line in enumerate(_wrap(p.name, 22)))
    cards = "".join(f'<rect x="470" y="{250 + i * 90}" width="290" height="72" rx="12" fill="#ffffff" opacity=".1"/><text x="490" y="{276 + i * 90}" font-size="15" fill="#f0b323" font-family="system-ui,Segoe UI,sans-serif" letter-spacing="1.5">{escape(k.upper())}</text>'
                    f'<text x="490" y="{306 + i * 90}" font-size="24" font-weight="700" fill="#fff" font-family="system-ui,Segoe UI,sans-serif">{escape(v)}</text>' for i, (k, v) in enumerate(chips))
    return _svg(_stage(p.drawing, p.maker, 0.62, 10, 60) + name + cards, f"{p.name}: key facts card", bg=("#26323a", "#182026"))


def accessory_image(a: D.Accessory) -> str:
    return _svg(_stage(a.drawing, None, 1.0, 0, 0, accessory=True), f"{a.name} (illustration)", bg=("#f4f1ea", "#e4dfd2"))


def bundle_image(b: D.Bundle) -> str:
    main = D.BY_ID[b.hire[0]]
    accs = [D.BY_ID[i] for i in (*b.buy, *b.hire_acc)][:3]
    inner = _stage(main.drawing, main.maker, 0.78, 10, 10)
    for i, a in enumerate(accs):
        inner += f'<g transform="translate({510 + (i % 2) * 140} {70 + (i // 2) * 170}) scale(.3)">{ACCESSORY_DRAWINGS[a.drawing](*MAKER_COLORS["Kestrel"])}</g>'
    return _svg(inner, f"{b.name} (illustration)")


def category_image(slug: str) -> str:
    items = [p for p in D.PRODUCTS if p.category == slug][:2]
    inner = _stage(items[0].drawing, items[0].maker, 0.7, 20, 40)
    if len(items) > 1:
        inner += _stage(items[1].drawing, items[1].maker, 0.45, 400, 230)
    return _svg(inner, f"{D.CATEGORY_BY_SLUG[slug].name} (illustration)")


def hero_image() -> str:
    # three pieces on one floor line, centres at x = 160, 500, 840 (each drawing is centred near x = 400 on its own canvas)
    layout = [("breaker", "Torvald", 0.78, 160), ("scaffold", "Torvald", 0.78, 500), ("tilesaw", "Marlow", 0.62, 790)]
    inner = '<rect x="0" y="490" width="1000" height="110" fill="#10171b" opacity=".55"/>'
    for d, m, sc, cx in layout:
        inner += _stage(d, m, sc, cx - 400 * sc, 505 - 520 * sc)
    return _svg(inner, "Ironbark Hire Co. equipment range (illustration)", 1000, 600, bg=("#2c3b44", "#162026"))


def logo_svg() -> str:
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64" role="img"><title>Ironbark Hire Co. logo</title>'
            '<polygon points="32,3 58,18 58,46 32,61 6,46 6,18" fill="#e0561a"/><polygon points="32,10 52,21.500 52,42.500 32,54 12,42.500 12,21.500" fill="#1f2a30"/>'
            '<rect x="28" y="20" width="8" height="24" rx="2" fill="#f0b323"/><rect x="22" y="20" width="20" height="6" rx="2" fill="#f0b323"/><rect x="22" y="38" width="20" height="6" rx="2" fill="#f0b323"/></svg>\n')
