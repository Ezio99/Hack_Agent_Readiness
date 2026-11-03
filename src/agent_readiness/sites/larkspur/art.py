"""Original SVG illustrations for the polished Larkspur site, drawn procedurally for this project (no photographs, no third-party artwork).

Deterministic: the same call always returns the same bytes. The images are decorative (every page states its facts as real text and marks these
images `alt=""`), so no image repeats or replaces a fact from `data.py`."""
from __future__ import annotations

VIOLET, VIOLET_D, VIOLET_L, SKY, SAGE, SAGE_D, CREAM, GOLD, INK, BLUSH = (
    "#5a43a6", "#3a2a78", "#b9a9ec", "#7f93ff", "#7fa383", "#4f7656", "#f7f3ea", "#e7a93c", "#221d3a", "#f1e6f6")

CATEGORY_TINT = {"Arts": ("#f4e3ef", "#c0508a"), "Languages": ("#e5ecfb", "#3f63c7"), "Technology": ("#e6f1ee", "#2f7d6d"),
                 "Trades": ("#f6ebdc", "#b0661f"), "Wellbeing": ("#eef3e3", "#5c8a3a")}


def _svg(w: int, h: int, body: str, label: str = "") -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-hidden="true">'
            f'{f"<title>{label}</title>" if label else ""}{body}</svg>')


def _floret(cx: float, cy: float, r: float, fill: str) -> str:
    """One larkspur floret: five rounded petals around a pale eye."""
    petals = "".join(f'<ellipse cx="{cx}" cy="{cy - r * 0.62:.1f}" rx="{r * 0.42:.1f}" ry="{r * 0.62:.1f}" fill="{fill}" transform="rotate({a} {cx} {cy})"/>'
                     for a in (0, 72, 144, 216, 288))
    return petals + f'<circle cx="{cx}" cy="{cy}" r="{r * 0.22:.1f}" fill="{CREAM}"/>'


def _stalk(x: float, base: float, height: float, scale: float, fill: str) -> str:
    """A larkspur spike: a curved stem with florets shrinking towards the tip."""
    out = [f'<path d="M{x} {base} q{-6 * scale:.1f} {-height / 2:.1f} {4 * scale:.1f} {-height:.1f}" stroke="{SAGE_D}" stroke-width="{3 * scale:.1f}" fill="none" stroke-linecap="round"/>']
    out += [f'<path d="M{x} {base - 18 * scale:.1f} q{-26 * scale:.1f} {-6 * scale:.1f} {-34 * scale:.1f} {-34 * scale:.1f} q{22 * scale:.1f} {4 * scale:.1f} {34 * scale:.1f} {34 * scale:.1f}z" fill="{SAGE}"/>']
    n = 7
    for i in range(n):
        t = i / (n - 1)
        y = base - height * (0.28 + 0.7 * t)
        dx = (-1) ** i * 9 * scale * (1 - t)
        out.append(_floret(x + dx + 3 * scale * t, y, (15 - 9 * t) * scale, fill))
    return "".join(out)


def logo() -> str:
    body = (f'<circle cx="32" cy="32" r="31" fill="{VIOLET_D}"/>'
            f'<path d="M30 54 q-3 -14 2 -38" stroke="{SAGE}" stroke-width="2.5" fill="none" stroke-linecap="round"/>'
            + _floret(31, 40, 7.5, VIOLET_L) + _floret(34, 29, 6.4, "#d9cffa") + _floret(31, 19.5, 5, "#efe9ff") + _floret(33.5, 12, 3.4, "#ffffff"))
    return _svg(64, 64, body)


