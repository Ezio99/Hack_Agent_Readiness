import './latest-live.css';
import { FEATURED, LIVE } from './showcase';

/** The featured live evaluation (Original vs Improved), as recorded (showcase.ts): a link to its report. Read-only; calls no API. */
export const LATEST_LIVE = { id: LIVE.id, date: FEATURED.liveDate, site: FEATURED.name, runs: LIVE.trials.length, of: LIVE.tasks.length,
  requests: { original: LIVE.totals.original.requests, improved: LIVE.totals.improved.requests },
  correct: { original: LIVE.correct.original, improved: LIVE.correct.improved } } as const;

export function LatestLive({ className = '' }: { className?: string }) {
  const e = LATEST_LIVE;
  return <a className={`latest-live ${className}`} href={`#/reports/${e.id}`} data-reveal>
    <span className="latest-live-eyebrow">Live evaluation · {e.site} · {e.date}</span>
    <strong>Original vs Improved · correct answers {e.correct.original}/{e.of} → {e.correct.improved}/{e.of} · {e.requests.original} → {e.requests.improved} model requests</strong>
    <span>{e.runs} Muse Spark browser agents · the same {e.of} customer tasks on each version · US${LIVE.cost_usd.toFixed(2)} of model calls</span>
    <span className="latest-live-go">Open the report <span aria-hidden="true">→</span></span>
  </a>;
}
