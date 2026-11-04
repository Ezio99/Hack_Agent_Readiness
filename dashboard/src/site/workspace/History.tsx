import { useState } from 'react';

interface ArmSummary { completed: number; evidence_supported_passes: number; requests_mean: number | null; requests_total: number; steps_mean: number | null; page_views_mean: number | null }
export interface HistoryItem { id: string; engine?: string; runs_per_repetition?: number | null; state: string; execution_state?: string; report_state?: string; repetitions: number; mode: string; created_at: number; finished_at?: number | null; completed_repetitions?: number; summary: { Original: ArmSummary; Modified?: ArmSummary } | null; arm_display?: { Original: string; Modified?: string } | null; cost_usd?: number | null; reserved_usd?: number | null; budget?: string | null }

/** Agent runs per repetition: from the server for Stage B evaluations (tasks x 2 sites); the retired Ironbark engine ran 8. */
const perRep = (i: HistoryItem) => i.runs_per_repetition ?? 8;
const rate = (a?: ArmSummary) => a && a.completed ? `${Math.round(100 * a.evidence_supported_passes / a.completed)}%` : '—';
const names = (i: HistoryItem) => i.arm_display ?? { Original: 'Original', Modified: 'Modified' };
const pair = <T,>(i: HistoryItem, a: T, b: T | undefined) => names(i).Modified ? `${a} → ${b}` : `${a}`;   // one version alone shows one value
const armsOf = (i: HistoryItem) => (names(i).Modified ? ['Original', 'Modified'] : ['Original']) as ('Original' | 'Modified')[];
const when = (t: number) => new Date(t * 1000).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });

/** Previous evaluation batches; pick two to compare side by side. */
export function History({ items, current, open }: { items: HistoryItem[]; current: string | null; open: (id: string) => void }) {
  const [picked, setPicked] = useState<string[]>([]);
  const toggle = (id: string) => setPicked(p => p.includes(id) ? p.filter(x => x !== id) : [...p.slice(-1), id]);
  const compare = picked.map(id => items.find(i => i.id === id)).filter((x): x is HistoryItem => !!x?.summary);
  return <section className="history" aria-label="Evaluation history">
    <div className="table-scroll"><table className="ws-table history-table"><thead><tr><th>Compare</th><th>Evaluation</th><th>Started</th><th>Runs</th><th>Mode</th><th>Versions</th><th>Exact match</th><th>Requests / task</th><th>Cost</th><th /></tr></thead>
      <tbody>{items.map(i => <tr key={i.id} aria-current={i.id === current ? 'true' : undefined}>
        <td><input type="checkbox" aria-label={`Compare ${i.id.slice(0, 13)}`} checked={picked.includes(i.id)} disabled={!i.summary} onChange={() => toggle(i.id)} /></td>
        <td><code>{i.id.slice(0, 13)}</code> <span className={`ws-pill ${i.execution_state ?? i.state}`}>{(i.execution_state ?? i.state).replaceAll('_', ' ')}</span>{i.execution_state && i.execution_state !== i.state && <small className="ws-record" title="The job record is kept exactly as it was written"> record: {i.state.replaceAll('_', ' ')}</small>}{i.report_state === 'withheld' && <small className="ws-record"> report withheld</small>}</td>
        <td>{when(i.created_at)}</td><td>{i.repetitions} × {perRep(i)}</td><td>{i.mode === 'live' ? 'Muse Spark' : 'Rehearsal'}</td>
        <td>{pair(i, names(i).Original, names(i).Modified)}</td><td>{i.summary ? pair(i, rate(i.summary.Original), rate(i.summary.Modified)) : '—'}</td>
        <td>{i.summary ? pair(i, i.summary.Original.requests_mean ?? '—', i.summary.Modified?.requests_mean ?? '—') : '—'}</td>
        <td>{i.cost_usd != null ? `US$${i.cost_usd.toFixed(2)}` : '—'}{i.mode === 'live' && <small className="ws-record" title="Where this run's cost is accounted"> {i.budget ? i.budget : 'programme'}</small>}</td>
        <td><button className="ws-link" onClick={() => open(i.id)}>Open</button></td></tr>)}</tbody></table></div>
    {compare.length === 2 && <div className="history-compare" aria-label="Comparison">{compare.map(i => <article key={i.id}>
      <p className="eyebrow">{i.mode === 'live' ? 'MUSE SPARK' : 'REHEARSAL · SCRIPTED'} · {when(i.created_at)} · {i.repetitions} REPETITION{i.repetitions > 1 ? 'S' : ''}</p>
      <dl>{armsOf(i).map(arm => <div key={arm}><dt>{names(i)[arm]}</dt>
        <dd><strong>{i.summary![arm]!.evidence_supported_passes}/{i.summary![arm]!.completed}</strong> exact match · {i.summary![arm]!.requests_mean ?? '—'} requests/task · {i.summary![arm]!.steps_mean ?? '—'} steps/task</dd></div>)}</dl></article>)}
      {compare[0].mode !== compare[1].mode && <p className="ws-alert">These evaluations used different modes; rehearsal results are not comparable to Muse Spark results.</p>}</div>}
    {picked.length === 1 && <p className="ws-note">Select one more finished evaluation to compare.</p>}
  </section>;
}
