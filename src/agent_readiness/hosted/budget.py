"""Separate, owner-opened evaluation budgets (2026-11): isolated from the A$50 programme, its history and the hosted ceiling.

A budget (write-once row `budgets`) has a fixed limit in integer micro-A$ and a fixed exchange rate (A$ per US$ as an integer ratio, 1.50 = 3/2).
Only spending explicitly charged to it counts:

  * hosted evaluations launched by the signed-in OPERATOR (one click; no launch count, no per-run attestation). What they run is fixed once, when the
    owner opens the budget: the budget pool (`lifecycle.arming.BudgetPool`: frozen suite, website versions, exact manifests, model), part of the same
    typed confirmation. Each launch's `budget_jobs` row is written in the reservation's own transaction; it counts at its full reservation until it
    settles automatically at its ledger-verified actual cost (`settlements`, unchanged rules). The judge arming and the A$50 programme are untouched;
  * off-host work (development, task generation, local experiments): the owner first records an ALLOCATION (its maximum is held before anything is
    sent); afterwards its durable request ledger settles it at the verified actual cost (`allocation_settlements`, write-once; one ledger can be
    charged once, and never if it already settled a hosted job).

    spent       = sum of settled actual costs (jobs and allocations), each converted to micro-A$ rounded up
    outstanding = sum of full reservations / allocation maxima not yet settled, converted the same way
    available   = limit - spent - outstanding          (admission and allocation refuse anything that would make it negative, atomically)

Historical jobs and the A$50 programme never touch a budget: a job without a `budget_jobs` row is a legacy (programme) job, bounded by the hosted
ceiling. There is no transfer operation. Global safety: opening a budget appends a durable global cap = previous cap (or the hosted ceiling) + this
budget's limit in US$ (rounded down), which admission enforces over every commitment in the database; and the total of all budget limits may never
exceed MAX_TOTAL_BUDGETS_MICRO_AUD (a reviewed code constant).

Owner commands (interactive terminal, typed confirmation):
    python -m agent_readiness.hosted.budget status   --db /data/hosted/live/admission.sqlite [--json]
    python -m agent_readiness.hosted.budget open     --db ... --id ar-a20-2026-11 --limit-aud 20 --rate 1.50 --frozen larkspur-core@v3 --variants original improved
    python -m agent_readiness.hosted.budget allocate --db ... --budget ar-a20-2026-11 --ref dev-2026-11-04-taskgen --max-usd 0.50 --purpose "..."
    python -m agent_readiness.hosted.budget settle-allocation --db ... --ref ... --ledger <ledger.jsonl> [...] --expect-settled 0.123456 [--allow-open-requests]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .admission import Admission, Refused, aud_micro

MAX_TOTAL_BUDGETS_MICRO_AUD = 20_000_000          # A$20: the owner's separate allocation (2026-11). Raising it is a reviewed code change.
BUDGET_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,40}$")
REF = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
TERMINAL_ACTOR = "owner terminal"


class BudgetRefused(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code, self.detail = code, detail


def _amount(text: str, what: str, *, zero: bool = False) -> int:
    """A decimal amount -> integer micro-units (exact: at most 6 decimals; positive, or >= 0 with zero=True)."""
    try:
        d = Decimal(str(text)) * 1_000_000
    except InvalidOperation:
        raise BudgetRefused("malformed", f"{what} is not a number") from None
    if not d.is_finite() or d != d.to_integral_value() or d < 0 or (d == 0 and not zero):
        raise BudgetRefused("malformed", f"{what} must be {'non-negative' if zero else 'positive'} with at most 6 decimals")
    return int(d)


def _rate(text: str) -> tuple[int, int]:
    """'1.50' -> (3, 2): A$ per US$ as a reduced integer ratio (at most 4 decimals)."""
    try:
        d = Decimal(str(text))
    except InvalidOperation:
        raise BudgetRefused("malformed", "the rate is not a number") from None
    if d <= 0 or d != d.quantize(Decimal("0.0001")):
        raise BudgetRefused("malformed", "the rate must be positive with at most 4 decimals")
    num, den = int(d * 10_000), 10_000
    from math import gcd
    g = gcd(num, den)
    return num // g, den // g


def aud(m: int) -> str:
    return f"A${m / 1e6:.6f}"


def usd(m: int) -> str:
    return f"US${m / 1e6:.6f}"


# ----------------------------------------------------------------------------------------------------------------------------- open
def open_text(budget_id: str, limit_micro_aud: int, num: int, den: int, limit_microusd: int, cap_after: int) -> str:
    return (f"I am the owner and I open budget {budget_id}: limit {aud(limit_micro_aud)} at {num}/{den} A$ per US$ ({usd(limit_microusd)}); it is separate "
            f"from the A$50 programme and all historical spending; the global hosted cap becomes {usd(cap_after)}")


def plan_open(admission: Admission, budget_id: str, limit_aud: str, rate: str, *, store=None, frozen: str | None = None, variants: list[str] | None = None,
              repetitions: list[int] | None = None, mode: str = "paid") -> dict:
    """Read-only: the budget, the new global cap and (with `frozen`) the operator budget pool it funds; `text` is the one confirmation to type."""
    if not BUDGET_ID.match(budget_id or ""):
        raise BudgetRefused("invalid_id", "budget ids are 3-41 lowercase letters, digits or hyphens")
    limit = _amount(limit_aud, "the limit")
    num, den = _rate(rate)
    limit_usd = limit * den // num                                       # the most this budget can commit in US$ (rounded down)
    with admission.connect() as db:
        led = admission._ledger(db)
    if budget_id in led["budgets"]:
        raise BudgetRefused("exists", f"budget {budget_id} is already open (write-once)")
    total = sum(b["limit_micro_aud"] for b in led["budgets"].values()) + limit
    if total > MAX_TOTAL_BUDGETS_MICRO_AUD:
        raise BudgetRefused("over_maximum", f"all budgets together would be {aud(total)}, above the reviewed maximum {aud(MAX_TOTAL_BUDGETS_MICRO_AUD)}")
    base = led["global_cap"] if led["global_cap"] is not None else admission.ceiling
    cap_after = base + limit_usd
    text = open_text(budget_id, limit, num, den, limit_usd, cap_after)
    pool = None
    if frozen:
        from ..lifecycle import arming as AR
        try:
            pool = AR.pool_terms(store, budget=budget_id, mode=mode, frozen_ref=frozen, variants=list(variants or []), repetitions=list(repetitions or [1]))
        except AR.ArmingRefused as exc:
            raise BudgetRefused(exc.code, exc.detail) from None
        if pool["mode"] == "paid" and pool["synthetic"]:
            raise BudgetRefused("synthetic_suite", "a synthetic fixture suite can never be evaluated with a paid model")
        text = f"{text}. {pool['attestation']}"
    return {"id": budget_id, "limit_micro_aud": limit, "rate_num": num, "rate_den": den, "limit_microusd": limit_usd, "global_cap_before": led["global_cap"],
            "global_cap_after": cap_after, "pool": pool, "text": text}


def open_budget(admission: Admission, budget_id: str, limit_aud: str, rate: str, *, actor: str, typed: str, now: float | None = None, store=None,
                frozen: str | None = None, variants: list[str] | None = None, repetitions: list[int] | None = None, mode: str = "paid") -> dict:
    """Write-once: the operator budget pool record (if any), then, in one transaction, the budget row and the new global cap. Refuses unless
    `typed` is the exact confirmation. A pool without its budget row (a crash in between) launches nothing: admission refuses an unknown budget,
    and re-running `open` with the same terms completes it."""
    p = plan_open(admission, budget_id, limit_aud, rate, store=store, frozen=frozen, variants=variants, repetitions=repetitions, mode=mode) \
        if not (frozen and _pool_exists(budget_id)) else _plan_with_existing_pool(admission, budget_id, limit_aud, rate, store, frozen, variants, repetitions, mode)
    if typed.strip() != p["text"]:
        raise BudgetRefused("confirmation_mismatch", "the typed confirmation does not match; nothing was recorded")
    now = time.time() if now is None else now
    if p["pool"] is not None and not _pool_exists(budget_id):
        from ..lifecycle import arming as AR
        from datetime import datetime, timezone
        AR.record_pool(store, p["pool"], at=datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds"))
    with admission.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            led = admission._ledger(db)
            base = led["global_cap"] if led["global_cap"] is not None else admission.ceiling
            if budget_id in led["budgets"] or base + p["limit_microusd"] != p["global_cap_after"]:
                raise BudgetRefused("changed", "the budgets changed meanwhile; nothing was recorded")
            db.execute("INSERT INTO budgets VALUES (?,?,?,?,?,?,?,?)", (budget_id, p["limit_micro_aud"], p["rate_num"], p["rate_den"], p["limit_microusd"], now,
                                                                       actor, p["text"]))
            db.execute("INSERT INTO global_caps (cap, at, actor, reason) VALUES (?,?,?,?)",
                       (p["global_cap_after"], now, actor, f"budget {budget_id} opened: + {usd(p['limit_microusd'])}"))
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
    return p


def _pool_exists(budget_id: str) -> bool:
    from ..lifecycle import arming as AR
    return AR.pool_path(budget_id).exists()


def _plan_with_existing_pool(admission, budget_id, limit_aud, rate, store, frozen, variants, repetitions, mode) -> dict:
    """Completing an interrupted `open`: the recorded pool must be exactly what would be recorded now."""
    from ..lifecycle import arming as AR
    rec = AR.load_pool(budget_id)
    p = plan_open(admission, budget_id, limit_aud, rate)
    a = {"budget": budget_id, "mode": mode, "site": rec.site, "frozen_suite": frozen, "frozen_suite_sha256": rec.frozen_suite_sha256,
         "variants": [list(v) for v in rec.variants], "options": [o.model_dump() for o in rec.options], "agent": rec.agent}
    if rec.attestation != AR.pool_attestation(a) or [n for n, _ in rec.variants] != list(variants or []) or AR.verify(store, rec):
        raise BudgetRefused("pool_differs", "a different budget pool is already recorded for this budget")
    return {**p, "pool": None, "text": f"{p['text']}. {rec.attestation}"}


# ----------------------------------------------------------------------------------------------------------------------------- allocations
def allocate(admission: Admission, budget_id: str, ref: str, max_usd: str, purpose: str, *, actor: str, now: float | None = None) -> dict:
    """Hold an off-host allocation's maximum in the budget BEFORE any request is sent (atomic budget + global check; write-once ref)."""
    if not REF.match(ref or ""):
        raise BudgetRefused("invalid_ref", "allocation refs are 3-64 lowercase letters, digits, dots, underscores or hyphens")
    if not (purpose or "").strip():
        raise BudgetRefused("invalid_purpose", "state what the allocation is for")
    m = _amount(max_usd, "the maximum")
    now = time.time() if now is None else now
    with admission.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            if db.execute("SELECT 1 FROM budget_allocations WHERE ref=?", (ref,)).fetchone():
                raise BudgetRefused("exists", f"allocation {ref} exists (write-once)")
            admission._check(db, m, budget_id)                                       # raises Refused (unknown budget, budget or global cap)
            db.execute("INSERT INTO budget_allocations VALUES (?,?,?,?,?,?)", (ref, budget_id, purpose.strip(), m, now, actor))
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
    return {"ref": ref, "budget": budget_id, "max_microusd": m}


