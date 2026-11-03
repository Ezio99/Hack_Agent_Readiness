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

it('operator diagnostics separate programme expenditure, the hosted ceiling and separate budgets, beside launch authority', async () => {
  const programme = { spent_usd: 19.418057, spent_aud: 29.13, recorded_usd: 18.786306, not_recorded: [{ job: ID, usd: 0.631751 }], held_usd: 0, ceiling_available_usd: 10.588249,
    worst_case_usd: 30.006306, worst_case_aud: 45.01, limit_aud: 50, rate_aud_per_usd: 1.5, within_limit: true, ledger_entries: 21, ledger_problems: 0, basis: 'actual' };
  const spending = { ceiling: 21.956, settled: 0.631751, outstanding: 10.736, committed: 11.367751, available: 10.588249, released: 3.108249, settled_jobs: 1, unsettled_jobs: 3,
    basis: 'calculated from provider-reported usage; not a bill', global: null, budgets: [], charged_to: null, programme };
  const pool = { ...armed, variants: ['original', 'improved'], launches: { max: 3, used: 1, left: 2 }, options: [{ repetitions: 1, trials: 6, reservation_usd: 3.74, manifest_sha256: 'd'.repeat(64), available: true, fits_hosted_ceiling: true }] };
  const hist = [{ id: ID, engine: 'stage-b', state: 'completed', repetitions: 1, mode: 'live', created_at: 1, summary: job.summary, cost_usd: 0.631751, reserved_usd: 3.74, budget: null, arm_display: { Original: 'Original', Modified: 'Improved' } }];
  server(url => url.endsWith('/config') ? config({ evaluation: pool, spending }) : url.endsWith('/jobs') ? hist : job);
  const host = await mount();
  const sec = (name: string) => host.querySelector(`.ws-budget section[aria-label="${name}"]`)!.textContent!;
  for (const x of ['Spent to dateA$29.13', 'US$19.42 of verified actual costs, including 1 hosted run not yet in the programme ledger', 'Worst caseA$45.01', 'of the A$50 limit'])
    expect(sec('Programme expenditure')).toContain(x);
  for (const x of ['a safety cap for programme runs, not spending', 'Settled actual costUS$0.63', '1 evaluation', 'Held for unsettled runsUS$10.74', '3 evaluations', 'AvailableUS$10.59', 'of the US$21.96 ceiling'])
    expect(sec('Hosted admission ceiling')).toContain(x);
  expect(sec('Separate budgets')).toContain('None open');
  for (const x of ['Authorised2 of 3 left', 'charged to the A$50 programme (hosted ceiling); each reserves US$3.74; the ceiling covers 2', 'Cost per completed evaluationUS$0.63'])
    expect(sec('Launch authority')).toContain(x);
  expect(host.querySelector('.ws-budget')!.textContent).not.toContain('hosted budget');                 // the ceiling is never called a budget
  expect(host.querySelector('.history-table')!.textContent).toContain('US$0.63 programme');
});

it('a launch charged to a separate budget shows that budget and its own capacity, never the programme or the ceiling', async () => {
  const b = { id: 'ar-a20-2026-11', limit_aud: 20, rate_aud_per_usd: 1.5, spent_aud: 0.947627, outstanding_aud: 5.61, available_aud: 13.442373, spent_usd: 0.631751, outstanding_usd: 3.74,
    available_usd: 8.961582, jobs: 2, settled_jobs: 1, allocations: 1, open_allocations: 0 };
  const spending = { ceiling: 21.956, settled: 0.631751, outstanding: 10.736, committed: 11.367751, available: 10.588249, released: 3.108249, settled_jobs: 1, unsettled_jobs: 3,
    basis: 'not a bill', global: { cap_usd: 35.289333, committed_usd: 15.739502, available_usd: 19.549831 }, budgets: [b], charged_to: 'ar-a20-2026-11', programme: null };
  const pool = { ...armed, budget: 'ar-a20-2026-11', launches: { max: 3, used: 2, left: 1 }, options: [{ repetitions: 1, trials: 6, reservation_usd: 3.74, manifest_sha256: 'd'.repeat(64), available: true, fits_hosted_ceiling: true }] };
  const hist = [{ id: ID, engine: 'stage-b', state: 'completed', repetitions: 1, mode: 'live', created_at: 1, summary: job.summary, cost_usd: 0.631751, reserved_usd: 3.74, budget: 'ar-a20-2026-11', arm_display: { Original: 'Original', Modified: 'Improved' } }];
  server(url => url.endsWith('/config') ? config({ evaluation: pool, spending }) : url.endsWith('/jobs') ? hist : job);
  const host = await mount();
  const sec = (name: string) => host.querySelector(`.ws-budget section[aria-label="${name}"]`)!.textContent!;
  expect(sec('Separate budgets')).toContain('ar-a20-2026-11A$13.44 available');
  expect(sec('Separate budgets')).toContain('of A$20.00 · spent A$0.95 · held A$5.61 · 2 runs, 1 off-host allocation');
  expect(sec('Launch authority')).toContain('charged to the separate budget ar-a20-2026-11; each reserves US$3.74; the budget covers 2');
  expect(host.querySelector('.ws-budget section[aria-label="Programme expenditure"]')).toBeNull();
  expect(host.querySelector('.history-table')!.textContent).toContain('US$0.63 ar-a20-2026-11');
});

