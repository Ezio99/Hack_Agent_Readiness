// @vitest-environment jsdom
/** Regression tests for the public experience: ONLY the final Larkspur Before -> After experiment is listed, selected or rendered; earlier
 *  experiments (Ironbark, Original vs Improved, the superseded redesign trials) never appear; the Workspace's job selection stays consistent; the
 *  journey's chapter bar follows the reader's scroll position. */
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { HostedEvaluation, defaultRun, isPublicItem, isPublicJob } from './workspace/HostedEvaluation';
import type { HistoryItem } from './workspace/History';
import { EvidenceNote, LatestReportPage, ReportPage, isPublicEvaluation } from './lifecycle/Report';
import { Lifecycle, activeStep } from './lifecycle/Lifecycle';
import { Story } from './story/Story';
import { PUBLIC_SCOPE } from '../lib/lifecycleApi';
import { AFTER, BEFORE, CANONICAL, JOURNEY, LIVE } from './showcase';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); localStorage.clear(); document.body.innerHTML = ''; window.location.hash = ''; });

const json = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body });
async function mount(node: React.ReactNode) {
  const host = document.createElement('div'); document.body.append(host);
  await act(async () => { createRoot(host).render(node); });
  for (let i = 0; i < 6; i++) await act(async () => { await new Promise(r => setTimeout(r, 0)); });
  return host;
}
const arm = { planned: 3, completed: 3, failed: 0, evidence_supported_passes: 1, strict_passes: 1, requests_total: 15, requests_mean: 5, page_views_mean: 5, steps_mean: 6, elapsed_mean: 40 };
const item = (id: string, display: Record<string, string> | null, created: number, extra: Partial<HistoryItem> = {}): HistoryItem => ({ id, engine: 'stage-b', state: 'completed', execution_state: 'completed',
  repetitions: 1, mode: 'live', created_at: created, summary: { Original: arm }, arm_display: display as HistoryItem['arm_display'], runs_per_repetition: 3, ...extra });
const OLD = 'eval-c04fdb100d6b1c877de96dabe76eb052', IRON = 'eval-9aaac35c' + '0'.repeat(19), TRIAL = 'eval-abc5fc838a5428b6753a424e189ba1cc';
const PAIR = 'eval-' + 'c'.repeat(32);
const SINGLES = [item(OLD, { Original: 'Original', Modified: 'Improved' }, 100), item(IRON, null, 50, { engine: undefined }), item(TRIAL, { Original: 'Earlier trial A' }, 200),
  item(BEFORE.id, { Original: 'Before' }, 300), item(AFTER.id, { Original: 'After' }, 400)];
const LIST = [...SINGLES, item(PAIR, { Original: 'Before', Modified: 'After' }, 450)];
const job = (id: string, variants: string[], label: string) => ({ id, engine: 'stage-b', state: 'completed', mode: 'live', repetitions: 1, created_at: 1, started_at: 1, finished_at: 2,
  execution: { state: 'completed', trials_planned: 3, trials_completed: 3, trials_failed: 0, trials_void: 0 }, report_status: { state: 'pending' }, evaluation: { frozen_suite: 'larkspur-core@v3', variants, repetitions: 1 },
  arm_display: { Original: label }, reps: [{ index: 1, state: 'completed', assessment: null, tasks: [{ arm: 'Original', task: 1, state: 'completed', outcome: 'evidence_supported_pass', requests: 6, page_views: 6, steps: 6, elapsed_seconds: 48, correct: true, exact_match: false }] }],
  summary: { Original: arm } });
const config = { engine: 'stage-b', available: true, mode: 'live', access: 'operator', judge_access: true, repetitions: [1], remaining_repetitions: 1, active: null, worker: { state: 'idle' },
  tasks: [1, 2, 3].map(n => ({ task: n, question: `Question ${n}?`, limits: { max_model_requests: 14 } })),
  evaluation: { site: 'larkspur', frozen_suite: 'larkspur-core@v3', frozen_suite_sha256: 'a'.repeat(64), variants: ['polishedoriginal', 'modifiedpolished'], mode: 'paid', launches: null, options: [{ repetitions: 1, trials: 6, reservation_usd: 3.74 }],
    agent: { model: 'muse-spark-1.3', reasoning_effort: 'low', max_completion_tokens: 4096, profile: 'suite-v2-compat2' } } };
function workspaceServer(list: HistoryItem[], jobs: Record<string, unknown>) {
  const f = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === 'POST') return json({ detail: 'no' }, 403);
    if (url.endsWith('/api/ironbark/config')) return json(config);
    if (url.endsWith('/api/ironbark/jobs')) return json(list);
    const m = url.match(/\/api\/ironbark\/jobs\/(eval-[0-9a-f]+)$/); if (m && jobs[m[1]]) return json(jobs[m[1]]);
    return json({ detail: 'Not found' }, 404);
  });
  vi.stubGlobal('fetch', f); return f;
}

