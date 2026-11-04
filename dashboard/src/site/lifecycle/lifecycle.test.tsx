// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterEach, expect, it, vi, beforeAll, afterAll } from 'vitest';
import { Lifecycle } from './Lifecycle';
import { ReportPage } from './Report';
import { useLoad } from './parts';
import { parse } from '../router';
import { AFTER, BEFORE, LIVE } from '../showcase';
import { PUBLIC_SCOPE } from '../../lib/lifecycleApi';
// These tests exercise the mechanics with fixtures of earlier evaluations: the public scope (final Larkspur experiment only) is lifted here and
// tested on its own in public-scope.test.tsx.
const SCOPE = PUBLIC_SCOPE.versions; beforeAll(() => { PUBLIC_SCOPE.versions = null; }); afterAll(() => { PUBLIC_SCOPE.versions = SCOPE; });
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { vi.unstubAllGlobals(); document.body.innerHTML = ''; window.location.hash = ''; });

// The real sanitized M7 dataset (committed), served as the API would serve it: the UI is tested on the recorded data, not on invented fixtures.
const DS = resolve(__dirname, '../../../../datasets/lifecycle/m7-larkspur-browser-1/v1');
const read = (p: string) => JSON.parse(readFileSync(resolve(DS, p), 'utf8'));
const EV = { ...read('evaluation.json'), source: { kind: 'dataset', id: 'm7-larkspur-browser-1', version: 1, built_at: 'x', description: 'd', runs: ['r'] } };
const json = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body });
const overview = { steps: [{ id: 'evaluate', label: 'E', available: true, action_available: false, detail: 'Launch from the workspace.' }],
  onboarding: { available: false, reason: 'x', detail: 'Onboarding from a URL is not available.' }, approval: { available: false, reason: 'owner_authentication_not_configured', detail: 'Approval needs a verified owner identity.' },
  sources: { datasets: [], store: false, jobs: false }, evaluation: null as unknown };

function server(routes: Record<string, unknown>) {
  const f = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === 'POST') return json({ detail: { code: 'paid_launch_not_authorized', message: 'refused' } }, 403);
    const hit = Object.entries(routes).find(([k]) => url.endsWith(k));
    return hit ? json(hit[1]) : json({ detail: 'Not found' }, 404);
  });
  vi.stubGlobal('fetch', f);
  return f;
}
async function mount(node: React.ReactNode) {
  const host = document.createElement('div'); document.body.append(host);
  await act(async () => { createRoot(host).render(node); });
  for (let i = 0; i < 4; i++) await act(async () => { await new Promise(r => setTimeout(r, 0)); });
  return host;
}

it('routes the lifecycle steps, suites and reports (hosted evaluations keep #/run/eval-…)', () => {
  expect(parse('#/lifecycle')).toEqual({ name: 'lifecycle', step: undefined });
  expect(parse('#/lifecycle/review')).toEqual({ name: 'lifecycle', step: 'review' });
  expect(parse('#/lifecycle/compare')).toEqual({ name: 'lifecycle', step: 'compare' });
  expect(parse('#/lifecycle/suites/' + 'a'.repeat(64))).toEqual({ name: 'lifecycle', step: 'review', suite: 'a'.repeat(64) });
  expect(parse('#/reports/eval-' + 'b'.repeat(32))).toEqual({ name: 'report', id: 'eval-' + 'b'.repeat(32), task: undefined });
  expect(parse('#/reports/m7-larkspur-browser-1/tasks/1')).toEqual({ name: 'report', id: 'm7-larkspur-browser-1', task: 1 });
  expect(parse('#/lifecycle/nope').name).toBe('home');
  expect(parse('#/run').name).toBe('run');                                      // the hosted workspace URLs are unchanged
});

