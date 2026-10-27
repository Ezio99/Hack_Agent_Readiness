import os
import stat
import sys
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_repo_env(path: Path | None = None) -> bool:
    """Load the repository-root .env without overriding the process environment.

    Only this explicit path is read (no upward search). Values are never printed.
    """
    path = Path(path) if path is not None else REPO_ROOT / ".env"
    if not path.is_file():
        return False
    if path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        print(f"warning: {path.name} is readable by other users; run chmod 600 {path.name}", file=sys.stderr)
    return load_dotenv(dotenv_path=path, override=False)


@contextmanager
def scrubbed_environment(*names: str):
    """Hide named variables from child processes (browser, Playwright driver) and restore them."""
    saved = {name: os.environ.pop(name) for name in names if name in os.environ}
    try:
        yield
    finally:
        os.environ.update(saved)
