

from . import netguard as _netguard

if _netguard.active():            # a worker spawned by a test inherits PYTEST_CURRENT_TEST: it is loopback-only too
    _netguard.install()
