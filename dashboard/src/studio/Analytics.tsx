import { Fragment, useEffect, useState } from 'react';

function useNarrow() {
  const query = '(max-width: 600px)';
  const [narrow, setNarrow] = useState(() => typeof window !== 'undefined' && !!window.matchMedia?.(query).matches);
  useEffect(() => { const m = window.matchMedia?.(query); if (!m) return; const on = () => setNarrow(m.matches); m.addEventListener?.('change', on); return () => m.removeEventListener?.('change', on); }, []);
  return narrow;
}
import type { Job, TaskRow } from './HostedEvaluation';

/** Experiment analytics computed from the server's per-trial rows (no client-side invention).
 *  Series colours are a validated categorical pair on the dark surface (#101B2B):
 *  Original #8E79E8, Modified #1A9DB3 (CVD ΔE 8.9, normal-vision ΔE 17.3). */
export const SERIES = { Original: '#8E79E8', Modified: '#1A9DB3' } as const;
type Arm = keyof typeof SERIES;
const ARMS: Arm[] = ['Original', 'Modified'];

interface Cell { done: number; supported: number; strict: number; requests: number[]; pages: number[]; steps: number[] }
export function perTask(job: Job): Record<number, Record<Arm, Cell>> {
  const out: Record<number, Record<Arm, Cell>> = {};
  for (const n of [1, 2, 3, 4]) out[n] = { Original: blank(), Modified: blank() };
  for (const rep of job.reps) for (const t of rep.tasks) {
    if (t.state !== 'completed') continue;
    const c = out[t.task]?.[t.arm as Arm]; if (!c) continue;
    c.done++; if (t.outcome === 'evidence_supported_pass') c.supported++;
    if (t.outcome === 'evidence_supported_pass' || t.outcome === 'strict_pass') c.strict++;
    if (t.requests != null) c.requests.push(t.requests);
    if (t.page_views != null) c.pages.push(t.page_views);
    if (t.steps != null) c.steps.push(t.steps);
  }
  return out;
}
function blank(): Cell { return { done: 0, supported: 0, strict: 0, requests: [], pages: [], steps: [] }; }
const mean = (xs: number[]) => xs.length ? Math.round(10 * xs.reduce((a, b) => a + b, 0) / xs.length) / 10 : null;

export function perRepetition(job: Job) {
  return job.reps.map(rep => {
    const row = (arm: Arm) => { const ts = rep.tasks.filter((t: TaskRow) => t.arm === arm && t.state === 'completed');
      return { done: ts.length, supported: ts.filter(t => t.outcome === 'evidence_supported_pass').length, requests: ts.reduce((a, t) => a + (t.requests ?? 0), 0) }; };
    return { index: rep.index, state: rep.state, Original: row('Original'), Modified: row('Modified') };
  });
}

function Legend() {
  return <div className="viz-legend" aria-hidden="true">{ARMS.map(a => <span key={a}><i style={{ background: SERIES[a] }} />{a}</span>)}</div>;
}

/** Horizontal paired bars: evidence-supported pass rate per task. */
function SuccessChart({ data, questions }: { data: ReturnType<typeof perTask>; questions: Record<number, string> }) {
  const W = useNarrow() ? 360 : 640, left = 70, right = 64, bar = 10, gap = 2, row = 2 * bar + gap + 22, H = 4 * row + 24;
  const x = (v: number) => left + v * (W - left - right);
  return <svg viewBox={`0 0 ${W} ${H}`} className="viz" role="img" aria-label="Evidence-supported pass rate per task, Original and Modified">
    {[0, .5, 1].map(v => <g key={v}><line x1={x(v)} x2={x(v)} y1={4} y2={H - 18} className="viz-grid" /><text x={x(v)} y={H - 4} className="viz-axis" textAnchor="middle">{v * 100}%</text></g>)}
    {[1, 2, 3, 4].map((n, i) => { const y0 = 6 + i * row; return <g key={n}>
      <text x={0} y={y0 + bar + 4} className="viz-label">Task {n}</text>
      {ARMS.map((arm, j) => { const c = data[n][arm], rate = c.done ? c.supported / c.done : 0, y = y0 + j * (bar + gap);
        return <g key={arm} className="viz-mark"><title>{`Task ${n} · ${arm}: ${c.supported} of ${c.done} completed runs evidence-supported${questions[n] ? ` — ${questions[n]}` : ''}`}</title>
          <rect x={left} y={y - 3} width={W - left - right} height={bar + 6} fill="transparent" />
          {c.done ? <rect x={left} y={y} width={Math.max(4, x(rate) - left)} height={bar} rx={4} fill={SERIES[arm]} /> : <rect x={left} y={y + bar / 2 - 1} width={W - left - right} height={2} className="viz-empty" />}
          <text x={c.done ? Math.max(x(rate), left + 4) + 8 : W - right + 8} y={y + bar - 1} className="viz-value">{c.done ? `${c.supported}/${c.done}` : '—'}</text></g>; })}
    </g>; })}
  </svg>;
}

