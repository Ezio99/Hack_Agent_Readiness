import './latest-live.css';
import { FEATURED, LIVE } from './showcase';

/** The featured live evaluation of the Larkspur site, as recorded (showcase.ts): a link to its report. Read-only; calls no API. */
export const LATEST_LIVE = { id: LIVE.id, date: FEATURED.liveDate, site: FEATURED.name, runs: LIVE.trials.length, of: LIVE.tasks.length,
  requests: { original: LIVE.totals.original.requests, modified: LIVE.totals.modified.requests } } as const;

export function LatestLive({ className = '' }: { className?: string }) {
  const e = LATEST_LIVE;
  return <a className={`latest-live ${className}`} href={`#/reports/${e.id}`} data-reveal>
    <span className="latest-live-eyebrow">Live evaluation · {e.site} · {e.date}</span>
    <strong>{e.runs} browser agents · Original vs Modified · {e.requests.original} → {e.requests.modified} model requests</strong>
    <span>{e.of} customer tasks on each version of the site · US${LIVE.cost_usd.toFixed(2)} of model calls</span>
    <span className="latest-live-go">Open the report <span aria-hidden="true">→</span></span>
  </a>;
}
