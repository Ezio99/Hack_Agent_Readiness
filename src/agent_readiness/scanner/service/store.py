"""SQLite persistence with atomic, race-safe operations (BEGIN IMMEDIATE). Codes and session tokens are stored only as HMAC-SHA256 hashes."""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from .config import ScannerConfig

SCHEMA = """
CREATE TABLE IF NOT EXISTS invitations (id TEXT PRIMARY KEY, code_hash TEXT UNIQUE NOT NULL, label TEXT NOT NULL, created_at REAL NOT NULL, expires_at REAL NOT NULL,
  max_redemptions INTEGER NOT NULL, redeemed INTEGER NOT NULL DEFAULT 0, scan_quota INTEGER NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL, invitation_id TEXT NOT NULL, created_at REAL NOT NULL, expires_at REAL NOT NULL,
  scan_quota INTEGER NOT NULL, scans_used INTEGER NOT NULL DEFAULT 0, revoked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS scans (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, invitation_id TEXT NOT NULL, task_id TEXT NOT NULL, variant_id TEXT NOT NULL, mode TEXT NOT NULL,
  mock_behavior TEXT, status TEXT NOT NULL, created_at REAL NOT NULL, started_at REAL, finished_at REAL, reserved_usd REAL NOT NULL DEFAULT 0, actual_usd REAL,
  idempotency_key TEXT, error TEXT, UNIQUE(session_id, idempotency_key));
CREATE TABLE IF NOT EXISTS ledger (id INTEGER PRIMARY KEY AUTOINCREMENT, scan_id TEXT NOT NULL, kind TEXT NOT NULL, usd REAL NOT NULL, ts REAL NOT NULL);
CREATE TABLE IF NOT EXISTS audits (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, invitation_id TEXT NOT NULL, target_id TEXT NOT NULL, previous_id TEXT, created_at REAL NOT NULL,
  with_scan INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, client TEXT NOT NULL, ts REAL NOT NULL);
"""
ACTIVE = ("queued", "running")


