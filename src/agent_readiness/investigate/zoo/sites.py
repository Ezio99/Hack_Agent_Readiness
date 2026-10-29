"""Small, structurally different, NON-shop test sites generated as static files (`{path: html}`) for development and the blind demonstrations.

Site ids are opaque (`site-N`). Nothing in a served page, a title or a function name below says what, if anything, is wrong with the site; the planted diagnoses live only in
a separate private manifest directory that no inspector/mirror/investigator module reads (a test enforces this). Content is invented."""
from __future__ import annotations

CSS = "body{font:16px/1.5 system-ui;margin:0}header,main,footer{max-width:760px;margin:auto;padding:12px}nav a{margin-right:14px}.card{border:1px solid #ccc;padding:8px;margin:8px 0;list-style:none}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:4px 8px}"


def page(title: str, body: str, nav: str, footer: str = "") -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{title}</title><meta name="description" content="{title}"><style>{CSS}</style></head>'
            f'<body><header>{nav}</header><main>{body}</main><footer>{footer or "&copy; 2026"}</footer></body></html>')


def _dl(rows: list[tuple[str, str]]) -> str:
    return "<dl>" + "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows) + "</dl>"


# --- site-1: community workshops ---------------------------------------------------------------------------------------------------------------------------------------------------
WORKSHOPS = [("pottery-basics", "Pottery Basics", "Hand-building with clay.", "$45", "12 Nov", "3", "Beginner", "Studio A", "2 hours"),
             ("bread-baking", "Sourdough Bread Baking", "Starters, folding and baking.", "$60", "14 Nov", "0", "Beginner", "Kitchen", "3 hours"),
             ("wood-carving", "Spoon Carving", "Carve a spoon with hand tools.", "$38", "19 Nov", "6", "Beginner", "Workshop", "2 hours"),
             ("screen-print", "Screen Printing", "Print your own tote bag.", "$52", "21 Nov", "2", "Intermediate", "Studio B", "3 hours"),
             ("watercolour", "Watercolour Landscapes", "Layering washes outdoors.", "$30", "26 Nov", "9", "Beginner", "Garden", "2 hours"),
             ("bookbinding", "Japanese Bookbinding", "Stab-bind a notebook.", "$42", "28 Nov", "0", "Intermediate", "Studio A", "2 hours"),
             ("candle-making", "Candle Making", "Pour and scent soy candles.", "$35", "3 Dec", "8", "Beginner", "Kitchen", "90 minutes"),
             ("jewellery", "Silver Ring Making", "Forge and polish a ring.", "$85", "5 Dec", "1", "Intermediate", "Workshop", "4 hours")]


def site_1() -> dict:
    nav = '<nav><a href="/">Home</a><a href="/workshops">Workshops</a><a href="/about">About</a><a href="/faq">FAQ</a><a href="/contact">Contact</a></nav>'
    files = {"/": page("Fieldhouse Community Workshops", "<h1>Fieldhouse Community Workshops</h1><p>Short evening and weekend classes run by local makers.</p><p><a href=\"/workshops\">See all workshops</a></p>", nav),
             "/about": page("About Fieldhouse", "<h1>About</h1><p>Fieldhouse is a volunteer-run makers' space opened in 2019.</p>", nav),
             "/faq": page("Frequently asked questions", "<h1>FAQ</h1><h2>Cancellations</h2><p>Full refund up to 7 days before a workshop; none after.</p><h2>What should I bring?</h2><p>All materials are provided.</p>", nav),
             "/contact": page("Contact", "<h1>Contact</h1><p>Email: hello@fieldhouse.example</p><p>Phone: 02 5550 0101</p>", nav)}
    cards = "".join(f'<li class="card"><a href="/workshops/{s}"><h3>{n}</h3></a><p>{b}</p></li>' for s, n, b, *_ in WORKSHOPS)
    files["/workshops"] = page("Workshops", f"<h1>Workshops</h1><ul>{cards}</ul>", nav)
    for s, n, b, price, date, seats, level, loc, dur in WORKSHOPS:
        files[f"/workshops/{s}"] = page(n, f"<h1>{n}</h1><p>{b}</p>" + _dl([("Price", price), ("Date", date), ("Seats left", seats), ("Level", level), ("Location", loc), ("Duration", dur)]) + '<p><a href="/workshops">Back to workshops</a></p>', nav)
    return files


