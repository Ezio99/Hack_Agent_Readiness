"""Offline scroll mechanism and sensitivity integrity checks; never a model trial."""
import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from agent_readiness.agent import apply_scroll_index_policy, profile
from agent_readiness.recorder import Recorder
from agent_readiness.investigate.evaluate import scroll_successor as ss
from agent_readiness.investigate.evaluate.stage import _check_control
from agent_readiness.ledger import Halt
from agent_readiness.suite.core import canonical_hash


def test_profile_changes_only_policy_and_identity():
    assert profile(ss.NEW) == {**profile(ss.OLD), 'id': ss.NEW, 'scroll_index_policy': 'page-fallback-v1'}


def test_wrapper_preserves_interface_other_actions_and_current_map(tmp_path):
    from browser_use import Tools
    from browser_use.tools.views import ScrollAction
    from browser_use.agent.views import ActionResult
    tools = Tools()
    schema = tools.registry.create_action_model().model_json_schema()
    before = {n: (a.function, a.description, a.param_model) for n, a in tools.registry.registry.actions.items()}
    seen = []
    async def original(params, browser_session, **kwargs):
        seen.append(params)
        return ActionResult(extracted_content='ordinary scroll', error='real scroll failure' if params.pages == 9 else None)
    tools.registry.registry.actions['scroll'].function = original
    rec = Recorder(tmp_path)
    apply_scroll_index_policy(tools, rec)
    assert tools.registry.create_action_model().model_json_schema() == schema
    for n, a in tools.registry.registry.actions.items():
        assert (a.description, a.param_model) == before[n][1:]
        if n != 'scroll':
            assert a.function is before[n][0]
    mapping = {17: object()}
    async def current():
        return mapping
    session = SimpleNamespace(get_selector_map=current)
    async def run():
        fn = tools.registry.registry.actions['scroll'].function
        for idx in (None, 0, 17, 999):
            p = ScrollAction(index=idx)
            r = await fn(params=p, browser_session=session, page_extraction_llm=None)
            assert r.extracted_content == 'ordinary scroll' and p.index == idx
        mapping.clear()  # formerly valid index is now stale
        await fn(params=ScrollAction(index=17), browser_session=session)
        r = await fn(params=ScrollAction(index=999, pages=9), browser_session=session)
        assert r.error == 'real scroll failure'  # unrelated failures are not hidden
        async def broken():
            raise RuntimeError('map unavailable')
        with pytest.raises(RuntimeError, match='map unavailable'):
            await fn(params=ScrollAction(index=999), browser_session=SimpleNamespace(get_selector_map=broken))
    asyncio.run(run())
    assert [p.index for p in seen] == [None, 0, 17, None, None, None]
    events = [json.loads(l) for l in (rec.path/'trace.jsonl').read_text().splitlines()]
    assert [e['requested_index'] for e in events] == [999, 17, 999]
    assert all(e['current_map_valid'] is False and e['executed_action']['scroll']['index'] is None for e in events)
    assert events[-1]['result']['error'] == 'real scroll failure'


def test_successor_control_is_opt_in_hashed_and_rejects_unrelated_changes(monkeypatch):
    limits = dict(max_steps=14, timeout_seconds=240, max_model_requests=14)
    def record(pid):
        return {'trial': {'profile': pid, 'profile_hash': canonical_hash({**profile(pid), **limits}), 'model': 'm', 'mode': 'live', 'schema_hashes': {}, 'snapshot_sha256': 's'}, 'task': {'limits': limits}}
    base, rec = record(ss.OLD), record(ss.NEW)
    declaration = ss.rule()
    enabled = True
    run = SimpleNamespace(has_artifact=lambda n: enabled, artifact=lambda n: declaration if n == ss.ARTIFACT else base)
    step = {'label': 'placebo', 'task': {'task_id': 'x'}}
    _check_control(run, step, rec)
    enabled = False
    with pytest.raises(Halt): _check_control(run, step, rec)
    enabled = True
    for path, value in [('model', 'other'), ('schema_hashes', {'full': 'other'}), ('snapshot_sha256', 'other'), ('profile_hash', 'other')]:
        bad = copy.deepcopy(rec); bad['trial'][path] = value
        with pytest.raises(Halt): _check_control(run, step, bad)
    bad = copy.deepcopy(rec); bad['task']['limits'] = {**limits, 'max_steps': 15}
    with pytest.raises(Halt): _check_control(run, step, bad)
    declaration = {**declaration, 'scope': 'tampered'}
    with pytest.raises(Halt): _check_control(run, step, rec)
    declaration = ss.rule()
    real = ss.profile
    monkeypatch.setattr(ss, 'profile', lambda pid: {**real(pid), **({'instructions': 'different'} if pid == ss.NEW else {})})
    with pytest.raises(Halt): ss.rule()


