import { useEffect, useRef, useState } from 'react';

/** Public hosted-evaluation flow: Select → Repetitions → Run → Progress → Results.
 *  Every number shown here comes from the server's job status; nothing is simulated in the browser. */

type Outcome = 'evidence_supported_pass' | 'strict_pass' | 'not_passed' | string;
export interface TaskRow { arm: 'Original' | 'Modified'; task: number; state: string; outcome: Outcome; requests: number | null; page_views: number | null; steps: number | null; elapsed_seconds: number | null }
export interface Rep { index: number; state: string; tasks: TaskRow[]; assessment: { frozen_rule: string | null; exploratory: string | null; evidence_origin: string | null } | null }
interface ArmSummary { planned: number; completed: number; failed: number; evidence_supported_passes: number; strict_passes: number; requests_total: number; requests_mean: number | null; page_views_mean: number | null; steps_mean: number | null; elapsed_mean: number | null }
export interface Job { id: string; state: string; mode: 'live' | 'rehearsal' | null; repetitions: number | null; recovery_required?: boolean; created_at: number; started_at: number | null; finished_at: number | null; reps: Rep[]; summary: Record<'Original' | 'Modified', ArmSummary> }
interface Config { available: boolean; mode: 'live' | 'rehearsal' | null; repetitions: number[]; model: string; agent_profile: string; tasks: { task: number; question: string; limits?: { max_steps?: number; timeout_seconds?: number } }[]; remaining_repetitions: number; active: string | null }
interface Recent { id: string; state: string; repetitions: number; mode: string; created_at: number }

const ACTIVE = ['reserved', 'running'];
const STORE = 'ironbark-hosted-job';
const MODE_LABEL = { live: 'Live · Meta Muse Spark', rehearsal: 'Rehearsal · scripted agent, no model' } as const;
const STATE_LABEL: Record<string, string> = { reserved: 'Queued', running: 'Running', completed: 'Completed', failed: 'Failed', timed_out: 'Timed out', interrupted: 'Interrupted', pending: 'Pending', preparing: 'Preparing snapshots', incomplete: 'Incomplete', unverified: 'Unverified' };
const label = (s: string) => STATE_LABEL[s] ?? s.replaceAll('_', ' ');
const pct = (n: number, d: number) => d ? Math.round(100 * n / d) : null;
const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

async function getJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, { cache: 'no-store', ...init });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof body?.detail === 'string' ? body.detail : 'The evaluation service is unavailable.');
  return body as T;
}

function cell(t: TaskRow | undefined) {
  if (!t) return { cls: 'pending', glyph: '·', text: 'Pending' };
  if (t.state === 'running') return { cls: 'running', glyph: '◌', text: 'Agent working' };
  if (t.state !== 'completed') return { cls: t.state === 'failed' ? 'failed' : 'pending', glyph: t.state === 'failed' ? '!' : '·', text: label(t.state) };
  if (t.outcome === 'evidence_supported_pass') return { cls: 'pass', glyph: '✓', text: 'Evidence-supported pass' };
  if (t.outcome === 'strict_pass') return { cls: 'partial', glyph: '≈', text: 'Correct, evidence not observed' };
  return { cls: 'miss', glyph: '✕', text: 'Not passed' };
}

export function ProgressGrid({ rep, questions }: { rep: Rep; questions: Record<number, string> }) {
  const find = (arm: string, task: number) => rep.tasks.find(t => t.arm === arm && t.task === task);
  return <table className="hosted-grid" aria-label={`Repetition ${rep.index} task progress`}>
    <thead><tr><th scope="col">Task</th><th scope="col">Original</th><th scope="col">Modified</th></tr></thead>
    <tbody>{[1, 2, 3, 4].map(n => <tr key={n}><th scope="row"><span>Task {n}</span><small>{questions[n] ?? ''}</small></th>
      {(['Original', 'Modified'] as const).map(arm => { const t = find(arm, n), c = cell(t); return <td key={arm} className={`hosted-cell ${c.cls}`}>
        <span className="hosted-glyph" aria-hidden="true">{c.glyph}</span><span><strong>{c.text}</strong>
          {t?.state === 'completed' && <small>{t.requests ?? '–'} requests · {t.page_views ?? '–'} pages{t.elapsed_seconds != null ? ` · ${Math.round(t.elapsed_seconds)} s` : ''}</small>}</span></td>; })}
    </tr>)}</tbody>
  </table>;
}

