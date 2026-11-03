// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterEach, expect, it, vi } from 'vitest';
import { HostedEvaluation } from './HostedEvaluation';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); document.body.innerHTML = ''; });

// The workspace in front of the Stage B engine: the same compose -> run -> watch flow; the launch body is still {repetitions} only; the results tab
// is the lifecycle readiness report (rendered here from the committed, real M7 projection served under a hosted job id).
const EV = JSON.parse(readFileSync(resolve(__dirname, '../../../../datasets/lifecycle/m7-larkspur-browser-1/v1/evaluation.json'), 'utf8'));
const ID = 'eval-' + 'c'.repeat(32);
const tasks = EV.tasks.map((t: any) => ({ task: t.n, question: t.customer_wording, limits: { max_steps: 14, timeout_seconds: 240, max_model_requests: 14 } }));
const armed = { arming_id: 'larkspur-live-1', arming_sha256: 'a'.repeat(64), mode: 'paid', site: 'larkspur', suite: 'larkspur-core v2', frozen_suite: 'larkspur-core@v2',
  frozen_suite_sha256: EV.frozen_suite.sha256, variants: ['original', 'modified'], armed_at: '2026-11-04T00:00:00+00:00', launches: { max: 2, used: 0, left: 2 },
  options: [{ repetitions: 1, trials: 12, reservation_usd: 7.436, manifest_sha256: EV.manifest.sha256, available: true, fits_hosted_ceiling: true }],
  agent: { model: 'muse-spark-1.3', reasoning_effort: 'low', max_completion_tokens: 4096, profile: 'suite-v2-compat2' } };
const config = (over = {}) => ({ engine: 'stage-b', available: true, mode: 'live', access: 'operator', repetitions: [1], model: 'muse-spark-1.3', agent_profile: 'suite-v2-compat2',
  remaining_repetitions: 2, active: null, tasks, evaluation: armed, worker: { state: 'idle', job: null }, ...over });
const row = (arm: string, n: number) => ({ arm, task: n, state: 'completed', outcome: 'not_passed', requests: 3, page_views: 3, steps: 3, elapsed_seconds: 16 });
const job = { id: ID, engine: 'stage-b', state: 'completed', mode: 'live', repetitions: 1, created_at: 1, started_at: 1, finished_at: 2, report: ID,
  reps: [{ index: 1, state: 'completed', assessment: null, tasks: tasks.flatMap((t: any) => [row('Original', t.task), row('Modified', t.task)]) }],
  summary: { Original: { planned: 6, completed: 6, failed: 0, evidence_supported_passes: 2, strict_passes: 2, requests_total: 65, requests_mean: 10.8, page_views_mean: 10, steps_mean: 11, elapsed_mean: 70 },
             Modified: { planned: 6, completed: 6, failed: 0, evidence_supported_passes: 1, strict_passes: 1, requests_total: 46, requests_mean: 7.7, page_views_mean: 7, steps_mean: 8, elapsed_mean: 33 } } };
const json = (body: unknown, ok = true) => ({ ok, status: ok ? 200 : 409, json: async () => body });
function server(routes: (url: string, init?: RequestInit) => unknown) {
  const mock = vi.fn(async (url: string, init?: RequestInit) => { const r = routes(url, init); return r && typeof r === 'object' && 'ok' in (r as object) ? r : json(r); });
  vi.stubGlobal('fetch', mock); return mock;
}
async function mount(props = {}) {
  const host = document.createElement('div'); document.body.append(host);
  await act(async () => { createRoot(host).render(<HostedEvaluation onOpen={() => {}} {...props} />); });
  for (let i = 0; i < 4; i++) await act(async () => { await new Promise(r => setTimeout(r, 0)); });
  return host;
}
const button = (host: HTMLElement, text: string) => [...host.querySelectorAll('button')].find(b => b.textContent?.includes(text)) as HTMLButtonElement;