# --- site-2: civic library services ------------------------------------------------------------------------------------------------------------------------------------------------
ICON = '<svg width="20" height="20" viewBox="0 0 20 20"><path d="M2 10h16"/></svg>'
ROOMS = [("quiet-1", "Quiet Room 1", "4", "Desk lamps"), ("quiet-2", "Quiet Room 2", "4", "Desk lamps, whiteboard"), ("group-a", "Group Room A", "8", "Projector, whiteboard"),
         ("group-b", "Group Room B", "10", "Projector, video calls"), ("studio", "Recording Studio", "3", "Microphones, mixer"), ("maker", "Maker Space", "12", "3D printer, soldering")]


def site_2() -> dict:
    nav = ('<nav>' + "".join(f'<a href="{h}">{ICON}</a>' for h in ("/", "/hours", "/rooms", "/catalogue", "/contact")) + '</nav>')
    files = {"/": page("Harbourside Library", "<h1>Harbourside Library</h1><p>Books, study space and community programs.</p>", nav),
             "/hours": page("Opening hours", "<h1>Opening hours</h1><table><tr><th>Day</th><td>Hours</td></tr><tr><th>Monday to Friday</th><td>9am to 8pm</td></tr><tr><th>Saturday</th><td>10am to 4pm</td></tr><tr><th>Sunday</th><td>Closed</td></tr></table>", nav),
             "/contact": page("Contact the library", "<h1>Contact</h1><p>Phone: 02 5550 0188</p><p>Address: 14 Wharf Road</p>", nav),
             "/catalogue": page("Catalogue search", '<h1>Catalogue</h1><form action="/catalogue" method="get"><input type="text" name="q" placeholder="Title or author"><button type="submit">' + ICON + "</button></form>", nav)}
    rows = "".join(f'<tr><td>{n}</td><td>{cap}</td><td>{eq}</td><td><a href="/rooms/{s}">{ICON}</a></td></tr>' for s, n, cap, eq in ROOMS)
    files["/rooms"] = page("Rooms", f"<h1>Rooms</h1><table><tr><th>Room</th><th>Capacity</th><th>Equipment</th><th></th></tr>{rows}</table>", nav)
    for s, n, cap, eq in ROOMS:
        files[f"/rooms/{s}"] = page(n, f"<h1>{n}</h1>" + _dl([("Capacity", cap), ("Equipment", eq), ("Booking limit", "2 hours per day")]) + '<form action="/rooms/book" method="get"><input type="text" name="name" placeholder="Your name"><input type="text" name="slot" placeholder="Time slot"><button type="submit">' + ICON + "</button></form>", nav)
    return files


# --- site-3: recipes -----------------------------------------------------------------------------------------------------------------------------------------------------------------
RECIPES = [("lentil-soup", "Lentil Soup", "35 min", "4", "Easy"), ("shakshuka", "Shakshuka", "25 min", "2", "Easy"), ("mushroom-risotto", "Mushroom Risotto", "50 min", "4", "Medium"),
           ("fish-tacos", "Fish Tacos", "30 min", "3", "Easy"), ("beef-stew", "Beef Stew", "2 hours", "6", "Medium"), ("pad-thai", "Pad Thai", "40 min", "3", "Medium"),
           ("apple-crumble", "Apple Crumble", "55 min", "6", "Easy"), ("croissants", "Butter Croissants", "6 hours", "8", "Hard")]


