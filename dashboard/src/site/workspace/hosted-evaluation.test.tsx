// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { HostedEvaluation, type Job } from './HostedEvaluation';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); document.body.innerHTML = ''; });

const config = (over = {}) => ({ available: true, mode: 'live', repetitions: [1, 3, 5], model: 'muse-spark-1.3', agent_profile: 'suite-v2-compat2', remaining_repetitions: 10, active: null,
  tasks: [1, 2, 3, 4].map(n => ({ task: n, question: `Question ${n}?`, limits: { max_steps: 14, timeout_seconds: 240 } })), ...over });
const arm = (o = {}) => ({ planned: 4, completed: 0, failed: 0, evidence_supported_passes: 0, strict_passes: 0, requests_total: 0, requests_mean: null, page_views_mean: null, steps_mean: null, elapsed_mean: null, ...o });
const job = (over: Partial<Job> = {}): Job => ({ id: 'eval-' + 'a'.repeat(32), state: 'running', mode: 'live', repetitions: 1, created_at: 1, started_at: 1, finished_at: null,
  reps: [{ index: 1, state: 'running', assessment: null, tasks: [{ arm: 'Original', task: 1, state: 'running', outcome: 'running', requests: null, page_views: null, steps: null, elapsed_seconds: null }] }],
  summary: { Original: arm(), Modified: arm() }, ...over });
const json = (body: unknown, ok = true) => ({ ok, json: async () => body });

function server(routes: (url: string, init?: RequestInit) => unknown) {
  const mock = vi.fn(async (url: string, init?: RequestInit) => { const r = routes(url, init); return r && typeof r === 'object' && 'ok' in (r as object) ? r : json(r); });
  vi.stubGlobal('fetch', mock); return mock;
}
async function mount(props = {}) {
  const host = document.createElement('div'); document.body.append(host); const root = createRoot(host);
  await act(async () => { root.render(<HostedEvaluation onOpen={() => {}} {...props} />); });
  await act(async () => {});
  return { host, root };
}
const button = (host: HTMLElement, text: string) => [...host.querySelectorAll('button')].find(b => b.textContent?.includes(text)) as HTMLButtonElement;

it('keeps the archived fallback when the hosted service is disabled and never posts', async () => {
  const f = server(url => url.endsWith('/config') ? config({ available: false, mode: null }) : []);
  const { host } = await mount();
  expect(host.textContent).toContain('currently unavailable');
  expect(button(host, 'Run evaluation').disabled).toBe(true);
  expect(f.mock.calls.some(c => c[1]?.method === 'POST')).toBe(false);
});

it('posts only the chosen repetition count after a click and shows server progress', async () => {
  const f = server((url, init) => init?.method === 'POST' ? { id: 'eval-' + 'a'.repeat(32), state: 'reserved' } : url.endsWith('/config') ? config() : url.endsWith('/jobs') ? [] : job({ repetitions: 3 }));
  const { host } = await mount();
  expect(host.textContent).toContain('Live · Meta Muse Spark');
  await act(async () => { button(host, '24 agent runs').click(); });
  await act(async () => { button(host, 'Run evaluation').click(); });
  const posts = f.mock.calls.filter(c => c[1]?.method === 'POST');
  expect(posts).toHaveLength(1);
  expect(JSON.parse(posts[0][1]!.body as string)).toEqual({ repetitions: 3 });
  expect(host.textContent).toContain('Agent working');
  expect(host.textContent).toContain('0 / 24 agent runs finished');
  expect(localStorage.getItem('ironbark-hosted-job')).toBe('eval-' + 'a'.repeat(32));
});

