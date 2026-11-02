"""Durable conservative admission for a single hosted paired evaluation.

Dollar values are integer microdollars. Reservations survive crashes and are
never reduced merely because a worker failed or disappeared.
"""
from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path


class Refused(ValueError):
    pass


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

    def connect(self):
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
                total = db.execute('SELECT COALESCE(SUM(reserved),0) FROM jobs').fetchone()[0]
                if total + self.cap * units > self.ceiling:
                    raise Refused('hosted budget exhausted')
                db.execute('INSERT INTO jobs VALUES (?,?,?,?,?)', (job_id, client, now, 'reserved', self.cap * units))
                db.execute('COMMIT')
            except BaseException:
                db.execute('ROLLBACK')
                raise

    def reserve_amount(self, job_id: str, client: str, microusd: int, *, now: float | None = None):
        """Lifecycle evaluations (M8): reserve an exact amount against the SAME durable ceiling and the SAME single evaluation slot as hosted
        repetitions. A zero-cost rehearsal reserves 0 (it still occupies the slot, so the hosted worker and a lifecycle worker never run Chromium
        at once); a paid lifecycle run reserves its manifest's worst case. Reservations are never reduced, as for repetitions. Job ids use the
        `lc-` prefix, so the hosted Ironbark routes never treat them as their own jobs."""
        if not re.fullmatch(r'lc-[0-9a-f]{32}', job_id) or not re.fullmatch(r'[a-f0-9]{64}', client):
            raise ValueError('invalid admission identity')
        if type(microusd) is not int or not 0 <= microusd <= self.ceiling:
            raise ValueError('invalid reservation amount')
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
                total = db.execute('SELECT COALESCE(SUM(reserved),0) FROM jobs').fetchone()[0]
                if total + microusd > self.ceiling:
                    raise Refused('hosted budget exhausted')
                db.execute('INSERT INTO jobs VALUES (?,?,?,?,?)', (job_id, client, now, 'reserved', microusd))
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
        with self.connect() as db:
            reserved = db.execute('SELECT COALESCE(SUM(reserved),0) FROM jobs').fetchone()[0]
        return {'ceiling_microusd': self.ceiling, 'reserved_microusd': reserved, 'per_repetition_microusd': self.cap}