class ScanRefused(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def hmac_hash(secret: str, value: str) -> str:
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


class Store:
    def __init__(self, config: ScannerConfig):
        self.config = config
        config.data_dir.mkdir(parents=True, exist_ok=True)
        config.results_dir.mkdir(parents=True, exist_ok=True)
        self.path = config.db_path
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)      # explicit transactions
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def tx(self):
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                yield c
                c.execute("COMMIT")
            except BaseException:
                c.execute("ROLLBACK")
                raise

    # ---- invitations (created out of band by the operator; never by the public API) -------------------------------------------
    def create_invitation(self, label: str, days: float = 7, max_redemptions: int = 1, scan_quota: int | None = None) -> tuple[str, str]:
        code = "AR-" + "-".join(secrets.token_hex(2).upper() for _ in range(4))
        inv_id = uuid.uuid4().hex[:12]
        with self.tx() as c:
            c.execute("INSERT INTO invitations VALUES (?,?,?,?,?,?,0,?,0)", (inv_id, hmac_hash(self.config.secret, code), label[:80], time.time(), time.time() + days * 86400,
                                                                          max_redemptions, scan_quota or self.config.default_scan_quota))
        return inv_id, code

    def revoke_invitation(self, inv_id: str) -> None:
        with self.tx() as c:
            c.execute("UPDATE invitations SET revoked=1 WHERE id=?", (inv_id,))
            c.execute("UPDATE sessions SET revoked=1 WHERE invitation_id=?", (inv_id,))

    def list_invitations(self) -> list[dict]:
        with self._conn() as c:
            return [dict(r) | {"code_hash": "…"} for r in c.execute("SELECT * FROM invitations ORDER BY created_at")]

    # ---- failed-attempt tracking (lockout) ---------------------------------------------------------------------------------------
    def failed_attempts(self, client: str, window: float = 600) -> int:
        with self._conn() as c:
            c.execute("DELETE FROM attempts WHERE ts < ?", (time.time() - window,))
            return c.execute("SELECT COUNT(*) FROM attempts WHERE client=? AND ts>=?", (client, time.time() - window)).fetchone()[0]

    def record_failed_attempt(self, client: str) -> None:
        with self._conn() as c:
            c.execute("INSERT INTO attempts(client, ts) VALUES (?,?)", (client, time.time()))

    # ---- redemption -> session (atomic; redemption cap cannot be raced) ----------------------------------------------------------
    def redeem(self, code: str) -> tuple[str, dict] | None:
        h = hmac_hash(self.config.secret, code.strip().upper())
        now = time.time()
        with self.tx() as c:
            inv = c.execute("SELECT * FROM invitations WHERE code_hash=?", (h,)).fetchone()
            if not inv or inv["revoked"] or inv["expires_at"] <= now or inv["redeemed"] >= inv["max_redemptions"]:
                return None
            c.execute("UPDATE invitations SET redeemed=redeemed+1 WHERE id=?", (inv["id"],))
            token = secrets.token_urlsafe(32)
            sid = uuid.uuid4().hex[:16]
            expires = min(now + self.config.session_ttl_seconds, inv["expires_at"])
            c.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?,0,0)", (sid, hmac_hash(self.config.secret, token), inv["id"], now, expires, inv["scan_quota"]))
            return token, {"session_id": sid, "expires_at": expires, "scan_quota": inv["scan_quota"], "scans_used": 0}

    def session_for(self, token: str) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT s.*, i.revoked AS inv_revoked FROM sessions s JOIN invitations i ON i.id=s.invitation_id WHERE s.token_hash=?", (hmac_hash(self.config.secret, token),)).fetchone()
        if not r or r["revoked"] or r["inv_revoked"] or r["expires_at"] <= time.time():
            return None
        return dict(r)

    # ---- scans: atomic quota / concurrency / budget reservation ------------------------------------------------------------------
    def reserve_scan(self, session: dict, task_id: str, variant_id: str, mode: str, mock_behavior: str | None, reserve_usd: float, live_budget: float,
                     idempotency_key: str | None = None) -> str:
        with self.tx() as c:
            if idempotency_key:
                dup = c.execute("SELECT id FROM scans WHERE session_id=? AND idempotency_key=?", (session["id"], idempotency_key)).fetchone()
                if dup:
                    return dup["id"]                                              # a double submission returns the original scan, never a second one
            s = c.execute("SELECT * FROM sessions WHERE id=?", (session["id"],)).fetchone()
            if not s or s["revoked"] or s["expires_at"] <= time.time():
                raise ScanRefused(401, "session_invalid", "The session is no longer valid.")
            if s["scans_used"] >= s["scan_quota"]:
                raise ScanRefused(429, "quota_exhausted", "This session's scan quota is used up.")
            if c.execute(f"SELECT COUNT(*) FROM scans WHERE status IN ({','.join('?' * len(ACTIVE))})", ACTIVE).fetchone()[0] >= 1:
                raise ScanRefused(409, "scan_in_progress", "Another scan is running; the scanner runs one scan at a time.")
            if mode == "live":
                spent = c.execute("SELECT COALESCE(SUM(usd),0) FROM ledger").fetchone()[0]
                if spent + reserve_usd > live_budget + 1e-9:
                    raise ScanRefused(402, "budget_exhausted", "The live-scan budget would be exceeded.")
            scan_id = uuid.uuid4().hex[:16]
            c.execute("INSERT INTO scans(id,session_id,invitation_id,task_id,variant_id,mode,mock_behavior,status,created_at,reserved_usd,idempotency_key) VALUES (?,?,?,?,?,?,?,'queued',?,?,?)",
                      (scan_id, s["id"], s["invitation_id"], task_id, variant_id, mode, mock_behavior, time.time(), reserve_usd, idempotency_key))
            c.execute("UPDATE sessions SET scans_used=scans_used+1 WHERE id=?", (s["id"],))
            if reserve_usd:
                c.execute("INSERT INTO ledger(scan_id,kind,usd,ts) VALUES (?,?,?,?)", (scan_id, "reserve", reserve_usd, time.time()))
            return scan_id

    def mark_running(self, scan_id: str) -> bool:
        with self.tx() as c:
            r = c.execute("UPDATE scans SET status='running', started_at=? WHERE id=? AND status='queued'", (time.time(), scan_id))
            return r.rowcount == 1

    def finish_scan(self, scan_id: str, status: str, actual_usd: float | None, error: str | None) -> None:
        with self.tx() as c:
            s = c.execute("SELECT reserved_usd FROM scans WHERE id=?", (scan_id,)).fetchone()
            c.execute("UPDATE scans SET status=?, finished_at=?, actual_usd=?, error=? WHERE id=?", (status, time.time(), actual_usd, (error or "")[:300] or None, scan_id))
            if s and s["reserved_usd"]:
                # conservative settlement: the reservation is replaced by max(actual, 0); a failed/interrupted live scan keeps its full reservation (spend is uncertain)
                settled = (actual_usd if actual_usd is not None and status == "complete" else s["reserved_usd"])
                c.execute("INSERT INTO ledger(scan_id,kind,usd,ts) VALUES (?,?,?,?)", (scan_id, "settle", settled - s["reserved_usd"], time.time()))

    def recover_interrupted(self) -> int:
        """After a restart no scan is silently re-run (a re-run could bill again): active scans are marked interrupted."""
        with self.tx() as c:
            ids = [r["id"] for r in c.execute(f"SELECT id FROM scans WHERE status IN ({','.join('?' * len(ACTIVE))})", ACTIVE)]
        for sid in ids:
            self.finish_scan(sid, "interrupted", None, "the service restarted while this scan was active; it was not retried")
        return len(ids)

    def get_scan(self, scan_id: str) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM scans WHERE id=?", (scan_id,)).fetchone()
        return dict(r) if r else None

    def scans_of(self, invitation_id: str) -> list[dict]:
        with self._conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM scans WHERE invitation_id=? ORDER BY created_at DESC", (invitation_id,))]

    def spent_usd(self) -> float:
        with self._conn() as c:
            return c.execute("SELECT COALESCE(SUM(usd),0) FROM ledger").fetchone()[0]

    def result_path(self, scan_id: str) -> Path:
        return self.config.results_dir / scan_id

    # ---- site audits (probe + recommendations; no model call, no cost) ---------------------------------------------------------------
    def audit_path(self, audit_id: str) -> Path:
        return self.config.results_dir / "audits" / f"{audit_id}.json"

    def audits_count(self, session_id: str) -> int:
        with self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM audits WHERE session_id=?", (session_id,)).fetchone()[0]

    def save_audit(self, session: dict, target_id: str, previous_id: str | None, report: dict, with_scan: bool) -> None:
        path = self.audit_path(report["audit_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=1))
        with self.tx() as c:
            c.execute("INSERT INTO audits VALUES (?,?,?,?,?,?,?)", (report["audit_id"], session["id"], session["invitation_id"], target_id, previous_id, time.time(), int(with_scan)))

    def get_audit(self, audit_id: str) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM audits WHERE id=?", (audit_id,)).fetchone()
        return dict(r) if r else None

    def audits_of(self, invitation_id: str) -> list[dict]:
        with self._conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM audits WHERE invitation_id=? ORDER BY created_at DESC", (invitation_id,))]
