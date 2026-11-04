// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi, beforeAll, afterAll } from 'vitest';
import { TrialView, type Trial } from './workspace/LiveAgent';
import { HostedEvaluation, type Job } from './workspace/HostedEvaluation';
import { Demo } from './demo/Demo';
import { trial } from './evidence';
import { PUBLIC_SCOPE } from '../lib/lifecycleApi';
// These tests exercise the mechanics with fixtures of earlier evaluations: the public scope (final Larkspur experiment only) is lifted here and
// tested on its own in public-scope.test.tsx.
const SCOPE = PUBLIC_SCOPE.versions; beforeAll(() => { PUBLIC_SCOPE.versions = null; }); afterAll(() => { PUBLIC_SCOPE.versions = SCOPE; });
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement, root: Root;
beforeEach(() => { host = document.createElement('div'); document.body.append(host); root = createRoot(host); window.scrollTo = vi.fn() as any; });
afterEach(() => { act(() => root.unmount()); host.remove(); vi.unstubAllGlobals(); sessionStorage.clear(); localStorage.clear(); });
const btn = (label: string) => [...host.querySelectorAll('button')].find(b => b.getAttribute('aria-label') === label || b.textContent === label) as HTMLButtonElement;

const t: Trial = { repetition: 1, arm: 'original', task: 1, state: 'completed', question: 'Which machine?', current: null, errors: [], steps: [1, 2, 3].map(n => ({
  step: n, path: '/hire', title: null, screenshot: `step-00${n}.png`, assessment: `assessed ${n}`, memory: `memory ${n}`, goal: `goal ${n}`,
  actions: [{ name: n === 3 ? 'Answer' : 'Click', target: n === 3 ? 'Scissor lift' : `link ${n}` }], error: null, done: n === 3 })) };

it('agent view: step bar, arrow keys and the compact timeline all drive the same selected step', () => {
  act(() => root.render(<TrialView jobId="eval-x" trial={t} live={false} scripted={false} />));
  const img = () => host.querySelector('.ws-browser img')!.getAttribute('src')!;
  expect(img()).toMatch(/step-003\.png$/);                       // latest by default
  act(() => btn('Previous step').click());
  expect(img()).toMatch(/step-002\.png$/);
  expect(host.querySelector('.ws-stepbar')!.textContent).toContain('Step 2');
  expect(host.querySelector('[aria-current="step"]')!.textContent).toContain('link 2');
  act(() => { host.querySelector('.agent-steps ol')!.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true })); });
  expect(img()).toMatch(/step-001\.png$/);
  expect(btn('Previous step').disabled).toBe(true);
  act(() => { host.querySelector('.agent-steps ol')!.dispatchEvent(new KeyboardEvent('keydown', { key: 'End', bubbles: true })); });
  expect(btn('Next step').disabled).toBe(true);
  expect(host.textContent).toContain('goal 1');
  act(() => btn('Compact').click());
  expect(host.querySelector('.ws-timeline')!.classList.contains('compact')).toBe(true);
  expect(sessionStorage.getItem('ar-ws-timeline-details')).toBe('compact');
});

it('focus mode hides the evaluation controls for evidence inspection and Esc restores them', async () => {
  const id = 'eval-' + 'f'.repeat(32);
  const job: Job = { id, state: 'completed', mode: 'live', repetitions: 1, created_at: 1, started_at: 1, finished_at: 2,
    reps: [{ index: 1, state: 'completed', assessment: null, tasks: [{ arm: 'Original', task: 1, state: 'completed', outcome: 'not_passed', requests: 3, page_views: 3, steps: 3, elapsed_seconds: 9 }] }],
    summary: { Original: { planned: 4, completed: 1, failed: 0, evidence_supported_passes: 0, strict_passes: 0, requests_total: 3, requests_mean: 3, page_views_mean: 3, steps_mean: 3, elapsed_mean: 9 },
      Modified: { planned: 4, completed: 0, failed: 0, evidence_supported_passes: 0, strict_passes: 0, requests_total: 0, requests_mean: null, page_views_mean: null, steps_mean: null, elapsed_mean: null } } };
  const f = vi.fn(async (url: string, _init?: RequestInit) => ({ ok: true, json: async () => url.endsWith('/config') ? { available: false, mode: null, repetitions: [1, 3, 5], model: 'm', agent_profile: 'p', tasks: [], remaining_repetitions: 0, active: null }
    : url.endsWith('/jobs') ? [] : url.includes('/trials/') ? t : job }));
  vi.stubGlobal('fetch', f);
  await act(async () => { root.render(<HostedEvaluation onOpen={() => {}} initialJob={id} />); });
  await act(async () => {});
  await act(async () => { host.querySelectorAll<HTMLButtonElement>('[role=tab]')[0].click(); });
  await act(async () => { btn('Watch Original task 1, repetition 1: Not passed').click(); });
  await act(async () => {});
  const layout = () => host.querySelector('.ws-layout')!;
  expect(host.querySelector('.ws-jobbar [role=tablist]')).toBeTruthy();        // tabs live in the sticky job bar
  await act(async () => btn('Focus evidence').click());
  expect(layout().classList.contains('focus')).toBe(true);
  expect(btn('Exit focus').getAttribute('aria-pressed')).toBe('true');
  await act(async () => { window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })); });
  expect(layout().classList.contains('focus')).toBe(false);
  expect(f.mock.calls.some(c => c[1]?.method === 'POST')).toBe(false);
});

it('demo change scene: recorded close-up, labelled fields, then the same card side by side', () => {
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('reduce'), media: q, addEventListener() {}, removeEventListener() {} }));
  act(() => root.render(<Demo />));
  const change = host.querySelector('#change')!;
  expect(change.querySelector('.ch-close img')!.getAttribute('alt')).toContain('Refundable deposit: $100');
  expect([...change.querySelectorAll('.ch-labels li')].map(l => l.textContent)).toEqual(['Refundable deposit', 'Minimum hire', 'Delivery and collection']);
  const crops = [...change.querySelectorAll('.ch-compare .crop img')];
  expect(crops).toHaveLength(2);
  expect(change.textContent).toContain('Original: task 1, step 3 · Modified: task 2, step 3');
  // both crops come from the recorded frames of this evaluation
  const frames = [trial('original', 1).steps[2].frame, trial('modified', 2).steps[2].frame];
  crops.forEach((img, i) => expect(img.getAttribute('src')).toContain(frames[i]!));
});

it('demo chapters: one active chapter, named in the header, earlier chapters marked done', () => {
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} }));
  act(() => root.render(<Demo />));
  const items = [...host.querySelectorAll('.rail li')];
  const active = items.findIndex(li => li.classList.contains('active'));
  expect(active).toBeGreaterThanOrEqual(0);
  expect(items.filter(li => li.classList.contains('active'))).toHaveLength(1);
  items.slice(0, active).forEach(li => expect(li.classList.contains('done')).toBe(true));
  expect(items[active].querySelector('a')!.getAttribute('aria-current')).toBe('true');
  expect(host.querySelector('.demo-chapter strong')!.textContent).toBe(items[active].querySelector('.rail-label')!.textContent);
});
