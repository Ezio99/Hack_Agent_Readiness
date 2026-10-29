"""Site zoo: opaque, generated test sites. `files(id)` / `snapshot(id)` expose only served content. Planted-issue manifests are in `sealed/` and are read ONLY by `sealed.py` (scoring
and blindness checks) — never by the inspector, mirror or any investigator input builder."""
from __future__ import annotations

from functools import lru_cache

from ..inspect.crawl import Limits, MappingFetcher, crawl
from ..sitemodel.snapshot import Snapshot
from .sites import BUILDERS


def ids() -> list[str]:
    return sorted(BUILDERS)


def files(site_id: str) -> dict:
    return BUILDERS[site_id]()


@lru_cache(maxsize=None)
def _snapshot(site_id: str) -> Snapshot:
    return crawl(MappingFetcher(files(site_id)), Limits())


def snapshot(site_id: str) -> Snapshot:
    return _snapshot(site_id)