def assess_allocation(admission: Admission, ref: str, ledgers: list[Path], *, allow_open: bool = False) -> dict:
    """Read-only: the allocation's verified actual cost from its durable request ledger(s)."""
    from .settlement import SettlementRefused, ledger_state
    with admission.connect() as db:
        row = db.execute("SELECT budget_id, max_microusd FROM budget_allocations WHERE ref=?", (ref,)).fetchone()
        done = db.execute("SELECT settled, ledger_sha256 FROM allocation_settlements WHERE ref=?", (ref,)).fetchone()
    if row is None:
        raise BudgetRefused("no_allocation", f"no allocation {ref}")
    if not ledgers:
        raise BudgetRefused("no_ledger", "name the allocation's durable request ledger(s)")
    try:
        led = ledger_state([Path(p) for p in ledgers])
    except SettlementRefused as exc:
        raise BudgetRefused(exc.code, exc.detail) from None
    commit = led["committed_microusd"] if allow_open else led["settled_microusd"]
    out = {"ref": ref, "budget": row[0], "max_microusd": row[1], "ledger": led, "commit_microusd": commit, "settled": done}
    if led["open_requests"] and not allow_open:
        raise BudgetRefused("open_requests", f"{led['open_requests']} request(s) were reserved but never settled; the allocation stays held")
    if commit > row[1]:
        raise BudgetRefused("exceeds_allocation", "the ledger commits more than the allocation's maximum; investigate (nothing released)")
    with admission.connect() as db:
        used = db.execute("SELECT ref FROM allocation_settlements WHERE ledger_sha256=? AND ref<>?", (led["sha256"], ref)).fetchone()
        job = db.execute("SELECT job_id FROM settlements WHERE ledger_sha256=?", (led["sha256"],)).fetchone()
    if used:
        raise BudgetRefused("ledger_already_charged", f"this ledger already settled allocation {used[0]}")
    if job:
        raise BudgetRefused("ledger_already_charged", f"this ledger already settled hosted job {job[0]}")
    return out


