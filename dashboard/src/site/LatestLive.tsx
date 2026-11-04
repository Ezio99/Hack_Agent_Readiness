import './latest-live.css';
import { AFTER_V, BEFORE_V, CANONICAL, FEATURED, PAIRED } from './showcase';
import { VARIANT_LABEL } from '../lib/lifecycleApi';

/** The homepage's fixed reference result: the recorded canonical paired evaluation (showcase.ts, PAIRED), linking to its report. It is NOT the latest
 *  run: it calls no API, so later evaluations never change it. (The export name is kept for compatibility.) */
export const LATEST_LIVE = { id: PAIRED.id, site: FEATURED.name, of: PAIRED.tasks.length,
  requests: { before: PAIRED.totals[BEFORE_V].requests, after: PAIRED.totals[AFTER_V].requests },
  correct: { before: PAIRED.correct[BEFORE_V], after: PAIRED.correct[AFTER_V] } } as const;

export function LatestLive({ className = '' }: { className?: string }) {
  const e = LATEST_LIVE;
  return <a className={`latest-live ${className}`} href={`#/reports/${CANONICAL.id}`} data-reveal>
    <span className="latest-live-eyebrow">Reference paired evaluation · {e.site} · {CANONICAL.date}</span>
    <strong>{VARIANT_LABEL(BEFORE_V)} → {VARIANT_LABEL(AFTER_V)} · correct answers {e.correct.before}/{e.of} → {e.correct.after}/{e.of} · {e.requests.before} → {e.requests.after} model requests</strong>
    <span>Muse Spark browser agents · the same {e.of} customer tasks on each version, in one evaluation · US${PAIRED.cost_usd.toFixed(2)} of model calls in total. Individual live runs may vary.</span>
    <span className="latest-live-go">View the full report <span aria-hidden="true">→</span></span>
  </a>;
}
