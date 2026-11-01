"""Reproduce the reviewed read-only public S1 presentation asset. No execution."""
import json
from pathlib import Path
from agent_readiness.investigate.export import export_run, public_demo
from agent_readiness.suite.core import canonical_hash

root = Path('scanner-data/live/live-ab-ironbark-s1')
h = '99f493d1558db5d925069e5ae8ea66fc21e2927e1364a69ddb45ec9ae3a550f8'
assert canonical_hash(json.loads((root/'artifacts/manifests'/f'post_trials-{h[:16]}.json').read_text())) == h
x = public_demo(export_run(root))
assert x['evidence_origin']['provider'] == 'real_model'
x['demo_case'] = {'id':'ironbark-s1','label':'Recorded Ironbark S1 · sensitivity experiment','recorded_on':'2026-11-01',
                  'note':'Owner-selected listing change; improvement not established. EXP-C and R1 are separate experiments.'}
Path('dashboard/src/fixtures/ironbark-s1-recorded.json').write_text(json.dumps(x, indent=2)+'\n')
