"""M9 test guard: when M9_NO_NETWORK=1, every Python process (service, worker, jail wrapper) refuses non-loopback connects and non-local DNS."""
import os
if os.environ.get("M9_NO_NETWORK") == "1":
    import ipaddress
    import socket
    _real = socket.socket

    def _check(addr):
        if isinstance(addr, tuple):
            try:
                ip = ipaddress.ip_address(addr[0])
            except ValueError:
                raise PermissionError("m9 guard: connect by hostname refused") from None
            if not ip.is_loopback:
                raise PermissionError(f"m9 guard: non-loopback {addr[0]} refused")

    class _Guarded(_real):
        def connect(self, a):
            _check(a)
            return super().connect(a)

        def connect_ex(self, a):
            _check(a)
            return super().connect_ex(a)
    socket.socket = _Guarded
    _gai = socket.getaddrinfo

    def _getaddrinfo(host, *a, **k):
        if host not in (None, "localhost", "127.0.0.1", "::1", b"localhost", b"127.0.0.1"):
            raise socket.gaierror(f"m9 guard: DNS refused for {host!r}")
        return _gai(host, *a, **k)
    socket.getaddrinfo = _getaddrinfo
