"""Network-isolated Chromium for publicly triggered evaluations (Linux only).

Browser Use launches ``executable_path --remote-debugging-port=N ...`` and then
connects to ``127.0.0.1:N``. :func:`wrapper` writes a small executable that
browser-use launches instead of Chromium. It runs the real Chromium inside new
user, network, PID and mount namespaces:

* the network namespace contains only a loopback interface, so DNS, the
  internet, the host, private/link-local ranges, cloud metadata, the provider
  endpoint and every other local service are unreachable by construction,
  including redirects, subresources and agent-initiated navigation;
* exactly two TCP ports are bridged through private Unix sockets: the
  snapshot mirror port (browser -> mirror) and the CDP port (controller ->
  browser). Both keep their original ``127.0.0.1`` URLs, so traces and the
  allowed origin are unchanged;
* a fresh ``/proc`` shows only the jail's processes (the worker's environment
  is not readable), and the application, data and secret directories are
  covered by empty read-only tmpfs mounts.

This module is the security boundary; browser-use's URL checks are not.
Any setup failure exits non-zero before Chromium starts (fail closed).
"""
from __future__ import annotations

import asyncio
import ctypes
import fcntl
import json
import os
import shlex
import signal
import socket
import stat
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ENV = 'AGENT_READINESS_BROWSER_JAIL'          # path of a jail policy JSON; set only by the hosted worker
_REQUIRED = False

MS_NOSUID, MS_NODEV, MS_NOEXEC, MS_RDONLY, MS_BIND, MS_REC, MS_PRIVATE = 2, 4, 8, 1, 4096, 16384, 1 << 18
PR_SET_PDEATHSIG = 1


def require():
    """Called by the hosted worker: from now on an unjailed browser launch is an error."""
    global _REQUIRED
    _REQUIRED = True


def required() -> bool:
    return _REQUIRED


def policy() -> dict | None:
    path = os.environ.get(ENV)
    if not path:
        if _REQUIRED:
            raise RuntimeError('browser isolation is required but no jail policy is configured')
        return None
    data = json.loads(Path(path).read_text())
    hide = [str(Path(p).resolve()) for p in data.get('hide', [])]
    if not hide or not all(Path(p).is_absolute() and Path(p) != Path('/') for p in hide):
        raise RuntimeError('jail policy must hide at least one absolute non-root path')
    base = Path(data.get('dir') or tempfile.gettempdir()).resolve()
    if len(str(base)) > 60:
        raise RuntimeError('jail directory path is too long for Unix sockets (60 characters at most)')
    return {'hide': hide, 'dir': str(base)}


def wrapper(chromium: str, url: str, pol: dict) -> str:
    """Write an executable launching ``chromium`` in the jail with only ``url``'s port bridged."""
    from urllib.parse import urlsplit
    parts = urlsplit(url)
    if parts.scheme != 'http' or parts.hostname != '127.0.0.1' or not parts.port:
        raise RuntimeError('the jail only bridges a loopback http mirror')
    base = Path(pol['dir'])
    needed = [Path(chromium).resolve(), Path(sys.base_prefix).resolve(), base]
    for hidden in map(Path, pol['hide']):
        if any(n == hidden or hidden in n.parents for n in needed):
            raise RuntimeError('jail policy hides the browser, the Python runtime or the jail directory')
    base.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix='jail-', dir=base))
    os.chmod(workdir, 0o700)
    cfg = workdir / 'jail.json'
    cfg.write_text(json.dumps({'chromium': str(Path(chromium).resolve()), 'mirror_port': parts.port, 'hide': pol['hide'], 'dir': str(workdir)}))
    script = workdir / 'chromium'
    pythonpath = str(Path(__file__).resolve().parents[2])
    script.write_text(f'#!/bin/sh\nPYTHONPATH={shlex.quote(pythonpath)} exec {shlex.quote(sys.executable)} -m agent_readiness.hosted.jail outer {shlex.quote(str(cfg))} "$@"\n')
    os.chmod(script, stat.S_IRWXU)
    return str(script)


# --- helpers ---------------------------------------------------------------------------------------------------

def _libc():
    return ctypes.CDLL(None, use_errno=True)


