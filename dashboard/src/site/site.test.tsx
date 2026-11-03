// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { existsSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import App from '../App';
import { parse } from './router';
import { evidence, headline, trial, isItemPage, replication } from './evidence';
import { LATEST_LIVE } from './LatestLive';
import { FEATURED, IMPROVEMENTS, LIVE } from './showcase';
import { Home } from './Home';
import { Demo } from './demo/Demo';
import { Workspace } from './workspace/Workspace';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement, root: Root;
beforeEach(() => { host = document.createElement('div'); document.body.append(host); root = createRoot(host); window.scrollTo = vi.fn() as any; });
afterEach(() => { act(() => root.unmount()); host.remove(); vi.unstubAllGlobals(); localStorage.clear(); window.location.hash = ''; });
const reducedMotion = (on: boolean) => vi.stubGlobal('matchMedia', (q: string) => ({ matches: on && q.includes('reduce'), media: q, addEventListener() {}, removeEventListener() {} }));
const noNetwork = () => { const f = vi.fn(async () => { throw new Error('no network expected'); }); vi.stubGlobal('fetch', f); return f; };

describe('routes', () => {
  it('keeps persistent evaluation URLs and adds home, demo scenes and the archive', () => {
    const id = 'eval-' + 'a'.repeat(32);
    expect(parse(`#/run/${id}`)).toEqual({ name: 'run', job: id });
    expect(parse('#/run')).toEqual({ name: 'run', job: null });
    expect(parse('#/run/eval-short').name).toBe('home');
    expect(parse('#/demo')).toEqual({ name: 'demo', scene: undefined });
    expect(parse('#/demo/friction')).toEqual({ name: 'demo', scene: 'friction' });
    expect(parse('#/demo/ironbark')).toEqual({ name: 'demo', scene: 'ironbark' });
    expect(parse('#/lifecycle/improve')).toEqual({ name: 'lifecycle', step: 'improve' });
    expect(parse('#/lifecycle/report')).toEqual({ name: 'lifecycle', step: 'recommendations' });   // an earlier step name still lands
    expect(parse('#/how')).toEqual({ name: 'home', section: 'how' });
    expect(parse('#/studio')).toEqual({ name: 'studio' });
    expect(parse('#/investigation')).toEqual({ name: 'classic', page: 'investigation' });
    expect(parse('')).toEqual({ name: 'home' });
    expect(parse('#/<script>')).toEqual({ name: 'home' });
  });
});

describe('recorded evidence (eval-9aaac35c)', () => {
  it('matches the recorded outcomes and verdicts exactly', () => {
    expect(evidence.source.job).toBe('eval-9aaac35ca488c2bf951e01e58746604a');
    expect(evidence.source.mode).toBe('live');
    expect(evidence.source.evidence_origin).toBe('real_model');
    expect(evidence.source.model).toBe('muse-spark-1.3');
    expect(headline.passes).toEqual({ original: 1, modified: 4, of: 4 });
    expect(headline.requests).toEqual({ original: 50, modified: 26, fewerPct: 48 });
    expect(evidence.frozen_rule.verdict).toBe('inconclusive');
    expect(evidence.exploratory_rule.verdict).toBe('consistent_with_h1');
    expect(evidence.frozen_rule.p_pass).toBeGreaterThan(evidence.frozen_rule.alpha);   // the copy says p is above α
    // row totals agree with the summary
    for (const arm of ['Original', 'Modified'] as const)
      expect(evidence.rows.filter(r => r.arm === arm).reduce((a, r) => a + r.requests, 0)).toBe(evidence.summary[arm].requests_total);
  });
  it('bundles a real screenshot for every step the demo shows', () => {
    const dir = join(__dirname, 'evidence', 'frames');
    const files = new Set(readdirSync(dir));
    for (const t of [trial('original', 1), trial('modified', 1)]) for (const s of t.steps) {
      expect(s.frame, `${t.arm} step ${s.step}`).toBeTruthy();
      expect(files.has(`${s.frame}.webp`)).toBe(true);
    }
    expect(existsSync(join(dir, `${trial('modified', 2).steps[2].frame}.webp`))).toBe(true);
  });
  it('supports the editorial claims made in the demo', () => {
    const o = trial('original', 1), m = trial('modified', 1);
    expect(o.steps.filter(s => isItemPage(s.path))).toHaveLength(3);
    expect(m.steps.filter(s => isItemPage(s.path))).toHaveLength(0);
    expect(o.steps[2].memory).toMatch(/correlates with highest value/);
    expect(o.steps[o.steps.length - 1].memory).toMatch(/budget exhausted/);
    expect(m.steps[m.steps.length - 1].memory).toMatch(/Verified all 16/);
    expect(evidence.insights.findings.find(f => f.id === 'detail-dependency')?.observed).toMatch(/3\.0 item detail pages/);
  });
});

