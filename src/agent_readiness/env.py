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
    """Hide named variables from child processes (browser, Playwright driver) and restore them.

    Browser Use calls ``dotenv.load_dotenv()`` at import time and finds the repository ``.env`` from inside
    this repo's ``.venv``; modules it imports lazily during a run would silently put the key back. While the
    context is active ``dotenv.load_dotenv`` is therefore inert (modules first imported inside the context keep
    the inert binding, which only matters at their import time).

    Limitation: this temporarily mutates process-global ``os.environ`` and ``dotenv.load_dotenv`` and is
    supported only for single-run, nonconcurrent execution (concurrent runs or threads would observe the
    missing variable, and overlapping contexts could restore stale state). If concurrent experiments become
    necessary, replace it with explicit sanitized environments passed to each subprocess.
    """
    import dotenv
    saved = {name: os.environ.pop(name) for name in names if name in os.environ}
    original = dotenv.load_dotenv
    dotenv.load_dotenv = lambda *args, **kwargs: False
    try:
        yield
    finally:
        dotenv.load_dotenv = original
        os.environ.update(saved)