def hero() -> str:
    """A garden of larkspur spikes in front of a low sun and two rolling hills."""
    body = (f'<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#efe8ff"/><stop offset="1" stop-color="{CREAM}"/></linearGradient></defs>'
            f'<rect width="640" height="480" rx="28" fill="url(#sky)"/>'
            f'<circle cx="452" cy="170" r="92" fill="{GOLD}" opacity=".9"/><circle cx="452" cy="170" r="122" fill="{GOLD}" opacity=".16"/>'
            f'<path d="M0 360 C120 300 240 330 340 350 S540 320 640 300 V480 H0Z" fill="#d7e5d3"/>'
            f'<path d="M0 400 C140 360 260 390 380 400 S560 380 640 372 V480 H0Z" fill="#b8d1b5"/>'
            + _stalk(110, 430, 250, 1.15, VIOLET) + _stalk(178, 440, 300, 1.25, "#7a62cc") + _stalk(250, 436, 220, 1.0, SKY)
            + _stalk(520, 444, 240, 1.05, "#8c6fd8") + _stalk(585, 440, 190, .9, VIOLET)
            + f'<g transform="translate(300 300)"><rect x="0" y="40" width="150" height="100" rx="10" fill="#fff"/><rect x="0" y="40" width="150" height="26" rx="10" fill="{VIOLET_D}"/>'
              f'<rect x="16" y="82" width="90" height="9" rx="4" fill="{VIOLET_L}"/><rect x="16" y="100" width="118" height="9" rx="4" fill="#e7e1f7"/>'
              f'<rect x="16" y="118" width="64" height="9" rx="4" fill="#e7e1f7"/><circle cx="20" cy="53" r="5" fill="{GOLD}"/></g>'
            + f'<path d="M0 452 C160 432 300 452 420 456 S580 446 640 444 V480 H0Z" fill="{SAGE}"/>')
    return _svg(640, 480, body)


def _arts(fg: str) -> str:
    return (f'<path d="M150 70 c-60 0 -100 40 -100 82 c0 30 24 44 46 34 c16 -7 30 6 26 22 c-5 22 14 34 40 30 c58 -8 92 -56 88 -96 c-4 -44 -44 -72 -100 -72z" fill="#fff" stroke="{fg}" stroke-width="5"/>'
            + "".join(f'<circle cx="{x}" cy="{y}" r="14" fill="{c}"/>' for x, y, c in ((112, 112, "#e25b78"), (154, 98, GOLD), (196, 116, "#3f8fcf"), (204, 158, SAGE)))
            + f'<path d="M232 30 L180 170" stroke="{INK}" stroke-width="8" stroke-linecap="round"/><path d="M182 164 q-14 18 -6 34 q14 -6 18 -26z" fill="{fg}"/>')


def _languages(fg: str) -> str:
    return (f'<rect x="40" y="46" width="150" height="92" rx="22" fill="#fff" stroke="{fg}" stroke-width="5"/><path d="M76 136 l-8 30 32 -28z" fill="#fff" stroke="{fg}" stroke-width="5" stroke-linejoin="round"/>'
            f'<rect x="130" y="104" width="140" height="84" rx="22" fill="{fg}"/><path d="M236 186 l10 26 -32 -26z" fill="{fg}"/>'
            f'<rect x="62" y="76" width="96" height="10" rx="5" fill="{fg}" opacity=".5"/><rect x="62" y="98" width="64" height="10" rx="5" fill="{fg}" opacity=".3"/>'
            + "".join(f'<circle cx="{x}" cy="146" r="8" fill="#fff"/>' for x in (172, 200, 228)))


def _technology(fg: str) -> str:
    return (f'<rect x="62" y="44" width="196" height="128" rx="12" fill="{INK}"/><rect x="74" y="56" width="172" height="104" rx="6" fill="#fff"/>'
            f'<path d="M40 182 h240 l-16 16 h-208z" fill="{fg}"/>'
            f'<path d="M118 88 l-22 20 22 20" stroke="{fg}" stroke-width="8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<path d="M202 88 l22 20 -22 20" stroke="{fg}" stroke-width="8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<path d="M174 80 l-26 56" stroke="{GOLD}" stroke-width="8" stroke-linecap="round"/>')