def site_3() -> dict:
    nav = ('<nav><a href="/">Home</a><a href="/recipes">Recipes</a><a href="/search">Search</a><a href="/policies">Policies</a></nav>')
    files = {"/": page("Brightwater Recipes", '<h1>Brightwater Recipes</h1><p>Tested weeknight and weekend recipes.</p><p><a href="/recipes">Browse recipes</a></p>', nav, '&copy; 2026 · <a href="/policies">Policies</a>'),
             "/policies": page("Policies", "<h1>Policies</h1><h2>Corrections</h2><p>Report an error and we will fix it within 3 working days.</p><h2>Attribution</h2><p>Recipes may be shared with a link back.</p>", nav, '&copy; 2026 · <a href="/policies">Policies</a>'),
             "/search": page("Search recipes", '<h1>Search</h1><form action="/search" method="get"><label for="q">Recipe name or ingredient</label><input id="q" type="text" name="q"><button type="submit">Search</button></form>', nav)}
    cards = "".join(f'<li class="card"><h3><a href="/recipes/{s}">{n}</a></h3><p>Cook time: {t}</p><p>Serves: {sv}</p><p>Difficulty: {d}</p></li>' for s, n, t, sv, d in RECIPES)
    files["/recipes"] = page("Recipes", f"<h1>Recipes</h1><ul>{cards}</ul>", nav)
    for s, n, t, sv, d in RECIPES:
        files[f"/recipes/{s}"] = page(n, f'<h1>{n}</h1><p><img src="/img/{s}.svg" alt="{n} served in a bowl"></p>' + _dl([("Cook time", t), ("Serves", sv), ("Difficulty", d)]) + "<h2>Ingredients</h2><ul><li>See the method for amounts.</li></ul>", nav)
        files[f"/img/{s}.svg"] = (200, "image/svg+xml", '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>')
    return files


# --- site-4: trail guide (development site) ------------------------------------------------------------------------------------------------------------------------------------
TRAILS = [("ridge-loop", "Ridge Loop", "8 km", "Moderate"), ("falls-walk", "Falls Walk", "3 km", "Easy"), ("summit-track", "Summit Track", "14 km", "Hard"),
          ("creek-path", "Creek Path", "5 km", "Easy"), ("canyon-route", "Canyon Route", "12 km", "Hard")]


def site_4() -> dict:
    nav = '<nav><a href="/">Home</a><a href="/trails">Trails</a><a href="/plan">Plan your visit</a></nav>'
    files = {"/": page("Ridgeway Trail Guide", "<h1>Ridgeway Trail Guide</h1><p>Walking trails in the Ridgeway reserve.</p>", nav),
             "/plan": page("Plan your visit", '<h1>Plan your visit</h1><ul><li><a href="/plan/getting-there">Getting there</a></li><li><a href="/plan/permits">Permits</a></li></ul>', nav),
             "/plan/getting-there": page("Getting there", "<h1>Getting there</h1><p>The car park is 2 km past the village on Reserve Road.</p>", nav),
             "/plan/permits": page("Permits", '<h1>Permits</h1><p>Permit types are listed below.</p><ul><li><a href="/plan/permits/day-use">Day-use permits</a></li><li><a href="/plan/permits/camping">Camping permits</a></li></ul>', nav),
             "/plan/permits/day-use": page("Day-use permits", "<h1>Day-use permits</h1>" + _dl([("Required for", "Trails over 10 km"), ("Fee", "$8 per person")]), nav),
             "/plan/permits/camping": page("Camping permits", "<h1>Camping permits</h1><p>Camping is limited to marked sites.</p>", nav)}
    cards = "".join(f'<li class="card"><h3><a href="/trails/{s}">{n}</a></h3><p>Distance: {dist}</p><p>Difficulty: {d}</p></li>' for s, n, dist, d in TRAILS)
    files["/trails"] = page("Trails", f"<h1>Trails</h1><ul>{cards}</ul>", nav)
    for s, n, dist, d in TRAILS:
        files[f"/trails/{s}"] = page(n, f"<h1>{n}</h1>" + _dl([("Distance", dist), ("Difficulty", d)]) + "<p>Permit rules apply to longer trails.</p>", nav)
    return files


BUILDERS = {"site-1": site_1, "site-2": site_2, "site-3": site_3, "site-4": site_4}
