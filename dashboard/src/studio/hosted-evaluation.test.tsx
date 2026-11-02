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
  server(url => url.endsWith('/config') ? config({ active: 'eval-' + 'b'.repeat(32) }) : url.endsWith('/jobs') ? [] : job({ id: 'eval-' + 'b'.repeat(32) }));
  const { host } = await mount();
  expect(button(host, 'Run evaluation').disabled).toBe(true);
  await act(async () => { button(host, 'Watch the running evaluation').click(); });
  expect(host.textContent).toContain('Running');
});
