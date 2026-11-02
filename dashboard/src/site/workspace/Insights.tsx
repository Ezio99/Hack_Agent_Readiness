import { useEffect, useState } from 'react';

interface Finding { id: string; severity: 'high' | 'medium' | 'low' | 'info'; title: string; observed: string }
interface Suggestion { for: string; text: string; status: 'not measured' | 'tested in this evaluation' }
export interface InsightReport { state: 'ok' | 'insufficient'; runs: { Original: number; Modified: number }; findings: Finding[]; suggestions: Suggestion[]; method?: string; mode: string | null; final: boolean }

/** Friction findings derived from observed agent telemetry, with suggestions kept separate and labelled. */
export function Insights({ jobId, active }: { jobId: string; active: boolean }) {
  const [data, setData] = useState<InsightReport | null>(null);
  useEffect(() => {
    let stop = false;
    const load = () => fetch(`/api/ironbark/jobs/${jobId}/insights`, { cache: 'no-store' }).then(r => r.ok ? r.json() : null).then(d => { if (!stop) setData(d); }).catch(() => {});
    void load();
    const t = active ? setInterval(load, 10000) : undefined;
    return () => { stop = true; if (t) clearInterval(t); };
  }, [jobId, active]);
  if (!data) return <p className="ws-empty-note">Loading insights…</p>;
  if (data.state === 'insufficient') return <p className="ws-empty-note">Insights need at least one finished run on the Original site.</p>;
  const byId = Object.fromEntries(data.findings.map(f => [f.id, f]));
  return <section className="insights" aria-label="Friction insights">
    {data.mode === 'rehearsal' && <p className="ws-alert">Rehearsal telemetry comes from a scripted agent. These findings describe the script, not Muse Spark.</p>}
    <p className="insights-basis">Based on {data.runs.Original} Original and {data.runs.Modified} Modified agent runs{data.final ? '' : ' so far'}. {data.method}</p>
    <div className="insights-grid">
      <article><h3>Observed friction</h3><p className="insights-sub">What the agents actually did</p>
        <ul className="insight-list">{data.findings.map(f => <li key={f.id} className={`insight ${f.severity}`}><span className="insight-sev">{f.severity === 'info' ? 'Observed' : `${f.severity} friction`}</span><strong>{f.title}</strong><p>{f.observed}</p></li>)}</ul>
        {!data.findings.length && <p>No friction pattern crossed the reporting thresholds.</p>}</article>
      <article><h3>Suggested improvements</h3><p className="insights-sub">Proposals, not measured results</p>
        <ul className="insight-list">{data.suggestions.map(s => <li key={s.for} className="suggestion"><span className={`insight-status ${s.status === 'not measured' ? 'unmeasured' : 'tested'}`}>{s.status === 'not measured' ? 'Not measured' : 'Tested here as “Modified”'}</span>
          <strong>{s.text}</strong>{byId[s.for] && <p>Addresses: {byId[s.for].title.toLowerCase()}.</p>}</li>)}</ul></article>
    </div>
  </section>;
}