def _pdeathsig():
    if _libc().prctl(PR_SET_PDEATHSIG, signal.SIGKILL) != 0:
        raise OSError(ctypes.get_errno(), 'prctl')


def _mount(src, target, fstype, flags, data=None):
    libc = _libc()
    enc = lambda s: s.encode() if isinstance(s, str) else s
    if libc.mount(enc(src), enc(target), enc(fstype), ctypes.c_ulong(flags), enc(data)) != 0:
        err = ctypes.get_errno()
        raise OSError(err, f'mount {fstype or "bind"} on {target}: {os.strerror(err)}')


def _loopback_up():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        ifr = struct.pack('16sH14s', b'lo', 0, b'')
        flags = struct.unpack('16sH14s', fcntl.ioctl(s, 0x8913, ifr))[1]       # SIOCGIFFLAGS
        fcntl.ioctl(s, 0x8914, struct.pack('16sH14s', b'lo', flags | 1, b''))  # SIOCSIFFLAGS |= IFF_UP


async def _pipe(reader, writer):
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, OSError):
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


def _bridge(connect):
    async def handle(reader, writer):
        try:
            r2, w2 = await connect()
        except OSError:
            writer.close()
            return
        await asyncio.gather(_pipe(reader, w2), _pipe(r2, writer))
    return handle


async def _unix(path, attempts=200):
    for _ in range(attempts):
        try:
            return await asyncio.open_unix_connection(path)
        except (FileNotFoundError, ConnectionRefusedError):
            await asyncio.sleep(.05)
    raise ConnectionRefusedError(path)


# --- outer: runs in the worker's namespaces -------------------------------------------------------------------

def outer(cfg_path: str, args: list[str]) -> int:
    _pdeathsig()                                   # the worker (browser-use) dies -> the whole jail dies
    cfg = json.loads(Path(cfg_path).read_text())
    ports = [a.split('=', 1)[1] for a in args if a.startswith('--remote-debugging-port=')]
    if len(ports) != 1 or not ports[0].isdigit():
        return 2
    cdp, mirror, d = int(ports[0]), int(cfg['mirror_port']), Path(cfg['dir'])
    cdp_sock, mirror_sock = str(d / 'cdp.sock'), str(d / 'mirror.sock')

    async def main():
        stop = asyncio.get_running_loop().create_future()
        asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, lambda: stop.done() or stop.set_result(None))
        inner = await asyncio.create_subprocess_exec(sys.executable, '-m', 'agent_readiness.hosted.jail', 'inner', cfg_path, str(cdp), *args,
                                                     stdin=subprocess.DEVNULL, preexec_fn=_pdeathsig)
        mirror_server = await asyncio.start_unix_server(_bridge(lambda: asyncio.open_connection('127.0.0.1', mirror)), mirror_sock)
        cdp_server = await asyncio.start_server(_bridge(lambda: _unix(cdp_sock)), '127.0.0.1', cdp)
        async with mirror_server, cdp_server:
            waiter = asyncio.ensure_future(inner.wait())
            await asyncio.wait([waiter, stop], return_when=asyncio.FIRST_COMPLETED)
            if not waiter.done():
                inner.kill()                       # its PID-namespace init dies, so every jailed process dies
            return await waiter
    try:
        return asyncio.run(main())
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


# --- inner: new user/net/pid/mount namespaces -----------------------------------------------------------------