describe('homepage (the featured Larkspur story)', () => {
  it('tells the Larkspur story from the recorded live evaluation, links the journey, workspace and report, and calls no API', () => {
    const f = noNetwork();
    act(() => root.render(<Home />));
    expect(host.querySelector('h1')?.textContent).toBe('See your website the way an agent does.');
    const hrefs = [...host.querySelectorAll('a')].map(a => a.getAttribute('href'));
    for (const h of ['#/run', '#/lifecycle', `#/reports/${LIVE.id}`, '#/lifecycle/improve']) expect(hrefs).toContain(h);
    const text = host.textContent!;
    const O = LIVE.totals.original, M = LIVE.totals.modified;
    for (const s of [`${O.requests}`, `${M.requests}`, `${Math.round(100 * (O.requests - M.requests) / O.requests)}% fewer on Modified`, `${LIVE.correct.original}/6`, `${LIVE.correct.modified}/6`,
                     'Larkspur Community College', 'Run Original vs Improved', ...IMPROVEMENTS.map(i => i.title)]) expect(text).toContain(s);
    expect(text).toContain(LIVE.journeys['original-1'].steps.at(-1)!.memory!);                     // the agent's own words, unedited
    for (const s of ['post-hoc', 'inconclusive', 'p =', 'xploratory', 'verified', 'pre-registered']) expect(text).not.toContain(s);
    expect(host.querySelector('main')!.textContent).not.toContain('Ironbark');                                // the earlier case study is only linked from the footer
    expect(f).not.toHaveBeenCalled();
  });
  it('the recorded showcase numbers are internally consistent with the per-agent records', () => {
    expect(LIVE.trials).toHaveLength(12);
    for (const v of ['original', 'modified']) {
      const ts = LIVE.trials.filter(t => t.variant === v);
      expect(ts.reduce((a, t) => a + t.requests, 0)).toBe(LIVE.totals[v].requests);
      expect(ts.filter(t => t.correct).length).toBe(LIVE.correct[v]);
      expect(ts.filter(t => t.passed).length).toBe(LIVE.passed[v]);
    }
    expect(LIVE.cost_usd).toBeCloseTo(LIVE.totals.original.cost_usd + LIVE.totals.modified.cost_usd, 4);
    expect(LATEST_LIVE.id).toBe(FEATURED.liveEvaluation);
    for (const x of IMPROVEMENTS) if (x.preview) expect(existsSync(join(__dirname, 'showcase', 'frames', `${x.preview}.webp`))).toBe(true);
  });
});

