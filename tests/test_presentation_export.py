import json
from pathlib import Path
from types import SimpleNamespace

from agent_readiness.investigate.presentation import origin, storyboard
from agent_readiness.investigate.export import check_clean, check_public, _evaluation


def run_fixture(tmp_path, events):
    d=tmp_path/'artifacts/trials'; d.mkdir(parents=True)
    rec={'task_id':'task-1','trial_dir':'trial-data/selected','trial':{'mode':'live'},'mirror':{'log':[{'method':'GET','status':200}]},'evaluation':{'passed':True,'evidence_backed':False}}
    (d/'patched-test.json').write_text(json.dumps(rec))
    t=tmp_path/'trial-data/selected';t.mkdir(parents=True);(t/'trace.jsonl').write_text('\n'.join(map(json.dumps,events)))
    return SimpleNamespace(dir=tmp_path,mode='live',has_artifact=lambda n:False,artifact=lambda n:rec)


def test_origin_requires_correlated_provider_records_not_mode_or_name(tmp_path):
    r=run_fixture(tmp_path,[]); assert origin(r)['provider']=='unknown'
    path=tmp_path/'trial-data/selected/trace.jsonl'
    def put(url):
        path.write_text('\n'.join(map(json.dumps,[{'kind':'model_http_request','index':1,'url':url},{'kind':'model_http_response','index':1,'http_status':200}])))
    put('http://127.0.0.1/v1');assert origin(r)['provider']=='dev_fixture'
    put('https://api.meta.ai/v1');assert origin(r)['provider']=='real_model'
    r.artifact=lambda n:{'trial':{'mode':'live'},'trial_dir':'trial-data/selected','mirror':{'log':[]}}
    assert origin(r)['provider']=='unknown'  # provider metadata alone does not prove browser observations
    r.has_artifact=lambda n:n=='fixture-evidence'; assert origin(r)['provider']=='scripted'
    r.has_artifact=lambda n:n=='dev-provider';assert origin(r)['provider']=='dev_fixture'
    r.mode='mock';r.has_artifact=lambda n:False;assert origin(r)['provider']=='scripted'


def test_effect_measurement_requires_verified_origin():
    effect = SimpleNamespace(proposal_id='p', measured=True, provenance=SimpleNamespace(mode='live'))
    ev = SimpleNamespace(effects={'effect': effect})
    evaluation = {'evaluated': True, 'results': {'p': {'verdict': 'inconclusive'}}, 'rule': {}}
    run = SimpleNamespace(has_artifact=lambda name: name == 'evaluation', artifact=lambda name: evaluation)
    assert _evaluation(run, ev, False)['results'][0]['measured'] is False
    assert _evaluation(run, ev, True)['results'][0]['measured'] is True


def test_origin_rejects_uncorrelated_and_mixed_provenance(tmp_path):
    events = [{'kind': 'model_http_request', 'index': 1, 'url': 'https://api.meta.ai/v1'},
              {'kind': 'model_http_response', 'index': 2, 'http_status': 200}]
    r = run_fixture(tmp_path, events)
    assert origin(r)['provider'] == 'unknown'
    path = tmp_path / 'trial-data/selected/trace.jsonl'
    events[1]['index'] = 1
    path.write_text('\n'.join(map(json.dumps, events)))
    assert origin(r)['provider'] == 'real_model'
    (tmp_path / 'artifacts/trials/second.json').write_text('{}')
    original = r.artifact
    r.artifact = lambda name: {'trial': {'mode': 'live'}} if name.endswith('second') else original(name)
    assert origin(r)['provider'] == 'unknown'


def test_origin_rejects_missing_assessment_trials(tmp_path):
    events = [{'kind': 'model_http_request', 'index': 1, 'url': 'https://api.meta.ai/v1'},
              {'kind': 'model_http_response', 'index': 1, 'http_status': 200}]
    r = run_fixture(tmp_path, events)
    trial = r.artifact('trials/patched-test')
    docs = {'evaluation': {'evaluated': True, 'results': {'p': {}}},
            'tasks-manifest': {'tasks': [{'task_id': 'task-1'}]}}
    r.has_artifact = lambda name: name in docs
    r.artifact = lambda name: docs[name] if name in docs else trial
    assert origin(r)['provider'] == 'unknown'


def test_storyboard_allowlists_actions_and_presence_without_exporting_payloads(tmp_path):
    events=[{'kind':'observation','sequence':1,'dom':'Refundable deposit: SECRET_TRUTH','url':'http://user:password@host/?token=secret'},
            {'kind':'scroll_index_fallback','sequence':2,'requested_index':1,'result':{'error':None,'extracted_content':'PRIVATE_TRACE'}},
            {'kind':'step_result','sequence':3,'result':{'model_output':{'action':[{'scroll':{'index':1}},{'done':{'data':{'answer':'SECRET_TRUTH'}}},{'navigate':{'url':'https://secret'}}]},'result':[{'extracted_content':'PRIVATE_TRACE'}, {'error':None}]}}]
    r=run_fixture(tmp_path,events);s=storyboard(r);text=json.dumps(s)
    assert [i['event'] for i in s['steps']]==[1,2,3,3]
    assert 'Navigated' not in text  # no execution result for this proposed action
    assert not any(x in text for x in ('SECRET_TRUTH','PRIVATE_TRACE','password','https://secret'))
    assert s['strict_pass'] and not s['evidence_supported'];check_clean(s)


def test_bundled_recording_is_public_sanitized_and_keeps_the_accepted_verdicts():
    d=json.loads(Path('dashboard/src/fixtures/ironbark-s1-recorded.json').read_text())
    check_clean(d);check_public(d)
    assert d['evidence_origin']=={'provider':'real_model','presentation':'recorded'}
    assert d['evaluation']['results'][0]['verdict']=='inconclusive'
    assert d['evaluation']['exploratory']['verdict']=='not_supported'
    for arm,n,req in [('placebo',2,50),('patched',3,29)]:
        rows=[r for t in d['tasks'] for rows in t[arm].values() for r in rows]
        assert sum(r['passed'] and r['evidence_backed'] for r in rows)==n
        assert sum(r['model_requests'] for r in rows)==req
    assert d['storyboard']['steps']