def settle_allocation(admission: Admission, ref: str, ledgers: list[Path], *, actor: str, expect_microusd: int | None = None, allow_open: bool = False,
                      now: float | None = None) -> dict:
    """Write-once and idempotent: the same settlement again is a no-op; a different one is refused."""
    a = assess_allocation(admission, ref, ledgers, allow_open=allow_open)
    if expect_microusd is not None and expect_microusd != a["commit_microusd"]:
        raise BudgetRefused("unexpected_amount", f"the ledger commits {a['commit_microusd']} microdollars, not the expected {expect_microusd}")
    led = a["ledger"]
    if a["settled"] is not None:
        if tuple(a["settled"]) != (a["commit_microusd"], led["sha256"]):
            raise BudgetRefused("already_settled", "a different settlement is already recorded; settlements are never changed")
        return {"ref": ref, "settled_microusd": a["commit_microusd"], "already": True}
    now = time.time() if now is None else now
    basis = f"off-host allocation {ref}: {led['settled_requests']}/{led['requests']} requests settled" + (
        f", {led['open_requests']} unsettled committed at their reserved bound" if led["open_requests"] else "")
    with admission.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            if db.execute("SELECT 1 FROM allocation_settlements WHERE ref=?", (ref,)).fetchone():
                raise BudgetRefused("already_settled", "settled meanwhile; nothing changed")
            db.execute("INSERT INTO allocation_settlements VALUES (?,?,?,?,?,?,?,?)", (ref, a["commit_microusd"], basis, led["sha256"], led["requests"],
                                                                                      led["open_requests"], now, actor))
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
    return {"ref": ref, "settled_microusd": a["commit_microusd"], "already": False}


