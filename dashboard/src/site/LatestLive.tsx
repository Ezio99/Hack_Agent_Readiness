import './latest-live.css';

/** I3 (M9): the latest live evaluation, as recorded. The home page and the demo deliberately call no API (they must render without the service),
 *  so this is a recorded constant, not a query. Source: the production report of eval-e529db2aafecbfddd21e5c571eb85243 (launched in the product
 *  2026-11-02 23:38 UTC = 3 Nov 2026 AEDT; 12/12 agent runs finished; official grader v1 and post-hoc grader v2 as recorded; immutable). */
export const LATEST_LIVE = {
  id: 'eval-e529db2aafecbfddd21e5c571eb85243',
  date: '3 Nov 2026',
  site: 'Larkspur Community College',
  suite: 'larkspur-core v2',
  runs: 12,
  of: 6,
  official: { original: 1, modified: 2 },
  postHoc: { original: 2, modified: 4 },
} as const;

/** A prominent link to the complete live evaluation (all six tasks; judges' shorter live runs appear in the workspace history), beside (not instead of) the earlier Ironbark story. Read-only: it only links to the report. */
export function LatestLive({ className = '' }: { className?: string }) {
  const e = LATEST_LIVE;
  return <a className={`latest-live ${className}`} href={`#/reports/${e.id}`}>
    <span className="latest-live-eyebrow">Complete live evaluation · all six tasks · {e.date}</span>
    <strong>{e.site} · {e.suite} · Original vs Modified</strong>
    <span>{e.runs} agent runs finished with a real model · official grader v1: {e.official.original}/{e.of} → {e.official.modified}/{e.of} passed · post-hoc grader v2: {e.postHoc.original}/{e.of} → {e.postHoc.modified}/{e.of}</span>
    <span className="latest-live-go">Open the readiness report <span aria-hidden="true">→</span></span>
  </a>;
}