@pytest.mark.browser
def test_real_browser_repeated_scroll_stale_index_and_recovery(tmp_path):
    from browser_use import Browser, Tools
    from browser_use.tools.views import ScrollAction
    from playwright.async_api import async_playwright
    from starlette.applications import Starlette
    from starlette.responses import HTMLResponse
    from starlette.routing import Route
    from agent_readiness.agent import browser_options, prepare_browser_environment
    from agent_readiness.scanner.serve import serve_app
    prepare_browser_environment()
    async def page(request):
        controls = '' if request.query_params.get('fresh') else '<a href="/">Top</a><button>Button</button>'
        return HTMLResponse('<html><body>' + controls + ''.join(f'<p style="height:300px">Row {i}</p>' for i in range(30)) + '</body></html>')
    async def run():
        async with serve_app(Starlette(routes=[Route('/', page)])) as url, async_playwright() as pw:
            browser = Browser(**browser_options(url, pw.chromium.executable_path, profile(ss.NEW)))
            try:
                await browser.start(); await browser.navigate_to(url)
                await browser.get_browser_state_summary(include_screenshot=False, cached=False)
                mapping = await browser.get_selector_map()
                valid = next(iter(mapping))
                old = Tools().registry.registry.actions['scroll'].function
                assert (await old(params=ScrollAction(index=999999), browser_session=browser)).error
                tools = Tools(); rec = Recorder(tmp_path); apply_scroll_index_policy(tools, rec)
                fn = tools.registry.registry.actions['scroll'].function
                async def y():
                    cdp = await browser.get_or_create_cdp_session()
                    r = await cdp.cdp_client.send.Runtime.evaluate(params={'expression': 'window.scrollY', 'returnByValue': True}, session_id=cdp.session_id)
                    return r['result']['value']
                last = await y()
                for idx in (999999, 999999, None, 0):
                    result = await fn(params=ScrollAction(index=idx), browser_session=browser)
                    assert not result.error
                    now = await y(); assert now > last; last = now
                assert not (await fn(params=ScrollAction(index=valid, down=False), browser_session=browser)).error
                # Invalidate the old map by navigating to a fresh document.
                await browser.navigate_to(url + '?fresh=1')
                await browser.get_browser_state_summary(include_screenshot=False, cached=False)
                current = await browser.get_selector_map()
                stale = valid
                assert stale not in current
                assert not (await fn(params=ScrollAction(index=stale), browser_session=browser)).error
                assert await y() > 0
                events = [json.loads(l) for l in (rec.path/'trace.jsonl').read_text().splitlines()]
                assert len(events) == 3 and events[-1]['requested_index'] == stale
            finally:
                await browser.kill()
    asyncio.run(run())


