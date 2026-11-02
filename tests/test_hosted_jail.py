"""The hosted browser boundary: Chromium runs with loopback-only networking and only the mirror port bridged."""
import asyncio
import json
import os
import socket
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from agent_readiness.hosted import jail


@pytest.fixture
def policy(tmp_path, monkeypatch):
    hidden = tmp_path / 'secret-app'
    hidden.mkdir()
    (hidden / 'secret.txt').write_text('TOP-SECRET-VALUE')
    path = tmp_path / 'policy.json'
    import shutil, tempfile
    short = tempfile.mkdtemp(prefix='arj-', dir='/tmp')                  # Unix socket paths must stay short
    path.write_text(json.dumps({'hide': [str(hidden)], 'dir': short}))
    monkeypatch.setenv(jail.ENV, str(path))
    yield hidden
    shutil.rmtree(short, ignore_errors=True)


def test_required_isolation_fails_closed_without_policy(monkeypatch):
    monkeypatch.delenv(jail.ENV, raising=False)
    monkeypatch.setattr(jail, '_REQUIRED', False)
    assert jail.policy() is None
    jail.require()
    try:
        with pytest.raises(RuntimeError, match='required'):
            jail.policy()
    finally:
        monkeypatch.setattr(jail, '_REQUIRED', False)


def test_policy_and_wrapper_refuse_unsafe_configuration(tmp_path, monkeypatch, policy):
    pol = jail.policy()
    with pytest.raises(RuntimeError, match='loopback'):
        jail.wrapper('/bin/true', 'http://example.com:80/', pol)
    with pytest.raises(RuntimeError, match='hides'):
        jail.wrapper(str(policy / 'chrome'), 'http://127.0.0.1:8000/', pol)
    for bad in ({'hide': ['/']}, {'hide': [str(policy)], 'dir': '/tmp/' + 'x' * 80}):
        (tmp_path / 'bad.json').write_text(json.dumps(bad))
        monkeypatch.setenv(jail.ENV, str(tmp_path / 'bad.json'))
        with pytest.raises(RuntimeError):
            jail.policy()


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/redirect':
            self.send_response(302)
            self.send_header('Location', self.server.redirect)
            self.end_headers()
            return
        body = f'<html><body>{self.server.tag}{self.path}<img src="{self.server.redirect}"></body></html>'.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


