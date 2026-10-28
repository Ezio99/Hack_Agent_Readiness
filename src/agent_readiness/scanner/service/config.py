"""Server configuration. Every default is the safe one: live inference OFF, no wildcard CORS, bounded bodies, one concurrent scan, short sessions."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ScannerConfig:
    data_dir: Path = Path("scanner-data")                       # private: database, results, traces (Git-ignored)
    secret: str = ""                                             # HMAC pepper for invitation codes and session tokens (never stored in the database)
    admin_token: str = ""                                        # enables the admin kill-switch endpoint when set
    session_ttl_seconds: int = 1800
    default_scan_quota: int = 5
    cors_origins: tuple[str, ...] = ()                           # exact origins only; empty = no cross-origin access
    max_body_bytes: int = 4096
    rate_limit_per_minute: int = 60                              # per client address, all endpoints
    code_attempts_per_10_min: int = 10                           # failed redemptions per client address before lockout
    allow_mock_behaviors: bool = True                            # lets a developer pick a labelled mock scenario in the UI
    live_enabled: bool = False                                   # live Meta inference; NEVER enabled by tests; needs approval, key and budget
    live_budget_usd: float = 0.0                                 # global ceiling of RESERVED estimated cost for live scans; 0 = live disabled
    live_api_key_env: str = "META_MODEL_API_KEY"
    scan_timeout_grace_seconds: int = 30

    @property
    def db_path(self) -> Path:
        return self.data_dir / "scanner.sqlite3"

    @property
    def results_dir(self) -> Path:
        return self.data_dir / "results"

    @property
    def kill_switch_path(self) -> Path:
        return self.data_dir / "KILL_SWITCH"

    @property
    def live_available(self) -> bool:
        return self.live_enabled and self.live_budget_usd > 0 and bool(os.environ.get(self.live_api_key_env))


def load_config(env=None) -> ScannerConfig:
    env = os.environ if env is None else env
    data_dir = Path(env.get("SCANNER_DATA_DIR", "scanner-data"))
    secret = env.get("SCANNER_SECRET", "")
    if not secret:                                               # local development convenience only; a deployment must set SCANNER_SECRET
        data_dir.mkdir(parents=True, exist_ok=True)
        path = data_dir / ".dev-secret"
        if not path.exists():
            path.write_text(secrets.token_urlsafe(32))
            path.chmod(0o600)
        secret = path.read_text().strip()
    return ScannerConfig(data_dir=data_dir, secret=secret, admin_token=env.get("SCANNER_ADMIN_TOKEN", ""),
                         cors_origins=tuple(o for o in env.get("SCANNER_CORS_ORIGINS", "").split(",") if o.strip()),
                         live_enabled=env.get("SCANNER_LIVE_ENABLED") == "1", live_budget_usd=float(env.get("SCANNER_LIVE_BUDGET_USD", "0") or 0))
