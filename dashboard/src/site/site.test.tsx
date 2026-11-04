// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import App from '../App';
import { parse } from './router';
import { evidence, headline, trial, isItemPage, replication } from './evidence';
import { LATEST_LIVE } from './LatestLive';
import { AFTER, AFTER_CHANGES, BEFORE, CANONICAL, FIRST_LIVE, IMPROVEMENTS, LIVE, PAIRED } from './showcase';
import { REPO_URL } from './Shell';
import { Home, QUALIFIER } from './Home';
import { Demo } from './demo/Demo';
import { Workspace } from './workspace/Workspace';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement, root: Root;
beforeEach(() => { host = document.createElement('div'); document.body.append(host); root = createRoot(host); window.scrollTo = vi.fn() as any; });
afterEach(() => { act(() => root.unmount()); host.remove(); vi.unstubAllGlobals(); localStorage.clear(); window.location.hash = ''; });
const reducedMotion = (on: boolean) => vi.stubGlobal('matchMedia', (q: string) => ({ matches: on && q.includes('reduce'), media: q, addEventListener() {}, removeEventListener() {} }));
const noNetwork = () => { const f = vi.fn(async () => { throw new Error('no network expected'); }); vi.stubGlobal('fetch', f); return f; };

describe('routes', () => {
  it('keeps persistent evaluation URLs; the Ironbark case study, the replay archive and the pre-redesign pages are not public routes', () => {
    const id = 'eval-' + 'a'.repeat(32);
    expect(parse(`#/run/${id}`)).toEqual({ name: 'run', job: id });
    expect(parse('#/run')).toEqual({ name: 'run', job: null });
    expect(parse('#/run/eval-short').name).toBe('home');
    expect(parse('#/demo')).toEqual({ name: 'demo' });                                          // the Larkspur journey
    expect(parse('#/showcase')).toEqual({ name: 'showcase' });
    for (const old of ['#/demo/friction', '#/demo/ironbark', '#/studio', '#/investigation', '#/overview', '#/replay']) expect(parse(old)).toEqual({ name: 'home' });
    expect(parse('#/lifecycle/improve')).toEqual({ name: 'lifecycle', step: 'improve' });
    expect(parse('#/lifecycle/report')).toEqual({ name: 'lifecycle', step: 'recommendations' });   // an earlier step name still lands
    expect(parse('#/how')).toEqual({ name: 'home', section: 'how' });
    expect(parse('')).toEqual({ name: 'home' });
    expect(parse('#/<script>')).toEqual({ name: 'home' });
  });});

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

describe('site navigation (judge-facing)', () => {
  it('header: How it works, See the results (the canonical paired report), Workspace and one Run CTA; footer: Product, Evidence, About without dated run links', () => {
    act(() => root.render(<Home />));
    const nav = [...host.querySelectorAll('#site-nav a:not(.nav-cta)')].map(a => [a.textContent, a.getAttribute('href')]);
    expect(nav).toEqual([['How it works', '#/lifecycle'], ['See the results', `#/reports/${CANONICAL.id}`], ['Workspace', '#/run']]);
    const cta = [...host.querySelectorAll('.site-head a')].filter(a => a.textContent?.startsWith('Run an evaluation'));
    expect(cta.map(a => a.getAttribute('href'))).toEqual(['#/run', '#/run']);           // the desktop button and the mobile-menu item
    const head = host.querySelector('.site-head')!.textContent!;
    for (const s of ['Showcase', 'journey', 'Live report']) expect(head).not.toContain(s);
    const foot = host.querySelector('.site-foot')!;
    expect([...foot.querySelectorAll('h4')].map(h => h.textContent)).toEqual(['Product', 'Evidence', 'About']);
    const links = Object.fromEntries([...foot.querySelectorAll('ul a')].map(a => [a.textContent, a.getAttribute('href')]));
    expect(links).toEqual({ 'The Larkspur journey': '#/lifecycle', 'Run an evaluation': '#/run', 'Before and after': '#/showcase',
      'Canonical evaluation results': `#/reports/${CANONICAL.id}`,
      'Technical methodology': '#/how', 'Isolation & limitations': '#/trust', 'GitHub repository': REPO_URL });
    expect(REPO_URL).toBe('https://github.com/Ezio99/Hack_Agent_Readiness/tree/final-showcase');
    for (const id of [BEFORE.id, AFTER.id]) expect(foot.innerHTML).not.toContain(id);
    expect(host.querySelector('.site-head a[href="#/reports/latest"], .site-foot a[href="#/reports/latest"]')).toBeNull();   // no global link to the changing latest report       // dated runs are linked from the evidence pages, not the footer
    for (const r of ['#/showcase', '#/lifecycle', '#/reports/latest']) expect(parse(r).name).not.toBe('home');
    expect(parse('#/how')).toEqual({ name: 'home', section: 'how' });                       // the methodology route is unchanged (no redirect)   // deep links still resolve
  });
});