it('renders the M7 report in plain product language: correct answers and exact matches, six dimensions, recommendations, no research framing', async () => {
  server({ '/api/lifecycle/evaluations/m7-larkspur-browser-1': EV });
  const host = await mount(<ReportPage id="m7-larkspur-browser-1" />);
  const t = host.textContent ?? '';
  expect(t).toContain('Live · Meta Muse Spark');
  const row = (k: string) => [...host.querySelectorAll('tr')].find(r => r.textContent?.startsWith(k))!.textContent!;
  expect(row('Correct answers')).toContain('3/6'); expect(row('Correct answers')).toContain('4/6');            // the recorded grades (v2)
  expect(row('Exact match')).toContain('2/6'); expect(row('Exact match')).toContain('1/6');                    // the recorded official grades (v1), unchanged
  expect(t).toContain('named 1 of 5'); expect(t).toContain('named 5 of 5');
  expect(t).toContain('US$1.5207');
  for (const d of ['Task success', 'Navigation efficiency', 'Evidence', 'Information accessibility', 'Agent reliability', 'What slowed the agents down, and what to change']) expect(t).toContain(d);
  expect(t).toContain('Likely causes and what to change'); expect(t).toContain('Observations');
  for (const s of ['post-hoc', 'prospective', 'xploratory', 'no statistical power', 'p =', 'Retrospective', 'grade of record', 'no composite']) expect(t).not.toContain(s);
  expect(host.querySelector('a[href="#/reports/m7-larkspur-browser-1/tasks/1"]')).not.toBeNull();
});

it('compares the availability task side by side from real screenshots and timelines', async () => {
  const o = EV.trials.find((x: any) => x.task === 1 && x.variant === 'original'), m = EV.trials.find((x: any) => x.task === 1 && x.variant === 'modified');
  server({ '/api/lifecycle/evaluations/m7-larkspur-browser-1': EV, [`/trials/${o.id}`]: read(`trials/${o.id}.json`), [`/trials/${m.id}`]: read(`trials/${m.id}.json`) });
  const host = await mount(<ReportPage id="m7-larkspur-browser-1" task={1} />);
  const t = host.textContent ?? '';
  expect(t).toContain('I need a course that costs $250 or less and still has at least 5 seats left. What qualifies?');
  expect(t).toContain('1 of 5 expected items'); expect(t).toContain('5 of 5 expected items');
  expect(t).toContain('12 of 14'); expect(t).toContain('3 of 14'); expect(t).toContain('67 s'); expect(t).toContain('16 s');
  expect(t).toContain('US$0.170'); expect(t).toContain('US$0.039');
  const imgs = [...host.querySelectorAll('img')].map(i => i.getAttribute('src'));
  expect(imgs.some(s => s?.includes(`/trials/${o.id}/screenshots/step-001.webp`))).toBe(true);
  expect(imgs.some(s => s?.includes(`/trials/${m.id}/screenshots/step-001.webp`))).toBe(true);
  expect(t).toContain('step 1 / 12'); expect(t).toContain('step 1 / 3');
});

it('the journey is one page with all eight steps on the final Before -> After experiment, and #/demo opens it', async () => {
  server({});
  const host = await mount(<Lifecycle />);
  expect(host.querySelector('h1')?.textContent).toBe('From a website to one agents can use.');
  for (const id of ['website', 'tasks', 'review', 'evaluate', 'recommendations', 'improve', 'reevaluate', 'compare']) expect(host.querySelector(`#lc-${id}`)).not.toBeNull();
  expect(host.querySelectorAll('.lc-stepper a')).toHaveLength(8);
  expect(host.textContent).toContain('Every fact on every course card');                                       // the After changes are static and always shown
  expect(host.querySelectorAll('.lc-versions img')).toHaveLength(2);                                          // Before and After only
  const main = host.querySelector('main')!.textContent!;
  for (const old of ['Ironbark', 'Original', 'Improved', 'Modified', 'first experiment', 'Earlier']) expect(main).not.toContain(old);
  expect(host.querySelector('[role=radiogroup]')).toBeNull();                                                 // no site selector
  document.body.innerHTML = '';
  window.location.hash = '#/demo';
  const { default: App } = await import('../../App');
  const app = await mount(<App />);
  expect(app.querySelector('h1')?.textContent).toBe('From a website to one agents can use.');
});