/** Dot = mean model requests; whisker = min–max across repetitions. */
function RequestsChart({ data }: { data: ReturnType<typeof perTask> }) {
  const all = [1, 2, 3, 4].flatMap(n => ARMS.flatMap(a => data[n][a].requests));
  const max = Math.max(4, ...all), top = Math.ceil(max / 4) * 4;
  const W = useNarrow() ? 360 : 640, left = 70, right = 30, row = 46, H = 4 * row + 24;
  const x = (v: number) => left + (v / top) * (W - left - right);
  return <svg viewBox={`0 0 ${W} ${H}`} className="viz" role="img" aria-label="Model requests per task: mean and range across repetitions">
    {[0, top / 2, top].map(v => <g key={v}><line x1={x(v)} x2={x(v)} y1={4} y2={H - 18} className="viz-grid" /><text x={x(v)} y={H - 4} className="viz-axis" textAnchor="middle">{v}</text></g>)}
    {[1, 2, 3, 4].map((n, i) => { const y0 = 12 + i * row; return <g key={n}>
      <text x={0} y={y0 + 10} className="viz-label">Task {n}</text>
      {ARMS.map((arm, j) => { const r = data[n][arm].requests, y = y0 + j * 14; if (!r.length) return null;
        const lo = Math.min(...r), hi = Math.max(...r), m = mean(r)!;
        return <g key={arm} className="viz-mark"><title>{`Task ${n} · ${arm}: mean ${m} requests (min ${lo}, max ${hi}, ${r.length} run${r.length > 1 ? 's' : ''})`}</title>
          <rect x={left} y={y - 7} width={W - left - right} height={14} fill="transparent" />
          {hi > lo && <line x1={x(lo)} x2={x(hi)} y1={y} y2={y} stroke={SERIES[arm]} strokeWidth={2} strokeLinecap="round" />}
          <circle cx={x(m)} cy={y} r={5} fill={SERIES[arm]} stroke="#101B2B" strokeWidth={2} />
          <text x={x(hi) + 10} y={y + 4} className="viz-value">{m}</text></g>; })}
    </g>; })}
  </svg>;
}

export function Analytics({ job, questions }: { job: Job; questions: Record<number, string> }) {
  const [table, setTable] = useState(false);
  const data = perTask(job), reps = perRepetition(job);
  const any = ARMS.some(a => [1, 2, 3, 4].some(n => data[n][a].done));
  if (!any) return <p className="agent-empty">Analytics appear as soon as the first agent runs are graded.</p>;
  return <section className="analytics" aria-label="Experiment analytics">
    <div className="analytics-head"><Legend /><button className="hosted-link" aria-pressed={table} onClick={() => setTable(t => !t)}>{table ? 'Show charts' : 'Show as table'}</button></div>
    {table ? <div className="table-scroll"><table className="hosted-grid analytics-table"><thead><tr><th>Task</th>{ARMS.map(a => <th key={a} colSpan={3}>{a}</th>)}</tr>
      <tr><th />{ARMS.map(a => <Fragment key={a}><th>Evidence-supported</th><th>Requests (mean · range)</th><th>Pages</th></Fragment>)}</tr></thead>
      <tbody>{[1, 2, 3, 4].map(n => <tr key={n}><th scope="row">Task {n}<small>{questions[n]}</small></th>{ARMS.map(a => { const c = data[n][a]; return <Fragment key={a}>
        <td>{c.done ? `${c.supported}/${c.done}` : '—'}</td><td>{c.requests.length ? `${mean(c.requests)} · ${Math.min(...c.requests)}–${Math.max(...c.requests)}` : '—'}</td><td>{mean(c.pages) ?? '—'}</td></Fragment>; })}</tr>)}</tbody></table></div>
    : <div className="analytics-charts">
      <article><h3>Task success by task</h3><p>Share of completed runs with an evidence-supported pass.</p><SuccessChart data={data} questions={questions} /></article>
      <article><h3>Model requests by task</h3><p>Dot: mean across repetitions · line: lowest to highest.</p><RequestsChart data={data} /></article>
    </div>}
    {reps.length > 1 && <article className="analytics-reps"><h3>Variation across repetitions</h3>
      <div className="table-scroll"><table className="hosted-grid"><thead><tr><th>Repetition</th><th>Original passes</th><th>Modified passes</th><th>Original requests</th><th>Modified requests</th></tr></thead>
        <tbody>{reps.map(r => <tr key={r.index}><th scope="row">{r.index}</th>
          {ARMS.map(a => <td key={a}><span className="rep-dots" aria-label={`${r[a].supported} of ${r[a].done}`}>{[0, 1, 2, 3].map(i => <i key={i} style={i < r[a].supported ? { background: SERIES[a] } : undefined} className={i < r[a].done ? '' : 'pending'} />)}</span> {r[a].supported}/{r[a].done}</td>)}
          {ARMS.map(a => <td key={a + 'q'}>{r[a].done ? r[a].requests : '—'}</td>)}</tr>)}</tbody></table></div></article>}
  </section>;
}