export function Metrics({ job }: { job: Job }) {
  const o = job.summary.Original, m = job.summary.Modified;
  const rate = (a: ArmSummary) => pct(a.evidence_supported_passes, a.completed);
  const fewer = o.requests_mean && m.requests_mean != null ? Math.round(100 * (o.requests_mean - m.requests_mean) / o.requests_mean) : null;
  const metric = (name: string, a: number | null, b: number | null, unit = '') => <div className="hosted-metric"><span>{name}</span><strong>{a ?? '–'}{a != null ? unit : ''}</strong><i>→</i><strong className="modified">{b ?? '–'}{b != null ? unit : ''}</strong></div>;
  return <section className="hosted-results" aria-label="Evaluation metrics">
    <div className="hosted-headline">
      <article><span>Task success · evidence-supported</span><div><strong>{o.evidence_supported_passes}/{o.completed}</strong><i>→</i><strong className="modified">{m.evidence_supported_passes}/{m.completed}</strong></div><small>Original → Modified{rate(o) != null && rate(m) != null ? ` · ${rate(o)}% → ${rate(m)}%` : ''}</small></article>
      <article><span>Model requests per task</span><div><strong>{o.requests_mean ?? '–'}</strong><i>→</i><strong className="modified">{m.requests_mean ?? '–'}</strong></div><small>{fewer != null ? (fewer >= 0 ? `${fewer}% fewer on Modified` : `${-fewer}% more on Modified`) : 'Awaiting completed tasks'} · {o.requests_total} → {m.requests_total} total</small></article>
    </div>
    <div className="hosted-metrics">
      {metric('Page views per task', o.page_views_mean, m.page_views_mean)}
      {metric('Agent steps per task', o.steps_mean, m.steps_mean)}
      {metric('Time per task', o.elapsed_mean != null ? Math.round(o.elapsed_mean) : null, m.elapsed_mean != null ? Math.round(m.elapsed_mean) : null, ' s')}
      {metric('Correct answers (strict)', o.strict_passes, m.strict_passes)}
    </div>
    <p className="hosted-caveat">Descriptive totals over {o.completed + m.completed} completed agent runs{o.failed + m.failed ? `; ${o.failed + m.failed} failed runs excluded` : ''}. Observed differences do not by themselves establish that the change caused them.</p>
  </section>;
}