it('shows the frozen task set as approved and frozen, with no approval control on the web', async () => {
  const sha = Object.keys(read('DATASET.json').files).find((f: string) => f.startsWith('suites/'))!.slice(7, 71);
  const suite = { ...read(`suites/${sha}.json`), source: 'dataset' };
  const f = server({ '/api/lifecycle/overview': overview, '/api/lifecycle/suites': [{ sha256: sha, name: suite.suite_name, version: suite.version, site: suite.site, tasks: suite.tasks.length, state: suite.state, refs: suite.refs, synthetic: false, created_at: '', created_by: 'system', gaps: 0, source: 'dataset' },
      { sha256: '0e46a1efe0a628ff2fb69c72ce0c0eb2323919570e4e3fbde1ac296d93460360', name: 'larkspur-core', version: 3, site: 'larkspur', tasks: 3, state: 'frozen', refs: ['larkspur-core@v3'], synthetic: false, created_at: '', created_by: 'owner', gaps: 0, source: 'store' }],
    [`/api/lifecycle/suites/${sha}`]: suite });
  const host = await mount(<Lifecycle step="review" suite={sha} />);
  const t = host.querySelector('#lc-review')!.textContent!;
  expect(t).toContain(`${suite.tasks.length} customer tasks`); expect(t).not.toContain(suite.suite_name);
  const first = [...suite.tasks].sort((a: any, b: any) => a.task_id.localeCompare(b.task_id))[0];
  expect(t).toContain(`Task 1${first.customer_wording}`);                                                  // numbered as in every report
  expect(t).toContain('fixed as an exact set before any evaluation');
  expect(t).toContain('Both the Before and the After evaluation');
  expect([...host.querySelectorAll('button')].some(b => /approve/i.test(b.textContent ?? ''))).toBe(false);
  expect(f.mock.calls.some(c => (c[1] as RequestInit | undefined)?.method === 'POST')).toBe(false);
});

it('re-evaluation sends launches to the workspace (the one launch path) and shows what is open, or that nothing is', async () => {
  server({ '/api/lifecycle/overview': overview, '/api/lifecycle/evaluations': [] });
  const host = await mount(<Lifecycle step="reevaluate" />);
  const sec = () => document.querySelector('#lc-reevaluate')!;
  expect(sec().textContent).toContain('No live run is open right now');
  expect(sec().querySelector('a[href="#/run"]')).not.toBeNull();
  expect([...host.querySelectorAll('button')].some(b => /launch|run/i.test(b.textContent ?? ''))).toBe(false);      // no second launch control
  document.body.innerHTML = '';
  const armed = { ...overview, evaluation: { engine: 'stage-b', armed: true, reason: null, repetitions: [1], evaluation: { arming_id: 'judge-pool-1', arming_sha256: 'a'.repeat(64), mode: 'paid', site: 'larkspur',
    suite: 'larkspur-core v3', frozen_suite: 'larkspur-core@v3', frozen_suite_sha256: 'b'.repeat(64), variants: ['original', 'improved'], armed_at: '2026-11-04T00:00:00+00:00',
    launches: { max: 4, used: 0, left: 4 }, options: [{ repetitions: 1, trials: 4, reservation_usd: 2.508, manifest_sha256: 'c'.repeat(64), available: true, fits_hosted_ceiling: true }],
    agent: { model: 'muse-spark-1.3', reasoning_effort: 'low', max_completion_tokens: 4096, profile: 'suite-v2-compat2' } } } };
  server({ '/api/lifecycle/overview': armed, '/api/lifecycle/evaluations': [] });
  await mount(<Lifecycle step="reevaluate" />);
  const t = sec().textContent!;
  expect(t).toContain('Run it yourself'); expect(t).toContain('4 of 4 live runs left'); expect(t).toContain('Improved');
  expect(sec().querySelector('a[href="#/run"]')!.textContent).toContain('Run it live');
  document.body.innerHTML = '';
  // the shared A$20 budget's evaluation has NO launch count (launches: null): the journey must render, not crash (production regression 2026-11-04)
  const shared = { ...armed, evaluation: { ...armed.evaluation, evaluation: { ...armed.evaluation.evaluation, arming_id: 'ar-a20-2026-11', launches: null } } };
  server({ '/api/lifecycle/overview': shared, '/api/lifecycle/evaluations': [] });
  await mount(<Lifecycle step="reevaluate" />);
  const u = sec().textContent!;
  expect(u).toContain('Run it yourself'); expect(u).toContain('runs while the A$20 evaluation budget lasts'); expect(u).not.toMatch(/live runs? left/);
  expect(sec().querySelector('a[href="#/run"]')!.textContent).toContain('Run it live');
});

