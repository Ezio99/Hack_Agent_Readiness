// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterEach, expect, it, vi } from 'vitest';
import { Lifecycle } from './Lifecycle';
import { ReportPage } from './Report';
import { parse } from '../router';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { vi.unstubAllGlobals(); document.body.innerHTML = ''; window.location.hash = ''; });

// The real sanitized M7 dataset (committed), served as the API would serve it: the UI is tested on the recorded data, not on invented fixtures.
const DS = resolve(__dirname, '../../../../datasets/lifecycle/m7-larkspur-browser-1/v1');
const read = (p: string) => JSON.parse(readFileSync(resolve(DS, p), 'utf8'));
const EV = { ...read('evaluation.json'), source: { kind: 'dataset', id: 'm7-larkspur-browser-1', version: 1, built_at: 'x', description: 'd', runs: ['r'] } };
const json = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body });
const overview = { steps: [{ id: 'evaluate', label: 'E', available: true, action_available: false, detail: 'Launching needs the lifecycle store.' }],
  onboarding: { available: false, reason: 'x', detail: 'Onboarding from a URL is not available.' }, approval: { available: false, reason: 'owner_authentication_not_configured', detail: 'Approval needs a verified owner identity.' },
  paid: { available: false, reason: 'paid_launch_not_authorized', detail: 'Paid evaluations need owner authorisation.' }, rehearsal: { available: false, operator_only: true, cost_usd: 0, reason: 'no_store' }, sources: { datasets: [], store: false, jobs: false } };

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

it('routes the lifecycle steps, suites, jobs and reports', () => {
  expect(parse('#/lifecycle')).toEqual({ name: 'lifecycle', step: undefined });
  expect(parse('#/lifecycle/review')).toEqual({ name: 'lifecycle', step: 'review' });
  expect(parse('#/lifecycle/suites/' + 'a'.repeat(64))).toEqual({ name: 'lifecycle', step: 'review', suite: 'a'.repeat(64) });
  expect(parse('#/lifecycle/jobs/lc-' + 'b'.repeat(32))).toEqual({ name: 'lifecycle', step: 'evaluate', job: 'lc-' + 'b'.repeat(32) });
  expect(parse('#/reports/m7-larkspur-browser-1/tasks/1')).toEqual({ name: 'report', id: 'm7-larkspur-browser-1', task: 1 });
  expect(parse('#/lifecycle/nope').name).toBe('home');
  expect(parse('#/run').name).toBe('run');                                      // the hosted workspace URLs are unchanged
});

it('renders the M7 report from the recorded dataset with both graders labelled and no composite score', async () => {
  server({ '/api/lifecycle/evaluations/m7-larkspur-browser-1': EV });
  const host = await mount(<ReportPage id="m7-larkspur-browser-1" />);
  const t = host.textContent ?? '';
  expect(t).toContain('Paid evaluation · real model');
  expect(t).toContain('no statistical power');
  expect(t).toContain('2/6'); expect(t).toContain('3/6'); expect(t).toContain('1/6'); expect(t).toContain('4/6');
  expect(t).toContain('v1 official'); expect(t).toContain('v2 post-hoc'); expect(t).toContain('v2.1 review rule (prospective)');
  expect(t).toContain('named 1 of 5'); expect(t).toContain('named 5 of 5');
  expect(t).toContain('US$1.520696');
  for (const d of ['Task success', 'Navigation efficiency', 'Evidence quality', 'Information accessibility', 'Agent reliability', 'Coverage']) expect(t).toContain(d);
  expect(t).toContain('no composite readiness score');
  expect(t).toContain('Hypotheses'); expect(t).toContain('Observed facts');
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

it('shows suite review with the exact hash and keeps web approval disabled', async () => {
  const sha = Object.keys(read('DATASET.json').files).find((f: string) => f.startsWith('suites/'))!.slice(7, 71);
  const suite = { ...read(`suites/${sha}.json`), source: 'dataset' };
  const f = server({ '/api/lifecycle/overview': overview, '/api/lifecycle/sites': [], '/api/lifecycle/suites': [{ sha256: sha, name: suite.suite_name, version: suite.version, site: suite.site, tasks: suite.tasks.length, state: suite.state, refs: suite.refs, synthetic: false, created_at: '', created_by: 'system', gaps: 0, source: 'dataset' }],
    [`/api/lifecycle/suites/${sha}`]: suite });
  const host = await mount(<Lifecycle step="review" suite={sha} />);
  expect(host.textContent).toContain(sha);
  const approve = [...host.querySelectorAll('button')].find(b => b.textContent?.includes('Approve and freeze')) as HTMLButtonElement;
  expect(approve.disabled).toBe(true);
  expect(host.textContent).toContain('Web approval is disabled');
  expect(f.mock.calls.some(c => (c[1] as RequestInit | undefined)?.method === 'POST')).toBe(false);
});

it('never offers a paid launch and disables rehearsal launch when the server cannot run it', async () => {
  server({ '/api/lifecycle/overview': overview, '/api/lifecycle/sites': [], '/api/lifecycle/frozen': [], '/api/lifecycle/evaluations': [] });
  const host = await mount(<Lifecycle step="evaluate" />);
  const btn = (s: string) => [...host.querySelectorAll('button')].find(b => b.textContent?.includes(s)) as HTMLButtonElement;
  expect(btn('Launch paid evaluation').disabled).toBe(true);
  expect(btn('Launch zero-cost rehearsal').disabled).toBe(true);
  expect(host.textContent).toContain('Paid evaluations need owner authorisation.');
  expect(host.textContent).toContain('Launching needs the lifecycle store.');
});

it('shows the recorded Stage A generation with its admissions and the disabled generate action', async () => {
  const gen = read('generation.json');
  server({ '/api/lifecycle/overview': overview, '/api/lifecycle/sites': [], '/api/lifecycle/generations': [{ id: gen.id, dataset: 'm7', site: 'larkspur', created_at: gen.created_at, mode: 'paid', stop_reason: gen.stop_reason, admissions: gen.admissions, proposals: 24, rounds: 2, cost: gen.cost, suite_sha256: gen.suite_sha256, generator: gen.generator }],
    [`/api/lifecycle/generations/${gen.id}`]: gen });
  const host = await mount(<Lifecycle step="tasks" />);
  const t = host.textContent ?? '';
  expect(t).toContain('18 natural'); expect(t).toContain('5 rejected'); expect(t).toContain('US$0.049804');
  expect(t).toContain('Generate new tasks — needs owner authorisation');
});
