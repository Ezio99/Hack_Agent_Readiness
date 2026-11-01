"""Explicit sensitivity-only exception to identical-profile controls.

No imported configuration is rewritten. Both new arms use the successor;
comparisons to the archived compat1 baseline are labelled sensitivity evidence.
"""
from ...agent import profile
from ...ledger import Halt
from ...suite.core import canonical_hash

ARTIFACT = 'scroll-profile-successor'
OLD, NEW = 'suite-v2-compat1', 'suite-v2-compat2'


def rule():
    old, new = profile(OLD), profile(NEW)
    if new != {**old, 'id': NEW, 'scroll_index_policy': 'page-fallback-v1'}:
        raise Halt('scroll successor differs beyond id and scroll_index_policy')
    return {'id': 'scroll-profile-successor-v1', 'baseline_profile': OLD, 'successor_profile': NEW,
            'baseline_profile_sha256': canonical_hash(old), 'successor_profile_sha256': canonical_hash(new),
            'allowed_changes': {'id': [OLD, NEW], 'scroll_index_policy': [None, 'page-fallback-v1']},
            'scope': 'EXP-C-S1 sensitivity: BOTH new arms; archived baseline remains compat1',
            'historical_comparison': 'different reference-agent version; never pooled with EXP-C/R1'}


def declared(run):
    if not run.has_artifact(ARTIFACT):
        return None
    r = run.artifact(ARTIFACT)
    if r != rule():
        raise Halt('scroll successor rule or profile hash drift')
    return {'rule': r, 'sha256': canonical_hash(r)}


def check(run, baseline, record):
    if not declared(run):
        return False
    for rec, pid in ((baseline, OLD), (record, NEW)):
        effective = profile(pid)
        limits = rec['task']['limits']
        effective.update({k: limits[k] for k in ('max_steps', 'timeout_seconds', 'max_model_requests')})
        if rec['trial'].get('profile') != pid or rec['trial'].get('profile_hash') != canonical_hash(effective):
            raise Halt('scroll successor: unexpected effective profile or limits')
    return True
