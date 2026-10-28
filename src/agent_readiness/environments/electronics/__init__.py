"""electronics-v1: a versioned, synthetic electronics retailer used as a controlled reference environment (Task 010)."""
from __future__ import annotations

from ...suite.core import Variant, register_environment
from . import tasks
from .app import create_app as _create_app
from .catalog import DATA_VERSION, ENVIRONMENT_ID
from .variants import DEFAULT_VARIANT, all_variants, sku_variants


class ElectronicsEnvironment:
    environment_id = ENVIRONMENT_ID
    data_version = DATA_VERSION

    def variants(self) -> list[Variant]:
        return all_variants() + sku_variants()

    def default_variant(self) -> Variant:
        return DEFAULT_VARIANT

    def create_app(self, variant: Variant):
        return _create_app(variant)


register_environment(ElectronicsEnvironment())
tasks.register()
