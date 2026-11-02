// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { HostedEvaluation, type Job } from './HostedEvaluation';
import { TrialView, type Trial } from './LiveAgent';
import { Insights } from './Insights';
import { History, type HistoryItem } from './History';
import { Analytics, perTask } from './Analytics';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); document.body.innerHTML = ''; });

async function mount(node: React.ReactNode) {
  const host = document.createElement('div'); document.body.append(host); const root = createRoot(host);
  await act(async () => { root.render(node); }); await act(async () => {});
  return host;
}
const json = (b: unknown, ok = true) => ({ ok, json: async () => b });
const arm = (o = {}) => ({ planned: 4, completed: 0, failed: 0, evidence_supported_passes: 0, strict_passes: 0, requests_total: 0, requests_mean: null, page_views_mean: null, steps_mean: null, elapsed_mean: null, ...o });
const row = (a: 'Original' | 'Modified', task: number, outcome: string, requests: number) => ({ arm: a, task, state: 'completed', outcome, requests, page_views: requests, steps: requests, elapsed_seconds: 10 });
const job = (over: Partial<Job> = {}): Job => ({ id: 'eval-' + 'a'.repeat(32), state: 'completed', mode: 'live', repetitions: 2, created_at: 1, started_at: 1, finished_at: 100,
  reps: [1, 2].map(i => ({ index: i, state: 'completed', assessment: null, tasks: [row('Original', 1, 'not_passed', 12 + i), row('Modified', 1, 'evidence_supported_pass', 5 + i)] })),
  summary: { Original: arm({ completed: 2 }), Modified: arm({ completed: 2, evidence_supported_passes: 2 }) }, ...over });

it('operator-only access: watching works, running needs a token sent as a bearer header', async () => {
  const f = vi.fn(async (url: string, init?: RequestInit) => init?.method === 'POST' ? json({ id: 'eval-' + 'b'.repeat(32) }) :
    url.endsWith('/config') ? json({ available: true, mode: 'live', access: 'operator', repetitions: [1, 3, 5], model: 'm', agent_profile: 'p', tasks: [], remaining_repetitions: 9, active: null }) :
    url.endsWith('/jobs') ? json([]) : url.endsWith('/live') ? json({ active: true, trial: null }) : json(job({ state: 'running' })));
  vi.stubGlobal('fetch', f);
  const host = await mount(<HostedEvaluation onOpen={() => {}} />);
  const run = [...host.querySelectorAll('button')].find(b => b.textContent === 'Run evaluation') as HTMLButtonElement;
  expect(run.disabled).toBe(true);
  expect(host.textContent).toContain('not open to the public yet');
  const input = host.querySelector('input[aria-label="Operator token"]') as HTMLInputElement;
  await act(async () => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!; set.call(input, 'x'.repeat(32)); input.dispatchEvent(new Event('input', { bubbles: true })); });
  expect(run.disabled).toBe(false);
  await act(async () => { run.click(); });
  const post = f.mock.calls.find(c => c[1]?.method === 'POST')!;
  expect((post[1]!.headers as Record<string, string>).Authorization).toBe('Bearer ' + 'x'.repeat(32));
});

it('renders real telemetry: screenshot URL, actions, goals, errors and the final answer', async () => {
  const trial: Trial = { repetition: 1, arm: 'modified', task: 2, state: 'completed', question: 'Which machine?', steps: [
    { step: 1, path: '/hire', title: null, screenshot: 'step-001.png', assessment: 'Start', memory: 'Need deposits', goal: 'Open the list', actions: [{ name: 'Click', target: '“Hire equipment” · /hire' }], error: null, done: false },
    { step: 2, path: '/hire/lift', title: null, screenshot: null, assessment: null, memory: null, goal: null, actions: [{ name: 'Answer', target: 'Scissor lift' }], error: 'net::ERR', done: true }],
    current: null, errors: [] };
  const host = await mount(<TrialView jobId={'eval-' + 'c'.repeat(32)} trial={trial} live={false} scripted={false} />);
  expect(host.textContent).toContain('Hire equipment');
  expect(host.textContent).toContain('Final answer: Scissor lift');
  expect(host.textContent).toContain('⚠ net::ERR');
  await act(async () => { (host.querySelectorAll('.agent-steps li button')[0] as HTMLButtonElement).click(); });
  expect(host.querySelector('img')!.getAttribute('src')).toBe(`/api/ironbark/jobs/eval-${'c'.repeat(32)}/repetitions/1/trials/modified/2/screenshots/step-001.png`);
  expect(host.textContent).toContain('Goal: Open the list');
  const scripted = await mount(<TrialView jobId="eval-x" trial={trial} live={false} scripted />);
  expect(scripted.textContent).toContain('scripted rehearsal agent (not a model)');
});

it('insights keep observations and unmeasured suggestions apart', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => json({ state: 'ok', mode: 'rehearsal', final: true, runs: { Original: 4, Modified: 4 }, method: 'Rules.',
    findings: [{ id: 'detail-dependency', severity: 'high', title: 'Comparison facts are only on item detail pages', observed: 'Opened 4 pages' }],
    suggestions: [{ for: 'detail-dependency', text: 'Show attributes on cards', status: 'tested in this evaluation' }, { for: 'x', text: 'Sort by deposit', status: 'not measured' }] })));
  const host = await mount(<Insights jobId="eval-x" active={false} />);
  expect(host.textContent).toContain('describe the script, not Muse Spark');
  expect(host.textContent).toContain('Tested here as “Modified”');
  expect(host.textContent).toContain('Not measured');
  expect(host.textContent).toContain('Proposals, not measured results');
});

it('history compares two evaluations and warns when modes differ', async () => {
  const s = { Original: arm({ completed: 4, evidence_supported_passes: 1, requests_mean: 12 }), Modified: arm({ completed: 4, evidence_supported_passes: 3, requests_mean: 6 }) };
  const items: HistoryItem[] = [{ id: 'eval-' + '1'.repeat(32), state: 'completed', repetitions: 1, mode: 'live', created_at: 1, summary: s },
    { id: 'eval-' + '2'.repeat(32), state: 'completed', repetitions: 1, mode: 'rehearsal', created_at: 2, summary: s }];
  const host = await mount(<History items={items} current={null} open={() => {}} />);
  for (const box of host.querySelectorAll('input[type=checkbox]')) await act(async () => { (box as HTMLInputElement).click(); });
  expect(host.querySelectorAll('.history-compare article')).toHaveLength(2);
  expect(host.textContent).toContain('rehearsal results are not comparable');
});

it('analytics aggregate per task across repetitions with a table view', async () => {
  const j = job();
  const t = perTask(j);
  expect(t[1].Original.requests).toEqual([13, 14]);
  expect(t[1].Modified.supported).toBe(2);
  const host = await mount(<Analytics job={j} questions={{ 1: 'Q1' }} />);
  expect(host.querySelectorAll('svg.viz')).toHaveLength(2);
  expect(host.textContent).toContain('Variation across repetitions');
  await act(async () => { ([...host.querySelectorAll('button')].find(b => b.textContent === 'Show as table') as HTMLButtonElement).click(); });
  expect(host.textContent).toContain('13.5 · 13–14');
});
