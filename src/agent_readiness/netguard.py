"""Test-time network guard: inside a test process, and inside any worker a test spawns, a socket connection to anything but this machine raises. Tests use fake transports and loopback servers;
nothing legitimate in the suite talks to the internet, and the operator's `.env` (which holds the production model key, and which Browser Use loads at import time) must never be able to turn a
test into a billed request. Active when `PYTEST_CURRENT_TEST` is set (spawned workers inherit it) or `AR_BLOCK_NONLOOPBACK=1`; `tests/conftest.py` installs it for the pytest process itself."""
from __future__ import annotations

import ipaddress
import os
import socket

_installed = False


def _local(address) -> bool:
    if isinstance(address, (str, bytes, os.PathLike)):
        return True                                             # AF_UNIX path
    host = address[0] if isinstance(address, tuple) and address else address
    if isinstance(host, bytes):
        host = host.decode(errors="replace")
    host = str(host).split("%")[0]
    if host in ("localhost", ""):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False                                            # an unresolved hostname is never trusted


def install() -> None:
    global _installed
    if _installed:
        return
    _installed = True
    real_connect, real_connect_ex = socket.socket.connect, socket.socket.connect_ex

    def guard(address):
        if not _local(address):
            raise OSError(f"netguard: a test process may not connect to {address!r} (only loopback); the real model endpoint is unreachable from tests")

    def connect(self, address):
        guard(address)
        return real_connect(self, address)

    def connect_ex(self, address):
        guard(address)
        return real_connect_ex(self, address)
    socket.socket.connect, socket.socket.connect_ex = connect, connect_ex


def active() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST")) or os.environ.get("AR_BLOCK_NONLOOPBACK") == "1"
