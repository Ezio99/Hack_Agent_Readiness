import { useEffect, useRef, type ReactNode } from 'react';

/** Scroll-linked scenes. One passive scroll listener drives every registered track inside a single
 *  requestAnimationFrame; tracks write CSS custom properties directly (no React render per frame).
 *  Reduced motion: tracks collapse to normal flow and render their resting state (see demo.css [data-static]). */

type Handler = () => void;
const handlers = new Set<Handler>();
let queued = false;
const flush = () => { queued = false; handlers.forEach(h => h()); };
const schedule = () => { if (!queued) { queued = true; requestAnimationFrame(flush); } };
let listening = false;
function listen() {
  if (listening || typeof window === 'undefined') return;
  listening = true;
  window.addEventListener('scroll', schedule, { passive: true });
  window.addEventListener('resize', schedule, { passive: true });
}
export function register(h: Handler) { listen(); handlers.add(h); schedule(); return () => { handlers.delete(h); }; }

export const clamp01 = (x: number) => x < 0 ? 0 : x > 1 ? 1 : x;
/** Sub-progress of p inside [start, end]. */
export const seg = (p: number, start: number, end: number) => clamp01((p - start) / (end - start));
export const easeOut = (x: number) => 1 - Math.pow(1 - x, 3);
export const easeInOut = (x: number) => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;

/** Progress (0..1) of a tall section scrolled past a viewport-high sticky stage. */
export function progressOf(el: HTMLElement) {
  const r = el.getBoundingClientRect();
  const total = r.height - window.innerHeight;
  return total > 0 ? clamp01(-r.top / total) : (r.top <= 0 ? 1 : 0);
}

export interface TrackProps {
  id: string; vh: number; label: string; className?: string; children: ReactNode; reduce: boolean;
  /** Derived CSS variables for the current progress (set on the track element). */
  vars?: (p: number) => Record<string, number>;
  onProgress?: (p: number) => void;
}

export function Track({ id, vh, label, className = '', children, reduce, vars, onProgress }: TrackProps) {
  const ref = useRef<HTMLElement>(null);
  const cb = useRef({ vars, onProgress });
  cb.current = { vars, onProgress };
  useEffect(() => {
    const el = ref.current;
    if (!el || reduce) return;
    let last = -1;
    return register(() => {
      const p = progressOf(el);
      if (Math.abs(p - last) < 0.0005) return;
      last = p;
      el.style.setProperty('--p', p.toFixed(4));
      const v = cb.current.vars?.(p);
      if (v) for (const k in v) el.style.setProperty(`--${k}`, v[k].toFixed(4));
      cb.current.onProgress?.(p);
    });
  }, [reduce]);
  return <section id={id} ref={ref} className={`track ${className}`} data-static={reduce ? '' : undefined} aria-label={label}
    style={reduce ? undefined : { height: `${vh}vh` }}>
    <div className="stage">{children}</div>
  </section>;
}

/** Scroll the window so that a track sits at a given progress. */
export function scrollToProgress(el: HTMLElement, p: number, smooth: boolean) {
  const top = el.getBoundingClientRect().top + window.scrollY;
  const total = el.offsetHeight - window.innerHeight;
  window.scrollTo({ top: top + Math.max(0, total) * p + 1, behavior: smooth ? 'smooth' : 'auto' });
}