# ----------------------------------------------------------------------------------------------------------------------------- status
def status(admission: Admission) -> dict:
    """Read-only statement of every budget: its figures, every job and allocation charged to it (with reservation, settlement and ledger)."""
    t = admission.totals()
    out = {"database": str(admission.path), "global_cap_microusd": t["global_cap_microusd"], "all_committed_microusd": t["all_committed_microusd"],
           "ceiling_scope": {k: t[k] for k in ("ceiling_microusd", "reserved_microusd", "settled_microusd", "outstanding_microusd", "committed_microusd",
                                                "available_microusd")}, "budgets": []}
    with admission.connect() as db:
        if not admission._has_budgets(db):
            return out
        meta = {r[0]: {"opened_at": r[1], "opened_by": r[2]} for r in db.execute("SELECT id, opened_at, opened_by FROM budgets")}
        jobs = db.execute("SELECT b.budget_id, j.id, j.state, j.reserved, s.settled, s.ledger_sha256 FROM budget_jobs b JOIN jobs j ON j.id=b.job_id "
                          "LEFT JOIN settlements s ON s.job_id=j.id ORDER BY j.created").fetchall()
        allocs = db.execute("SELECT a.budget_id, a.ref, a.purpose, a.max_microusd, x.settled, x.ledger_sha256 FROM budget_allocations a "
                            "LEFT JOIN allocation_settlements x ON x.ref=a.ref ORDER BY a.opened_at").fetchall()
    for b in t["budgets"]:
        out["budgets"].append({**b, **meta.get(b["budget"], {}),
                               "jobs_detail": [{"job": r[1], "state": r[2], "reserved_microusd": r[3], "settled_microusd": r[4], "ledger_sha256": r[5]}
                                               for r in jobs if r[0] == b["budget"]],
                               "allocations_detail": [{"ref": r[1], "purpose": r[2], "max_microusd": r[3], "settled_microusd": r[4], "ledger_sha256": r[5]}
                                                      for r in allocs if r[0] == b["budget"]]})
    return out


