import { useEffect, useState } from 'react';

/** Hash routes. The hosted server serves a single static index.html, so every route lives after `#`.
 *  Persistent evaluation URLs (`#/run/eval-<32 hex>`) are unchanged from the previous release. */
export type Route =
  | { name: 'home'; section?: string }
  | { name: 'demo'; scene?: string }
  | { name: 'run'; job: string | null }
  | { name: 'lifecycle'; step?: string; suite?: string; job?: string }
  | { name: 'report'; id: string; task?: number }
  | { name: 'studio' }
  | { name: 'classic'; page: string };

export const CLASSIC = ['investigation', 'overview', 'scopes', 'evidence', 'replay', 'scanner'] as const;
export const HOME_SECTIONS = ['problem', 'how', 'learn', 'evidence', 'trust'] as const;

export const LIFECYCLE_STEPS = ['website', 'tasks', 'review', 'evaluate', 'report', 'reevaluate'] as const;

export function parse(hash: string): Route {
  const h = hash.replace(/^#\/?/, '');
  const lc = h.match(/^lifecycle(?:\/([a-z]+))?$/);
  if (lc && (!lc[1] || (LIFECYCLE_STEPS as readonly string[]).includes(lc[1]))) return { name: 'lifecycle', step: lc[1] };
  const suite = h.match(/^lifecycle\/suites\/([0-9a-f]{64})$/);
  if (suite) return { name: 'lifecycle', step: 'review', suite: suite[1] };
  const lj = h.match(/^lifecycle\/jobs\/(lc-[0-9a-f]{32})$/);
  if (lj) return { name: 'lifecycle', step: 'evaluate', job: lj[1] };
  const rep = h.match(/^reports\/([a-z0-9][a-z0-9-]{2,60}|lc-[0-9a-f]{32})(?:\/tasks\/(\d{1,2}))?$/);
  if (rep) return { name: 'report', id: rep[1], task: rep[2] ? Number(rep[2]) : undefined };
  const run = h.match(/^run(?:\/(eval-[0-9a-f]{32}))?$/);
  if (run) return { name: 'run', job: run[1] ?? null };
  const demo = h.match(/^demo(?:\/([a-z-]+))?$/);
  if (demo) return { name: 'demo', scene: demo[1] };
  if (h === 'studio') return { name: 'studio' };
  if ((CLASSIC as readonly string[]).includes(h)) return { name: 'classic', page: h };
  if ((HOME_SECTIONS as readonly string[]).includes(h)) return { name: 'home', section: h };
  return { name: 'home' };
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parse(window.location.hash));
  useEffect(() => {
    const on = () => setRoute(parse(window.location.hash));
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);
  return route;
}

export const reducedMotion = () => typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

export function useReducedMotion(): boolean {
  const [reduce, setReduce] = useState(reducedMotion);
  useEffect(() => {
    const m = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    if (!m) return;
    const on = () => setReduce(m.matches);
    m.addEventListener?.('change', on);
    return () => m.removeEventListener?.('change', on);
  }, []);
  return reduce;
}
