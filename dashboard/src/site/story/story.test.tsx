// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import data from '../showcase/larkspur.json';
import { parse } from '../router';
import { Story } from './Story';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement, root: Root;
beforeEach(() => { host = document.createElement('div'); document.body.append(host); root = createRoot(host); window.scrollTo = vi.fn() as any; });
afterEach(() => { act(() => root.unmount()); host.remove(); vi.unstubAllGlobals(); });
const reducedMotion = (on: boolean) => vi.stubGlobal('matchMedia', (q: string) => ({ matches: on && q.includes('reduce'), media: q, addEventListener() {}, removeEventListener() {} }));

describe('the cinematic showcase (#/showcase): Before -> After', () => {
  it('is its own route, separate from the functional journey', () => {
    expect(parse('#/showcase')).toEqual({ name: 'showcase' });
    expect(parse('#/demo')).toEqual({ name: 'demo', scene: undefined });
  });

  it('states the recorded Before and After results, never internal snapshot names, and calls no API', () => {
    reducedMotion(true);
    const f = vi.fn(async () => { throw new Error('no network expected'); }); vi.stubGlobal('fetch', f);
    act(() => root.render(<Story />));
    const text = host.textContent ?? '';
    const b = (data as any).before, a = (data as any).after;
    expect(b.id).toBe('eval-ea13944e8ba5c08e8893426b2f8b1c8f');
    expect(a.id).toBe('eval-5cf934b372942da74f5157c5fca39fd6');
    const table = [...host.querySelectorAll('.st-table tbody tr')].map(r => [...r.children].map(c => c.textContent));
    expect(table).toContainEqual(['Correct answers', `${b.correct.polishedoriginal}/3`, `${a.correct.modifiedpolished}/3`]);
    expect(table).toContainEqual(['Model requests', String(b.totals.polishedoriginal.requests), String(a.totals.modifiedpolished.requests)]);
    expect(table).toContainEqual(['Actual cost', `US$${b.totals.polishedoriginal.cost_usd.toFixed(2)}`, `US$${a.totals.modifiedpolished.cost_usd.toFixed(2)}`]);
    const last = b.journeys['polishedoriginal-2'].steps.at(-1);
    expect(text).toContain(last.memory);                                              // the agent's own recorded words
    expect(text).not.toMatch(/polished|Polished|v1|v2 /);                             // no internal names on the page
    expect(f).not.toHaveBeenCalled();
    const spec = host.querySelector('.st-spec')!.textContent!;                         // one understated line of the recorded limits, identical for both runs
    expect(spec).toBe('3 customer tasks · 1 agent each · max 14 requests/steps per agent · US$1.89 (A$2.84) cap per evaluation, within the A$20 budget · same limits on both websites');
    expect([...b.trials, ...a.trials].every((t: any) => t.limit === 14)).toBe(true);
    for (const img of host.querySelectorAll('img')) expect(img.getAttribute('alt')).toBeTruthy();
  });
});
