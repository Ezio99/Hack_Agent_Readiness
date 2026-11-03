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
  expect(t).toContain('Larkspur Community College'); expect(t).toContain('6 customer tasks · Original vs Modified site · 2 of 2 live runs left');
  expect(t).toContain('12 browser agents, one per task on each site'); expect(t).not.toContain('reserves US$');                   // judge-facing: no reservation figures
  const input = host.querySelector('#ws-operator-token') as HTMLInputElement;
  await act(async () => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!; set.call(input, 't'.repeat(32)); input.dispatchEvent(new Event('input', { bubbles: true })); });
  await act(async () => { button(host, 'Run live evaluation').click(); });
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
  for (const d of ['Task success', 'Navigation efficiency', 'Evidence', 'Information accessibility', 'Agent reliability', 'Coverage', 'What slowed the agents down']) expect(t).toContain(d);
  expect(t).toContain('Exact match'); expect(t).toContain('Correct');
  expect(t).not.toContain('post-hoc');
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
  expect(host.textContent).toContain('Live run in this product');
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

// M9 final sprint: worker health, launch authorisation and a running evaluation are distinct; the intro describes the product, not Ironbark.
const used = { ...armed, launches: { max: 1, used: 1, left: 0 }, options: armed.options.map(o => ({ ...o, available: false })) };
const exhausted = config({ evaluation: used, available: false, repetitions: [], reason: 'launches_exhausted', remaining_repetitions: 0,
  launch: { authorized: false, ready: false, reason: 'launches_exhausted', detail: 'All live runs available for this demonstration have been used.', launches_left: 0 } });

it('does not call the worker "available" when the authorised launch has been used', async () => {
  server(url => url.endsWith('/config') ? exhausted : []);
  const host = await mount();
  const banner = host.querySelector('.ws-worker')!;
  expect(banner.textContent).toContain('Worker ready · no launch authorised');
  expect(banner.textContent).toContain('All live runs available for this demonstration have been used');
  expect(banner.textContent).not.toContain('Ready to start a new evaluation');
  expect(banner.className).toContain('blocked');
  expect(button(host, 'Run live evaluation').disabled).toBe(true);
  expect(host.querySelector('#ws-run-note')!.textContent).toContain('All live runs available');
});

it('says "Worker available" only when a launch is authorised', async () => {
  server(url => url.endsWith('/config') ? config({ launch: { authorized: true, ready: true, reason: null, detail: null, launches_left: 2 } }) : []);
  const host = await mount();
  expect(host.querySelector('.ws-worker')!.textContent).toContain('Worker available');
});

it('describes the product plainly and says the improved websites were changed by hand from the report', async () => {
  server(url => url.endsWith('/config') ? config({ evaluation: null, available: false, repetitions: [], tasks: [], reason: 'not_armed',
    launch: { authorized: false, ready: false, reason: 'not_armed', detail: 'No evaluation is authorised. The owner authorises one at the server terminal.', launches_left: null } }) : []);
  const host = await mount();
  const intro = host.querySelector('.ws-intro')!.textContent ?? '';
  expect(intro).toContain('Fresh Muse Spark browser agents do real customer tasks on two versions of a website');
  expect(intro).toContain('what to change');
  expect(intro).toContain('the improvements were made by hand from the report');
  for (const old of ['Ironbark', 'four frozen tasks', 'eight new agent runs', '4 owner-approved']) expect(intro).not.toContain(old);
  expect(host.textContent).not.toContain('Ironbark Hire');
});

it('an Original vs Improved pool is named as such in the compose panel, the task grid and the live agent view', async () => {
  const improved = { ...armed, suite: 'larkspur-core v3', frozen_suite: 'larkspur-core@v3', variants: ['original', 'improved'], launches: { max: 4, used: 1, left: 3 },
    options: [{ repetitions: 1, trials: 4, reservation_usd: 2.508, manifest_sha256: 'd'.repeat(64), available: true, fits_hosted_ceiling: true }] };
  const two = tasks.slice(0, 2);
  const j = { ...job, arm_display: { Original: 'Original', Modified: 'Improved' }, reps: [{ index: 1, state: 'completed', assessment: null, tasks: two.flatMap((t: any) => [row('Original', t.task), row('Modified', t.task)]) }] };
  server(url => url.endsWith('/config') ? config({ evaluation: improved, tasks: two, judge_access: true, launch: { authorized: true, ready: true, reason: null, detail: null, launches_left: 3 } })
    : url.endsWith('/jobs') ? [] : url.includes('/live') || url.includes('/trials/') ? { active: false, trial: null } : url.includes('/api/lifecycle/') ? json({ detail: 'unavailable' }, false) : j);
  let host = await mount();
  const compose = host.querySelector('.ws-compose')!.textContent!;
  expect(compose).toContain('Original vs Improved site'); expect(compose).toContain('3 of 4 live runs left');
  for (const t of two) expect(compose).toContain(t.question);
  expect(host.querySelector('.ws-intro')!.textContent).toContain('The Improved site applies every recommendation');
  document.body.innerHTML = '';
  host = await mount({ initialJob: ID });
  await act(async () => { button(host, 'Agent runs').click(); });
  const head = [...host.querySelectorAll('.ws-grid thead th')].map(th => th.textContent);
  expect(head).toEqual(['Task', 'Original', 'Improved']);
  expect(host.querySelector('.ws-grid .swatch.i')).not.toBeNull();
});

