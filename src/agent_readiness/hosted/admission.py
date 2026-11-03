"""Durable conservative admission for a single hosted paired evaluation.

Dollar values are integer microdollars. Reservations survive crashes and are
never reduced merely because a worker failed or disappeared.

Final showcase: actual-cost settlement (`settlement.py`). A job's commitment against the ceiling is its verified settled cost once a settlement
row exists, else its full reservation; admission enforces  sum(committed) + new reservation <= ceiling.  `jobs.reserved` is never rewritten;
settlements are write-once rows in their own table, so an older image (which only sums `jobs.reserved`) stays correct and more conservative.
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
            for ddl in SETTLEMENT_DDL:                                     # additive: no existing row or table changes
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
        return db.execute(COMMITTED_SQL).fetchone()[0] if self._has_settlements(db) else db.execute('SELECT COALESCE(SUM(reserved),0) FROM jobs').fetchone()[0]

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
                total = self._committed(db)
                if total + self.cap * units > self.ceiling:
                    raise Refused('hosted budget exhausted')
                db.execute('INSERT INTO jobs VALUES (?,?,?,?,?)', (job_id, client, now, 'reserved', self.cap * units))
                db.execute('COMMIT')
            except BaseException:
                db.execute('ROLLBACK')
                raise

    def reserve_amount(self, job_id: str, client: str, microusd: int, *, now: float | None = None):
        """Stage B hosted evaluations (M8): reserve an exact amount (the armed manifest's worst case plus one request bound; a zero-cost rehearsal
        reserves 0) against the SAME durable ceiling and the SAME single evaluation slot as repetitions always did. The persisted policy row
        (per-repetition unit) is untouched, so an older image still opens this database. Reservations are never reduced."""
        if not re.fullmatch(r'eval-[0-9a-f]{32}', job_id) or not re.fullmatch(r'[a-f0-9]{64}', client):
            raise ValueError('invalid admission identity')
        if type(microusd) is not int or microusd < 0:
            raise ValueError('invalid reservation amount')
        if microusd > self.ceiling:
            raise Refused('hosted budget exhausted')
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
                total = self._committed(db)
                if total + microusd > self.ceiling:
                    raise Refused('hosted budget exhausted')
                db.execute('INSERT INTO jobs VALUES (?,?,?,?,?)', (job_id, client, now, 'reserved', microusd))
                db.execute('INSERT INTO auto_settle VALUES (?,?)', (job_id, now))     # settlement-aware admission: may settle automatically once verified
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
        """`reserved_microusd` = every reservation as written (unchanged meaning); `committed_microusd` = settled + outstanding, the amount admission
        enforces against the ceiling; `available_microusd` = ceiling - committed."""
        with self.connect() as db:
            reserved = db.execute('SELECT COALESCE(SUM(reserved),0) FROM jobs').fetchone()[0]
            jobs = db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
            if self._has_settlements(db):
                settled, n_settled, settled_reserved = db.execute('SELECT COALESCE(SUM(s.settled),0), COUNT(*), COALESCE(SUM(j.reserved),0) FROM settlements s '
                                                                  'JOIN jobs j ON j.id=s.job_id').fetchone()
            else:
                settled, n_settled, settled_reserved = 0, 0, 0
        outstanding = reserved - settled_reserved
        committed = settled + outstanding
        return {'ceiling_microusd': self.ceiling, 'reserved_microusd': reserved, 'per_repetition_microusd': self.cap,
                'settled_microusd': settled, 'settled_jobs': n_settled, 'released_microusd': settled_reserved - settled,
                'outstanding_microusd': outstanding, 'unsettled_jobs': jobs - n_settled, 'committed_microusd': committed,
                'available_microusd': self.ceiling - committed}

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