it('shows the recorded task generation: proposed, accepted and its model cost; no generate control', async () => {
  const gen = read('generation.json');
  server({ '/api/lifecycle/overview': overview, '/api/lifecycle/generations': [{ id: gen.id, dataset: 'm7', site: 'larkspur', created_at: gen.created_at, mode: 'paid', stop_reason: gen.stop_reason, admissions: gen.admissions, proposals: 24, rounds: 2, cost: gen.cost, suite_sha256: gen.suite_sha256, generator: gen.generator }],
    [`/api/lifecycle/generations/${gen.id}`]: gen });
  await mount(<Lifecycle step="tasks" />);
  const t = document.querySelector('#lc-tasks')!.textContent!;
  expect(t).toContain('Questions proposed24'); expect(t).toContain(`Accepted${(gen.post_fix_reevaluation ?? gen).admissions.natural}`);
  expect(t).toContain('US$0.050'); expect(t).toContain('Not used4'); expect(t).not.toContain('Accepted 18');   // final counts only, no per-question status
  expect([...document.querySelectorAll('#lc-tasks button')].some(b => /generate/i.test(b.textContent ?? ''))).toBe(false);
});

it('maps every recommendation of the Before report to the After change that applies it', async () => {
  const d0 = EV.diagnostics[Object.keys(EV.diagnostics)[0]];
  const ev = { ...EV, id: BEFORE.id, diagnostics: { natural: { ...d0, findings: d0.findings.map((f: any) => ({ ...f, variant: f.variant === 'original' ? 'polishedoriginal' : f.variant })) } } };
  server({ [`/api/lifecycle/evaluations/${BEFORE.id}`]: ev });                                                  // the run the recommendations came from
  await mount(<Lifecycle step="recommendations" />);
  const sec = document.querySelector('#lc-recommendations')!;
  const items = [...sec.querySelectorAll('.lc-rec-list li')];
  expect(items.length).toBeGreaterThan(3);
  expect(items.filter(li => li.textContent!.includes('Applied:')).length).toBeGreaterThanOrEqual(items.length - 1);
  expect(sec.textContent).toContain('State campus on each card');
  expect(sec.textContent).toContain('What the agents ran into (Before)');
});

it('compares only the final Before and After evaluations (never earlier experiments or rehearsals), with the recorded result featured', async () => {
  const row = (id: string, variants: string[], extra = {}) => ({ id, title: id, mode: 'paid', state: 'completed', source: 'launched', site: 'Larkspur Community College', site_id: 'larkspur', variants, started_at: '2026-11-04T01:00:00+00:00', tasks: 3, trials: 3,
    success: Object.fromEntries(variants.map(v => [v, { trials: 3, v1_passed: 1, v1_evidence_backed: 1, v2_passed: 3, v2_evidence_backed: 3, v2_1_contrast_review_passes: 0 }])), requests: Object.fromEntries(variants.map(v => [v, 15])), ...extra });
  PUBLIC_SCOPE.versions = SCOPE;                                                                               // the public scope, as deployed
  try {
    server({ '/api/lifecycle/evaluations': [row(LIVE.id, ['original', 'improved']), row(BEFORE.id, ['polishedoriginal']), row(AFTER.id, ['modifiedpolished']),
      row('eval-' + '9'.repeat(32), ['modifiedpolished'], { mode: 'rehearsal' }), row('eval-' + 'e'.repeat(32), ['polished'])] });
    await mount(<Lifecycle step="compare" />);
    const sec = document.querySelector('#lc-compare')!;
    expect(sec.querySelectorAll('tbody tr')).toHaveLength(2);
    expect(sec.querySelector(`a[href="#/reports/${BEFORE.id}"]`)).not.toBeNull(); expect(sec.querySelector(`a[href="#/reports/${AFTER.id}"]`)).not.toBeNull();
    expect(sec.querySelector(`a[href="#/reports/${LIVE.id}"]`)).toBeNull();
    const f = sec.querySelector('.lc-featured')!;
    expect(f.textContent).toContain('0/3'); expect(f.textContent).toContain('3/3'); expect(f.textContent).toContain('Before'); expect(f.textContent).toContain('After');
    expect(f.querySelectorAll('img')).toHaveLength(2);
  } finally { PUBLIC_SCOPE.versions = null; }
});