describe('demo', () => {
  it('reduced motion: scenes collapse to normal flow and the journey becomes a stepper', () => {
    reducedMotion(true); noNetwork();
    act(() => root.render(<Demo />));
    for (const id of ['intro', 'task', 'original', 'friction', 'change', 'modified', 'outcome', 'method', 'run']) expect(host.querySelector(`#${id}`)).toBeTruthy();
    const tracks = [...host.querySelectorAll<HTMLElement>('section.track')];
    expect(tracks.length).toBeGreaterThan(5);
    for (const t of tracks) { expect(t.hasAttribute('data-static')).toBe(true); expect(t.style.height).toBe(''); }
    const original = host.querySelector('#original')!;
    expect(original.querySelector('.j-step')?.textContent).toBe('01');
    const next = [...original.querySelectorAll('button')].find(b => b.textContent?.includes('Next step'))!;
    act(() => next.click()); act(() => next.click());
    expect(original.querySelector('.j-step')?.textContent).toBe('03');
    expect(original.textContent).toContain(trial('original', 1).steps[2].memory!);
    // direct step navigation
    act(() => (original.querySelectorAll('.j-ticks button')[11] as HTMLButtonElement).click());
    expect(original.textContent).toContain('Not passed');
    const modified = host.querySelector('#modified')!;
    act(() => (modified.querySelectorAll('.j-ticks button')[7] as HTMLButtonElement).click());
    expect(modified.textContent).toContain('Evidence-supported pass');
  });
  it('motion: scenes are tall scroll tracks with sticky stages, a chapter rail and a full transcript', () => {
    reducedMotion(false); noNetwork();
    act(() => root.render(<Demo scene="outcome" />));
    const intro = host.querySelector<HTMLElement>('#intro')!;
    expect(intro.style.height).toBe('320vh');
    expect(host.querySelector<HTMLElement>('#original')!.style.height).toBe(`${60 + trial('original', 1).steps.length * 55}vh`);
    const rail = host.querySelectorAll('.rail a');
    expect(rail).toHaveLength(9);
    expect(rail[0].getAttribute('href')).toBe('#/demo/intro');
    const transcripts = host.querySelectorAll('.transcript li');
    expect(transcripts).toHaveLength(trial('original', 1).steps.length + trial('modified', 1).steps.length);
  });
  it('never invents results: every on-screen request count comes from the recording', () => {
    reducedMotion(true); noNetwork();
    act(() => root.render(<Demo />));
    const vals = [...host.querySelectorAll('.oc-val')].map(e => Number(e.textContent));
    const expected = evidence.tasks.flatMap(t => (['Original', 'Modified'] as const).map(a => evidence.rows.find(r => r.arm === a && r.task === t.task)!.requests));
    expect(vals).toEqual(expected);
  });
});

describe('workspace and app shell', () => {
  it('a persistent evaluation URL opens that evaluation through the existing API, without posting', async () => {
    const id = 'eval-' + 'c'.repeat(32);
    const f = vi.fn(async (url: string, _init?: RequestInit) => ({ ok: true, json: async () => url.endsWith('/config') ? { available: false, mode: null, repetitions: [1, 3, 5], model: 'm', agent_profile: 'p', tasks: [], remaining_repetitions: 0, active: null }
      : url.endsWith('/jobs') ? [] : { id, state: 'completed', mode: 'live', repetitions: 1, created_at: 1, started_at: 1, finished_at: 2, reps: [], summary: { Original: { completed: 0, failed: 0, evidence_supported_passes: 0, strict_passes: 0, requests_total: 0, requests_mean: null }, Modified: { completed: 0, failed: 0, evidence_supported_passes: 0, strict_passes: 0, requests_total: 0, requests_mean: null } } } }));
    vi.stubGlobal('fetch', f);
    window.location.hash = `#/run/${id}`;
    await act(async () => { root.render(<App />); });
    await act(async () => {});
    expect(f.mock.calls.some(c => c[0] === `/api/ironbark/jobs/${id}`)).toBe(true);
    expect(f.mock.calls.some(c => (c[1] as RequestInit | undefined)?.method === 'POST')).toBe(false);
    expect(host.textContent).toContain('Run real agents on a website.');
    expect(document.title).toContain('Evaluation workspace');
  });
  it('the root URL is the product homepage', () => {
    noNetwork(); window.location.hash = '';
    act(() => root.render(<App />));
    expect(host.querySelector('h1')?.textContent).toContain('See your website');
  });
  it('the workspace header keeps keyboard-reachable navigation and a skip link', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, json: async () => ({}) })));
    await act(async () => { root.render(<Workspace job={null} />); });
    expect(host.querySelector('.ar-skip')?.getAttribute('href')).toBe('#ws-main');
    expect(host.querySelector('nav[aria-label="Primary"] a[aria-current="page"]')?.textContent).toBe('Workspace');
  });
});

describe('earlier case study (Ironbark, archived)', () => {
  it('the demo outcome keeps its recorded replication figures', () => {
    reducedMotion(true); noNetwork();
    act(() => root.render(<Demo scene="outcome" />));
    const outcome = host.querySelector('#outcome')!;
    expect(outcome.textContent).toContain('Replicated later the same day by a second live run of the same four tasks (eval-aa23e330)');
    expect(host.textContent).toContain('Earlier case study · Ironbark Hire');
  });
  it('the replication figures are the recorded ones (first run = the bundled evidence)', () => {
    expect(replication.first.official).toEqual({ original: headline.passes.original, modified: headline.passes.modified });
    expect(replication.first.requests).toEqual({ original: headline.requests.original, modified: headline.requests.modified });
    expect(evidence.source.job.startsWith(replication.first.job)).toBe(true);
  });
});