// ------------------------------------------------------------------------------------------------ one-click operator evaluations (A$20 budget)
const B = 'ar-a20-2026-11';
const budgetFig = { id: B, limit_aud: 20, rate_aud_per_usd: 1.5, spent_aud: 0.947633, outstanding_aud: 0, available_aud: 19.052367, spent_usd: 0.631755, outstanding_usd: 0,
  available_usd: 12.701578, jobs: 1, settled_jobs: 1, allocations: 0, open_allocations: 0 };
const opSpending = { ceiling: 21.956, settled: 0.631751, outstanding: 10.736, committed: 11.367751, available: 10.588249, released: 3.108249, settled_jobs: 1, unsettled_jobs: 3,
  basis: 'not a bill', global: { cap_usd: 35.289333, committed_usd: 11.999506, available_usd: 23.289827 }, budgets: [budgetFig], charged_to: null, programme: null };
const budgetEval = { budget: B, mode: 'paid', site: 'larkspur', suite: 'larkspur-core v3', variants: ['original', 'improved'], launches_so_far: 1, available_usd: 12.701578,
  options: [{ repetitions: 1, trials: 6, reservation_usd: 3.74, covered: 3, available: true }] };
const opConfig = (over = {}) => config({ judge_access: true, launch: { authorized: true, ready: true, reason: null, detail: null, launches_left: 2 }, spending: opSpending,
  operator: { signed_in: true, sign_in_available: true }, budget_evaluation: budgetEval, budget_tasks: tasks,
  budget_launch: { authorized: true, ready: true, reason: null, detail: null }, ...over });

it('a signed-in operator runs an evaluation with one click: no token in the page, a CSRF header and one idempotency key per click', async () => {
  const f = server((url, init) => url.endsWith('/config') ? opConfig() : url.endsWith('/jobs') && init?.method === 'POST' ? { id: ID, state: 'reserved', repetitions: 1 }
    : url.endsWith('/jobs') ? [] : { ...job, accounting: { reserved_usd: 3.74, cost_usd: 0.631755, settled: true, budget: B } });
  const host = await mount();
  expect(host.querySelector('#ws-operator-token')).toBeNull();                                   // no token field for the signed-in operator
  expect(host.querySelector('.ws-operator-budget')!.textContent).toContain('A$19.05 of A$20.00 left in ar-a20-2026-11');
  expect(host.querySelector('#ws-run-note')!.textContent).toContain('Each run reserves up to A$5.61 until it finishes, then only its actual cost counts · the budget covers 3 more runs now');
  expect(host.querySelector('.ws-target')!.textContent).toContain('runs while the budget lasts (no launch limit)');
  const run = button(host, 'Run evaluation');
  expect(run.disabled).toBe(false);
  await act(async () => { run.click(); run.click(); });                                         // a double-click
  for (let i = 0; i < 4; i++) await act(async () => { await new Promise(r => setTimeout(r, 0)); });
  const posts = f.mock.calls.filter(c => (c[1] as RequestInit | undefined)?.method === 'POST');
  expect(posts.length).toBe(1);
  const h = (posts[0][1] as RequestInit).headers as Record<string, string>;
  expect(h['X-Agent-Readiness']).toBe('1');
  expect(h['Idempotency-Key']).toMatch(/^[A-Za-z0-9_-]{16,64}$/);
  expect(h.Authorization).toBeUndefined();
  expect(JSON.parse((posts[0][1] as RequestInit).body as string)).toEqual({ repetitions: 1 });
  expect(host.querySelector('.ws-cost')!.textContent).toBe(`Actual cost US$0.63 · ${B}`);
});

it('the operator signs in once; the token is sent once, then cleared and never stored', async () => {
  let signedIn = false;
  const f = server((url, init) => url.endsWith('/api/operator/session') && init?.method === 'POST' ? (signedIn = true, { signed_in: true, expires_at: 9e9 })
    : url.endsWith('/config') ? opConfig({ operator: { signed_in: signedIn, sign_in_available: true } }) : url.endsWith('/jobs') ? [] : job);
  const host = await mount();
  expect(host.querySelector('.ws-signin')).not.toBeNull();
  const input = host.querySelector('#ws-signin-token') as HTMLInputElement;
  const secret = 'o'.repeat(32);
  await act(async () => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!; set.call(input, secret); input.dispatchEvent(new Event('input', { bubbles: true })); });
  await act(async () => { (host.querySelector('.ws-signin form') as HTMLFormElement).requestSubmit(); });
  for (let i = 0; i < 4; i++) await act(async () => { await new Promise(r => setTimeout(r, 0)); });
  const login = f.mock.calls.find(c => String(c[0]).endsWith('/api/operator/session'))!;
  expect(((login[1] as RequestInit).headers as Record<string, string>).Authorization).toBe(`Bearer ${secret}`);
  expect(((login[1] as RequestInit).headers as Record<string, string>)['X-Agent-Readiness']).toBe('1');
  expect(host.querySelector('.ws-operator-who')!.textContent).toContain('Signed in as operator');
  expect(host.innerHTML).not.toContain(secret);
  expect(JSON.stringify({ ...localStorage })).not.toContain(secret);
  expect(JSON.stringify({ ...sessionStorage })).not.toContain(secret);
});

it('the run button explains a refusal when the budget cannot cover another run', async () => {
  server(url => url.endsWith('/config') ? opConfig({ budget_launch: { authorized: false, ready: false, reason: 'budget_exhausted', detail: 'The remaining budget does not cover the maximum cost of another run.' } })
    : url.endsWith('/jobs') ? [] : job);
  const host = await mount();
  expect(button(host, 'Run evaluation').disabled).toBe(true);
  expect(host.querySelector('#ws-run-note')!.textContent).toContain('The remaining budget does not cover the maximum cost of another run.');
});