it('labels the recorded first evaluation and a live run in this product differently, and shows the finished agent runs', async () => {
  server({ '/api/lifecycle/evaluations/m7-larkspur-browser-1': EV });
  let host = await mount(<ReportPage id="m7-larkspur-browser-1" />);
  expect(host.textContent).toContain('First evaluation · recorded');
  expect(host.textContent).not.toContain('Live run in this product');
  expect(host.textContent).toContain('12/12 finished');
  document.body.innerHTML = '';
  const id = 'eval-' + 'e'.repeat(32);
  const trials = EV.trials.map((t: any, i: number) => i === 0 ? { ...t, answer: ['/courses/x'], answer_normalized: { fixture_origin_replaced: 1, note: 'shown as a site path' } } : t);
  server({ [`/api/lifecycle/evaluations/${id}`]: { ...EV, id, trials, source: { kind: 'launched', job: id, state: 'completed' } } });
  host = await mount(<ReportPage id={id} />);
  expect(host.textContent).toContain('Live run in this product');
  expect(host.textContent).not.toContain('First evaluation · recorded');
});

it('C2: useLoad never returns the previous key\'s data while the next key loads', async () => {
  const seen: string[] = [];
  let release: (v: string) => void = () => {};
  function Probe({ k }: { k: string }) {
    const r = useLoad(() => k === 'a' ? Promise.resolve('data-a') : new Promise<string>(res => { release = res; }), k);
    seen.push(`${k}:${r.data ?? (r.loading ? 'loading' : 'none')}`);
    return null;
  }
  const host = document.createElement('div'); document.body.append(host);
  const root = createRoot(host);
  await act(async () => { root.render(<Probe k="a" />); });
  await act(async () => { await new Promise(r => setTimeout(r, 0)); });
  expect(seen.at(-1)).toBe('a:data-a');
  await act(async () => { root.render(<Probe k="b" />); });
  expect(seen.filter(x => x.startsWith('b:'))).not.toContain('b:data-a');                               // the bug: b rendered with a's data
  expect(seen.at(-1)).toBe('b:loading');
  await act(async () => { release('data-b'); await new Promise(r => setTimeout(r, 0)); });
  expect(seen.at(-1)).toBe('b:data-b');
  act(() => root.unmount());
});

it('the production run eval-c04fdb10: correct 0/3 -> 3/3, exact match 0/3 both, and the comparison table counted as equivalent evidence', async () => {
  const C04 = JSON.parse(readFileSync(resolve(__dirname, '../../fixtures/live/eval-c04fdb10-report.json'), 'utf8'));
  server({ [`/api/lifecycle/evaluations/${C04.id}`]: C04 });
  const host = await mount(<ReportPage id={C04.id} />);
  const row = (k: string) => [...host.querySelectorAll('tr')].find(r => r.textContent?.startsWith(k))!.textContent!;
  expect(row('Correct answers')).toBe('Correct answers0/33/3');
  expect(row('Exact match')).toBe('Exact match0/30/3');
  expect(row('Shown the pages that hold the answer')).toContain('0/3');                                      // the recorded rule, unchanged
  expect(row('…or an equivalent page')).toBe('…or an equivalent page that states every deciding fact for every course (e.g. a comparison table)0/33/3');
  expect(host.textContent).toContain('Original vs Improved');
});

it('the trace view names the equivalent page the agent read the facts from', async () => {
  const C04 = JSON.parse(readFileSync(resolve(__dirname, '../../fixtures/live/eval-c04fdb10-report.json'), 'utf8'));
  const tl = { id: 'x', steps: [], errors: [], screenshots: [] };
  server({ [`/api/lifecycle/evaluations/${C04.id}`]: C04, '/trials/original-gen-8334922e62-n-r1': tl, '/trials/improved-gen-8334922e62-n-r1': tl });
  const host = await mount(<ReportPage id={C04.id} task={2} />);
  const imp = host.querySelector('.lc-side.i')!.textContent!;
  expect(imp).toContain('every deciding fact shown on /courses/compare');
  expect(host.querySelector('.lc-side.o')!.textContent).toContain('required page(s) not shown');
});
