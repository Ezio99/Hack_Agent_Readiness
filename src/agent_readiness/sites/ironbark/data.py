"""Source of truth for the fictional Ironbark Hire Co. storefront (candidate Experiment-2 site; NOT the EXP-B tool-library site).

Everything the website shows is derived from this module, and the grading helpers in `grading.py` read the same data, so no answer can contradict what the pages expose.
All values are deterministic: no wall-clock time, no unseeded randomness. The "as of" date below is fixed so pages are reproducible; a real business would show live dates.
Ironbark Hire Co., its makers (Kestrel, Marlow, Torvald), phone number and e-mail address are fictional.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from datetime import date, timedelta

AS_OF = date(2026, 11, 2)                       # a Monday; availability and "today" on every page refer to this date
WINDOW_DAYS = 56                                # eight weeks of bookings are modelled (and shown on the availability pages)
LAST_DAY = AS_OF + timedelta(days=WINDOW_DAYS - 1)

BUSINESS = {
    "name": "Ironbark Hire Co.", "tagline": "Tool and equipment hire for tradies and weekend warriors",
    "address": "Unit 4, 18 Foundry Lane, Marrickville NSW 2204", "phone": "(02) 5550 1234", "phone_href": "+61255501234", "email": "hello@ironbarkhire.example",
    "hours": [("Monday to Friday", "7:00 am – 5:00 pm"), ("Saturday", "8:00 am – 12:00 pm"), ("Sunday and public holidays", "Closed")],
}

# --- hire terms (the pricing rules the site states in words on /hire-terms and that `quote()` implements) ---------------------------------------------------------------------------------------
WAIVER_RATE = 0.10                              # optional damage waiver: 10 % of the hire charge, rounded to the nearest cent
DELIVERY_FEES = {"courier": 45, "machine": 120}  # per job, covers delivery AND collection, Sydney metro only
BUNDLE_DISCOUNT = 0.10                          # kits: 10 % off the combined daily/weekend/weekly rates of the hired items; consumables at list price
GST_NOTE = "All prices are in Australian dollars and include GST."
WEEKEND_RULE = "Weekend hire: collect between 1:00 pm and 5:00 pm on Friday, return by 9:00 am on Monday (one weekend rate)."


@dataclass(frozen=True)
class Category:
    slug: str
    name: str
    blurb: str


CATEGORIES = [
    Category("drilling-and-breaking", "Drilling & breaking", "Drills, rotary hammers, breakers and core drills for timber, brick and concrete."),
    Category("cutting", "Cutting", "Wet and dry saws for tiles, paving, concrete and timber."),
    Category("landscaping", "Landscaping", "Hedge, lawn, stump and green-waste machines for the garden and larger blocks."),
    Category("access", "Access & height", "Ladders, scaffold towers and lifts for working safely at height."),
    Category("ground-and-concrete", "Ground & concrete", "Compaction and mixing equipment for paving, slabs and bedding."),
]


@dataclass(frozen=True)
class Product:
    id: str                       # stable product ID, never reused
    slug: str
    category: str                 # Category.slug
    name: str                     # the formal (trade) name used on the site
    maker: str
    model: str
    summary: str                  # one sentence for cards
    description: str
    power: str                    # "240 V mains" | "18 V cordless" | "Petrol"
    weight_kg: float
    daily: int                    # AUD inc. GST
    weekend: int
    weekly: int
    deposit: int                  # refundable pre-authorisation, not a charge
    min_days: int                 # minimum hire in days (weekend hire counts as one 'weekend')
    delivery: str                 # "optional" or "required"
    delivery_class: str           # "courier" or "machine" (fee applies when delivery is chosen or required)
    units: int                    # units in the fleet
    popularity: float             # deterministic booking intensity used to generate the booking calendar
    specs: tuple                  # ordered (label, value) pairs shown in the specification table
    included: tuple               # supplied with the hire
    conditions: tuple             # operator and hire conditions stated on the product page
    jobs: tuple                   # job slugs this item suits (surfaced only by the discoverability variant)
    also_called: tuple            # everyday names customers use (surfaced only by the discoverability variant)
    compat: tuple                 # compatibility tags, e.g. "sds-plus", "blade-350" (matched against accessory.fits)
    drawing: str                  # which illustration to draw


def P(**kw):
    return Product(**kw)


PRODUCTS = [
    P(id="IB-DRL-001", slug="cordless-drill-driver-kit-18v", category="drilling-and-breaking", name="Cordless drill driver kit 18 V", maker="Kestrel", model="KD-18",
      summary="Two-battery 18 V drill driver with hammer action for timber, steel and light masonry.",
      description="A compact two-speed drill driver with a hammer-action mode for the odd brick or block hole. The kit includes two 2.0 Ah batteries and a one-hour charger, so a day of screwing and drilling does not stop for charging.",
      power="18 V cordless", weight_kg=1.8, daily=25, weekend=40, weekly=90, deposit=100, min_days=1, delivery="optional", delivery_class="courier", units=3, popularity=0.10,
      specs=(("Chuck", "13 mm keyless"), ("Max hole, timber", "38 mm"), ("Max hole, steel", "13 mm"), ("Max hole, masonry (hammer mode)", "10 mm"), ("Batteries", "2 × 18 V 2.0 Ah"), ("Weight", "1.8 kg")),
      included=("2 × 18 V batteries", "Charger", "Carry case", "Driver bit set (15 pieces)"),
      conditions=("Operator must be 18 or over.", "Charger is for indoor use only."),
      jobs=("drill-into-brick-or-concrete", "assemble-and-fix"), also_called=("power drill", "screw gun", "battery drill", "impact driver kit"), compat=("kestrel-18v",), drawing="drill"),
    P(id="IB-DRL-002", slug="sds-plus-rotary-hammer-26mm", category="drilling-and-breaking", name="SDS-Plus rotary hammer 26 mm", maker="Kestrel", model="RH-26",
      summary="Mains rotary hammer for clean holes in brick, block and concrete up to 26 mm.",
      description="A 3-mode rotary hammer (drill, hammer-drill, chisel) with a vibration-damped handle. Fitted with a depth stop and an SDS-Plus chuck, it is the standard choice for fixing anchors into concrete and drilling through brick.",
      power="240 V mains", weight_kg=3.1, daily=55, weekend=90, weekly=200, deposit=150, min_days=1, delivery="optional", delivery_class="courier", units=2, popularity=0.11,
      specs=(("Chuck", "SDS-Plus"), ("Max hole, concrete", "26 mm"), ("Max hole, steel", "13 mm"), ("Impact energy", "2.8 J"), ("Modes", "Drill / hammer-drill / chisel"), ("Weight", "3.1 kg")),
      included=("Side handle", "Depth stop", "Carry case"),
      conditions=("Operator must be 18 or over.", "Hearing protection required."),
      jobs=("drill-into-brick-or-concrete",), also_called=("hammer drill", "concrete drill", "masonry drill", "Hilti-style drill"), compat=("sds-plus", "240v"), drawing="rotary"),
    P(id="IB-DRL-003", slug="electric-demolition-hammer-15kg", category="drilling-and-breaking", name="Electric demolition hammer 15 kg", maker="Torvald", model="DH-15",
      summary="Mains-powered demolition hammer for breaking slabs, footings and tiles.",
      description="A 15 kg-class electric demolition hammer with a 30 mm hex chuck. It suits breaking up paths, slabs up to about 100 mm and old tile beds. Chisels are not included and are sold separately.",
      power="240 V mains", weight_kg=15.0, daily=95, weekend=150, weekly=340, deposit=250, min_days=1, delivery="optional", delivery_class="courier", units=2, popularity=0.12,
      specs=(("Chuck", "30 mm hex"), ("Impact energy", "30 J"), ("Blows per minute", "1,400"), ("Suited to slabs up to", "100 mm"), ("Cord length", "5 m"), ("Weight", "15.0 kg")),
      included=("Side handle", "Carry case"),
      conditions=("Operator must be 18 or over.", "Chisels sold separately.", "Hearing and eye protection required."),
      jobs=("break-up-concrete",), also_called=("jackhammer", "jack hammer", "concrete breaker", "electric breaker", "kango"), compat=("hex-30", "240v"), drawing="breaker"),
    P(id="IB-DRL-004", slug="diamond-core-drill-152mm", category="drilling-and-breaking", name="Diamond core drill 152 mm (wet)", maker="Torvald", model="CD-152",
      summary="Wet diamond core drill with stand for large holes through concrete and brick.",
      description="A rig-mounted core drill that cuts clean holes up to 152 mm through reinforced concrete for pipes and vents. Supplied with a stand, a water pressure tank and one 152 mm core bit.",
      power="240 V mains", weight_kg=22.0, daily=120, weekend=190, weekly=430, deposit=400, min_days=1, delivery="optional", delivery_class="machine", units=1, popularity=0.09,
      specs=(("Max hole diameter", "152 mm"), ("Max depth with bit", "300 mm"), ("Water supply", "Pressure tank (supplied)"), ("Speeds", "3"), ("Stand", "Included"), ("Weight (drill and stand)", "22.0 kg")),
      included=("Drill stand", "Water pressure tank", "1 × 152 mm core bit"),
      conditions=("Operator must be 18 or over.", "Wet use: connect through a safety switch (RCD)."),
      jobs=("drill-into-brick-or-concrete", "core-large-holes"), also_called=("core hole machine", "concrete hole saw", "diamond drill"), compat=("240v",), drawing="core"),
    P(id="IB-CUT-001", slug="wet-tile-saw-250mm", category="cutting", name="Wet tile saw 250 mm", maker="Marlow", model="TS-250",
      summary="Bench tile saw with water tray for ceramic, porcelain and natural stone.",
      description="A 250 mm bench tile saw with a sliding table and mitre guide. The water-cooled blade gives chip-free cuts in ceramic, porcelain and natural stone tiles and light pavers up to 80 mm thick.",
      power="240 V mains", weight_kg=17.0, daily=65, weekend=105, weekly=240, deposit=200, min_days=1, delivery="optional", delivery_class="courier", units=2, popularity=0.10,
      specs=(("Blade diameter", "250 mm"), ("Max cutting depth", "80 mm"), ("Max cutting length", "620 mm"), ("Mitre", "0–45°"), ("Water", "Recirculating tray"), ("Weight", "17.0 kg")),
      included=("Continuous-rim tile blade fitted", "Mitre guide"),
      conditions=("Operator must be 18 or over.", "Connect through a safety switch (RCD)."),
      jobs=("cut-tiles-or-paving",), also_called=("tile cutter", "tile cutting machine", "porcelain cutter", "wet saw"), compat=("blade-250", "240v"), drawing="tilesaw"),
    P(id="IB-CUT-002", slug="petrol-cut-off-saw-350mm", category="cutting", name="Petrol cut-off saw 350 mm", maker="Torvald", model="CS-350",
      summary="Hand-held petrol cut-off saw with a 350 mm diamond blade, cuts up to 125 mm deep.",
      description="A powerful 2-stroke cut-off saw for concrete, pavers, bricks and steel pipe. It cuts to a depth of 125 mm and is supplied with a general-purpose diamond blade and a water attachment to keep dust down.",
      power="Petrol (2-stroke)", weight_kg=10.0, daily=110, weekend=175, weekly=395, deposit=300, min_days=1, delivery="optional", delivery_class="courier", units=1, popularity=0.13,
      specs=(("Blade diameter", "350 mm"), ("Max cutting depth", "125 mm"), ("Engine", "73 cc 2-stroke"), ("Fuel", "2-stroke mix (not supplied)"), ("Water attachment", "Included"), ("Weight", "10.0 kg")),
      included=("1 × general-purpose diamond blade fitted", "Water attachment"),
      conditions=("Operator must be 18 or over.", "Fuel not supplied.", "Dust mask, eye and ear protection required."),
      jobs=("cut-tiles-or-paving", "break-up-concrete"), also_called=("concrete saw", "road saw", "quick-cut saw", "consaw", "angle grinder (large)"), compat=("blade-350", "two-stroke"), drawing="cutoff"),
    P(id="IB-CUT-003", slug="petrol-chainsaw-45cm", category="cutting", name="Petrol chainsaw 45 cm", maker="Marlow", model="CH-45",
      summary="45 cm bar petrol chainsaw for felling small trees, limbing and firewood.",
      description="A professional-weight petrol chainsaw with a 45 cm bar and chain brake. Suited to storm clean-up, limbing and cutting firewood. Chaps and helmet are included with every hire.",
      power="Petrol (2-stroke)", weight_kg=5.6, daily=70, weekend=110, weekly=250, deposit=250, min_days=1, delivery="optional", delivery_class="courier", units=2, popularity=0.12,
      specs=(("Bar length", "45 cm"), ("Engine", "50 cc 2-stroke"), ("Fuel", "2-stroke mix (not supplied)"), ("Chain brake", "Inertia"), ("Weight (no fuel)", "5.6 kg")),
      included=("Chainsaw chaps", "Helmet with visor and ear muffs", "Spare chain"),
      conditions=("Operator must be 18 or over.", "Fuel not supplied.", "Chaps and helmet must be worn."),
      jobs=("clear-the-garden",), also_called=("tree saw", "firewood saw", "petrol saw"), compat=("two-stroke",), drawing="chainsaw"),
    P(id="IB-LND-001", slug="cordless-hedge-trimmer-60cm", category="landscaping", name="Cordless hedge trimmer 60 cm", maker="Kestrel", model="HT-60",
      summary="Light 60 cm cordless hedge trimmer on the same battery platform as our 18 V drill.",
      description="A quiet, light trimmer for domestic hedges. It uses the same 18 V batteries as the Kestrel drill kit, and the supplied batteries will cut roughly 250 m of hedge.",
      power="18 V cordless", weight_kg=3.4, daily=35, weekend=55, weekly=125, deposit=100, min_days=1, delivery="optional", delivery_class="courier", units=3, popularity=0.11,
      specs=(("Blade length", "60 cm"), ("Cutting capacity", "20 mm"), ("Batteries", "2 × 18 V 2.0 Ah"), ("Weight", "3.4 kg")),
      included=("2 × 18 V batteries", "Charger", "Blade cover"),
      conditions=("Operator must be 18 or over.",),
      jobs=("clear-the-garden",), also_called=("hedge cutter", "hedge shears", "hedger"), compat=("kestrel-18v",), drawing="hedge"),
    P(id="IB-LND-002", slug="petrol-lawn-scarifier-40cm", category="landscaping", name="Petrol lawn scarifier 40 cm", maker="Marlow", model="SC-40",
      summary="Petrol scarifier with 40 cm working width to remove thatch and renovate lawns.",
      description="A self-propelled scarifier with adjustable depth that lifts thatch and moss, leaving the lawn ready for overseeding. Blades are changed to dethatching or light aeration tines on request.",
      power="Petrol (4-stroke)", weight_kg=34.0, daily=85, weekend=135, weekly=300, deposit=250, min_days=1, delivery="optional", delivery_class="machine", units=1, popularity=0.09,
      specs=(("Working width", "40 cm"), ("Engine", "163 cc 4-stroke"), ("Depth settings", "5"), ("Collection bag", "Included"), ("Weight", "34.0 kg")),
      included=("Dethatching blades fitted", "Collection bag"),
      conditions=("Operator must be 18 or over.", "Delivered with fuel in tank; return with the tank full."),
      jobs=("renovate-a-lawn",), also_called=("dethatcher", "lawn rake", "lawn aerator", "verticutter"), compat=(), drawing="scarifier"),
    P(id="IB-LND-003", slug="stump-grinder-13hp", category="landscaping", name="Stump grinder 13 hp", maker="Torvald", model="SG-13",
      summary="Self-propelled 13 hp stump grinder, grinds stumps up to 300 mm below ground.",
      description="A self-propelled petrol stump grinder with a hydraulic-feel swing control. It grinds stumps up to 500 mm across to about 300 mm below ground level and passes through a standard side gate.",
      power="Petrol (4-stroke)", weight_kg=215.0, daily=190, weekend=300, weekly=680, deposit=500, min_days=1, delivery="required", delivery_class="machine", units=1, popularity=0.10,
      specs=(("Engine", "13 hp 4-stroke"), ("Max stump diameter", "500 mm"), ("Grinding depth below ground", "300 mm"), ("Width", "78 cm (fits a standard gate)"), ("Weight", "215 kg")),
      included=("Operator guide", "Safety chaps and visor"),
      conditions=("Operator must be 18 or over.", "Delivery and collection required.", "Delivered with fuel in tank; return with the tank full."),
      jobs=("clear-the-garden",), also_called=("stump removal machine", "stump cutter", "tree stump grinder"), compat=(), drawing="stump"),
    P(id="IB-LND-004", slug="wood-chipper-100mm", category="landscaping", name="Wood chipper 100 mm", maker="Torvald", model="WC-100",
      summary="Trailer-mounted petrol chipper for branches up to 100 mm across.",
      description="A towable petrol chipper that turns branches up to 100 mm thick into mulch. It is delivered on its own trailer and set up where you need it.",
      power="Petrol (4-stroke)", weight_kg=320.0, daily=180, weekend=285, weekly=640, deposit=500, min_days=1, delivery="required", delivery_class="machine", units=1, popularity=0.12,
      specs=(("Max branch diameter", "100 mm"), ("Engine", "15 hp 4-stroke"), ("Feed", "Gravity hopper"), ("Mounting", "Trailer (supplied)"), ("Weight", "320 kg")),
      included=("Trailer", "Safety visor and ear muffs"),
      conditions=("Operator must be 18 or over.", "Delivery and collection required.", "Delivered with fuel in tank; return with the tank full."),
      jobs=("clear-the-garden",), also_called=("mulcher", "shredder", "branch chipper"), compat=(), drawing="chipper"),
    P(id="IB-ACC-001", slug="fibreglass-extension-ladder-7m", category="access", name="Fibreglass extension ladder 7.3 m", maker="Marlow", model="LD-73",
      summary="Two-section 7.3 m fibreglass extension ladder, reaches a second-storey gutter.",
      description="A Type 1 industrial two-section ladder with non-slip feet. Extended length is 7.3 m, which reaches a typical second-storey gutter line safely at the correct angle. Fibreglass rails are non-conductive.",
      power="Manual", weight_kg=17.5, daily=32, weekend=50, weekly=115, deposit=150, min_days=1, delivery="optional", delivery_class="courier", units=3, popularity=0.14,
      specs=(("Extended length", "7.3 m"), ("Closed length", "4.1 m"), ("Safe working reach", "6.3 m"), ("Duty rating", "Industrial, 120 kg"), ("Rails", "Fibreglass (non-conductive)"), ("Weight", "17.5 kg")),
      included=("Ladder stabiliser", "Safe-use leaflet"),
      conditions=("Operator must be 18 or over.", "Must be tied off at the top when used above 3 m."),
      jobs=("work-at-height",), also_called=("extension ladder", "tall ladder", "two-storey ladder", "gutter ladder"), compat=(), drawing="ladder"),
    P(id="IB-ACC-002", slug="aluminium-scaffold-tower-4m", category="access", name="Aluminium mobile scaffold tower 4 m", maker="Torvald", model="MT-40",
      summary="Mobile aluminium scaffold tower with 4 m working height, delivered and set up.",
      description="A castor-mounted aluminium tower with guard rails and toe boards that gives a 4 m working platform height. The tower is delivered in sections with an assembly guide and can be wheeled around a room or driveway.",
      power="Manual", weight_kg=120.0, daily=75, weekend=120, weekly=270, deposit=300, min_days=2, delivery="required", delivery_class="machine", units=2, popularity=0.13,
      specs=(("Platform working height", "4.0 m"), ("Platform size", "1.8 m × 0.7 m"), ("Safe working load", "200 kg"), ("Castors", "Locking, 4"), ("Weight", "120 kg")),
      included=("Guard rails and toe boards", "Assembly guide", "4 outriggers"),
      conditions=("Operator must be 18 or over.", "Two-day minimum hire.", "Delivery and collection required.", "Must be assembled on firm, level ground."),
      jobs=("work-at-height",), also_called=("scaffolding", "scaffold", "working platform", "painter's scaffold"), compat=(), drawing="scaffold"),
    P(id="IB-ACC-003", slug="electric-scissor-lift-6m", category="access", name="Electric scissor lift 6 m", maker="Torvald", model="SL-60",
      summary="Battery-electric scissor lift with 6 m platform height, narrow enough for a standard doorway.",
      description="A self-propelled electric scissor lift for indoor and outdoor work at height. The platform reaches 6 m and the base passes through a standard 810 mm doorway. Delivered by truck with an operator induction.",
      power="Battery electric", weight_kg=1150.0, daily=210, weekend=330, weekly=740, deposit=600, min_days=2, delivery="required", delivery_class="machine", units=1, popularity=0.11,
      specs=(("Platform height", "6.0 m"), ("Safe working load", "230 kg"), ("Base width", "76 cm"), ("Drive", "Self-propelled"), ("Power", "Battery electric, 24 V"), ("Weight", "1,150 kg")),
      included=("Charger", "Operator induction on delivery"),
      conditions=("Operator must be 18 or over and complete the induction.", "Two-day minimum hire.", "Delivery and collection required."),
      jobs=("work-at-height",), also_called=("platform lift", "access platform", "work platform", "elevated work platform"), compat=(), drawing="scissor"),
    P(id="IB-GRD-001", slug="reversible-plate-compactor-90kg", category="ground-and-concrete", name="Reversible plate compactor 90 kg", maker="Torvald", model="PC-90",
      summary="Reversible 90 kg petrol plate compactor for paving bases and trenches.",
      description="A reversible vibrating plate with a 500 mm base plate, suitable for compacting road base, sand bedding and trench backfill. Optional paving mat is included for finishing pavers.",
      power="Petrol (4-stroke)", weight_kg=90.0, daily=80, weekend=125, weekly=280, deposit=300, min_days=1, delivery="optional", delivery_class="machine", units=2, popularity=0.12,
      specs=(("Plate width", "50 cm"), ("Compaction force", "20 kN"), ("Engine", "5.5 hp 4-stroke"), ("Direction", "Reversible"), ("Weight", "90 kg")),
      included=("Paving mat", "Operator guide"),
      conditions=("Operator must be 18 or over.", "Delivered with fuel in tank; return with the tank full."),
      jobs=("pave-and-compact",), also_called=("whacker packer", "wacker", "ground tamper", "vibrating plate"), compat=(), drawing="compactor"),
    P(id="IB-GRD-002", slug="electric-concrete-mixer-140l", category="ground-and-concrete", name="Electric concrete mixer 140 L", maker="Marlow", model="CM-140",
      summary="140 L electric drum mixer, mixes about three barrow-loads per batch.",
      description="A drum mixer with a tilting frame and a 140 L drum (about 100 L of mixed concrete per batch). Runs from a standard 240 V outlet, so no fuel is needed on site.",
      power="240 V mains", weight_kg=62.0, daily=45, weekend=70, weekly=160, deposit=200, min_days=1, delivery="optional", delivery_class="machine", units=2, popularity=0.12,
      specs=(("Drum capacity", "140 L"), ("Mixed output per batch", "about 100 L"), ("Motor", "650 W, 240 V"), ("Frame", "Tilting, on wheels"), ("Weight", "62 kg")),
      included=("Wheeled stand",),
      conditions=("Operator must be 18 or over.", "Return cleaned of concrete, or a cleaning fee applies."),
      jobs=("pave-and-compact", "mix-concrete"), also_called=("cement mixer", "concrete drum mixer"), compat=("240v",), drawing="mixer"),
]
assert len(PRODUCTS) == 16

JOBS = {   # job slug -> (title, intro)
    "break-up-concrete": ("Break up concrete", "Slabs, footings, old paths and tile beds."),
    "drill-into-brick-or-concrete": ("Drill into brick or concrete", "Anchors, fixings and pipe or vent holes."),
    "cut-tiles-or-paving": ("Cut tiles, pavers or concrete", "Straight and mitred cuts in tile, stone, brick and concrete."),
    "clear-the-garden": ("Clear a garden or remove a stump", "Hedges, branches, storm damage and stumps."),
    "renovate-a-lawn": ("Renovate a lawn", "Thatch and moss removal ahead of reseeding."),
    "work-at-height": ("Work at height", "Gutters, painting and ceiling work."),
    "pave-and-compact": ("Lay pavers or a slab base", "Compacting bedding, trench backfill and mixing concrete."),
    "mix-concrete": ("Mix concrete", "Small to medium batches on site."),
    "core-large-holes": ("Core large holes", "Pipe, vent and flue holes up to 152 mm."),
    "assemble-and-fix": ("Assemble and fix", "Fixing, screwing and general building tasks."),
}


@dataclass(frozen=True)
class Accessory:
    id: str
    slug: str
    name: str
    kind: str                     # "purchase" (consumable, sold) or "hire" (per day)
    price: int                    # purchase price, or daily hire rate
    summary: str
    fits_text: str                # what the control site says in words
    fits: tuple                   # compatibility tags (matched against product.compat); empty tuple = universal
    detail: tuple                 # ordered (label, value)
    drawing: str


ACCESSORIES = [
    Accessory("IB-ACX-001", "sds-plus-masonry-bit-set", "SDS-Plus masonry bit set (5 piece)", "purchase", 38, "Five SDS-Plus bits, 5 to 16 mm, for brick, block and concrete.",
              "SDS-Plus shank. Suits SDS-Plus rotary hammers.", ("sds-plus",), (("Sizes", "5, 6, 8, 10, 16 mm"), ("Shank", "SDS-Plus"), ("Length", "160 mm")), "bits"),
    Accessory("IB-ACX-002", "hex-30-chisel-set", "30 mm hex chisel set (3 piece)", "purchase", 62, "Point, flat and spade chisels for 30 mm hex demolition hammers.",
              "30 mm hex shank. Suits 30 mm hex demolition hammers.", ("hex-30",), (("Pieces", "Point, flat 50 mm, spade 100 mm"), ("Shank", "30 mm hex"), ("Length", "400 mm")), "chisels"),
    Accessory("IB-ACX-003", "diamond-blade-350mm", "Diamond blade 350 mm (concrete and masonry)", "purchase", 149, "Segmented diamond blade for concrete, pavers and brick.",
              "350 mm blade with 25.4 mm bore. Suits 350 mm cut-off saws.", ("blade-350",), (("Diameter", "350 mm"), ("Bore", "25.4 mm"), ("Material", "Concrete, brick, pavers")), "blade"),
    Accessory("IB-ACX-004", "continuous-rim-tile-blade-250mm", "Continuous-rim tile blade 250 mm", "purchase", 45, "Chip-free diamond blade for ceramic, porcelain and stone tile.",
              "250 mm blade with 25.4 mm bore. Suits 250 mm wet tile saws.", ("blade-250",), (("Diameter", "250 mm"), ("Bore", "25.4 mm"), ("Material", "Ceramic, porcelain, stone")), "blade"),
    Accessory("IB-ACX-005", "kestrel-18v-battery-5ah", "Spare 18 V 5.0 Ah battery (Kestrel)", "hire", 8, "Higher-capacity spare battery for the Kestrel 18 V tool platform.",
              "Kestrel 18 V platform. Fits Kestrel 18 V tools.", ("kestrel-18v",), (("Voltage", "18 V"), ("Capacity", "5.0 Ah"), ("Charge time", "1 hour")), "battery"),
    Accessory("IB-ACX-006", "extension-lead-20m", "Heavy-duty extension lead 20 m", "hire", 6, "20 m, 10 A outdoor lead with an RCD at the plug.",
              "240 V, 10 A. Suits any 240 V mains tool.", ("240v",), (("Length", "20 m"), ("Rating", "10 A, 240 V"), ("Protection", "Built-in RCD")), "lead"),
    Accessory("IB-ACX-007", "safety-pack", "Safety pack (glasses, ear muffs, gloves, P2 mask)", "purchase", 29, "Eye, ear, hand and dust protection for one operator.",
              "Universal. Suits any tool.", (), (("Contents", "Safety glasses, ear muffs, gloves, 2 × P2 masks"), ("Size", "One size")), "safety"),
    Accessory("IB-ACX-008", "two-stroke-fuel-mix-5l", "2-stroke fuel mix 5 L (pre-mixed)", "purchase", 18, "Pre-mixed 2-stroke petrol for chainsaws and cut-off saws.",
              "50:1 pre-mix. Suits 2-stroke engines.", ("two-stroke",), (("Volume", "5 L"), ("Mix", "50:1"), ("Fuel", "Unleaded 91 pre-mix")), "fuel"),
]


@dataclass(frozen=True)
class Bundle:
    id: str
    slug: str
    name: str
    summary: str
    hire: tuple                   # product ids hired for the period
    hire_acc: tuple               # hire accessories included in the kit at no extra charge
    buy: tuple                    # accessory ids sold at list price


BUNDLES = [
    Bundle("IB-KIT-001", "concrete-demolition-kit", "Concrete demolition kit", "Demolition hammer, chisel set, safety pack and a 20 m lead.", ("IB-DRL-003",), ("IB-ACX-006",), ("IB-ACX-002", "IB-ACX-007")),
    Bundle("IB-KIT-002", "tile-and-paving-cutting-kit", "Tile and paving cutting kit", "Wet tile saw with a fresh tile blade, safety pack and a 20 m lead.", ("IB-CUT-001",), ("IB-ACX-006",), ("IB-ACX-004", "IB-ACX-007")),
    Bundle("IB-KIT-003", "masonry-drilling-kit", "Masonry drilling kit", "SDS-Plus rotary hammer, masonry bit set, safety pack and a 20 m lead.", ("IB-DRL-002",), ("IB-ACX-006",), ("IB-ACX-001", "IB-ACX-007")),
]

BY_ID = {x.id: x for x in [*PRODUCTS, *ACCESSORIES, *BUNDLES]}
PRODUCT_BY_SLUG = {p.slug: p for p in PRODUCTS}
CATEGORY_BY_SLUG = {c.slug: c for c in CATEGORIES}


# --- derived values -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def rnd(x: float) -> int:
    return int(math.floor(x + 0.5))


def bundle_rates(b: Bundle) -> dict:
    """Combined hire rates for a kit: 10 % off the hired products' combined rates (rounded to the nearest dollar). Hire accessories in the kit (the extension lead) are included at no extra
    charge; consumables are bought separately at list price."""
    hired = [BY_ID[i] for i in b.hire]
    rate = lambda f: sum(f(p) for p in hired)
    full = {"daily": rate(lambda p: p.daily), "weekend": rate(lambda p: p.weekend), "weekly": rate(lambda p: p.weekly)}
    return {"hire": {k: rnd(v * (1 - BUNDLE_DISCOUNT)) for k, v in full.items()}, "list": full, "consumables": sum(BY_ID[i].price for i in b.buy)}


def compatible_accessories(p: Product) -> list[Accessory]:
    return [a for a in ACCESSORIES if a.fits and set(a.fits) & set(p.compat) or (not a.fits)]


def compatible_products(a: Accessory) -> list[Product]:
    return [p for p in PRODUCTS if a.fits and set(a.fits) & set(p.compat)]


def kits_including(item_id: str) -> list[Bundle]:
    return [b for b in BUNDLES if item_id in (*b.hire, *b.hire_acc, *b.buy)]


# --- bookings and dated availability ------------------------------------------------------------------------------------------------------------------------------------------------------
def _byte(*parts) -> int:
    return hashlib.sha256("|".join(map(str, parts)).encode()).digest()[0]


# Hand-written reservations (unit, first day offset, last day offset; offset 0 = Monday 2 Nov 2026). They guarantee that some items are booked out on specific days and weekends so that
# dated-availability questions are not trivial; the hash-generated bookings below fill in the rest of the calendar.
FIXED_BOOKINGS = {
    "IB-DRL-002": [(0, 0, 3), (1, 2, 5)],
    "IB-DRL-003": [(0, 4, 7), (1, 5, 6), (0, 18, 21), (1, 18, 20)],
    "IB-DRL-004": [(0, 1, 3), (0, 8, 10)],
    "IB-CUT-001": [(0, 4, 7), (1, 4, 6)],
    "IB-CUT-002": [(0, 0, 2), (0, 4, 7), (0, 11, 13)],
    "IB-LND-002": [(0, 0, 0), (0, 4, 6)],
    "IB-LND-003": [(0, 7, 9)],
    "IB-LND-004": [(0, 4, 5), (0, 11, 12)],
    "IB-ACC-001": [(0, 5, 5), (1, 5, 6), (2, 5, 5)],
    "IB-ACC-003": [(0, 0, 4), (0, 10, 15)],
    "IB-GRD-001": [(0, 4, 7), (1, 4, 7)],
}


def bookings(p: Product) -> list[tuple[int, int, int]]:
    """Deterministic booking list: (unit, first_day_offset, last_day_offset) inclusive, offsets from AS_OF. Derived from a hash of the product id, never from a clock or an unseeded RNG."""
    out = list(FIXED_BOOKINGS.get(p.id, []))
    for unit in range(p.units):
        d = 0
        while d < WINDOW_DAYS:
            if _byte(p.id, unit, d, "start") / 255 < p.popularity:
                length = 1 + _byte(p.id, unit, d, "len") % 5
                out.append((unit, d, min(d + length - 1, WINDOW_DAYS - 1)))
                d += length + 1
            else:
                d += 1
    return out


def units_free(p: Product, day: date) -> int:
    off = (day - AS_OF).days
    if not 0 <= off < WINDOW_DAYS:
        raise ValueError(f"{day} is outside the modelled booking window {AS_OF}..{LAST_DAY}")
    return p.units - len({u for u, a, b in bookings(p) if a <= off <= b})


def available_on(p: Product, day: date) -> bool:
    return units_free(p, day) > 0


def available_for(p: Product, start: date, end: date) -> bool:
    """A hire is accepted when at least one unit is free on every day from `start` to `end` inclusive (the booking system may allocate a different unit on different days)."""
    d = start
    while d <= end:
        if not available_on(p, d):
            return False
        d += timedelta(days=1)
    return True


def next_free_day(p: Product, after: date = AS_OF) -> date | None:
    d = after
    while d <= LAST_DAY:
        if available_on(p, d):
            return d
        d += timedelta(days=1)
    return None


def next_booked_day(p: Product, after: date = AS_OF) -> date | None:
    d = after
    while d <= LAST_DAY:
        if not available_on(p, d):
            return d
        d += timedelta(days=1)
    return None


def unavailable_periods(p: Product) -> list[tuple[date, date]]:
    """Maximal runs of fully booked days inside the window."""
    runs, start = [], None
    for i in range(WINDOW_DAYS):
        day = AS_OF + timedelta(days=i)
        if not available_on(p, day):
            start = start or day
        elif start:
            runs.append((start, day - timedelta(days=1))); start = None
    if start:
        runs.append((start, LAST_DAY))
    return runs


def weekends() -> list[tuple[date, date]]:
    """(Friday, Monday) pairs of weekend hires that start inside the window and end inside it."""
    out, d = [], AS_OF
    while d <= LAST_DAY:
        if d.weekday() == 4 and d + timedelta(days=3) <= LAST_DAY:
            out.append((d, d + timedelta(days=3)))
        d += timedelta(days=1)
    return out


def next_free_weekend(p: Product) -> tuple[date, date] | None:
    return next((w for w in weekends() if available_for(p, *w)), None)


# --- pricing --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def hire_charge(p: Product, period: str) -> int:
    """period: 'weekend' or '<n>d' for n = 1..7. n days cost n × daily, capped at the weekly rate; 7 days = weekly."""
    if period == "weekend":
        return p.weekend
    n = int(period.rstrip("d"))
    if not 1 <= n <= 7:
        raise ValueError("periods of 1 to 7 days (or a weekend) are priced online; ask for a quote for longer hires")
    if n < p.min_days:
        raise ValueError(f"{p.name} has a minimum hire of {p.min_days} days")
    return min(n * p.daily, p.weekly)


def quote(p: Product, period: str, *, waiver: bool = False, delivery: bool | None = None) -> dict:
    """Total cost of a hire in AUD inc. GST. Delivery is added when chosen, and always when the product requires it. The deposit is refundable and is NOT part of the total."""
    hire = hire_charge(p, period)
    deliver = p.delivery == "required" if delivery is None else (delivery or p.delivery == "required")
    waiver_amt = round(hire * WAIVER_RATE, 2) if waiver else 0.0
    delivery_amt = DELIVERY_FEES[p.delivery_class] if deliver else 0
    return {"product": p.id, "period": period, "hire": hire, "waiver": waiver_amt, "delivery": delivery_amt, "total": round(hire + waiver_amt + delivery_amt, 2), "deposit_held": p.deposit}


def money(x: float) -> str:
    return f"${x:,.0f}" if float(x).is_integer() else f"${x:,.2f}"


def fmt_date(d: date, weekday: bool = True) -> str:
    return f"{d.strftime('%a') + ' ' if weekday else ''}{d.day} {d.strftime('%b')}"


def from_price(p: Product) -> int:
    return p.daily


def export_catalogue() -> dict:
    """The machine-readable source of truth (committed as catalogue.json). Everything here is exposed on the site."""
    prod = lambda p: {**{k: (list(v) if isinstance(v, tuple) else v) for k, v in p.__dict__.items() if k not in ("popularity", "drawing")},
                      "specs": [list(s) for s in p.specs], "bookings": [{"unit": u, "from": (AS_OF + timedelta(days=a)).isoformat(), "to": (AS_OF + timedelta(days=b)).isoformat()} for u, a, b in sorted(set(bookings(p)), key=lambda t: (t[1], t[0]))]}
    return {"business": {**BUSINESS, "hours": [list(h) for h in BUSINESS["hours"]]}, "as_of": AS_OF.isoformat(), "window_last_day": LAST_DAY.isoformat(),
            "terms": {"waiver_rate": WAIVER_RATE, "delivery_fees": DELIVERY_FEES, "bundle_discount": BUNDLE_DISCOUNT, "weekend": WEEKEND_RULE, "gst": GST_NOTE},
            "categories": [c.__dict__ for c in CATEGORIES], "jobs": {k: list(v) for k, v in JOBS.items()},
            "products": [prod(p) for p in PRODUCTS],
            "accessories": [{**{k: (list(v) if isinstance(v, tuple) else v) for k, v in a.__dict__.items() if k != "drawing"}, "detail": [list(x) for x in a.detail]} for a in ACCESSORIES],
            "bundles": [{**{k: list(v) if isinstance(v, tuple) else v for k, v in b.__dict__.items()}, "rates": bundle_rates(b)} for b in BUNDLES]}
