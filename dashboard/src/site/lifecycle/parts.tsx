import { useEffect, useState, type ReactNode } from 'react';
import { ApiError, VARIANT_LABEL, audienceText, variantClass, type Grade } from '../../lib/lifecycleApi';

/** Load once per key; errors are shown, never replaced by invented data. */
export function useLoad<T>(load: () => Promise<T>, key: string): { data: T | null; error: string | null; loading: boolean; reload: () => void } {
  // M9 (C2): the state remembers which key it belongs to, and data is returned only for the CURRENT key, so a view never combines a new key
  // (e.g. another evaluation's id) with the previous key's data while the next load is in flight. A reload of the same key keeps its data.
  const [state, setState] = useState<{ key: string | null; data: T | null; error: string | null; loading: boolean }>({ key: null, data: null, error: null, loading: true });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    setState(s => ({ ...s, loading: true, error: null }));
    load().then(d => live && setState({ key, data: d, error: null, loading: false }),
      e => live && setState({ key, data: null, error: e instanceof ApiError || e instanceof Error ? e.message : 'Unavailable.', loading: false }));
    return () => { live = false; };
  }, [key, tick]);
  const current = state.key === key;
  return { data: current ? state.data : null, error: current ? state.error : null, loading: !current || state.loading, reload: () => setTick(t => t + 1) };
}

/** Display wording for recorded server text (finding details): the graders by what they check. The recorded data is unchanged. */
export const plain = (t: string) => audienceText(t).replace(/ \(\d+\/\d+ trials?\)/g, '').replace(/Re-run diagnostics: /g, 'After the change, ').replace(/\bitem pages\b/g, 'course pages').replace(/\bitem-page\b/g, 'course-page').replace(/\blisting cards\b/g, 'course cards').replace(/the official grader v1/g, 'the exact-match grader').replace(/official grader v1/g, 'exact-match grader')
  .replace(/post-hoc grader v2/g, 'the correctness grader').replace(/grader v2/g, 'the correctness grader').replace(/grader v1/g, 'the exact-match grader');

export function Loading({ what }: { what: string }) { return <p className="lc-loading" aria-busy="true">Loading {what}…</p>; }
export function Failed({ error, what }: { error: string; what: string }) { return <p className="lc-error" role="alert"><strong>{what} unavailable.</strong> {error}</p>; }

/** A hash shown short, with the full value one click away (approval and freezing are always of the exact full hash). */
export function Hash({ sha, label, full = false }: { sha: string; label?: string; full?: boolean }) {
  const [open, setOpen] = useState(full);
  return <span className="lc-hash">{label && <span className="lc-hash-l">{label}</span>}
    <code title={sha}>{open ? sha : `${sha.slice(0, 12)}…`}</code>
    {!full && <button type="button" className="lc-hash-b" onClick={() => setOpen(o => !o)} aria-label={open ? 'Show short hash' : `Show full hash ${label ?? ''}`}>{open ? 'less' : 'full'}</button>}</span>;
}

export function ModeBadge({ mode }: { mode: string }) {
  return mode === 'paid' ? <span className="lc-mode paid">Live · Meta Muse Spark</span> : <span className="lc-mode rehearsal">Rehearsal · scripted agent, no model</span>;
}

export function VariantName({ v }: { v: string }) {
  return <span className="lc-vname"><span className={`swatch ${variantClass(v)}`} aria-hidden="true" />{VARIANT_LABEL(v)}</span>;
}

export function Legend({ variants }: { variants: string[] }) {
  return <p className="lc-legend" aria-label="Legend">{variants.map(v => <VariantName key={v} v={v} />)}</p>;
}

/** A recorded grade in plain words: `v2` = correct (consistent extra detail allowed), `v1` = exact match (the official grader). */
export function GradeTag({ g, which }: { g: Grade | null | undefined; which: 'v1' | 'v2' }) {
  const [yes, no] = which === 'v1' ? ['Exact match', 'Not an exact match'] : ['Correct', 'Not correct'];
  if (!g) return null;
  return <span className={`tag ${g.passed ? (which === 'v1' ? 'tag-neutral' : 'tag-pass') : (which === 'v1' ? 'tag-neutral' : 'tag-fail')}`} title={g.reasons?.join(', ')}>{g.passed ? '✓' : '✕'} {g.passed ? yes : no}</span>;
}

export function Section({ id, n, title, basis, children }: { id: string; n?: string; title: string; basis?: string; children: ReactNode }) {
  return <section className="lc-section" id={id} aria-labelledby={`${id}-h`}>
    <header className="lc-section-head">{n && <span className="eyebrow">{n}</span>}<h2 id={`${id}-h`}>{title}</h2>{basis && <p className="lc-basis"><b>Basis.</b> {basis}</p>}</header>
    {children}
  </section>;
}

/** Paired horizontal bars, one row per item, Original and Modified side by side; values are direct labels; the table view is the task matrix. */
export function PairBars({ rows, variants, unit, label }: { rows: { key: string; label: string; values: Record<string, number | null> }[]; variants: string[]; unit: string; label: string }) {
  const max = Math.max(1, ...rows.flatMap(r => variants.map(v => r.values[v] ?? 0)));
  return <figure className="lc-bars" aria-label={label}>
    <Legend variants={variants} />
    <div role="table" aria-label={label}>
      {rows.map(r => <div role="row" className="lc-bar-row" key={r.key}>
        <span role="rowheader" className="lc-bar-k">{r.label}</span>
        <span role="cell" className="lc-bar-cells">{variants.map(v => { const x = r.values[v]; return <span key={v} className="lc-bar-line" title={`${r.label} · ${VARIANT_LABEL(v)}: ${x ?? '–'} ${unit}`}>
          <span className={`lc-bar ${variantClass(v)}`} style={{ width: `${x == null ? 0 : Math.max(1.5, 100 * x / max)}%` }} /><span className="lc-bar-v">{x == null ? '–' : `${Math.round(x * 10) / 10} ${unit}`}</span></span>; })}</span>
      </div>)}
    </div>
  </figure>;
}

export function Disabled({ title, detail, children }: { title: string; detail: string; children?: ReactNode }) {
  return <div className="lc-disabled" role="note"><strong>{title}</strong><p>{detail}</p>{children}</div>;
}
