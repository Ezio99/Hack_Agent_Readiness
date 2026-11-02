"""Owner-authorised migration of the hosted spending ceiling (M8 follow-up).

The admission policy fails closed when the persisted ceiling differs from `AR_HOSTED_CEILING_USD` (evaluations are disabled, `budget_policy_mismatch`).
That protection is unchanged. This tool is the ONLY way to change the persisted ceiling, and it never touches the accounting:

    python -m agent_readiness.hosted.ceiling status  --db /data/hosted/live/admission.sqlite
    python -m agent_readiness.hosted.ceiling migrate --db /data/hosted/live/admission.sqlite --to 10.736 \\
        --expect-ceiling 10 --expect-reserved 3.3 --reason "..."          # owner, interactive terminal, service stopped

`migrate`:
  * needs an interactive terminal and the owner's typed confirmation of the EXACT transition (it names the database, the current and new ceiling, the
    reserved total, the number of jobs and the reason); there is no API route, so neither the public API nor the operator token can reach it;
  * refuses while the hosted service holds the data directory (`.service.lock`): the running service keeps its policy in memory, so a migration is
    applied with the app stopped and takes effect when it starts with the new `AR_HOSTED_CEILING_USD`;
  * binds what the owner saw: the current ceiling and the reserved total must equal `--expect-ceiling` / `--expect-reserved`, and the per-repetition
    unit and the interval are kept;
  * refuses on unexpected database state (missing or duplicate policy row, unknown schema, negative or non-integer reservations), on any active
    (reserved or running) job, on a new ceiling below the reservations already held, above the programme ceiling (A$50 at the ledger's conservative
    1.50 AUD/USD = US$33.333333), or not a whole number of microdollars;
  * changes ONE value (`policy.ceiling`) and appends ONE audit row (`policy_migrations`) in a single `BEGIN IMMEDIATE` transaction, after re-checking
    everything inside it: a crash leaves either the old state or the new state, never a partial one; jobs, reservations, states and timestamps are
    never rewritten (verified by a fingerprint of the jobs table before and after, recorded in the audit row);
  * is idempotent: re-running a migration whose target is already in place, recorded by the last audit row, reports it and changes nothing.

Rollback of the IMAGE does not need a database change: the previous image opens the same database, finds ceiling != its configured value and stays
fail-closed (evaluations disabled, history viewable) until `AR_HOSTED_CEILING_USD` is set to the migrated value (cap and interval are unchanged, so it
then admits normally). Lowering the ceiling again is a new migration, refused below the reservations held. Reservations are never released."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import socket
import sqlite3
import sys
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

SCHEMA = "hosted-ceiling-migration-v1"
MAX_CEILING_MICROUSD = 33_333_333            # A$50 programme ceiling at the ledger's conservative 1.50 AUD/USD planning rate
JOBS_COLUMNS = ["id", "client", "created", "state", "reserved"]
POLICY_COLUMNS = ["id", "ceiling", "cap", "interval"]
AUDIT_DDL = ("CREATE TABLE IF NOT EXISTS policy_migrations (seq INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, schema TEXT NOT NULL, "
             "from_ceiling INTEGER NOT NULL, to_ceiling INTEGER NOT NULL, cap INTEGER NOT NULL, interval INTEGER NOT NULL, reserved INTEGER NOT NULL, "
             "jobs INTEGER NOT NULL, jobs_fingerprint TEXT NOT NULL, reason TEXT NOT NULL, confirmation TEXT NOT NULL, actor TEXT NOT NULL, host TEXT NOT NULL)")


class MigrationRefused(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code, self.detail = code, detail


def microusd(value: str | float | int, what: str = "amount") -> int:
    try:
        d = Decimal(str(value)) * 1_000_000
    except InvalidOperation:
        raise MigrationRefused("malformed", f"{what} is not a number") from None
    if d != d.to_integral_value() or d < 0:
        raise MigrationRefused("malformed", f"{what} must be a non-negative US$ amount with at most 6 decimals")
    return int(d)


def usd(micro: int) -> str:
    return f"US${micro / 1_000_000:.6f}"


def env_value(micro: int) -> str:
    """The exact `AR_HOSTED_CEILING_USD` value for a ceiling in microdollars (M9: `:g` would round to 6 significant digits, e.g. 12.345678 ->
    12.3457, and the service would then stay fail-closed with budget_policy_mismatch)."""
    text = f"{Decimal(micro) / 1_000_000:f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def _columns(db, table: str) -> list[str]:
    return [r[1] for r in db.execute(f"PRAGMA table_info({table})").fetchall()]


def _connect(path: Path, *, write: bool) -> sqlite3.Connection:
    path = Path(path)
    if not path.is_file():
        raise MigrationRefused("no_database", f"no admission database at {path}")
    return sqlite3.connect(f"file:{path}?mode={'rw' if write else 'ro'}", uri=True, timeout=5, isolation_level=None)


def snapshot(db: sqlite3.Connection) -> dict:
    """The current state, checked for anything unexpected (raises MigrationRefused)."""
    if _columns(db, "policy") != POLICY_COLUMNS or _columns(db, "jobs") != JOBS_COLUMNS:
        raise MigrationRefused("unexpected_schema", "the admission database does not have the expected policy/jobs schema")
    rows = db.execute("SELECT id, ceiling, cap, interval FROM policy").fetchall()
    if len(rows) != 1 or rows[0][0] != 1:
        raise MigrationRefused("unexpected_policy", f"expected exactly one policy row, found {len(rows)}")
    _, ceiling, cap, interval = rows[0]
    if any(type(x) is not int or x <= 0 for x in (ceiling, cap, interval)):
        raise MigrationRefused("unexpected_policy", "the policy row holds non-positive or non-integer values")
    jobs = db.execute("SELECT id, client, created, state, reserved FROM jobs ORDER BY id").fetchall()
    if any(type(j[4]) is not int or j[4] < 0 for j in jobs):
        raise MigrationRefused("unexpected_jobs", "a job holds a negative or non-integer reservation")
    reserved = sum(j[4] for j in jobs)
    active = [j[0] for j in jobs if j[3] in ("reserved", "running")]
    fingerprint = hashlib.sha256(json.dumps(jobs, separators=(",", ":")).encode()).hexdigest()
    history = []
    if "policy_migrations" in {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
        history = [dict(zip(("seq", "at", "from_ceiling", "to_ceiling", "reason", "actor"), r))
                   for r in db.execute("SELECT seq, at, from_ceiling, to_ceiling, reason, actor FROM policy_migrations ORDER BY seq")]
    return {"ceiling": ceiling, "cap": cap, "interval": interval, "reserved": reserved, "remaining": ceiling - reserved, "jobs": len(jobs),
            "active": active, "jobs_fingerprint": fingerprint, "history": history, "by_state": _by_state(jobs)}


def _by_state(jobs) -> dict:
    out: dict = {}
    for j in jobs:
        s = out.setdefault(j[3], {"jobs": 0, "reserved": 0})
        s["jobs"] += 1
        s["reserved"] += j[4]
    return out


def status(path: Path) -> dict:
    db = _connect(path, write=False)
    try:
        return {"database": str(path), **snapshot(db)}
    finally:
        db.close()


def confirmation_text(path: Path, frm: int, to: int, reserved: int, jobs: int, reason: str) -> str:
    return (f"I am the owner and I change the hosted ceiling of {Path(path).resolve()} from {usd(frm)} to {usd(to)} "
            f"with {usd(reserved)} reserved by {jobs} job(s), because: {reason}")


def _service_lock(path: Path):
    lock_path = Path(path).parent / ".service.lock"
    if not lock_path.exists():
        return None
    f = lock_path.open("a")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        f.close()
        raise MigrationRefused("service_running", "the hosted service holds this data directory; stop the app first (docker compose stop app)") from None
    return f


def plan(path: Path, *, to: str, expect_ceiling: str, expect_reserved: str, reason: str) -> dict:
    """Validate a proposed migration against the CURRENT state (read-only). Raises MigrationRefused."""
    if not reason or len(reason.strip()) < 10:
        raise MigrationRefused("malformed", "state the reason for the change (at least 10 characters)")
    target, exp_c, exp_r = microusd(to, "the new ceiling"), microusd(expect_ceiling, "--expect-ceiling"), microusd(expect_reserved, "--expect-reserved")
    st = status(path)
    last = st["history"][-1] if st["history"] else None
    # Already applied (M9): the target is in place and the last audit row recorded it. Re-running the SAME command (`--expect-ceiling` = the old
    # ceiling, e.g. after a dropped SSH session) or one that names the new ceiling is a no-op, not a policy mismatch.
    already = last is not None and target == st["ceiling"] == last["to_ceiling"] and exp_c in (last["from_ceiling"], target)
    if st["ceiling"] != exp_c and not already:
        raise MigrationRefused("policy_mismatch", f"the persisted ceiling is {usd(st['ceiling'])}, not the expected {usd(exp_c)}; nothing changed")
    if st["reserved"] != exp_r:
        raise MigrationRefused("reservations_mismatch", f"{usd(st['reserved'])} is reserved, not the expected {usd(exp_r)}; nothing changed")
    if st["active"]:
        raise MigrationRefused("active_jobs", f"{len(st['active'])} job(s) are reserved or running; wait until none is active")
    if target < st["reserved"]:
        raise MigrationRefused("below_reservations", f"{usd(target)} is below the {usd(st['reserved'])} already reserved (reservations are never released)")
    if target < st["cap"]:
        raise MigrationRefused("below_unit", "the ceiling may not be below the per-repetition unit of the persisted policy")
    if target > MAX_CEILING_MICROUSD:
        raise MigrationRefused("above_programme", f"{usd(target)} exceeds the programme ceiling (A$50 at 1.50 AUD/USD = {usd(MAX_CEILING_MICROUSD)})")
    if target == st["ceiling"] and not already:
        raise MigrationRefused("no_change", "the new ceiling equals the current one")
    return {**st, "to": target, "already_applied": already, "reason": reason.strip(),
            "confirmation": confirmation_text(path, st["ceiling"], target, st["reserved"], st["jobs"], reason.strip())}


def migrate(path: Path, *, to: str, expect_ceiling: str, expect_reserved: str, reason: str, typed: str, interactive: bool, actor: str,
            _fail_before_commit: bool = False) -> dict:
    if not interactive:
        raise MigrationRefused("not_interactive", "the ceiling can only be changed by the owner at an interactive server terminal")
    lock = _service_lock(path)
    try:
        p = plan(path, to=to, expect_ceiling=expect_ceiling, expect_reserved=expect_reserved, reason=reason)
        if p["already_applied"]:
            return {"applied": False, "already_applied": True, "ceiling": p["ceiling"]}
        if typed.strip() != p["confirmation"]:
            raise MigrationRefused("confirmation_mismatch", "the typed confirmation does not match exactly; nothing changed")
        db = _connect(path, write=True)
        try:
            db.execute("PRAGMA busy_timeout=5000")
            db.execute("BEGIN IMMEDIATE")                                      # excludes every other writer until COMMIT
            try:
                now = snapshot(db)                                             # re-check INSIDE the transaction
                if (now["ceiling"], now["reserved"], now["jobs_fingerprint"], now["active"]) != (p["ceiling"], p["reserved"], p["jobs_fingerprint"], []):
                    raise MigrationRefused("concurrent_change", "the admission database changed since the plan was shown; nothing changed")
                db.execute(AUDIT_DDL)
                n = db.execute("UPDATE policy SET ceiling=? WHERE id=1 AND ceiling=? AND cap=? AND interval=?",
                               (p["to"], p["ceiling"], p["cap"], p["interval"])).rowcount
                if n != 1:
                    raise MigrationRefused("concurrent_change", "the policy row changed during the migration; nothing changed")
                db.execute("INSERT INTO policy_migrations (at, schema, from_ceiling, to_ceiling, cap, interval, reserved, jobs, jobs_fingerprint, reason, "
                           "confirmation, actor, host) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (time.time(), SCHEMA, p["ceiling"], p["to"], p["cap"], p["interval"], p["reserved"], p["jobs"], p["jobs_fingerprint"],
                            p["reason"], typed.strip(), actor, socket.gethostname()))
                after = snapshot(db)
                if after["jobs_fingerprint"] != p["jobs_fingerprint"] or after["reserved"] != p["reserved"]:
                    raise MigrationRefused("accounting_changed", "the jobs table changed during the migration; nothing changed")
                if _fail_before_commit:
                    raise RuntimeError("simulated crash before commit (test)")
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise
        finally:
            db.close()
        final = status(path)
        return {"applied": True, "already_applied": False, "from": p["ceiling"], "to": final["ceiling"], "reserved": final["reserved"],
                "remaining": final["remaining"], "jobs": final["jobs"], "audit_seq": final["history"][-1]["seq"]}
    finally:
        if lock is not None:
            lock.close()


def _print_state(st: dict) -> None:
    print(f"database        {st['database']}")
    print(f"policy          ceiling {usd(st['ceiling'])}; per-repetition unit {usd(st['cap'])}; interval {st['interval']} s")
    print(f"reservations    {usd(st['reserved'])} held by {st['jobs']} job(s) " + ", ".join(f"{k}: {v['jobs']} ({usd(v['reserved'])})" for k, v in sorted(st["by_state"].items())))
    print(f"remaining       {usd(st['remaining'])}; active jobs: {len(st['active'])}")
    for h in st["history"]:
        print(f"migration #{h['seq']}    {time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime(h['at']))} {usd(h['from_ceiling'])} -> {usd(h['to_ceiling'])} by {h['actor']}: {h['reason']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agent_readiness.hosted.ceiling")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status")
    s.add_argument("--db", type=Path, required=True)
    m = sub.add_parser("migrate")
    m.add_argument("--db", type=Path, required=True)
    m.add_argument("--to", required=True, help="the new ceiling in US$ (at most 6 decimals)")
    m.add_argument("--expect-ceiling", required=True, help="the ceiling you expect to find now (US$)")
    m.add_argument("--expect-reserved", required=True, help="the reserved total you expect to find now (US$)")
    m.add_argument("--reason", required=True)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "status":
            st = status(a.db)
            _print_state(st)
            return 0
        p = plan(a.db, to=a.to, expect_ceiling=a.expect_ceiling, expect_reserved=a.expect_reserved, reason=a.reason)
        _print_state({"database": str(a.db), **p})
        print(f"proposed        ceiling {usd(p['to'])} (remaining after the change {usd(p['to'] - p['reserved'])}); reason: {p['reason']}")
        if p["already_applied"]:
            print("already applied: the persisted ceiling is the target and the last migration recorded it; nothing changed")
            return 0
        if not sys.stdin.isatty():
            raise MigrationRefused("not_interactive", "migrate needs an interactive terminal (ssh -t / docker compose run -it)")
        print(f"\nType exactly, to confirm (anything else cancels):\n{p['confirmation']}")
        typed = input("> ")
        out = migrate(a.db, to=a.to, expect_ceiling=a.expect_ceiling, expect_reserved=a.expect_reserved, reason=a.reason, typed=typed,
                      interactive=sys.stdin.isatty(), actor=f"owner terminal (uid {os.getuid()})")
        print(f"migrated: ceiling {usd(out['from'])} -> {usd(out['to'])}; reserved {usd(out['reserved'])} by {out['jobs']} job(s) (unchanged); "
              f"audit row #{out['audit_seq']}. Set AR_HOSTED_CEILING_USD={env_value(out['to'])} in deploy/.env before starting the app.")
        return 0
    except MigrationRefused as exc:
        print(f"refused [{exc.code}]: {exc.detail}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