def _print_status(st: dict) -> None:
    c = st["ceiling_scope"]
    print(f"database        {st['database']}")
    print(f"hosted ceiling  {usd(c['ceiling_microusd'])} (programme/legacy jobs only): committed {usd(c['committed_microusd'])}, available {usd(c['available_microusd'])}")
    print(f"global cap      {'none (no budget open)' if st['global_cap_microusd'] is None else usd(st['global_cap_microusd'])}; all commitments {usd(st['all_committed_microusd'])}")
    if not st["budgets"]:
        print("budgets         none open")
    for b in st["budgets"]:
        print(f"budget          {b['budget']}: limit {aud(b['limit_micro_aud'])} ({usd(b['limit_microusd'])} at {b['rate_num']}/{b['rate_den']}); spent {aud(b['spent_micro_aud'])}; "
              f"outstanding {aud(b['outstanding_micro_aud'])}; available {aud(b['available_micro_aud'])} ({usd(b['available_microusd'])})")
        for j in b["jobs_detail"]:
            print(f"  job           {j['job']} {j['state']}: reserved {usd(j['reserved_microusd'])}" + (f", settled {usd(j['settled_microusd'])}" if j["settled_microusd"] is not None else ", held in full"))
        for a in b["allocations_detail"]:
            print(f"  allocation    {a['ref']} ({a['purpose']}): max {usd(a['max_microusd'])}" + (f", settled {usd(a['settled_microusd'])}" if a["settled_microusd"] is not None else ", held in full"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m agent_readiness.hosted.budget", description="Separate evaluation budgets (owner tools).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("open")
    s.add_argument("--id", required=True)
    s.add_argument("--limit-aud", required=True)
    s.add_argument("--rate", required=True, help="A$ per US$ (fixed for the budget's life), e.g. 1.50")
    s.add_argument("--frozen", help="the frozen suite the operator's one-click evaluations run, e.g. larkspur-core@v3")
    s.add_argument("--variants", nargs=2, help="the two website versions, e.g. original improved")
    s.add_argument("--mode", choices=("paid", "rehearsal"), default="paid")
    s.add_argument("--store", help="lifecycle store (default: AR_LIFECYCLE_STORE)")
    s = sub.add_parser("allocate")
    s.add_argument("--budget", required=True)
    s.add_argument("--ref", required=True)
    s.add_argument("--max-usd", required=True)
    s.add_argument("--purpose", required=True)
    s = sub.add_parser("settle-allocation")
    s.add_argument("--ref", required=True)
    s.add_argument("--ledger", required=True, nargs="+", type=Path)
    s.add_argument("--expect-settled", required=True)
    s.add_argument("--allow-open-requests", action="store_true")
    for s in sub.choices.values():
        s.add_argument("--db", required=True, type=Path)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "status":
            st = status(Admission.open_read_only(a.db))
            print(json.dumps(st, indent=1)) if a.json else _print_status(st)
            return 0
        if not sys.stdin.isatty():
            print("refused: budget changes are owner actions at an interactive terminal", file=sys.stderr)
            return 2
        adm = Admission.open_existing(a.db)
        actor = f"{TERMINAL_ACTOR} (uid {os.getuid()})"
        if a.cmd == "open":
            store = None
            if a.frozen:
                from ..lifecycle import arming as AR                           # the store only through the lifecycle layer
                store = AR.open_store(Path(a.store or os.environ.get("AR_LIFECYCLE_STORE") or "/data/hosted/lifecycle/store"))
            kw = dict(store=store, frozen=a.frozen, variants=a.variants, mode=a.mode)
            p = plan_open(adm, a.id, a.limit_aud, a.rate, **kw) if not (a.frozen and _pool_exists(a.id)) else \
                _plan_with_existing_pool(adm, a.id, a.limit_aud, a.rate, store, a.frozen, a.variants, [1], a.mode)
            print(p["text"])
            typed = input("Type the line above exactly to confirm: ")
            open_budget(adm, a.id, a.limit_aud, a.rate, actor=actor, typed=typed, **kw)
            print(f"opened {a.id}: available {aud(p['limit_micro_aud'])}; global hosted cap {usd(p['global_cap_after'])}")
            return 0
        if a.cmd == "allocate":
            text = f"I am the owner and I allocate up to US${a.max_usd} from budget {a.budget} to {a.ref}: {a.purpose.strip()}"
            print(text)
            if input("Type the line above exactly to confirm: ").strip() != text:
                print("refused: the confirmation did not match; nothing changed", file=sys.stderr)
                return 1
            allocate(adm, a.budget, a.ref, a.max_usd, a.purpose, actor=actor)
            print(f"allocated {a.ref}; held in full until its ledger settles it")
            return 0
        pre = assess_allocation(adm, a.ref, a.ledger, allow_open=a.allow_open_requests)
        text = f"I am the owner and I settle allocation {a.ref} at {usd(pre['commit_microusd'])} (max {usd(pre['max_microusd'])}), verified against ledger sha256 {pre['ledger']['sha256']}"
        print(text)
        if input("Type the line above exactly to confirm: ").strip() != text:
            print("refused: the confirmation did not match; nothing changed", file=sys.stderr)
            return 1
        out = settle_allocation(adm, a.ref, a.ledger, actor=actor, expect_microusd=_amount(a.expect_settled, "the expected amount", zero=True),
                                allow_open=a.allow_open_requests)
        print(f"settled {a.ref}: {usd(out['settled_microusd'])}{' (already recorded)' if out['already'] else ''}")
        return 0
    except (BudgetRefused, Refused) as exc:
        print(f"refused [{getattr(exc, 'code', 'refused')}]: {getattr(exc, 'detail', exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