describe('homepage hero layout', () => {
  it('the trace card stays inside its own column: no negative margins pull it over the figure or its caption (regression: overlap at 1280/768/390 px)', () => {
    const css = readFileSync(join(__dirname, 'home.css'), 'utf8');
    const rules = [...css.matchAll(/\.hero-note\{([^}]*)\}/g)].map(m => m[1]);
    expect(rules.length).toBeGreaterThan(0);
    for (const r of rules) expect(r).not.toMatch(/margin[^;]*-\s*\d|margin[^;]*calc\(\s*-/);
    expect(css).not.toMatch(/\.plate-verdicts small\{[^}]*nowrap/);                              // verdict lines wrap inside the card
  });
});

describe('homepage (the featured Larkspur story)', () => {
  it('features ONLY the canonical paired evaluation as fixed reference results, in the audience labels, and calls no API', () => {
    const f = noNetwork();
    act(() => root.render(<Home />));
    expect(host.querySelector('h1')?.textContent).toBe('See your website the way an agent does.');
    const hrefs = [...host.querySelectorAll('a')].map(a => a.getAttribute('href'));
    for (const h of ['#/run', '#/lifecycle', '#/showcase', `#/reports/${CANONICAL.id}`]) expect(hrefs).toContain(h);
    for (const h of hrefs) expect(h ?? '').not.toMatch(/#\/(studio|demo\/|investigation|overview|replay|scopes|evidence$|scanner)/);   // no archive links anywhere (footer included)
    for (const h of hrefs.filter(h => h?.startsWith('#/reports/'))) expect(h).toBe(`#/reports/${CANONICAL.id}`);   // one evaluation: no separate-run or latest links
    const text = host.textContent!;
    for (const s of ['39', '10', '74% fewer after the change', '0/3', '3/3', '326 s → 57 s, 83% less', 'US$0.571 → US$0.134, 77% less', 'weekend task: 1/4 → 4/4 courses found',
                     '1 of 4 courses found', 'All 4 courses found', QUALIFIER, 'Larkspur Community College', 'Measured live', 'Original website', 'Agent-ready website',
                     'View full paired evaluation report', ...AFTER_CHANGES.map(i => i.title)]) expect(text).toContain(s);
    const toShowcase = [...host.querySelectorAll('main a[href="#/showcase"]')].map(a => a.textContent!.replace('→', '').trim());
    expect(toShowcase.length).toBeGreaterThan(0); for (const t of toShowcase) expect(t).toBe('Explore an earlier evaluation');   // the historical runs, named as such
    expect(text).not.toContain('Watch before and after');
    const O = BEFORE.totals.polishedoriginal, M = AFTER.totals.modifiedpolished;
    for (const s of [`${O.requests} → ${M.requests}`, `${O.seconds} s → ${M.seconds} s`, '58%', 'latest']) expect(text).not.toContain(s);   // never the separate historical runs
    expect(text).toContain(PAIRED.journeys['polishedoriginal-2'].steps.at(-1)!.memory!);          // the agent's own words, unedited
    expect(text).not.toMatch(/[Pp]olished|Original(?! website)|Improved|Modified|Ironbark|Earlier|earlier experiment|Archive|\bBefore ·|\bAfter ·/);   // audience labels only
    const prose = PAIRED.journeys['polishedoriginal-2'].steps.reduce((t, s) => t.replaceAll(s.memory ?? '\u0000', ''), text);   // minus the agent's own quoted words
    for (const s of ['post-hoc', 'inconclusive', 'p =', 'xploratory', 'verified', 'pre-registered']) expect(prose).not.toContain(s);
    expect(host.querySelector('main')!.textContent).not.toContain('Ironbark');
    expect(f).not.toHaveBeenCalled();
  });
  it('the recorded showcase numbers are internally consistent with the per-agent records', () => {
    expect(LIVE.id).toBe('eval-c04fdb100d6b1c877de96dabe76eb052');                                   // the earlier experiment: Original vs Improved, live
    expect(LIVE.trials).toHaveLength(6); expect(FIRST_LIVE.trials).toHaveLength(12);
    for (const [run, vs] of [[LIVE, ['original', 'improved']], [FIRST_LIVE, ['original', 'modified']], [BEFORE, ['polishedoriginal']], [AFTER, ['modifiedpolished']]] as const) for (const v of vs) {
      const ts = run.trials.filter(t => t.variant === v);
      expect(ts.reduce((a, t) => a + t.requests, 0)).toBe(run.totals[v].requests);
      expect(ts.filter(t => t.correct).length).toBe(run.correct[v]);
      expect(ts.filter(t => t.passed).length).toBe(run.passed[v]);
    }
    expect([LIVE.correct.original, LIVE.correct.improved, LIVE.totals.original.requests, LIVE.totals.improved.requests]).toEqual([0, 3, 39, 6]);
    expect([BEFORE.correct.polishedoriginal, AFTER.correct.modifiedpolished, BEFORE.totals.polishedoriginal.requests, AFTER.totals.modifiedpolished.requests]).toEqual([0, 3, 36, 15]);
    expect(LIVE.cost_usd).toBeCloseTo(LIVE.totals.original.cost_usd + LIVE.totals.improved.cost_usd, 4);
    // the canonical paired evaluation: ONE job with both versions; the figures quoted for the submission
    expect(PAIRED.id).toBe(CANONICAL.id); expect(LATEST_LIVE.id).toBe(CANONICAL.id);
    for (const v of ['polishedoriginal', 'modifiedpolished']) { const ts = PAIRED.trials.filter(t => t.variant === v);
      expect(ts).toHaveLength(3); expect(ts.reduce((a, t) => a + t.requests, 0)).toBe(PAIRED.totals[v].requests); expect(ts.filter(t => t.correct).length).toBe(PAIRED.correct[v]); }
    const [o, m] = [PAIRED.totals.polishedoriginal, PAIRED.totals.modifiedpolished];
    expect([PAIRED.correct.polishedoriginal, PAIRED.correct.modifiedpolished, o.requests, m.requests, o.seconds, m.seconds]).toEqual([0, 3, 39, 10, 326, 57]);
    expect([o.cost_usd.toFixed(3), m.cost_usd.toFixed(3)]).toEqual(['0.571', '0.134']);
    expect([PAIRED.journeys['polishedoriginal-2'].answer.length, PAIRED.journeys['modifiedpolished-2'].answer.length]).toEqual([1, 4]);   // weekend courses: 1/4 -> 4/4
    for (const x of IMPROVEMENTS) if (x.preview) expect(existsSync(join(__dirname, 'showcase', 'frames', `${x.preview}.webp`))).toBe(true);
    for (const v of ['polishedoriginal', 'modifiedpolished']) expect(existsSync(join(__dirname, 'showcase', 'frames', `site-${v}-courses.webp`))).toBe(true);
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