// M9: judges start the armed live evaluation with a separate, launch-only access code.
const typeCode = async (host: HTMLElement, code: string) => {
  const input = host.querySelector('#ws-operator-token') as HTMLInputElement;
  await act(async () => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!; set.call(input, code); input.dispatchEvent(new Event('input', { bubbles: true })); });
};
const judgeConfig = () => config({ judge_access: true, launch: { authorized: true, ready: true, reason: null, detail: null, launches_left: 2 } });

it('judges see an access-code field and "Run live evaluation", which posts only the repetitions with their code', async () => {
  const f = server((url, init) => init?.method === 'POST' ? { id: ID, state: 'reserved', repetitions: 1 } : url.endsWith('/config') ? judgeConfig() : url.endsWith('/jobs') ? [] : { ...job, state: 'running' });
  const host = await mount();
  expect(host.querySelector('label[for="ws-operator-token"]')!.textContent).toContain('Access code');
  expect((host.querySelector('#ws-operator-token') as HTMLInputElement).placeholder).toBe('Paste your access code');
  expect(host.querySelector('#ws-run-note')!.textContent).toContain('Enter your access code to start a live evaluation');
  expect(host.querySelector('.ws-worker')!.textContent).toContain('Ready to start a live evaluation');
  expect(host.querySelector('.ws-worker')!.textContent).not.toContain('Muse Spark run');
  const code = 'judge-access-code-0123456789abcdef';
  await typeCode(host, code);
  await act(async () => { button(host, 'Run live evaluation').click(); });
  const post = f.mock.calls.find(c => (c[1] as RequestInit | undefined)?.method === 'POST')!;
  expect(post[0]).toBe('/api/ironbark/jobs');
  expect(JSON.parse(String((post[1] as RequestInit).body))).toEqual({ repetitions: 1 });
  expect(((post[1] as RequestInit).headers as Record<string, string>).Authorization).toBe('Bearer ' + code);
  expect(f.mock.calls.every(c => !String(c[0]).includes(code))).toBe(true);                               // never in a URL
});

it('a refused access code gets a judge-worded message and is cleared', async () => {
  server((url, init) => init?.method === 'POST' ? { ok: false, status: 403, json: async () => ({ detail: 'Starting a live evaluation needs a valid access code' }) } : url.endsWith('/config') ? judgeConfig() : []);
  const host = await mount();
  await typeCode(host, 'wrong-code-wrong-code-wrong-code');
  await act(async () => { button(host, 'Run live evaluation').click(); });
  for (let i = 0; i < 3; i++) await act(async () => { await new Promise(r => setTimeout(r, 0)); });
  expect(host.querySelector('[role="alert"]')!.textContent).toContain('That access code was not accepted');
  expect((host.querySelector('#ws-operator-token') as HTMLInputElement).value).toBe('');
});

it('history shows each Stage B evaluation\'s own number of agent runs (not the retired engine\'s 8)', async () => {
  const hist = [{ id: ID, engine: 'stage-b', runs_per_repetition: 4, state: 'completed', execution_state: 'completed', report_state: 'available', repetitions: 1, mode: 'live', created_at: 1, summary: job.summary },
                { id: 'eval-' + 'd'.repeat(32), state: 'completed', repetitions: 1, mode: 'live', created_at: 0, summary: job.summary }];
  server(url => url.endsWith('/config') ? config() : url.endsWith('/jobs') ? hist : job);
  const host = await mount();
  const rows = [...host.querySelectorAll('tbody tr')].map(r => r.textContent ?? '');
  expect(rows.some(r => r.includes('1 × 4'))).toBe(true);
  expect(rows.some(r => r.includes('1 × 8'))).toBe(true);                                                      // a historical Ironbark job
});

// Final presentation fix: the real production run eval-c04fdb10 (Original vs Improved). The grid reads like the readiness report.
const C04_STATUS = JSON.parse(readFileSync(resolve(__dirname, '../../fixtures/live/eval-c04fdb10-status.json'), 'utf8'));
const C04_REPORT = JSON.parse(readFileSync(resolve(__dirname, '../../fixtures/live/eval-c04fdb10-report.json'), 'utf8'));
it('the Agent runs grid shows Correct / Not correct as the report counts it, with exact match kept as its own line (production run)', async () => {
  server(url => url.endsWith('/config') ? config({ evaluation: { ...armed, variants: ['original', 'improved'] }, tasks: tasks.slice(0, 3) })
    : url.endsWith('/jobs') ? [] : url.includes('/live') || url.includes('/trials/') ? { active: false, trial: null }
    : url.includes('/api/lifecycle/') ? C04_REPORT : C04_STATUS);
  const host = await mount({ initialJob: C04_STATUS.id });
  await act(async () => { button(host, 'Agent runs').click(); });
  const head = [...host.querySelectorAll('.ws-grid thead th')].map(th => th.textContent);
  expect(head).toEqual(['Task', 'Original', 'Improved']);
  const rows = [...host.querySelectorAll('.ws-grid tbody tr')].map(r => [...r.querySelectorAll('td')].map(td => td.querySelector('strong')!.textContent));
  expect(rows).toEqual([['Not correct', 'Correct'], ['Not correct', 'Correct'], ['Not correct', 'Correct']]);
  expect(host.querySelector('.ws-grid')!.textContent).not.toContain('Not passed');
  expect([...host.querySelectorAll('.ws-exact')].map(x => x.textContent)).toEqual(Array(6).fill('Exact match: no'));
  expect(host.querySelector('.ws-grid')!.textContent).toContain('2 requests');
});