def _serve(tag):
    server = HTTPServer(('127.0.0.1', 0), _Handler)
    server.tag, server.hits = tag, 0
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.mark.browser
def test_jailed_chromium_reaches_only_the_mirror(tmp_path, policy):
    mirror, other = _serve('MIRROR'), _serve('OTHER')
    mirror.redirect = other.redirect = f'http://127.0.0.1:{other.server_port}/leak'
    seen = []
    original = _Handler.do_GET
    def counting(self):
        seen.append((self.server.tag, self.path))
        original(self)
    _Handler.do_GET = counting

    async def main():
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            exe = jail.wrapper(pw.chromium.executable_path, f'http://127.0.0.1:{mirror.server_port}/', jail.policy())
            with socket.socket() as s:
                s.bind(('127.0.0.1', 0))
                port = s.getsockname()[1]
            proc = subprocess.Popen([exe, f'--remote-debugging-port={port}', '--headless=new', '--no-sandbox', f'--user-data-dir={tmp_path}/profile', 'about:blank'],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                for _ in range(150):
                    try:
                        browser = await pw.chromium.connect_over_cdp(f'http://127.0.0.1:{port}')
                        break
                    except Exception:
                        await asyncio.sleep(.2)
                ctx = browser.contexts[0]

                async def visit(url):
                    page = await ctx.new_page()
                    try:
                        await page.goto(url, timeout=8000)
                        return await page.inner_text('body')
                    except Exception as exc:
                        return 'ERROR ' + str(exc).splitlines()[0]
                    finally:
                        await page.close()
                results = {u: await visit(u) for u in [
                    f'http://127.0.0.1:{mirror.server_port}/page', f'http://127.0.0.1:{other.server_port}/direct',
                    f'http://127.0.0.1:{mirror.server_port}/redirect', 'https://example.com/', 'http://169.254.169.254/latest/meta-data/',
                    'file://' + str(policy / 'secret.txt')]}
                page = await ctx.new_page()
                await page.goto(f'http://127.0.0.1:{mirror.server_port}/page')
                fetched = await page.evaluate(f"fetch('http://127.0.0.1:{other.server_port}/fetch').then(r => 'reached').catch(() => 'blocked')")
                procs = await visit('file:///proc/')
                await browser.close()
                return results, fetched, procs
            finally:
                proc.terminate()
                proc.wait(10)
    try:
        results, fetched, procs = asyncio.run(main())
    finally:
        _Handler.do_GET = original
    pages = list(results.values())
    assert pages[0].startswith('MIRROR/page')
    assert all(p.startswith('ERROR') for p in pages[1:]), results
    assert 'TOP-SECRET-VALUE' not in json.dumps(results)
    assert fetched == 'blocked'
    assert not any(tag == 'OTHER' for tag, _ in seen), seen          # no request (navigation, redirect, image, fetch) left the jail
    assert str(os.getpid()) not in procs.split()                     # the worker's /proc (environment) is not visible
    assert not list((Path(jail.policy()['dir'])).glob('jail-*'))     # per-launch directory cleaned up


@pytest.mark.browser
def test_real_agent_stack_runs_a_graded_trial_inside_the_jail(tmp_path, policy):
    from agent_readiness.investigate import zoo
    from agent_readiness.investigate.trials.runner import run_trial
    from .test_investigate_trials import frozen_run, instance_for
    run = frozen_run(tmp_path)
    inst = instance_for(run, 'page_fact')
    rec = asyncio.run(run_trial(inst, zoo.snapshot('site-1'), provider='mock', mock_behavior='correct', output=tmp_path / 't'))
    assert rec['outcome']['run_status'] == 'completed', rec['outcome']
    assert rec['evaluation']['passed'] is True and rec['evaluation']['evidence_backed'] is True
    events = [json.loads(l) for l in (Path(rec['artifact_path']) / 'trace.jsonl').read_text().splitlines()]
    assert any(e['kind'] == 'browser_isolation' and e['mode'] == 'netns-loopback-mirror-only' for e in events)


@pytest.mark.browser
def test_selftest_passes_with_the_jail_and_fails_without_it(policy, monkeypatch):
    assert jail.selftest() == {'ok': True, 'mirror_reachable': True, 'escapes_blocked': True, 'filesystem_hidden': True}
    monkeypatch.setattr(jail, 'wrapper', lambda chromium, url, pol: chromium)       # an unjailed browser
    result = jail.selftest()
    assert result['ok'] is False and result['escapes_blocked'] is False


@pytest.mark.browser
def test_jailed_chromium_starts_when_the_real_home_is_hidden(tmp_path, monkeypatch):
    """Regression (found in the container): with $HOME hidden read-only, Chromium needs a private writable home."""
    import shutil, tempfile
    home = tmp_path / 'home'
    (home / '.config').mkdir(parents=True)
    import os
    monkeypatch.setenv('PLAYWRIGHT_BROWSERS_PATH', os.environ.get('PLAYWRIGHT_BROWSERS_PATH') or os.path.expanduser('~/.cache/ms-playwright'))
    monkeypatch.setenv('HOME', str(home))
    short = tempfile.mkdtemp(prefix='arj-', dir='/tmp')
    path = tmp_path / 'policy.json'
    path.write_text(json.dumps({'hide': [str(home)], 'dir': short}))
    monkeypatch.setenv(jail.ENV, str(path))
    try:
        assert jail.selftest()['ok'] is True
    finally:
        shutil.rmtree(short, ignore_errors=True)
