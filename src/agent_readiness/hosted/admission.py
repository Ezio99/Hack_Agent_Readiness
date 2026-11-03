"""Durable conservative admission for a single hosted paired evaluation.

Dollar values are integer microdollars. Reservations survive crashes and are
never reduced merely because a worker failed or disappeared.

Final showcase: actual-cost settlement (`settlement.py`). A job's commitment against the ceiling is its verified settled cost once a settlement
row exists, else its full reservation; admission enforces  sum(committed) + new reservation <= ceiling.  `jobs.reserved` is never rewritten;
settlements are write-once rows in their own table, so an older image (which only sums `jobs.reserved`) stays correct and more conservative.

Separate budgets (2026-11, `budget.py`): a job charged to an owner-opened budget (`budget_jobs`, written in the reservation's own transaction) is
bounded by that budget, in integer micro-A$ at the budget's fixed rate, and NOT by the hosted ceiling, which now scopes the legacy (programme) jobs only.
While a budget is open it is SHARED: every new evaluation reservation is charged to it, whoever launches it and by whatever path (decided inside the
reservation's own transaction); jobs reserved before it opened, e.g. eval-c04, keep their scope and never consume it.
A durable global cap (`global_caps`, raised only when the owner opens a budget, by exactly that budget's limit) bounds every commitment in this
database together. An older image ignores these tables and counts every job against the ceiling again (more conservative).
"""
from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path


class Refused(ValueError):
    pass


SETTLEMENT_DDL = ('CREATE TABLE IF NOT EXISTS settlements (job_id TEXT PRIMARY KEY, settled INTEGER NOT NULL CHECK (settled >= 0), basis TEXT NOT NULL, '
                  'ledger_sha256 TEXT NOT NULL, ledger_requests INTEGER NOT NULL, open_requests INTEGER NOT NULL, at REAL NOT NULL, actor TEXT NOT NULL)',
                  'CREATE TABLE IF NOT EXISTS auto_settle (job_id TEXT PRIMARY KEY, at REAL NOT NULL)')
# committed per job: its settlement if recorded (only ever <= its reservation), else its full reservation
COMMITTED_SQL = 'SELECT COALESCE(SUM(CASE WHEN s.job_id IS NULL THEN j.reserved ELSE s.settled END),0) FROM jobs j LEFT JOIN settlements s ON s.job_id=j.id'
# separate budgets (additive, write-once rows; see budget.py)
BUDGET_DDL = ('CREATE TABLE IF NOT EXISTS budgets (id TEXT PRIMARY KEY, limit_micro_aud INTEGER NOT NULL CHECK (limit_micro_aud > 0), rate_num INTEGER NOT NULL '
              'CHECK (rate_num > 0), rate_den INTEGER NOT NULL CHECK (rate_den > 0), limit_microusd INTEGER NOT NULL CHECK (limit_microusd > 0), opened_at REAL NOT NULL, '
              'opened_by TEXT NOT NULL, attestation TEXT NOT NULL)',
              'CREATE TABLE IF NOT EXISTS budget_jobs (job_id TEXT PRIMARY KEY, budget_id TEXT NOT NULL, at REAL NOT NULL)',
              'CREATE TABLE IF NOT EXISTS budget_allocations (ref TEXT PRIMARY KEY, budget_id TEXT NOT NULL, purpose TEXT NOT NULL, '
              'max_microusd INTEGER NOT NULL CHECK (max_microusd > 0), opened_at REAL NOT NULL, opened_by TEXT NOT NULL)',
              'CREATE TABLE IF NOT EXISTS allocation_settlements (ref TEXT PRIMARY KEY, settled INTEGER NOT NULL CHECK (settled >= 0), basis TEXT NOT NULL, '
              'ledger_sha256 TEXT NOT NULL UNIQUE, ledger_requests INTEGER NOT NULL, open_requests INTEGER NOT NULL, at REAL NOT NULL, actor TEXT NOT NULL)',
              'CREATE TABLE IF NOT EXISTS global_caps (seq INTEGER PRIMARY KEY AUTOINCREMENT, cap INTEGER NOT NULL CHECK (cap > 0), at REAL NOT NULL, '
              'actor TEXT NOT NULL, reason TEXT NOT NULL)')
