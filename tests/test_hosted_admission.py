from concurrent.futures import ThreadPoolExecutor

import pytest

from agent_readiness.hosted.admission import Admission, Refused


def test_atomic_concurrent_reservations_and_crash_recovery(tmp_path):
    path = tmp_path / 'budget.sqlite'
    store = Admission(path, ceiling_microusd=3200000, job_cap_microusd=1600000)
    def attempt(i):
        try:
            Admission(path, ceiling_microusd=3200000, job_cap_microusd=1600000).reserve('job'+str(i), str(i)*64, now=100)
            return True
        except Refused:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, [1, 2]))
    assert sorted(outcomes) == [False, True]
    job = 'job'+str(outcomes.index(True)+1)
    restarted = Admission(path, ceiling_microusd=3200000, job_cap_microusd=1600000)
    assert restarted.get(job)['state'] == 'reserved'
    with pytest.raises(Refused):
        restarted.reserve('other', 'a'*64, now=300)
    restarted.transition(job, 'reserved', 'failed')
    assert restarted.get(job)['reserved_microusd'] == 1600000
    restarted.reserve('other', 'a'*64, now=300)
    restarted.transition('other', 'reserved', 'failed')
    with pytest.raises(Refused, match='budget exhausted'):
        restarted.reserve('third', 'b'*64, now=400)


def test_rate_limit_and_policy_fail_closed(tmp_path):
    p = tmp_path / 'budget.sqlite'
    store = Admission(p, ceiling_microusd=3200000, job_cap_microusd=1000000)
    store.reserve('one', 'a'*64, now=100)
    store.transition('one', 'reserved', 'running')
    store.transition('one', 'running', 'timed_out')
    with pytest.raises(Refused, match='rate limit'):
        store.reserve('two', 'a'*64, now=101)
    with pytest.raises(ValueError, match='policy differs'):
        Admission(p, ceiling_microusd=9000000, job_cap_microusd=1000000)
    with pytest.raises(Refused):
        store.transition('one', 'running', 'completed')