@pytest.mark.browser
def test_two_invalid_scrolls_stop_compat1_but_compat2_can_finish(tmp_path, monkeypatch):
    from agent_readiness.scanner import mock
    from agent_readiness.scanner.execute import execute_scan
    from agent_readiness.environments.electronics.variants import make_variant
    from agent_readiness.suite import registry
    registry.load_all()
    original = mock.make_handler
    def handler(instance, variant, base_url, behavior):
        normal = original(instance, variant, base_url, behavior)
        n = 0
        def respond(request):
            nonlocal n
            n += 1
            if n <= 2:
                return mock._reply(n, [{'scroll': {'down': True, 'pages': 0.5, 'index': 999999}}])
            return normal(request)
        return respond
    monkeypatch.setattr(mock, 'make_handler', handler)
    def run(pid):
        return asyncio.run(execute_scan('t1-anc-headphones-under-250-all', make_variant('listing', 'structured'), provider='mock', mock_behavior='correct', output=tmp_path/pid, profile_id=pid))
    old, new = run(ss.OLD), run(ss.NEW)
    assert old['outcome']['run_status'] == 'agent_failure'
    assert new['outcome']['run_status'] == 'completed' and new['evaluation']['passed']
    events = [json.loads(l) for l in (__import__('pathlib').Path(new['artifact_path'])/'trace.jsonl').read_text().splitlines()]
    assert len([e for e in events if e['kind'] == 'scroll_index_fallback']) == 2


def test_sensitivity_manifest_binds_rule_and_execution_uses_approved_profile(tmp_path, monkeypatch):
    from .test_investigate_expb import exp_ctx
    from agent_readiness.investigate.evaluate import stage as ev
    from agent_readiness.investigate.trials import stage as ts
    run, prop, plan, ctx = exp_ctx(tmp_path)
    old = ev.post_manifest(ctx)
    run.write_artifact(ss.ARTIFACT, ss.rule())
    from agent_readiness.investigate.report import notices_for
    assert notices_for(run, ['live'])[0].startswith('EXP-C-S1 SENSITIVITY:')
    new = ev.post_manifest(ctx)
    assert new['profile_successor'] == {'rule': ss.rule(), 'sha256': canonical_hash(ss.rule())}
    assert new['agent_profile'] == ss.NEW
    assert not new['same_tasks_profile_model_and_limits_as_baseline']
    assert new['placebo']['archived_baseline_reference']['agent_profile'] == ss.OLD
    for k in ('execution_order', 'execution_order_sha256', 'task_ids', 'tasks_manifest_sha256', 'snapshot_sha256', 'arms', 'caps_usd', 'model', 'endpoint', 'evaluation_rule_sha256', 'exploratory'):
        assert new[k] == old[k]
    calls = []
    async def fake(*args, **kwargs):
        calls.append(kwargs)
        d = kwargs['output'] / 'fake'; d.mkdir(parents=True)
        return {'artifact_path': str(d), 'outcome': {'run_status': 'completed'}}
    monkeypatch.setattr(ts, 'run_trial', fake)
    st = dict(label='placebo', prefix='test', repeat=1, task={'task_id': 'x', 'partition': 'investigation'}, inst=object(), snap=object())
    ts.run_plan(ctx, [st], manifest_=new)
    assert calls[0]['profile_id'] == ss.NEW


def test_legacy_trial_plan_without_profile_keeps_original_runner_default(tmp_path, monkeypatch):
    from agent_readiness.investigate.trials import stage as ts
    from agent_readiness.investigate.run import InvestigationRun
    from agent_readiness.investigate.pipeline import Context
    from agent_readiness.investigate.flow import STAGES
    run = InvestigationRun.create(tmp_path, 'legacy', target='site-1', mode='mock', stages=STAGES)
    calls = []
    async def fake(*args, **kwargs):
        calls.append(kwargs['profile_id'])
        out = kwargs['output'] / 'fake'; out.mkdir(parents=True)
        return {'artifact_path': str(out), 'outcome': {'run_status': 'completed'}}
    monkeypatch.setattr(ts, 'run_trial', fake)
    step = dict(label='baseline', prefix='legacy', repeat=1, task={'task_id':'x','partition':'investigation'}, inst=object(), snap=object())
    ts.run_plan(Context(run), [step], manifest_={})
    assert calls == ['suite-v2-compat1']