JOB_COMMITTED_SQL = ('SELECT j.id, CASE WHEN s.job_id IS NULL THEN j.reserved ELSE s.settled END, s.job_id IS NOT NULL, j.reserved, b.budget_id '
                     'FROM jobs j LEFT JOIN settlements s ON s.job_id=j.id LEFT JOIN budget_jobs b ON b.job_id=j.id')
ALLOC_COMMITTED_SQL = ('SELECT a.ref, a.budget_id, a.max_microusd, x.settled FROM budget_allocations a LEFT JOIN allocation_settlements x ON x.ref=a.ref')


def aud_micro(microusd: int, rate_num: int, rate_den: int) -> int:
    """µUS$ -> µA$ at rate_num/rate_den A$ per US$, rounded UP (a commitment is never understated)."""
    return -(-microusd * rate_num // rate_den)


class Admission:
    def __init__(self, path: Path, *, ceiling_microusd: int, job_cap_microusd: int, min_interval_seconds: int = 60):
        if any(type(x) is not int or x <= 0 for x in (ceiling_microusd, job_cap_microusd, min_interval_seconds)) or job_cap_microusd > ceiling_microusd:
            raise ValueError('invalid hosted policy')
        self.path = Path(path)
        self.ceiling, self.cap, self.interval = ceiling_microusd, job_cap_microusd, min_interval_seconds
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, client TEXT NOT NULL, created REAL NOT NULL, state TEXT NOT NULL, reserved INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS policy (id INTEGER PRIMARY KEY CHECK (id=1), ceiling INTEGER NOT NULL, cap INTEGER NOT NULL, interval INTEGER NOT NULL)')
            db.execute('INSERT OR IGNORE INTO policy VALUES (1,?,?,?)', (self.ceiling, self.cap, self.interval))
            if db.execute('SELECT ceiling, cap, interval FROM policy WHERE id=1').fetchone() != (self.ceiling, self.cap, self.interval):
                raise ValueError('hosted budget policy differs from durable policy; manual reconciliation required')
            for ddl in SETTLEMENT_DDL + BUDGET_DDL:                        # additive: no existing row or table changes
                db.execute(ddl)
        self._ro = False

    @classmethod
    def open_existing(cls, path: Path) -> 'Admission':
        """Open with the durable policy (used by the worker, which must not define its own)."""
        db = sqlite3.connect(f'file:{Path(path)}?mode=rw', uri=True, timeout=10)
        try:
            row = db.execute('SELECT ceiling, cap, interval FROM policy WHERE id=1').fetchone()
        finally:
            db.close()
        if not row:
            raise ValueError('hosted budget policy is missing')
        return cls(path, ceiling_microusd=row[0], job_cap_microusd=row[1], min_interval_seconds=row[2])

    @classmethod
    def open_read_only(cls, path: Path) -> 'Admission':
        """Read-only view (audits): opens the database with mode=ro and never creates or changes anything."""
        db = sqlite3.connect(f'file:{Path(path)}?mode=ro', uri=True, timeout=10)
        try:
            row = db.execute('SELECT ceiling, cap, interval FROM policy WHERE id=1').fetchone()
        finally:
            db.close()
        if not row:
            raise ValueError('hosted budget policy is missing')
        self = cls.__new__(cls)
        self.path, (self.ceiling, self.cap, self.interval), self._ro = Path(path), row, True
        return self

    def _has_settlements(self, db) -> bool:
        return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='settlements'").fetchone() is not None

    def _committed(self, db) -> int:
        """Every job's commitment (all scopes)."""
        return db.execute(COMMITTED_SQL).fetchone()[0] if self._has_settlements(db) else db.execute('SELECT COALESCE(SUM(reserved),0) FROM jobs').fetchone()[0]

    @staticmethod
    def _has_budgets(db) -> bool:
        return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='budget_jobs'").fetchone() is not None

    def _ledger(self, db) -> dict:
        """One consistent read (inside the caller's transaction) of every commitment by scope: per job (settled cost or full reservation) and per
        off-host allocation (settled cost or its full maximum)."""
        if not (self._has_settlements(db) and self._has_budgets(db)):
            rows = db.execute('SELECT id, reserved, 0, reserved, NULL FROM jobs').fetchall() if not self._has_settlements(db) else \
                db.execute(JOB_COMMITTED_SQL.replace(' LEFT JOIN budget_jobs b ON b.job_id=j.id', '').replace('b.budget_id', 'NULL')).fetchall()
            return {'jobs': rows, 'allocations': [], 'budgets': {}, 'global_cap': None}
        budgets = {r[0]: {'limit_micro_aud': r[1], 'rate_num': r[2], 'rate_den': r[3], 'limit_microusd': r[4]}
                   for r in db.execute('SELECT id, limit_micro_aud, rate_num, rate_den, limit_microusd FROM budgets')}
        cap = db.execute('SELECT cap FROM global_caps ORDER BY seq DESC LIMIT 1').fetchone()
        return {'jobs': db.execute(JOB_COMMITTED_SQL).fetchall(), 'allocations': db.execute(ALLOC_COMMITTED_SQL).fetchall(), 'budgets': budgets,
                'global_cap': cap[0] if cap else None}

    @staticmethod
    def _scope(led: dict, budget: str | None) -> dict:
        """Commitments of one scope: budget None = legacy jobs (no budget), checked against the hosted ceiling in µUS$; a budget = its jobs and
        allocations, each converted to µA$ (rounded up) and checked against its fixed A$ limit."""
        if budget is None:
            rows = [r for r in led['jobs'] if r[4] is None]
            settled = sum(r[1] for r in rows if r[2])
            return {'committed_microusd': sum(r[1] for r in rows), 'settled_microusd': settled, 'reserved_microusd': sum(r[3] for r in rows),
                    'outstanding_microusd': sum(r[1] for r in rows if not r[2]), 'released_microusd': sum(r[3] for r in rows if r[2]) - settled,
                    'jobs': len(rows), 'settled_jobs': sum(1 for r in rows if r[2])}
        b = led['budgets'][budget]
        num, den = b['rate_num'], b['rate_den']
        jobs = [r for r in led['jobs'] if r[4] == budget]
        allocs = [r for r in led['allocations'] if r[1] == budget]
        spent = [r[1] for r in jobs if r[2]] + [r[3] for r in allocs if r[3] is not None]
        held = [r[1] for r in jobs if not r[2]] + [r[2] for r in allocs if r[3] is None]
        spent_aud, held_aud = sum(aud_micro(x, num, den) for x in spent), sum(aud_micro(x, num, den) for x in held)
        return {'budget': budget, 'limit_micro_aud': b['limit_micro_aud'], 'limit_microusd': b['limit_microusd'], 'rate_num': num, 'rate_den': den,
                'spent_microusd': sum(spent), 'outstanding_microusd': sum(held), 'spent_micro_aud': spent_aud, 'outstanding_micro_aud': held_aud,
                'committed_micro_aud': spent_aud + held_aud, 'available_micro_aud': b['limit_micro_aud'] - spent_aud - held_aud,
                'available_microusd': max(0, (b['limit_micro_aud'] - spent_aud - held_aud) * den // num),
                'released_microusd': sum(r[3] for r in jobs if r[2]) - sum(r[1] for r in jobs if r[2]) + sum(r[2] - r[3] for r in allocs if r[3] is not None),
                'jobs': len(jobs), 'settled_jobs': sum(1 for r in jobs if r[2]), 'allocations': len(allocs),
                'open_allocations': sum(1 for r in allocs if r[3] is None)}

    @staticmethod
    def _shared(led: dict) -> str | None:
        """The shared evaluation budget: while one is open, EVERY new evaluation reservation is charged to it (judges and operators alike),
        whatever path made it; jobs reserved before it opened keep their scope. At most one exists (a reviewed maximum)."""
        return sorted(led['budgets'])[0] if led['budgets'] else None

    def charge_scope(self) -> str | None:
        """Where the next evaluation would be charged: the shared budget, or None (the hosted ceiling) while none is open."""
        with self.connect() as db:
            return self._shared(self._ledger(db))

    @staticmethod
    def _all_committed(led: dict) -> int:
        return sum(r[1] for r in led['jobs']) + sum(r[2] if r[3] is None else r[3] for r in led['allocations'])

    def _check(self, db, microusd: int, budget: str | None, *, soft: bool = False) -> None:
        """Inside BEGIN IMMEDIATE: the new commitment fits its scope (legacy ceiling, or its budget) and the global cap. Raises Refused.
        soft (evaluations charged to the shared budget): admitted while the budget's commitments so far (actual settled costs, plus the full
        reservation of any run not yet reconciled) are BELOW its limit; the new run's own worst case is not counted against what remains, so the
        last admitted run may finish above the limit. The global cap (raised at opening by the limit plus one run's maximum) stays hard."""
        led = self._ledger(db)
        if budget is None:
            if self._scope(led, None)['committed_microusd'] + microusd > self.ceiling:
                raise Refused('hosted budget exhausted')
        else:
            if budget not in led['budgets']:
                raise Refused('no such budget: the owner opens a budget at the server terminal')
            sc = self._scope(led, budget)
            if (sc['committed_micro_aud'] >= sc['limit_micro_aud']) if soft else \
                    (sc['committed_micro_aud'] + aud_micro(microusd, sc['rate_num'], sc['rate_den']) > sc['limit_micro_aud']):
                raise Refused(f'budget {budget} exhausted')
        if led['global_cap'] is not None and self._all_committed(led) + microusd > led['global_cap']:
            raise Refused('global hosted cap reached')

    def connect(self):
        if getattr(self, '_ro', False):
            db = sqlite3.connect(f'file:{self.path}?mode=ro', uri=True, timeout=10, isolation_level=None)
            db.execute('PRAGMA busy_timeout=10000')
            return db
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.execute('PRAGMA busy_timeout=10000')
        return db

    def reserve(self, job_id: str, client: str, *, now: float | None = None, units: int = 1):
        """Reserve ``units`` x the per-unit cap (one unit = one paired repetition), atomically."""
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', job_id) or not re.fullmatch(r'[a-f0-9]{64}', client):
            raise ValueError('invalid admission identity')
        if type(units) is not int or not 1 <= units <= 5:
            raise ValueError('invalid reservation size')
        now = time.time() if now is None else now
        if not isinstance(now, (int, float)) or not 0 <= now < 10**12:
            raise ValueError('invalid timestamp')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                if db.execute("SELECT 1 FROM jobs WHERE state IN ('reserved','running') LIMIT 1").fetchone():
                    raise Refused('evaluation capacity is occupied')
                last = db.execute('SELECT MAX(created) FROM jobs WHERE client=?', (client,)).fetchone()[0]
                if last is not None and now - last < self.interval:
                    raise Refused('rate limit exceeded')
                scope = self._shared(self._ledger(db))
                self._check(db, self.cap * units, scope, soft=scope is not None)
                db.execute('INSERT INTO jobs VALUES (?,?,?,?,?)', (job_id, client, now, 'reserved', self.cap * units))
                if scope is not None:
                    db.execute('INSERT INTO budget_jobs VALUES (?,?,?)', (job_id, scope, now))
                db.execute('COMMIT')
            except BaseException:
                db.execute('ROLLBACK')
                raise

    def reserve_amount(self, job_id: str, client: str, microusd: int, *, now: float | None = None, budget: str | None = None):
        """Stage B hosted evaluations (M8): reserve an exact amount (the armed manifest's worst case plus one request bound; a zero-cost rehearsal
        reserves 0) against the SAME single evaluation slot as repetitions always did, and against its scope: the hosted ceiling (legacy jobs,
        `budget=None`) or the named owner-opened budget (written atomically as `budget_jobs`), plus the global cap. The persisted policy row
        (per-repetition unit) is untouched, so an older image still opens this database. Reservations are never reduced."""
        if not re.fullmatch(r'eval-[0-9a-f]{32}', job_id) or not re.fullmatch(r'[a-f0-9]{64}', client):
            raise ValueError('invalid admission identity')
        if type(microusd) is not int or microusd < 0:
            raise ValueError('invalid reservation amount')
        if budget is not None and not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,40}', budget):
            raise ValueError('invalid budget id')
        now = time.time() if now is None else now
        if not isinstance(now, (int, float)) or not 0 <= now < 10**12:
            raise ValueError('invalid timestamp')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                if db.execute("SELECT 1 FROM jobs WHERE state IN ('reserved','running') LIMIT 1").fetchone():
                    raise Refused('evaluation capacity is occupied')
                scope = budget if budget is not None else self._shared(self._ledger(db))     # an open shared budget takes every new evaluation
                if scope is None:                                 # the per-client interval applies to the legacy (ceiling) scope only; the shared
                    last = db.execute('SELECT MAX(created) FROM jobs WHERE client=?', (client,)).fetchone()[0]   # budget's launches need only a
                    if last is not None and now - last < self.interval:                                          # valid code and an under-budget pool
                        raise Refused('rate limit exceeded')
                if scope is not None and budget is not None and scope != budget:
                    raise Refused('no such budget: the owner opens a budget at the server terminal')
                self._check(db, microusd, scope, soft=scope is not None)
                db.execute('INSERT INTO jobs VALUES (?,?,?,?,?)', (job_id, client, now, 'reserved', microusd))
                db.execute('INSERT INTO auto_settle VALUES (?,?)', (job_id, now))     # settlement-aware admission: may settle automatically once verified
                if scope is not None:
                    db.execute('INSERT INTO budget_jobs VALUES (?,?,?)', (job_id, scope, now))
                db.execute('COMMIT')
            except BaseException:
                db.execute('ROLLBACK')
                raise

    def transition(self, job_id: str, expected: str, state: str):
        allowed = {('reserved', 'running'), ('reserved', 'failed'), ('running', 'completed'), ('running', 'failed'), ('running', 'timed_out'),
                   ('reserved', 'interrupted'), ('running', 'interrupted')}
        if (expected, state) not in allowed:
            raise ValueError('invalid transition')
        with self.connect() as db:
            if db.execute('UPDATE jobs SET state=? WHERE id=? AND state=?', (state, job_id, expected)).rowcount != 1:
                raise Refused('job state changed or does not exist')

    def get(self, job_id: str):
        with self.connect() as db:
            row = db.execute('SELECT id, state, created, reserved FROM jobs WHERE id=?', (job_id,)).fetchone()
        return dict(zip(('id', 'state', 'created', 'reserved_microusd'), row)) if row else None

    def active(self):
        with self.connect() as db:
            return [r[0] for r in db.execute("SELECT id FROM jobs WHERE state IN ('reserved','running') ORDER BY created")]

    def recent(self, limit: int = 20):
        with self.connect() as db:
            rows = db.execute('SELECT id, state, created, reserved FROM jobs ORDER BY created DESC LIMIT ?', (limit,)).fetchall()
        return [dict(zip(('id', 'state', 'created', 'reserved_microusd'), r)) for r in rows]

    def totals(self):
        """The hosted CEILING's scope (legacy jobs: those not charged to a separate budget). `reserved_microusd` = their reservations as written;
        `committed_microusd` = settled + outstanding, what admission enforces against the ceiling; `available_microusd` = what a legacy launch may
        still reserve (the ceiling's room, also within the global cap). Every job and allocation together: `all_*`; per budget: `budgets`."""
        with self.connect() as db:
            led = self._ledger(db)
        lg = self._scope(led, None)
        allc = self._all_committed(led)
        gcap = led['global_cap']
        avail = self.ceiling - lg['committed_microusd']
        if gcap is not None:
            avail = min(avail, gcap - allc)
        return {'ceiling_microusd': self.ceiling, 'reserved_microusd': lg['reserved_microusd'], 'per_repetition_microusd': self.cap,
                'settled_microusd': lg['settled_microusd'], 'settled_jobs': lg['settled_jobs'], 'released_microusd': lg['released_microusd'],
                'outstanding_microusd': lg['outstanding_microusd'], 'unsettled_jobs': lg['jobs'] - lg['settled_jobs'], 'committed_microusd': lg['committed_microusd'],
                'available_microusd': avail, 'ceiling_available_microusd': self.ceiling - lg['committed_microusd'],
                'all_reserved_microusd': sum(r[3] for r in led['jobs']), 'all_committed_microusd': allc, 'global_cap_microusd': gcap,
                'global_available_microusd': None if gcap is None else gcap - allc,
                'budgets': [self._scope(led, b) for b in sorted(led['budgets'])]}

    def capacity_microusd(self, budget: str | None = None) -> int:
        """What one more reservation in this scope could be at most now (its scope's room, within the global cap)."""
        with self.connect() as db:
            led = self._ledger(db)
        if budget is None:
            room = self.ceiling - self._scope(led, None)['committed_microusd']
        elif budget in led['budgets']:
            room = self._scope(led, budget)['available_microusd']
        else:
            return 0
        if led['global_cap'] is not None:
            room = min(room, led['global_cap'] - self._all_committed(led))
        return max(0, room)

    def budget_admits(self, budget: str) -> bool:
        """Whether the shared budget admits another evaluation now (soft cap: its commitments so far are below its limit)."""
        with self.connect() as db:
            led = self._ledger(db)
        if budget not in led['budgets']:
            return False
        sc = self._scope(led, budget)
        return sc['committed_micro_aud'] < sc['limit_micro_aud']

    def job_budget(self, job_id: str) -> str | None:
        with self.connect() as db:
            if not self._has_budgets(db):
                return None
            row = db.execute('SELECT budget_id FROM budget_jobs WHERE job_id=?', (job_id,)).fetchone()
        return row[0] if row else None

    def settlement(self, job_id: str) -> dict | None:
        with self.connect() as db:
            if not self._has_settlements(db):
                return None
            row = db.execute('SELECT settled, basis, ledger_sha256, ledger_requests, open_requests, at, actor FROM settlements WHERE job_id=?', (job_id,)).fetchone()
        return dict(zip(('settled_microusd', 'basis', 'ledger_sha256', 'ledger_requests', 'open_requests', 'at', 'actor'), row)) if row else None

    def auto_settle_enabled(self, job_id: str) -> bool:
        with self.connect() as db:
            if not self._has_settlements(db):
                return False
            return db.execute('SELECT 1 FROM auto_settle WHERE job_id=?', (job_id,)).fetchone() is not None

    def record_settlement(self, job_id: str, settled_microusd: int, *, basis: str, ledger_sha256: str, ledger_requests: int, open_requests: int,
                          actor: str, now: float | None = None) -> dict:
        """Write-once and idempotent, in one transaction: the job must exist and be terminal, and the settlement may not exceed its reservation.
        The same settlement again is a no-op; a different one is refused (a settlement is never changed)."""
        if type(settled_microusd) is not int or settled_microusd < 0 or not re.fullmatch(r'[0-9a-f]{64}', ledger_sha256 or ''):
            raise ValueError('invalid settlement')
        if getattr(self, '_ro', False):
            raise PermissionError('read-only admission')
        now = time.time() if now is None else now
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                row = db.execute('SELECT state, reserved FROM jobs WHERE id=?', (job_id,)).fetchone()
                if row is None:
                    raise Refused('no such job')
                if row[0] not in ('completed', 'failed', 'timed_out', 'interrupted'):
                    raise Refused('the job is not terminal; its reservation is kept')
                if settled_microusd > row[1]:
                    raise Refused('a settlement cannot exceed the reservation')
                old = db.execute('SELECT settled, ledger_sha256 FROM settlements WHERE job_id=?', (job_id,)).fetchone()
                if old is not None:
                    db.execute('ROLLBACK')
                    if old != (settled_microusd, ledger_sha256):
                        raise Refused('a different settlement is already recorded; settlements are never changed')
                    return {'job_id': job_id, 'settled_microusd': settled_microusd, 'already': True}
                db.execute('INSERT INTO settlements VALUES (?,?,?,?,?,?,?,?)', (job_id, settled_microusd, basis, ledger_sha256, ledger_requests, open_requests, now, actor))
                db.execute('COMMIT')
            except BaseException:
                if db.in_transaction:
                    db.execute('ROLLBACK')
                raise
        return {'job_id': job_id, 'settled_microusd': settled_microusd, 'already': False}