def _trades(fg: str) -> str:
    return (f'<rect x="40" y="150" width="240" height="30" rx="6" fill="#d9a066"/><rect x="40" y="150" width="240" height="8" rx="4" fill="#b5793d"/>'
            f'<path d="M84 60 L196 150" stroke="#7a4e25" stroke-width="12" stroke-linecap="round"/><rect x="58" y="36" width="64" height="34" rx="6" fill="{INK}" transform="rotate(38 90 53)"/>'
            f'<path d="M226 54 L176 148" stroke="{fg}" stroke-width="10" stroke-linecap="round"/><path d="M232 40 l18 12 -16 18 -16 -12z" fill="{INK}"/>'
            + "".join(f'<circle cx="{x}" cy="165" r="4" fill="#7a4e25"/>' for x in (70, 120, 170, 220, 260)))


def _wellbeing(fg: str) -> str:
    leaves = "".join(f'<path d="M160 176 q{d * 70} -30 {d * 78} -96 q{-d * 62} 18 {-d * 78} 96z" fill="{c}"/>' for d, c in ((1, fg), (-1, SAGE)))
    return (f'<circle cx="160" cy="112" r="88" fill="#fff" opacity=".7"/>' + leaves
            + f'<path d="M160 180 q-14 -60 0 -122 q14 62 0 122z" fill="{fg}" opacity=".85"/><path d="M90 190 h140" stroke="{fg}" stroke-width="6" stroke-linecap="round"/>')


DRAW = {"Arts": _arts, "Languages": _languages, "Technology": _technology, "Trades": _trades, "Wellbeing": _wellbeing}


def category(cat: str) -> str:
    bg, fg = CATEGORY_TINT[cat]
    dots = "".join(f'<circle cx="{x}" cy="{y}" r="3" fill="{fg}" opacity=".18"/>' for x in range(20, 320, 34) for y in (18, 214) )
    return _svg(320, 232, f'<rect width="320" height="232" fill="{bg}"/>{dots}' + DRAW[cat](fg))


def campus(name: str) -> str:
    river = name == "Riverside"
    sky, main = ("#e3f1f4", "#2f7d8c") if river else ("#ece6fb", VIOLET)
    body = (f'<rect width="480" height="260" fill="{sky}"/><circle cx="392" cy="70" r="34" fill="{GOLD}" opacity=".85"/>'
            f'<rect x="120" y="92" width="220" height="118" fill="#fff"/><path d="M106 96 L230 40 L354 96z" fill="{main}"/>'
            + "".join(f'<rect x="{x}" y="{y}" width="28" height="30" rx="3" fill="{main}" opacity=".35"/>' for x in (146, 196, 246, 296) for y in (114, 160) if not (x == 216 and y == 160))
            + f'<rect x="212" y="160" width="36" height="50" rx="4" fill="{main}"/>'
            + "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{SAGE}"/><rect x="{x - 3}" y="{y}" width="6" height="{214 - y}" fill="{SAGE_D}"/>' for x, y, r in ((70, 160, 34), (410, 168, 28)))
            + (f'<path d="M0 222 C120 206 240 236 480 214 V260 H0Z" fill="#7fb7c4"/><path d="M0 236 C150 224 300 248 480 232" stroke="#fff" stroke-width="3" fill="none" opacity=".7"/>'
               if river else f'<rect y="210" width="480" height="50" fill="#b8d1b5"/>'))
    return _svg(480, 260, body)


def assets() -> dict[str, bytes]:
    from . import data as D
    out = {"/assets/img/logo.svg": logo(), "/assets/img/hero.svg": hero()}
    out.update({f"/assets/img/subject-{c.lower()}.svg": category(c) for c in D.CATEGORIES})
    out.update({f"/assets/img/campus-{c.lower()}.svg": campus(c) for c in ("Northside", "Riverside")})
    return {k: v.encode() for k, v in out.items()}