describe('public scope', () => {
  it('is the final Larkspur experiment only (deployed default)', () => {
    expect(PUBLIC_SCOPE.versions && [...PUBLIC_SCOPE.versions].sort()).toEqual(['modifiedpolished', 'polishedoriginal']);
    expect(LIST.filter(isPublicItem).map(i => i.id)).toEqual([BEFORE.id, AFTER.id, PAIR]);
    expect(isPublicJob({ evaluation: { variants: ['modifiedpolished'] } })).toBe(true);
    expect(isPublicJob({ evaluation: { variants: ['polishedoriginal', 'modifiedpolished'] } })).toBe(true);
    for (const v of [['original', 'improved'], ['polished'], ['polished2'], ['original', 'modified'], ['original', 'modifiedpolished'], []]) expect(isPublicJob({ evaluation: { variants: v } })).toBe(false);
    expect(defaultRun(LIST.filter(isPublicItem))!.id).toBe(PAIR);                                             // the newest completed PAIRED evaluation
    expect(defaultRun(SINGLES.filter(isPublicItem))).toBeNull();                                               // never a single-version run as "the" result
    expect(defaultRun(LIST.filter(isPublicItem), BEFORE.id)!.id).toBe(BEFORE.id);                             // a running public evaluation wins
  });

  it('the Workspace lists only final-experiment runs and opens the latest paired Before vs After run by default (never an old job)', async () => {
    localStorage.setItem('ironbark-hosted-job', OLD);                                                       // a stale selection from an earlier visit is ignored
    const f = workspaceServer(LIST, { [PAIR]: { ...job(PAIR, ['polishedoriginal', 'modifiedpolished'], 'Before'), arm_display: { Original: 'Before', Modified: 'After' } }, [OLD]: job(OLD, ['original', 'improved'], 'Original') });
    const host = await mount(<HostedEvaluation onOpen={() => {}} />);
    const fetched = f.mock.calls.map(c => String(c[0]));
    expect(fetched.some(u => u.endsWith(`/jobs/${PAIR}`))).toBe(true);
    expect(fetched.some(u => u.endsWith(`/jobs/${OLD}`))).toBe(false);
    expect(host.querySelector('.ws-job')?.getAttribute('aria-label')).toBe(`Evaluation ${PAIR.slice(0, 13)}`);
    expect(host.querySelector('.ws-version')?.textContent).toContain('Before vs After');
    const rows = [...host.querySelectorAll('.history-table tbody tr')].map(r => r.textContent ?? '');
    expect(rows).toHaveLength(3);
    expect(rows.join(' ')).not.toMatch(/Original|Improved|Earlier|eval-c04f|eval-9aaa|eval-abc5/);
    expect(f.mock.calls.some(c => (c[1] as RequestInit | undefined)?.method === 'POST')).toBe(false);
  });

  it('without a paired run, nothing is opened and the recorded Before and After evidence is linked', async () => {
    workspaceServer(SINGLES, { [AFTER.id]: job(AFTER.id, ['modifiedpolished'], 'After') });
    const host = await mount(<HostedEvaluation onOpen={() => {}} />);
    expect(host.querySelector('.ws-job')).toBeNull();
    expect(host.textContent).toContain('Run the first side-by-side evaluation of Before and After');
    for (const id of [BEFORE.id, AFTER.id]) expect(host.querySelector(`a[href="#/reports/${id}"]`)).not.toBeNull();
  });

  it('an old job URL shows a notice, never its data, and offers the latest public run', async () => {
    workspaceServer(LIST, { [OLD]: job(OLD, ['original', 'improved'], 'Original') });
    const host = await mount(<HostedEvaluation onOpen={() => {}} initialJob={OLD} />);
    expect(host.textContent).toContain('not part of the current Larkspur Community College experiment');
    expect(host.querySelector('.ws-job')).toBeNull();
    expect([...host.querySelectorAll('button')].some(b => b.textContent?.includes('Open the latest evaluation'))).toBe(true);
  });

  it('follows a new paired run (live while it runs) while the visitor has not chosen one', async () => {
    const NEW = 'eval-' + 'f'.repeat(32);
    let list = LIST, cfg: any = config;
    const pairJob = (id: string) => ({ ...job(id, ['polishedoriginal', 'modifiedpolished'], 'Before'), arm_display: { Original: 'Before', Modified: 'After' } });
    const jobs: Record<string, unknown> = { [PAIR]: pairJob(PAIR), [NEW]: { ...pairJob(NEW), state: 'running' } };
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url.endsWith('/config') ? json(cfg) : url.endsWith('/api/ironbark/jobs') ? json(list)
      : jobs[url.split('/').pop()!] ? json(jobs[url.split('/').pop()!]) : json({ detail: 'x' }, 404)));
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    const flush = async () => { for (let i = 0; i < 6; i++) await act(async () => { await new Promise(r => setTimeout(r, 0)); }); };
    try {
      const host = await mount(<HostedEvaluation onOpen={() => {}} />);
      expect(host.querySelector('.ws-job')?.getAttribute('aria-label')).toBe(`Evaluation ${PAIR.slice(0, 13)}`);
      cfg = { ...config, active: NEW, worker: { state: 'busy', job: NEW } };                                // someone starts a new paired run
      list = [...LIST, item(NEW, { Original: 'Before', Modified: 'After' }, 500, { state: 'running', execution_state: 'running' })];
      await act(async () => { vi.advanceTimersByTime(31_000); }); await flush();
      await act(async () => { vi.advanceTimersByTime(11_000); }); await flush();
      expect(host.querySelector('.ws-job')?.getAttribute('aria-label')).toBe(`Evaluation ${NEW.slice(0, 13)}`);   // shown live, then kept when it completes
    } finally { vi.useRealTimers(); }
  });

  it('reports of earlier experiments are not shown on the public site (a notice; the record stays reachable for audit)', async () => {
    const ev = (variants: string[]) => ({ id: 'x', title: 'Live evaluation · Larkspur Community College · Original vs Improved', mode: 'paid', site: { id: 'larkspur', label: 'Larkspur Community College' },
      manifest: { variants: variants.map(name => ({ name, snapshot_sha256: 'a'.repeat(64) })) } });
    expect(isPublicEvaluation(ev(['polishedoriginal']) as any)).toBe(true);
    expect(isPublicEvaluation(ev(['original', 'improved']) as any)).toBe(false);
    vi.stubGlobal('fetch', vi.fn(async () => json(ev(['original', 'improved']))));
    const host = await mount(<ReportPage id={OLD} />);
    expect(host.textContent).toContain('not part of the current Larkspur Community College experiment');
    expect(host.querySelector('.lc-report')).toBeNull();
    expect(host.querySelector(`a[href="#/reports/${BEFORE.id}"]`)).not.toBeNull();
  });

  it('Live report opens the latest genuine paired evaluation; before one exists it shows the two separate runs as two runs', async () => {
    const row = (id: string, variants: string[], started: string, extra = {}) => ({ id, title: id, mode: 'paid', state: 'completed', source: 'launched', site: 'Larkspur Community College', site_id: 'larkspur',
      variants, started_at: started, tasks: 3, trials: 3 * variants.length, ...extra });
    const singles = [row(BEFORE.id, ['polishedoriginal'], '2026-11-03T23:31:00Z'), row(AFTER.id, ['modifiedpolished'], '2026-11-03T23:42:00Z'), row(OLD, ['original', 'improved'], '2026-11-03T03:00:00Z')];
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url.endsWith('/api/lifecycle/evaluations') ? json(singles) : json({ detail: 'x' }, 404)));
    let host = await mount(<LatestReportPage />);
    expect(host.textContent).toContain('two separate live runs');
    expect(host.querySelector('.lc-report')).toBeNull();                                                       // never a fake paired report
    for (const id of [BEFORE.id, AFTER.id]) expect(host.querySelector(`a[href="#/reports/${id}"]`)).not.toBeNull();
    expect(host.textContent).toContain(BEFORE.id.slice(5, 13)); expect(host.textContent).toContain(AFTER.id.slice(5, 13));   // genuine run ids
    document.body.innerHTML = '';
    const PAIRED = 'eval-' + '7'.repeat(32), NEWER_REHEARSAL = 'eval-' + '8'.repeat(32);
    const list = [...singles, row(PAIRED, ['polishedoriginal', 'modifiedpolished'], '2026-11-05T00:00:00Z'),
      row(NEWER_REHEARSAL, ['polishedoriginal', 'modifiedpolished'], '2026-11-05T01:00:00Z', { mode: 'rehearsal' })];
    const f = vi.fn(async (url: string) => url.endsWith('/api/lifecycle/evaluations') ? json(list) : json({ detail: 'x' }, 404));
    vi.stubGlobal('fetch', f);
    host = await mount(<LatestReportPage />);
    expect(f.mock.calls.some(c => String(c[0]).endsWith(`/api/lifecycle/evaluations/${PAIRED}`))).toBe(true);   // the live paired run, not the rehearsal
    expect(f.mock.calls.some(c => String(c[0]).endsWith(`/api/lifecycle/evaluations/${NEWER_REHEARSAL}`))).toBe(false);
  });

  it('every public report says which evidence it is: the canonical paired evaluation, or another run that points to it', async () => {
    let host = await mount(<EvidenceNote id={CANONICAL.id} />);
    expect(host.textContent).toContain('Canonical evaluation.'); expect(host.querySelector('a')).toBeNull();
    for (const id of [BEFORE.id, AFTER.id, 'eval-' + '7'.repeat(32)]) {
      document.body.innerHTML = ''; host = await mount(<EvidenceNote id={id} />);
      expect(host.textContent).not.toContain('Canonical evaluation.');
      expect(host.textContent).toContain(id === 'eval-' + '7'.repeat(32) ? 'Another live evaluation' : 'two separate live runs');
      expect(host.querySelector(`a[href="#/reports/${CANONICAL.id}"]`)).not.toBeNull();
    }
  });

  it('the showcase tells only the Before -> After story (no earlier experiments)', async () => {
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('reduce'), media: q, addEventListener() {}, removeEventListener() {} }));
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('no network'); }));
    const host = await mount(<Story />);
    const main = host.querySelector('main')!.textContent!;
    expect(main).not.toMatch(/Original|Improved|Earlier|Ironbark|trial/);
    expect(host.querySelector(`a[href="#/reports/${LIVE.id}"]`)).toBeNull();
  });
});

