import './latest-live.css';
import { AFTER, AFTER_V, BEFORE, BEFORE_V, FEATURED } from './showcase';

/** The featured live evaluations (Before and After, 4 Nov 2026), as recorded (showcase.ts): a link to the showcase. Read-only; calls no API. */
export const LATEST_LIVE = { before: BEFORE.id, after: AFTER.id, site: FEATURED.name, of: BEFORE.tasks.length,
  requests: { before: BEFORE.totals[BEFORE_V].requests, after: AFTER.totals[AFTER_V].requests },
  correct: { before: BEFORE.correct[BEFORE_V], after: AFTER.correct[AFTER_V] } } as const;

export function LatestLive({ className = '' }: { className?: string }) {
  const e = LATEST_LIVE;
  return <a className={`latest-live ${className}`} href="#/showcase" data-reveal>
    <span className="latest-live-eyebrow">Live evaluations · {e.site} · 4 Nov 2026</span>
    <strong>Before vs after · correct answers {e.correct.before}/{e.of} → {e.correct.after}/{e.of} · {e.requests.before} → {e.requests.after} model requests</strong>
    <span>Muse Spark browser agents · the same {e.of} customer tasks on each version · US${(BEFORE.cost_usd + AFTER.cost_usd).toFixed(2)} of model calls in total</span>
    <span className="latest-live-go">Watch before and after <span aria-hidden="true">→</span></span>
  </a>;
}