it('shows server metrics and labels rehearsal results as not model results', async () => {
  const done = job({ state: 'completed', mode: 'rehearsal', finished_at: 61,
    reps: [{ index: 1, state: 'completed', assessment: { frozen_rule: 'inconclusive', exploratory: 'not_supported', evidence_origin: 'scripted' },
      tasks: [{ arm: 'Original', task: 1, state: 'completed', outcome: 'not_passed', requests: 12, page_views: 9, steps: 12, elapsed_seconds: 80 },
              { arm: 'Modified', task: 1, state: 'completed', outcome: 'evidence_supported_pass', requests: 6, page_views: 4, steps: 6, elapsed_seconds: 40 }] }],
    summary: { Original: arm({ completed: 1, requests_total: 12, requests_mean: 12 }), Modified: arm({ completed: 1, evidence_supported_passes: 1, strict_passes: 1, requests_total: 6, requests_mean: 6 }) } });
  localStorage.setItem('ironbark-hosted-job', done.id);
  server(url => url.endsWith('/config') ? config({ mode: 'rehearsal' }) : url.endsWith('/jobs') ? [] : done);
  const { host } = await mount();
  expect(host.textContent).toContain('These are not Muse Spark results');
  expect(host.textContent).toContain('50% fewer on Modified');
  expect(host.textContent).toContain('Evidence-supported pass');
  expect(host.textContent).toContain('Frozen comparison rule: inconclusive');
  expect(host.textContent).toContain('Evidence: scripted');
});

it('offers to watch another visitor’s running evaluation instead of starting a second one', async () => {
  const other = 'eval-' + 'b'.repeat(32);
  server(url => url.endsWith('/config') ? config({ active: other, worker: { state: 'busy', job: other, finished_runs: 5, total_runs: 24, estimated_remaining_seconds: 1500 } }) : url.endsWith('/jobs') ? [] : url.endsWith('/live') ? { active: true, trial: null } : job({ id: other }));
  const { host } = await mount();
  expect(button(host, 'Run evaluation').disabled).toBe(true);
  expect(host.textContent).toContain('Worker busy');
  expect(host.textContent).toContain('5 of 24 agent runs finished, about 25 min left (estimate)');
  expect(host.textContent).toContain('Completed evaluations below remain available');
  await act(async () => { button(host, 'Watch it live').click(); });
  expect(host.textContent).toContain('Running');
});

it('shows an available worker and duration estimates from the measured basis', async () => {
  server(url => url.endsWith('/config') ? config({ worker: { state: 'idle', job: null }, repetition_duration: { seconds: 558, basis: 'first genuine run', samples: 0 } }) : []);
  const { host } = await mount();
  expect(host.textContent).toContain('Worker available');
  expect(host.textContent).toContain('about 9 min per repetition (based on the first genuine Muse Spark run)');
  expect(host.textContent).toContain('40 agent runs');
  expect(host.textContent).toContain('about 47 min');
  expect(button(host, 'Run evaluation').disabled).toBe(false);
});

it('shows grader v2 only as a labelled post-hoc line beside the official v1 result, and marks only cells where it differs', async () => {
  const v2 = { label: 'Post-hoc rescore with grader v2', faithful: true, assessment: { frozen_rule: 'inconclusive', exploratory: 'consistent_with_h1' },
    tasks: [{ arm: 'Original' as const, task: 1, outcome: 'evidence_supported_pass', reasons: ['matches_truth_with_consistent_detail'] }, { arm: 'Modified' as const, task: 1, outcome: 'evidence_supported_pass', reasons: ['matches_truth'] }] };
  const done = job({ state: 'completed', finished_at: 61,
    reps: [{ index: 1, state: 'completed', assessment: { frozen_rule: 'inconclusive', exploratory: 'consistent_with_h1', evidence_origin: 'real_model' }, grading_v2: v2,
      tasks: [{ arm: 'Original', task: 1, state: 'completed', outcome: 'not_passed', requests: 13, page_views: 13, steps: 14, elapsed_seconds: 62 },
              { arm: 'Modified', task: 1, state: 'completed', outcome: 'evidence_supported_pass', requests: 6, page_views: 6, steps: 7, elapsed_seconds: 32 }] }],
    summary: { Original: arm({ completed: 1, requests_total: 13, requests_mean: 13 }), Modified: arm({ completed: 1, evidence_supported_passes: 1, strict_passes: 1, requests_total: 6, requests_mean: 6 }) },
    summary_v2: { label: 'Post-hoc rescore with grader v2', repetitions: 1, Original: { completed: 1, evidence_supported_passes: 1, strict_passes: 1 }, Modified: { completed: 1, evidence_supported_passes: 1, strict_passes: 1 } } });
  localStorage.setItem('ironbark-hosted-job', done.id);
  server(url => url.endsWith('/config') ? config() : url.endsWith('/jobs') ? [] : url.endsWith('/insights') ? { state: 'unavailable' } : done);
  const { host } = await mount();
  const big = host.querySelector('.ws-big')!.textContent!;
  expect(big).toContain('0/1');                                                     // the official headline stays grader v1
  const line = host.querySelector('.ws-v2-line')!.textContent!;
  expect(line).toContain('Grader v2, post-hoc rescore: 1/1 → 1/1');
  expect(line).toContain('official result above: grader v1');
  const diffs = [...host.querySelectorAll('.ws-v2-diff')].map(e => e.textContent);
  expect(diffs).toEqual(['Grader v2 (post-hoc): pass']);                           // Original task 1 only; Modified agrees with v1
  expect(host.querySelector('.ws-v2-verdicts')!.textContent).toContain('not pre-registered');
});