describe('journey chapter bar (scroll spy)', () => {
  /** Lay out the eight sections 1000 px apart, offset by the current scroll position, and report the page height. */
  function layout(scrollY: number) {
    Object.defineProperty(window, 'scrollY', { value: scrollY, configurable: true });
    Object.defineProperty(window, 'innerHeight', { value: 900, configurable: true });
    Object.defineProperty(document.documentElement, 'scrollHeight', { value: 9000, configurable: true });
    vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (this: Element) {
      const id = (this as HTMLElement).id; const i = JOURNEY.findIndex(s => `lc-${s.id}` === id);
      const top = i >= 0 ? 600 + i * 1000 - scrollY : this.classList.contains('site-head') ? 0 : 64;
      return { top, bottom: top + (i >= 0 ? 1000 : 64), left: 0, right: 1000, width: 1000, height: i >= 0 ? 1000 : 64, x: 0, y: top, toJSON() {} } as DOMRect;
    });
  }
  const current = (host: HTMLElement) => host.querySelector('.lc-stepper a[aria-current=step]')?.getAttribute('href');

  it('follows manual scrolling forward, backward and rapidly, and reaches the last chapter at the end of the page', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json({ detail: 'x' }, 404)));
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => { cb(0); return 0; });
    layout(0);
    const host = await mount(<Lifecycle />);
    expect(current(host)).toBe('#/lifecycle/website');
    for (const [y, id] of [[4550, 'recommendations'], [600, 'website'], [1550, 'tasks'], [7600, 'compare'], [2600, 'review'], [3550, 'evaluate']] as const) {   // section i passes the line (64 + 24 px) at y >= 512 + 1000 i
      vi.restoreAllMocks(); layout(y);
      await act(async () => { window.dispatchEvent(new Event('scroll')); });
      expect(current(host)).toBe(`#/lifecycle/${id}`);
      expect(activeStep()).toBe(id);
    }
    vi.restoreAllMocks(); layout(8100);                                                                         // bottom of the page
    await act(async () => { window.dispatchEvent(new Event('scroll')); });
    expect(current(host)).toBe('#/lifecycle/compare');
  });

  it('a chapter click scrolls below the sticky header and chapter bar and marks that chapter', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json({ detail: 'x' }, 404)));
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => { cb(0); return 0; });
    const to = vi.fn(); vi.stubGlobal('scrollTo', to); window.scrollTo = to as any;
    layout(0);
    const host = await mount(<Lifecycle step="improve" />);
    expect(current(host)).toBe('#/lifecycle/improve');
    const target = to.mock.calls.at(-1)![0] as ScrollToOptions;
    expect(target.top).toBe(600 + 5 * 1000 - 64 - 12);                                                      // section top - header - margin (bar not sticky in jsdom)
    window.location.hash = '#/lifecycle/improve';
    await act(async () => { (host.querySelector('.lc-stepper a[href="#/lifecycle/improve"]') as HTMLAnchorElement).click(); });   // the same chapter again
    expect(current(host)).toBe('#/lifecycle/improve');
    expect(to.mock.calls.length).toBeGreaterThan(1);
  });
});
