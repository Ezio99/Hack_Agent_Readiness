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

describe('the cinematic Larkspur showcase (#/showcase)', () => {
  it('is its own route, separate from the functional journey', () => {
    expect(parse('#/showcase')).toEqual({ name: 'showcase' });
    expect(parse('#/demo')).toEqual({ name: 'demo', scene: undefined });
  });

  it('states the recorded numbers of both live evaluations and the measured outcome, calling no API', () => {
    reducedMotion(true);
    const f = vi.fn(async () => { throw new Error('no network expected'); }); vi.stubGlobal('fetch', f);
    act(() => root.render(<Story />));
    const text = host.textContent ?? '';
    const v1 = (data as any).polished_v1, v2 = (data as any).polished_v2;
    expect(v1.id).toBe('eval-abc5fc838a5428b6753a424e189ba1cc');
    expect(v2.id).toBe('eval-11ee8a1e6dad19998865db7187c8cb5e');
    expect(text).toContain('v2 did not beat v1.');
    const table = [...host.querySelectorAll('.st-table tbody tr')].map(r => [...r.children].map(c => c.textContent));
    expect(table).toContainEqual(['Model requests', String(v1.totals.polished.requests), String(v2.totals.polished2.requests)]);
    expect(table).toContainEqual(['Correct answers', `${v1.correct.polished}/3`, `${v2.correct.polished2}/3`]);
    expect(table).toContainEqual(['Actual cost', `US$${v1.totals.polished.cost_usd.toFixed(2)}`, `US$${v2.totals.polished2.cost_usd.toFixed(2)}`]);
    // the friction quote is the agent's own recorded memory
    const step3 = v1.journeys['polished-2'].steps.find((s: any) => s.step === 3);
    expect(text).toContain(step3.memory);
    expect(f).not.toHaveBeenCalled();
    // every image has alt text and a recorded source
    for (const img of host.querySelectorAll('img')) expect(img.getAttribute('alt')).toBeTruthy();
  });
});