it('shows the armed frozen suite and posts only the repetitions with the operator token', async () => {
  const f = server((url, init) => init?.method === 'POST' ? { id: ID, state: 'reserved', repetitions: 1 } : url.endsWith('/config') ? config() : url.endsWith('/jobs') ? [] : { ...job, state: 'running' });
  const host = await mount();
  const t = host.textContent ?? '';
  expect(t).toContain('Larkspur Community College'); expect(t).toContain('Frozen suite larkspur-core v2 (owner-approved, 6 tasks)'); expect(t).toContain('2 of 2 launches left');
  expect(t).toContain('12 agent runs'); expect(t).toContain('reserves US$7.44');
  const input = host.querySelector('#ws-operator-token') as HTMLInputElement;
  await act(async () => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!; set.call(input, 't'.repeat(32)); input.dispatchEvent(new Event('input', { bubbles: true })); });
  await act(async () => { button(host, 'Run evaluation').click(); });
  const post = f.mock.calls.find(c => (c[1] as RequestInit | undefined)?.method === 'POST')!;
  expect(post[0]).toBe('/api/ironbark/jobs');
  expect(JSON.parse(String((post[1] as RequestInit).body))).toEqual({ repetitions: 1 });                 // the launch contract is unchanged
  expect(((post[1] as RequestInit).headers as Record<string, string>).Authorization).toBe('Bearer ' + 't'.repeat(32));
});

it('explains when nothing is armed and keeps Run disabled', async () => {
  server(url => url.endsWith('/config') ? config({ available: false, evaluation: null, repetitions: [], reason: 'not_armed' }) : []);
  const host = await mount();
  expect(host.textContent).toContain('No evaluation is armed');
  expect(button(host, 'Run evaluation').disabled).toBe(true);
});

it('shows a completed Stage B evaluation as the six-dimension readiness report', async () => {
  server(url => url.endsWith('/config') ? config() : url.endsWith('/jobs') ? [] : url.includes('/api/lifecycle/evaluations/') ? { ...EV, id: ID } : job);
  const host = await mount({ initialJob: ID });
  for (let i = 0; i < 4; i++) await act(async () => { await new Promise(r => setTimeout(r, 0)); });
  const t = host.textContent ?? '';
  expect(button(host, 'Readiness report')).toBeTruthy();
  expect(button(host, 'Insights')).toBeFalsy();
  for (const d of ['Task success', 'Navigation efficiency', 'Evidence quality', 'Information accessibility', 'Agent reliability', 'Coverage']) expect(t).toContain(d);
  expect(t).toContain('v1 official'); expect(t).toContain('v2 post-hoc');
  expect(host.querySelector(`a[href="#/reports/${ID}/tasks/1"]`)).not.toBeNull();                       // the trace comparison
});

// M9: execution outcome vs report publication vs the preserved job record.
const exec = { state: 'completed', trials_planned: 12, trials_completed: 12, trials_failed: 0, trials_void: 0 };
const NOTE = 'Execution completed: 12/12 agent runs finished. The job record reads “failed” because, when the run finished, its report did not pass the publication check of that release, which treated a completed run with an unpublishable report as failed. The report has since passed the current publication check and is available. The original record is kept unchanged.';

it('shows a completed run with a preserved "failed" record as completed, explains the record and serves the report', async () => {
  server(url => url.endsWith('/config') ? config() : url.endsWith('/jobs') ? [] : url.includes('/api/lifecycle/evaluations/') ? { ...EV, id: ID, source: { kind: 'launched', job: ID, state: 'completed' } }
    : { ...job, state: 'failed', execution: exec, report_status: { state: 'available' }, record_note: NOTE });
  const host = await mount({ initialJob: ID });
  for (let i = 0; i < 4; i++) await act(async () => { await new Promise(r => setTimeout(r, 0)); });
  const status = host.querySelector('.ws-status')!.textContent ?? '';
  expect(status).toContain('Completed'); expect(status).toContain('Job record: failed');
  expect(host.textContent).toContain('The original record is kept unchanged');
  expect(host.textContent).not.toContain('it has no report');
  await act(async () => { button(host, 'Readiness report').click(); });
  for (let i = 0; i < 4; i++) await act(async () => { await new Promise(r => setTimeout(r, 0)); });
  expect(host.textContent).toContain('Task success');
  expect(host.textContent).toContain('Live run launched in this product');
});

it('keeps a withheld report withheld while showing that every agent run finished', async () => {
  const f = server(url => url.endsWith('/config') ? config() : url.endsWith('/jobs') ? [] : url.includes('/api/lifecycle/evaluations/') ? json({ detail: 'withheld' }, false)
    : { ...job, state: 'completed', report: null, execution: exec, report_status: { state: 'withheld', detail: 'x' }, record_note: null });
  const host = await mount({ initialJob: ID });
  await act(async () => { button(host, 'Readiness report').click(); });
  for (let i = 0; i < 4; i++) await act(async () => { await new Promise(r => setTimeout(r, 0)); });
  expect(host.textContent).toContain('the readiness report is withheld');
  expect(host.textContent).toContain('only the readiness report is withheld');
  expect(f.mock.calls.some(c => String(c[0]).includes('/api/lifecycle/evaluations/'))).toBe(false);   // never requested
});