export function HostedEvaluation({ onOpen, initialJob }: { onOpen: (report: unknown, label: string) => void; initialJob?: string | null }) {
  const [config, setConfig] = useState<Config | null>(null);
  const [reps, setReps] = useState(1);
  const [job, setJob] = useState<Job | null>(null);
  const [recent, setRecent] = useState<Recent[]>([]);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(Date.now() / 1000);
  const current = useRef<string | null>(null);

  async function load(id: string) {
    current.current = id;
    const next = await getJSON<Job>(`/api/ironbark/jobs/${encodeURIComponent(id)}`);
    if (current.current === id) setJob(next);
    return next;
  }
  const refreshList = () => getJSON<Recent[]>('/api/ironbark/jobs').then(setRecent).catch(() => {});
  const refreshConfig = () => getJSON<Config>('/api/ironbark/config').then(setConfig).catch(() => setConfig(null));

  useEffect(() => {
    void refreshConfig(); void refreshList();
    const id = initialJob || localStorage.getItem(STORE);
    if (id) load(id).catch(() => localStorage.removeItem(STORE));
  }, [initialJob]);
  useEffect(() => {
    if (!job || !ACTIVE.includes(job.state)) return;
    const poll = setInterval(() => { load(job.id).then(j => { if (!ACTIVE.includes(j.state)) { void refreshConfig(); void refreshList(); } }).catch(e => setMessage(e.message)); }, 2500);
    const tick = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => { clearInterval(poll); clearInterval(tick); };
  }, [job?.id, job?.state]);

  async function start() {
    setBusy(true); setMessage('');
    try {
      const data = await getJSON<{ id: string }>('/api/ironbark/jobs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ repetitions: reps }) });
      localStorage.setItem(STORE, data.id);
      history.replaceState(null, '', `#/run/${data.id}`);
      await load(data.id); void refreshConfig(); void refreshList();
    } catch (e) { setMessage(e instanceof Error ? e.message : 'Evaluation unavailable.'); void refreshConfig(); }
    finally { setBusy(false); }
  }
  async function open(rep: Rep) {
    if (!job) return;
    try { onOpen(await getJSON(`/api/ironbark/jobs/${job.id}/repetitions/${rep.index}/export`), `Evaluation ${job.id.slice(5, 13)} · repetition ${rep.index}`); }
    catch (e) { setMessage(e instanceof Error ? e.message : 'Sanitized results are unavailable.'); }
  }
  const select = (id: string) => { localStorage.setItem(STORE, id); history.replaceState(null, '', `#/run/${id}`); setMessage(''); load(id).catch(e => setMessage(e.message)); };

  const questions = Object.fromEntries((config?.tasks ?? []).map(t => [t.task, t.question]));
  const running = !!job && ACTIVE.includes(job.state);
  const othersRunning = !!config?.active && config.active !== job?.id;
  const done = job ? job.reps.reduce((a, r) => a + r.tasks.filter(t => t.state === 'completed' || t.state === 'failed').length, 0) : 0;
  const total = (job?.repetitions ?? 0) * 8;
  const elapsed = job?.started_at ? (job.finished_at ?? now) - job.started_at : 0;
  const mode = job?.mode ?? config?.mode;
  const canRun = !!config?.available && !busy && !running && !othersRunning && config.remaining_repetitions >= reps;

  return <section className="hosted" aria-label="New evaluation">
    <div className="studio-title"><div><p className="studio-kicker">NEW EVALUATION</p><h1>Run real agents on a website.</h1></div>
      {mode && <span className={`hosted-mode ${mode}`}>{MODE_LABEL[mode]}</span>}</div>
    <p className="hosted-intro">Each repetition gives four frozen tasks to fresh browser agents on the <strong>Original</strong> and the <strong>Modified</strong> site: eight new agent runs, graded independently of what the agent claims.</p>

    <ol className="hosted-steps">
      <li><span className="hosted-step">1 · Website</span>
        <div className="hosted-choice selected" aria-label="Selected website"><strong>Ironbark Hire Co.</strong><small>Controlled rental-equipment site · Original vs Modified listing cards</small></div></li>
      <li><span className="hosted-step">2 · Repetitions</span>
        <div className="hosted-reps" role="radiogroup" aria-label="Paired repetitions">{(config?.repetitions ?? [1, 3, 5]).map(n =>
          <button key={n} role="radio" aria-checked={reps === n} disabled={running} onClick={() => setReps(n)}><strong>{n}</strong><small>{n * 8} agent runs</small></button>)}</div></li>
      <li><span className="hosted-step">3 · Run</span>
        <button className="hosted-run" disabled={!canRun} onClick={() => void start()}>{busy ? 'Starting…' : running ? 'Evaluation running' : 'Run evaluation'}</button>
        <small className="hosted-note">{!config ? 'Connecting to the evaluation service…' : !config.available ? 'New evaluations are currently unavailable. The archived replay remains available.' : othersRunning ? 'Another visitor’s evaluation is running.' : config.remaining_repetitions < reps ? 'The hosted budget for new evaluations is exhausted.' : `One evaluation at a time · up to ${reps * 8} agent runs`}</small>
        {othersRunning && config?.active && <button className="hosted-link" onClick={() => select(config.active!)}>Watch the running evaluation →</button>}</li>
    </ol>
    {message && <p role="alert" className="hosted-alert">{message}</p>}

    {job && <div className="hosted-job" aria-live="polite">
      <div className="hosted-status"><span className={`hosted-dot ${job.state}`} aria-hidden="true" /><strong>{label(job.state)}</strong>
        <span>{done} / {total || '–'} agent runs finished</span>{job.started_at && <span>{clock(elapsed)} elapsed</span>}<code>{job.id.slice(0, 13)}</code></div>
      <div className="hosted-bar" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={done}><i style={{ width: `${total ? 100 * done / total : 0}%` }} /></div>
      {job.recovery_required && <p className="hosted-alert">This evaluation lost its worker and will be marked interrupted.</p>}
      {job.mode === 'rehearsal' && <p className="hosted-alert">Rehearsal: real browsers and grading, but a scripted agent instead of a model. These are not Muse Spark results.</p>}
      {job.summary.Original.completed + job.summary.Modified.completed > 0 && <Metrics job={job} />}
      <div className="hosted-reps-list">{job.reps.map(rep => <article key={rep.index} className="hosted-rep">
        <header><strong>Repetition {rep.index}</strong><span className={`hosted-pill ${rep.state}`}>{label(rep.state)}</span>
          {rep.assessment && <button onClick={() => void open(rep)}>Inspect evidence & replay →</button>}</header>
        <ProgressGrid rep={rep} questions={questions} />
        {rep.assessment && <p className="hosted-verdicts">Frozen comparison rule: <strong>{rep.assessment.frozen_rule ?? 'unavailable'}</strong> · Exploratory listing rule: <strong>{rep.assessment.exploratory ?? 'unavailable'}</strong> · Evidence: {rep.assessment.evidence_origin === 'real_model' ? 'real model' : rep.assessment.evidence_origin ?? 'unverified'}</p>}
      </article>)}</div>
    </div>}

    <details className="hosted-details"><summary>Methodology & provenance</summary>
      <p><strong>Agent.</strong> Browser Use agent driven by <code>{config?.model ?? 'muse-spark-1.3'}</code> with profile <code>{config?.agent_profile ?? 'suite-v2-compat2'}</code>; each task is limited to {config?.tasks[0]?.limits?.max_steps ?? 14} steps and {config?.tasks[0]?.limits?.timeout_seconds ?? 240} seconds; no retries.</p>
      <p><strong>Tasks.</strong> The same four frozen tasks run on both versions, in a counterbalanced order, for every repetition:</p>
      <ol>{(config?.tasks ?? []).map(t => <li key={t.task}>{t.question}</li>)}</ol>
      <p><strong>Grading.</strong> An independent grader checks each answer against ground truth the agent never sees. “Evidence-supported” also requires that the agent actually viewed the pages holding the answer. Agent self-assessment is ignored.</p>
      <p><strong>Sites.</strong> Original and Modified are frozen snapshots of a controlled test site; Modified shows the refundable deposit, minimum hire and delivery fields on the listing cards (an owner-selected change).</p>
      <p><strong>Isolation.</strong> Each browser runs in its own network namespace that can reach only the snapshot mirror; it has no internet, DNS, local-service or provider access. Model credentials never enter the browser.</p>
      <p><strong>Limits.</strong> Each repetition is capped at US$1.60 of calculated model spend (US$0.80 per version), enforced before every model request. Calculated spend is not a bill.</p>
      <p><strong>Interpretation.</strong> Each completed repetition is also assessed with the pre-registered paired rule and the exploratory listing rule; small samples are often inconclusive. No difference here is a general claim about real websites.</p>
    </details>

    {recent.length > 0 && <details className="hosted-details"><summary>Previous evaluations</summary><ul className="hosted-recent">{recent.map(r =>
      <li key={r.id}><button onClick={() => select(r.id)} aria-current={r.id === job?.id ? 'true' : undefined}><code>{r.id.slice(0, 13)}</code><span>{label(r.state)}</span><span>{r.repetitions} × 8 runs</span><span>{r.mode === 'live' ? 'Live' : 'Rehearsal'}</span><span>{new Date(r.created_at * 1000).toLocaleString()}</span></button></li>)}</ul></details>}
  </section>;
}