it('hides grader v2 entirely when the rescore was not faithful', async () => {
  const done = job({ state: 'completed', finished_at: 61,
    reps: [{ index: 1, state: 'completed', assessment: { frozen_rule: 'inconclusive', exploratory: null, evidence_origin: 'real_model' },
      grading_v2: { label: 'x', faithful: false, tasks: [], assessment: null },
      tasks: [{ arm: 'Original', task: 1, state: 'completed', outcome: 'not_passed', requests: 13, page_views: 13, steps: 14, elapsed_seconds: 62 }] }],
    summary: { Original: arm({ completed: 1, requests_total: 13, requests_mean: 13 }), Modified: arm() }, summary_v2: null });
  localStorage.setItem('ironbark-hosted-job', done.id);
  server(url => url.endsWith('/config') ? config() : url.endsWith('/jobs') ? [] : url.endsWith('/insights') ? { state: 'unavailable' } : done);
  const { host } = await mount();
  expect(host.querySelector('.ws-v2-line')).toBeNull();
  expect(host.querySelector('.ws-v2-diff')).toBeNull();
  expect(host.querySelector('.ws-v2-verdicts')).toBeNull();
});

it('shows recorded model provenance and the frozen profile settings, both from the server', async () => {
  const provenance = { trials: 8, model_requests_recorded: 78, consistent: true, model: { value: 'muse-spark-1.3', consistent: true }, reasoning_effort: { value: 'low', consistent: true },
    max_completion_tokens: { value: 4096, consistent: true }, agent_profile: { name: 'suite-v2-compat2', sha256: '29ad53dcf7c9d799be4e', verified_against_profile_file: true },
    graders: { official: [{ id: 'generated-criteria', version: '1' }], post_hoc: { id: 'generated-criteria', version: '2', derivation_id: 'abc' } },
    by_arm: { baseline: { trials: 4, agent_profile: { name: 'suite-v2-compat1' } } } };
  const done = job({ state: 'completed', finished_at: 61,
    reps: [{ index: 1, state: 'completed', assessment: { frozen_rule: 'inconclusive', exploratory: 'consistent_with_h1', evidence_origin: 'real_model' }, provenance,
      tasks: [{ arm: 'Original', task: 1, state: 'completed', outcome: 'not_passed', requests: 13, page_views: 13, steps: 14, elapsed_seconds: 62 }] }],
    summary: { Original: arm({ completed: 1, requests_total: 13, requests_mean: 13 }), Modified: arm() } });
  localStorage.setItem('ironbark-hosted-job', done.id);
  server(url => url.endsWith('/config') ? config({ agent_settings: { profile: 'suite-v2-compat2', profile_file_sha256: 'x', reasoning_effort: 'low', max_completion_tokens: 4096 } }) : url.endsWith('/jobs') ? [] : url.endsWith('/insights') ? { state: 'unavailable' } : done);
  const { host } = await mount();
  const notes = [...host.querySelectorAll('.ws-provenance')].map(n => n.textContent ?? '');
  expect(notes.length).toBeGreaterThanOrEqual(1);
  for (const s of ['muse-spark-1.3', 'reasoning_effort low', 'max_completion_tokens 4096', 'suite-v2-compat2', '29ad53dcf7c9', 'matches the profile file', '78 model requests', 'generated-criteria v1', 'never the official result', 'suite-v2-compat1'])
    expect(notes[0]).toContain(s);
  expect(host.querySelector('.ws-method')!.textContent).toContain('read from the profile file');
});