def inner(cfg_path: str, cdp: int, args: list[str]) -> int:
    cfg = json.loads(Path(cfg_path).read_text())
    uid, gid = os.getuid(), os.getgid()
    os.unshare(os.CLONE_NEWUSER | os.CLONE_NEWNET | os.CLONE_NEWNS | os.CLONE_NEWPID)
    Path('/proc/self/setgroups').write_text('deny')
    Path('/proc/self/uid_map').write_text(f'0 {uid} 1')
    Path('/proc/self/gid_map').write_text(f'0 {gid} 1')
    pid = os.fork()
    if pid:                                        # stays in the parent PID namespace and relays the exit status
        _, status = os.waitpid(pid, 0)
        return os.waitstatus_to_exitcode(status) if os.WIFEXITED(status) else 1
    try:
        _pdeathsig()
        _loopback_up()
        _mount(None, '/', None, MS_REC | MS_PRIVATE)
        _mount('proc', '/proc', 'proc', MS_NOSUID | MS_NODEV | MS_NOEXEC)
        for path in cfg['hide']:
            if os.path.isdir(path):
                _mount('tmpfs', path, 'tmpfs', MS_NOSUID | MS_NODEV | MS_NOEXEC | MS_RDONLY, 'size=4k,mode=0555')
            elif os.path.exists(path):
                _mount('/dev/null', path, None, MS_BIND)
        d = Path(cfg['dir'])
        mirror_sock, cdp_sock = str(d / 'mirror.sock'), str(d / 'cdp.sock')

        async def main():
            mirror_server = await asyncio.start_server(_bridge(lambda: _unix(mirror_sock)), '127.0.0.1', int(cfg['mirror_port']))
            cdp_server = await asyncio.start_unix_server(_bridge(lambda: asyncio.open_connection('127.0.0.1', cdp)), cdp_sock)
            browser = await asyncio.create_subprocess_exec(cfg['chromium'], *args, stdin=subprocess.DEVNULL, preexec_fn=_pdeathsig)
            async with mirror_server, cdp_server:
                return await browser.wait()
        os._exit(asyncio.run(main()) & 0xff)
    except BaseException:
        os._exit(3)                               # PID 1 exits: the kernel kills every process in the jail


def selftest(timeout: float = 30) -> dict:
    """Launch the jailed browser against a probe mirror and verify the boundary. Used at service start."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer
    hits = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append((self.server.tag, self.path))
            if self.path == '/redirect':
                self.send_response(302)
                self.send_header('Location', f'http://127.0.0.1:{other.server_port}/via-redirect')
                self.end_headers()
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(f'<html><body>{self.server.tag}<img src="http://127.0.0.1:{other.server_port}/via-image"></body></html>'.encode())

        def log_message(self, *_):
            pass
    servers = []
    for tag in ('MIRROR', 'OTHER'):
        srv = HTTPServer(('127.0.0.1', 0), Handler)
        srv.tag = tag
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
    mirror, other = servers

    async def probe():
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            exe = wrapper(pw.chromium.executable_path, f'http://127.0.0.1:{mirror.server_port}/', policy())
            with socket.socket() as s:
                s.bind(('127.0.0.1', 0))
                port = s.getsockname()[1]
            profile = tempfile.mkdtemp(prefix='jail-probe-')
            proc = subprocess.Popen([exe, f'--remote-debugging-port={port}', '--headless=new', '--no-sandbox', f'--user-data-dir={profile}', 'about:blank'],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                browser = None
                for _ in range(int(timeout * 5)):
                    try:
                        browser = await pw.chromium.connect_over_cdp(f'http://127.0.0.1:{port}')
                        break
                    except Exception:
                        await asyncio.sleep(.2)
                if browser is None:
                    return {'ok': False, 'reason': 'jailed browser did not start'}
                page = await browser.contexts[0].new_page()
                await page.goto(f'http://127.0.0.1:{mirror.server_port}/', timeout=10000)
                reached = 'MIRROR' in await page.inner_text('body')
                blocked = []
                for url in (f'http://127.0.0.1:{other.server_port}/direct', f'http://127.0.0.1:{mirror.server_port}/redirect', 'http://1.1.1.1/', 'http://169.254.169.254/'):
                    try:
                        await page.goto(url, timeout=5000)
                        blocked.append(False)
                    except Exception:
                        blocked.append(True)
                await browser.close()
                return {'ok': reached and all(blocked) and not any(t == 'OTHER' for t, _ in hits), 'mirror_reachable': reached, 'escapes_blocked': all(blocked)}
            finally:
                proc.terminate()
                try:
                    proc.wait(10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                import shutil
                shutil.rmtree(profile, ignore_errors=True)
    try:
        return asyncio.run(probe())
    except Exception as exc:
        return {'ok': False, 'reason': type(exc).__name__}
    finally:
        for srv in servers:
            srv.shutdown()


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == 'outer':
        raise SystemExit(outer(sys.argv[2], sys.argv[3:]))
    if len(sys.argv) >= 4 and sys.argv[1] == 'inner':
        raise SystemExit(inner(sys.argv[2], int(sys.argv[3]), sys.argv[4:]))
    raise SystemExit('internal entry point')


if __name__ == '__main__':
    main()
