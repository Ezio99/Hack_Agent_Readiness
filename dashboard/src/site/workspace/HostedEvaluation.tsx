import { useEffect, useRef, useState } from 'react';
import { AgentPanel, type Selection } from './LiveAgent';
import { Analytics } from './Analytics';
import { Insights } from './Insights';
import { History, type HistoryItem } from './History';
import { Report } from '../lifecycle/Report';
import type { Evaluation } from '../../lib/lifecycleApi';

/** Hosted evaluation workspace: compose (website, repetitions, run) → live progress → results → history.
 *  Every number shown here comes from the server's job status; nothing is simulated in the browser.
 *  Admission, budget and operator-only access are enforced by the server; the UI only reflects them. */

type Outcome = 'evidence_supported_pass' | 'strict_pass' | 'not_passed' | string;
export interface TaskRow { arm: 'Original' | 'Modified'; task: number; state: string; outcome: Outcome; requests: number | null; page_views: number | null; steps: number | null; elapsed_seconds: number | null;
  /** the readiness report's grades for this agent run (Stage B, once the report is published): correct = as the report counts it; exact match = official grader */
  correct?: boolean; exact_match?: boolean }
export interface GradingV2 { label: string; faithful: boolean; tasks: { arm: 'Original' | 'Modified'; task: number; outcome: string; reasons: string[] }[]; assessment: { frozen_rule: string | null; exploratory: string | null } | null }
type Setting = { value: string | number | (string | number)[] | null; consistent: boolean };
export interface Provenance { trials: number; model_requests_recorded: number; model: Setting; reasoning_effort: Setting; max_completion_tokens: Setting; consistent: boolean;
  agent_profile: { name: string | string[]; sha256: string | string[]; verified_against_profile_file: boolean };
  graders: { official: { id: string; version: string }[]; post_hoc: { id: string; version: string; derivation_id: string } | null };
  by_arm?: Record<string, { trials: number; agent_profile: { name: string | string[] } }>; arm_labels?: Record<string, string> }
export interface Rep { index: number; state: string; tasks: TaskRow[]; assessment: { frozen_rule: string | null; exploratory: string | null; evidence_origin: string | null } | null; grading_v2?: GradingV2 | null; provenance?: Provenance | null }
type ArmV2 = { completed: number; evidence_supported_passes: number; strict_passes: number };
interface ArmSummary { planned: number; completed: number; failed: number; evidence_supported_passes: number; strict_passes: number; requests_total: number; requests_mean: number | null; page_views_mean: number | null; steps_mean: number | null; elapsed_mean: number | null }
export interface Execution { state: string; trials_planned: number | null; trials_completed: number; trials_failed: number; trials_void: number }
export interface ReportStatus { state: 'available' | 'withheld' | 'pending' | 'unavailable' | 'unknown'; detail?: string }
export interface Job { engine?: 'stage-b'; execution?: Execution; report_status?: ReportStatus; record_note?: string | null; report?: string | null; error?: string | null; stopped?: string | null; id: string; state: string; mode: 'live' | 'rehearsal' | null; repetitions: number | null; recovery_required?: boolean; created_at: number; started_at: number | null; finished_at: number | null; reps: Rep[]; summary: Record<'Original' | 'Modified', ArmSummary>; arm_display?: Record<'Original' | 'Modified', string> | null; summary_v2?: ({ label: string; repetitions: number } & Record<'Original' | 'Modified', ArmV2>) | null }
interface Worker { state: 'idle' | 'busy' | 'unavailable'; job: string | null; started_at?: number | null; repetitions?: number; finished_runs?: number; total_runs?: number | null; estimated_remaining_seconds?: number | null }
interface ArmedEvaluation { arming_id: string; mode: 'paid' | 'rehearsal'; site: string; suite: string; frozen_suite: string; frozen_suite_sha256: string; variants: string[]; armed_at: string;
  launches: { max: number; used: number; left: number }; options: { repetitions: number; trials: number; reservation_usd: number; manifest_sha256: string; available: boolean; fits_hosted_ceiling: boolean | null }[];
  agent: { model: string; reasoning_effort: string | null; max_completion_tokens: number; profile: string } }
interface LaunchState { authorized: boolean; ready: boolean; reason: string | null; detail: string | null; launches_left: number | null }
interface Config { engine?: 'stage-b'; launch?: LaunchState; judge_access?: boolean; service?: { state: 'operational' | 'unavailable'; reason: string | null }; evaluation?: ArmedEvaluation | null; ceiling?: { ceiling_usd: number; reserved_usd: number };
  spending?: { ceiling: number; settled: number; outstanding: number; committed: number; available: number; released: number; settled_jobs: number; unsettled_jobs: number; basis: string };
  agent_settings?: { profile: string; profile_file_sha256: string; reasoning_effort: string | null; max_completion_tokens: number | null } | null; worker?: Worker; repetition_duration?: { seconds: number; basis: 'measured' | 'first genuine run' | 'default'; samples: number }; available: boolean; mode: 'live' | 'rehearsal' | null; access?: 'public' | 'operator'; reason?: string | null; repetitions: number[]; model: string; agent_profile: string; tasks: { task: number; question: string; capability?: string; limits?: { max_steps?: number; timeout_seconds?: number; max_model_requests?: number } }[]; remaining_repetitions: number; active: string | null }

const ACTIVE = ['reserved', 'running'];
const STORE = 'ironbark-hosted-job';
const LEGACY_TOKEN = 'ironbark-operator-token';   // earlier builds kept the token in sessionStorage; it is now held in memory only and this key is removed
const FOCUS = 'ar-ws-focus';
const MODE_LABEL = { live: 'Live · Meta Muse Spark', rehearsal: 'Rehearsal · scripted agent, no model' } as const;
const STATE_LABEL: Record<string, string> = { reserved: 'Queued', running: 'Running', completed: 'Completed', failed: 'Failed', timed_out: 'Timed out', interrupted: 'Interrupted', pending: 'Pending', preparing: 'Preparing snapshots', incomplete: 'Incomplete', unverified: 'Unverified' };
export const label = (s: string) => STATE_LABEL[s] ?? s.replaceAll('_', ' ');
const pct = (n: number, d: number) => d ? Math.round(100 * n / d) : null;
const minutes = (s: number) => s < 90 ? 'about 1 min' : `about ${Math.round(s / 60)} min`;
const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
const when = (t: number) => new Date(t * 1000).toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

async function getJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, { cache: 'no-store', ...init });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(typeof body?.detail === 'string' ? body.detail : 'The evaluation service is unavailable.'), { status: r.status });
  return body as T;
}

function cell(t: TaskRow | undefined) {
  if (!t) return { cls: 'pending', glyph: '·', text: 'Pending' };
  if (t.state === 'running') return { cls: 'running', glyph: '◌', text: 'Agent working' };
  if (t.state !== 'completed') return { cls: t.state === 'failed' ? 'failed' : 'pending', glyph: t.state === 'failed' ? '!' : '·', text: label(t.state) };
  if (t.correct !== undefined) return t.correct ? { cls: 'pass', glyph: '✓', text: 'Correct' } : { cls: 'miss', glyph: '✕', text: 'Not correct' };   // as in the readiness report
  if (t.outcome === 'evidence_supported_pass') return { cls: 'pass', glyph: '✓', text: 'Evidence-supported pass' };
  if (t.outcome === 'strict_pass') return { cls: 'partial', glyph: '≈', text: 'Correct, evidence not observed' };
  return { cls: 'miss', glyph: '✕', text: 'Not passed' };
}

const V2_TEXT: Record<string, string> = { evidence_supported_pass: 'pass', strict_pass: 'correct, evidence not observed', not_passed: 'not passed' };

const show = (v: unknown) => Array.isArray(v) ? v.join(' / ') : String(v ?? 'not recorded');

/** Model and grader provenance as recorded for one evaluation (derived server-side from its trial records and request traces). */
export function ProvenanceNote({ p }: { p: Provenance }) {
  const official = p.graders.official.map(g => `${g.id} v${g.version}`).join(', ');
  const baseline = p.by_arm?.baseline;
  return <p className="ws-provenance" aria-label="Recorded model provenance">
    <strong>Recorded for this evaluation.</strong> Model <code>{show(p.model.value)}</code> · reasoning_effort <code>{show(p.reasoning_effort.value)}</code> · max_completion_tokens <code>{show(p.max_completion_tokens.value)}</code> ·
    agent profile <code>{show(p.agent_profile.name)}</code> (sha256 <code>{show(p.agent_profile.sha256).slice(0, 12)}…</code>{p.agent_profile.verified_against_profile_file ? ', matches the profile file' : ', NOT verified against the profile file'}) ·
    {' '}{p.trials} agent runs, {p.model_requests_recorded} model requests recorded. Official grade: {official}{p.graders.post_hoc ? `; post-hoc rescore: ${p.graders.post_hoc.id} v${p.graders.post_hoc.version} (shown separately, never the official result)` : ''}.
    {!p.consistent && <> <strong>Inconsistent across runs:</strong> see the export's model_provenance.</>}
    {baseline && <> The historical baseline used only by the frozen comparison rule was recorded with profile <code>{show(baseline.agent_profile.name)}</code>.</>}
  </p>;
}

export function ProgressGrid({ rep, questions, onSelect, selected, names = { Original: 'Original', Modified: 'Modified' } }: { rep: Rep; questions: Record<number, string>; onSelect?: (s: Selection) => void; selected?: Selection | null; names?: Record<'Original' | 'Modified', string> }) {
  const numbers = [...new Set([...rep.tasks.map(t => t.task), ...Object.keys(questions).map(Number)])].sort((a, b) => a - b);
  const find = (arm: string, task: number) => rep.tasks.find(t => t.arm === arm && t.task === task);
  const v2 = (arm: string, task: number) => rep.grading_v2?.faithful ? rep.grading_v2.tasks.find(t => t.arm === arm && t.task === task) : undefined;
  return <table className="ws-grid" aria-label={`Repetition ${rep.index} task progress`}>
    <thead><tr><th scope="col">Task</th><th scope="col"><span className="swatch o" aria-hidden="true" />{names.Original}</th><th scope="col"><span className={`swatch ${names.Modified === 'Improved' ? 'i' : 'm'}`} aria-hidden="true" />{names.Modified}</th></tr></thead>
    <tbody>{(numbers.length ? numbers : [1, 2, 3, 4]).map(n => <tr key={n}><th scope="row"><span className="ws-task-n">Task {n}</span><small>{questions[n] ?? ''}</small></th>
      {(['Original', 'Modified'] as const).map(arm => { const t = find(arm, n), c = cell(t), key = arm.toLowerCase() as 'original' | 'modified';
        const isSel = selected?.repetition === rep.index && selected.arm === key && selected.task === n;
        const body = <><span className="ws-glyph" aria-hidden="true">{c.glyph}</span><span className="ws-cell-text"><strong>{c.text}</strong>
          {t?.state === 'completed' && <small>{t.requests ?? '–'} requests · {t.page_views ?? '–'} pages{t.elapsed_seconds != null ? ` · ${Math.round(t.elapsed_seconds)} s` : ''}</small>}
          {t?.state === 'completed' && t.exact_match !== undefined && <small className="ws-exact">Exact match: {t.exact_match ? 'yes' : 'no'}</small>}
          {(() => { const d = v2(arm, n); return d && t?.state === 'completed' && d.outcome !== t.outcome ? <small className="ws-v2-diff">Grader v2 (post-hoc): {V2_TEXT[d.outcome] ?? d.outcome}</small> : null; })()}</span></>;
        return <td key={arm} className={`ws-cell ${c.cls}${isSel ? ' selected' : ''}`}>
          {onSelect && t && t.state !== 'pending' ? <button className="ws-cell-button" aria-label={`Watch ${names[arm]} task ${n}, repetition ${rep.index}: ${c.text}`} aria-pressed={isSel} onClick={() => onSelect({ repetition: rep.index, arm: key, task: n })}>{body}</button> : <div className="ws-cell-button static">{body}</div>}</td>; })}
    </tr>)}</tbody>
  </table>;
}

export function Metrics({ job }: { job: Job }) {
  const o = job.summary.Original, m = job.summary.Modified;
  const rate = (a: ArmSummary) => pct(a.evidence_supported_passes, a.completed);
  const fewer = o.requests_mean && m.requests_mean != null ? Math.round(100 * (o.requests_mean - m.requests_mean) / o.requests_mean) : null;
  const metric = (name: string, a: number | null, b: number | null, unit = '') => <div className="ws-metric"><dt>{name}</dt><dd><span className="o">{a ?? '–'}{a != null ? unit : ''}</span><i aria-hidden="true">→</i><span className="m">{b ?? '–'}{b != null ? unit : ''}</span></dd></div>;
  return <section className="ws-results" aria-label="Evaluation metrics">
    <div className="ws-headline">
      <article><h3>Task success · evidence-supported</h3><div className="ws-big"><span className="o">{o.evidence_supported_passes}/{o.completed}</span><i aria-hidden="true">→</i><span className="m">{m.evidence_supported_passes}/{m.completed}</span></div><p>Original → Modified{rate(o) != null && rate(m) != null ? ` · ${rate(o)}% → ${rate(m)}%` : ''}</p>
        {job.summary_v2 && <p className="ws-v2-line" title={job.summary_v2.label}>Grader v2, post-hoc rescore: <span className="o">{job.summary_v2.Original.evidence_supported_passes}/{job.summary_v2.Original.completed}</span> → <span className="m">{job.summary_v2.Modified.evidence_supported_passes}/{job.summary_v2.Modified.completed}</span> <small>(official result above: grader v1)</small></p>}</article>
      <article><h3>Model requests per task</h3><div className="ws-big"><span className="o">{o.requests_mean ?? '–'}</span><i aria-hidden="true">→</i><span className="m">{m.requests_mean ?? '–'}</span></div><p>{fewer != null ? (fewer >= 0 ? `${fewer}% fewer on Modified` : `${-fewer}% more on Modified`) : 'Awaiting completed tasks'} · {o.requests_total} → {m.requests_total} total</p></article>
    </div>
    <dl className="ws-metrics">
      {metric('Page views per task', o.page_views_mean, m.page_views_mean)}
      {metric('Agent steps per task', o.steps_mean, m.steps_mean)}
      {metric('Time per task', o.elapsed_mean != null ? Math.round(o.elapsed_mean) : null, m.elapsed_mean != null ? Math.round(m.elapsed_mean) : null, ' s')}
      {metric('Correct answers (strict)', o.strict_passes, m.strict_passes)}
    </dl>
    <p className="ws-caveat">Descriptive totals over {o.completed + m.completed} completed agent runs{o.failed + m.failed ? `; ${o.failed + m.failed} failed runs excluded` : ''}. Observed differences do not by themselves establish that the change caused them.</p>
  </section>;
}

/** The readiness report of a Stage B evaluation: the same lifecycle projection and report component as the preloaded M7 dataset. */
function StageBReport({ job }: { job: Job }) {
  const [ev, setEv] = useState<Evaluation | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const publishable = job.report_status ? job.report_status.state === 'available' : job.state === 'completed';
  useEffect(() => {
    if (!publishable) return;
    let live = true;
    getJSON<Evaluation>(`/api/lifecycle/evaluations/${encodeURIComponent(job.id)}`).then(d => live && setEv(d), e => live && setErr(e instanceof Error ? e.message : 'unavailable'));
    return () => { live = false; };
  }, [job.id, publishable]);
  if (job.report_status?.state === 'withheld') return <p className="ws-alert">The agent runs finished, but the readiness report is withheld: it did not pass the publication leak audit (fail-closed). The agent runs, traces and screenshots remain available under Agent runs.</p>;
  if (!publishable) return <p className="ws-empty-note">{ACTIVE.includes(job.state) ? 'The readiness report appears when every agent run is graded and the evidence has passed the leak audit.' : `This evaluation ended ${label(job.state).toLowerCase()}; it has no report.${job.error ? ` ${job.error}` : ''}`}</p>;
  if (err) return <p className="ws-alert">The readiness report is unavailable: {err}</p>;
  if (!ev) return <p className="ws-empty-note">Loading the readiness report…</p>;
  return <div className="ws-report"><Report ev={ev} /><p className="ws-note"><a className="ws-link" href={`#/reports/${job.id}`}>Open the report on its own page →</a> · <a className="ws-link" href={`/api/ironbark/jobs/${job.id}/repetitions/1/export`} download={`${job.id.slice(0, 13)}.json`}>Export JSON</a></p></div>;
}

/** Operator diagnostics: what has actually been spent, what is still held, and what the owner has authorised (two separate limits). */
function Budget({ s, ev, history }: { s: NonNullable<Config['spending']>; ev: ArmedEvaluation | null; history: HistoryItem[] }) {
  const usd = (n: number) => `US$${n.toFixed(2)}`;
  const costs = history.filter(h => h.cost_usd != null && h.mode === 'live').map(h => h.cost_usd as number);
  const per = ev?.options[0]?.reservation_usd ?? null;
  return <details className="ws-method ws-budget"><summary>Budget &amp; capacity</summary>
    <dl>
      <div><dt>Actual model spend</dt><dd>{usd(s.settled)} <small>settled, {s.settled_jobs} evaluation{s.settled_jobs === 1 ? '' : 's'}</small></dd></div>
      <div><dt>Held for unsettled runs</dt><dd>{usd(s.outstanding)} <small>{s.unsettled_jobs} evaluation{s.unsettled_jobs === 1 ? '' : 's'}, kept at their full reservation</small></dd></div>
      <div><dt>Available</dt><dd>{usd(s.available)} <small>of the {usd(s.ceiling)} hosted budget</small></dd></div>
      {ev && <div><dt>Live runs authorised</dt><dd>{ev.launches.left} of {ev.launches.max} left <small>{per ? `each reserves ${usd(per)}; the budget covers ${Math.floor(s.available / per + 1e-9)}` : ''}</small></dd></div>}
      {costs.length > 0 && <div><dt>Cost per completed evaluation</dt><dd>{costs.map(usd).join(' · ')}</dd></div>}
    </dl>
    <p className="ws-budget-note">A run reserves its worst case before it starts. When it has finished and every model request is settled in its durable ledger, only its actual cost stays committed and the rest is released; runs with unsettled requests keep their full reservation. {s.basis}.</p>
  </details>;
}

export function HostedEvaluation({ onOpen, initialJob }: { onOpen: (report: unknown, label: string) => void; initialJob?: string | null }) {
  const [config, setConfig] = useState<Config | null>(null);
  const [reps, setReps] = useState(1);
  const [job, setJob] = useState<Job | null>(null);
  const [recent, setRecent] = useState<HistoryItem[]>([]);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(Date.now() / 1000);
  const [tab, setTab] = useState<'watch' | 'results' | 'insights'>('watch');
  const [selection, setSelection] = useState<Selection | null>(null);
  const [token, setToken] = useState('');   // memory only: never written to browser storage; re-entered after a reload
  useEffect(() => { sessionStorage.removeItem(LEGACY_TOKEN); }, []);
  const current = useRef<string | null>(null);
  const top = useRef<HTMLDivElement>(null);
  const agent = useRef<HTMLDivElement>(null);
  const [focus, setFocus] = useState(() => sessionStorage.getItem(FOCUS) === '1');
  const toggleFocus = () => setFocus(f => { sessionStorage.setItem(FOCUS, f ? '0' : '1'); return !f; });

  async function load(id: string) {
    const changed = current.current !== id;
    current.current = id;
    const next = await getJSON<Job>(`/api/ironbark/jobs/${encodeURIComponent(id)}`);
    if (current.current === id) {
      setJob(next);
      if (changed) { setSelection(null); setTab(ACTIVE.includes(next.state) ? 'watch' : 'results'); }
    }
    return next;
  }
  const refreshList = () => getJSON<HistoryItem[]>('/api/ironbark/jobs').then(setRecent).catch(() => {});
  const refreshConfig = () => getJSON<Config>('/api/ironbark/config').then(setConfig).catch(() => setConfig(null));

  useEffect(() => {
    void refreshConfig(); void refreshList();
    const id = initialJob || localStorage.getItem(STORE);
    if (id) load(id).catch(() => localStorage.removeItem(STORE));
  }, [initialJob]);
  useEffect(() => {
    if (!job || !ACTIVE.includes(job.state)) return;
    const poll = setInterval(() => { load(job.id).then(j => { if (!ACTIVE.includes(j.state)) { setTab('results'); void refreshConfig(); void refreshList(); } }).catch(e => setMessage(e.message)); }, 2500);
    const tick = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => { clearInterval(poll); clearInterval(tick); };
  }, [job?.id, job?.state]);
  useEffect(() => { // keep the worker status fresh; re-enables Run when another evaluation finishes
    const busy = config?.worker?.state === 'busy';
    const t = setInterval(() => { void refreshConfig(); if (busy) void refreshList(); }, busy ? 10000 : 30000);
    return () => clearInterval(t);
  }, [config?.worker?.state, config?.worker?.job]);

  useEffect(() => { // Esc leaves evidence focus
    if (!focus) return;
    const on = (e: KeyboardEvent) => { if (e.key === 'Escape') { sessionStorage.setItem(FOCUS, '0'); setFocus(false); } };
    window.addEventListener('keydown', on); return () => window.removeEventListener('keydown', on);
  }, [focus]);

  async function start() {
    setBusy(true); setMessage('');
    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (operatorOnly && token) headers.Authorization = `Bearer ${token}`;
      const data = await getJSON<{ id: string }>('/api/ironbark/jobs', { method: 'POST', headers, body: JSON.stringify({ repetitions: reps }) });
      localStorage.setItem(STORE, data.id);
      history.replaceState(null, '', `#/run/${data.id}`);
      await load(data.id); setTab('watch'); void refreshConfig(); void refreshList();
    } catch (e) {
      if (operatorOnly && (e as { status?: number }).status === 403) { setToken(''); setMessage(config?.judge_access ? 'That access code was not accepted. Check it and try again.' : 'The operator token was not accepted. Re-enter it to start an evaluation.'); }
      else setMessage(e instanceof Error ? e.message : 'Evaluation unavailable.');
      void refreshConfig();
    }
    finally { setBusy(false); }
  }
  async function open(rep: Rep) {
    if (!job) return;
    try { onOpen(await getJSON(`/api/ironbark/jobs/${job.id}/repetitions/${rep.index}/export`), `Evaluation ${job.id.slice(5, 13)} · repetition ${rep.index}`); }
    catch (e) { setMessage(e instanceof Error ? e.message : 'Sanitized results are unavailable.'); }
  }
  const select = (id: string) => { localStorage.setItem(STORE, id); history.replaceState(null, '', `#/run/${id}`); setMessage(''); load(id).catch(e => setMessage(e.message)); top.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' }); };
  const reduce = () => !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  // Selecting a run brings the agent view (below the sticky job bar) into view.
  const watch = (s: Selection) => { setSelection(s); setTab('watch'); requestAnimationFrame(() => agent.current?.scrollIntoView?.({ behavior: reduce() ? 'auto' : 'smooth', block: 'start' })); };

  const questions = Object.fromEntries((config?.tasks ?? []).map(t => [t.task, t.question]));
  const cap = (v: string | undefined, d: string) => v ? v.charAt(0).toUpperCase() + v.slice(1) : d;
  const armedNames = { Original: cap(config?.evaluation?.variants?.[0], 'Original'), Modified: cap(config?.evaluation?.variants?.[1], 'Modified') };
  const names = job?.arm_display ?? (job ? { Original: 'Original', Modified: 'Modified' } : armedNames);
  const lowerNames = { original: names.Original, modified: names.Modified };
  const SITE_HOST: Record<string, string> = { larkspur: 'larkspur-college', ironbark: 'ironbark-hire' };
  const operatorOnly = config?.access === 'operator';
  const running = !!job && ACTIVE.includes(job.state);
  const othersRunning = !!config?.active && config.active !== job?.id;
  const stageB = config?.engine === 'stage-b';
  const ev = config?.evaluation ?? null;
  const nTasks = config?.tasks?.length || 4;
  const runsPerRep = 2 * nTasks;
  const done = job ? job.reps.reduce((a, r) => a + r.tasks.filter(t => t.state === 'completed' || t.state === 'failed').length, 0) : 0;
  const total = job?.engine === 'stage-b' ? job.reps.reduce((a, r) => a + r.tasks.length, 0) : (job?.repetitions ?? 0) * 8;
  // M9: a Stage B job shows what EXECUTED; the preserved admission record is shown beside it when the two differ (see record_note).
  const shown = job && job.engine === 'stage-b' && job.execution && !ACTIVE.includes(job.state) && !ACTIVE.includes(job.execution.state) ? job.execution.state : (job?.state ?? 'pending');
  const elapsed = job?.started_at ? (job.finished_at ?? now) - job.started_at : 0;
  const mode = job?.mode ?? config?.mode;
  const budgetOk = stageB ? (config?.repetitions ?? []).includes(reps) && (config?.remaining_repetitions ?? 0) > 0 : (config?.remaining_repetitions ?? 0) >= reps;
  const canRun = !!config?.available && !busy && !running && !othersRunning && budgetOk && (!operatorOnly || token.length >= 24);
  const judgeAccess = !!config?.judge_access;
  const liveRun = stageB && ev?.mode === 'paid';
  const perRep = config?.repetition_duration?.seconds ?? 560;
  const worker = config?.worker;
  const basis = config?.repetition_duration?.basis === 'measured' ? `measured over ${config.repetition_duration.samples} completed evaluation${config.repetition_duration.samples > 1 ? 's' : ''}` : 'based on the first genuine Muse Spark run';
  const note = !config ? 'Connecting to the evaluation service…'
    : stageB && config.launch && !config.launch.authorized ? `${config.launch.detail ?? 'No launch is authorised.'} Recorded evaluations remain available.`
    : stageB && !ev ? 'No evaluation is armed. The owner arms a frozen suite at the server terminal; recorded evaluations remain available.'
    : !config.available ? 'New evaluations are currently unavailable. Recorded and previous evaluations remain available.'
    : othersRunning ? 'Another evaluation is running. Start yours when the worker is available again.'
    : !budgetOk ? (stageB ? (ev && ev.launches.left <= 0 ? 'Every armed launch has been used. The owner arms a new evaluation at the server terminal.' : 'This number of repetitions is not armed, or its reservation does not fit the remaining hosted budget.') : 'The hosted budget for new evaluations is exhausted.')
    : operatorOnly && token.length < 24 ? (judgeAccess ? 'Enter your access code to start a live evaluation. Anyone can watch running and completed evaluations.' : 'New evaluations are not open to the public yet: starting one needs the operator token (above). Anyone can watch and inspect existing evaluations.')
    : stageB ? `${reps * runsPerRep} browser agents · ${minutes(perRep * reps)}, varies with the agent`
    : `${reps * 8} fresh agent runs · ${minutes(perRep * reps)}, varies with the agent`;
  const latest = recent.find(r => r.id !== job?.id && r.summary);

  return <div className="ws-eval">
    <div className="ws-intro">
      <div>
        <p className="eyebrow">Evaluation workspace</p>
        <h1 className="ws-title">Run real agents on a website.</h1>
        <p className="ws-lede">Fresh Muse Spark browser agents do real customer tasks on two versions of a website. Every answer is checked against the site’s own records, and the report shows where agents got stuck and what to change.</p>
        <p className="ws-lede-note">{stageB && ev ? <>This live evaluation gives {nTasks} customer task{nTasks === 1 ? '' : 's'} from the <a className="ws-link" href="#/lifecycle/review">{ev.site === 'larkspur' ? 'Larkspur' : ev.site} task set</a> to browser agents on the <strong>{armedNames.Original}</strong> and the <strong>{armedNames.Modified}</strong> site.{armedNames.Modified === 'Improved' ? <> The Improved site applies every recommendation from the <a className="ws-link" href="#/lifecycle/improve">first evaluation</a>.</> : null} </> : null}The websites are frozen copies of the fictional Larkspur Community College; the improvements were made by hand from the report.</p>
      </div>
      {config && <div className={`ws-worker ${worker?.state === 'idle' && stageB && config.launch && !config.launch.authorized ? 'blocked' : worker?.state ?? 'unavailable'}`} role="status">
        <span className="ws-dot" aria-hidden="true" />
        <div>
          {worker?.state === 'idle' && stageB && config.launch && !config.launch.authorized ? <><strong>Worker ready · no launch authorised</strong><span>{config.launch.detail} Completed evaluations remain available.</span></>
          : worker?.state === 'idle' ? <><strong>Worker available</strong><span>{stageB ? `Ready to start ${liveRun ? 'a live evaluation' : 'an evaluation'} · one runs at a time · ${minutes(perRep)}` : `Ready to start a new evaluation · one evaluation runs at a time · ${minutes(perRep)} per repetition (${basis})`}</span></>
          : worker?.state === 'busy' ? <><strong>Evaluation running</strong><span>{worker.job === job?.id ? 'Running your selected evaluation' : 'Another evaluation is running'}: {worker.finished_runs ?? 0} of {worker.total_runs ?? (worker.job === job?.id && total ? total : ev?.options[0]?.trials ?? '–')} agent runs finished{worker.estimated_remaining_seconds ? `, ${minutes(worker.estimated_remaining_seconds)} left (estimate)` : ''}. Completed evaluations below remain available.</span>
              {worker.job && worker.job !== job?.id && <button className="ws-link" onClick={() => select(worker.job!)}>Watch it live →</button>}</>
          : <><strong>Evaluations unavailable</strong><span>New evaluations are paused. Recorded and completed evaluations remain available.</span></>}
        </div>
      </div>}
    </div>

    <div className={`ws-layout${job ? ' has-job' : ''}${focus && job && tab === 'watch' ? ' focus' : ''}`}>
      <aside className="ws-compose" aria-label="New evaluation">
        <div className="ws-compose-head"><h2>New evaluation</h2>{mode && <span className={`ws-mode ${mode}`}>{MODE_LABEL[mode]}</span>}</div>
        <ol className="ws-steps">
          <li><span className="ws-step">01 · Website</span>
            {stageB ? <div className="ws-target" aria-label="Selected website">{ev ? <><strong>{ev.site === 'larkspur' ? 'Larkspur Community College' : ev.site === 'ironbark' ? 'Ironbark Hire Co.' : ev.site}</strong>
                <small>{nTasks} customer task{nTasks === 1 ? '' : 's'} · {armedNames.Original} vs {armedNames.Modified} site · {ev.launches.left} of {ev.launches.max} live run{ev.launches.max === 1 ? '' : 's'} left</small></>
                : <><strong>No evaluation armed</strong><small>The owner selects and authorises the frozen suite at the server terminal.</small></>}</div>
              : <div className="ws-target" aria-label="Selected website"><strong>No evaluation available</strong><small>New evaluations are not available on this server right now; recorded evaluations remain available.</small></div>}</li>
          {stageB && (config?.repetitions?.length ?? 0) <= 1
            ? <li><span className="ws-step">02 · What runs</span>
                <p className="ws-run-summary">{ev ? `${runsPerRep} browser agents, one per task on each site · ${minutes(perRep)}` : 'Nothing to run right now.'}</p>
                {ev && (config?.tasks?.length ?? 0) > 0 && <ol className="ws-task-list">{config!.tasks.map(t => <li key={t.task}><q>{t.question}</q></li>)}</ol>}</li>
            : <li><span className="ws-step">02 · Repetitions</span>
            <div className="ws-reps" role="radiogroup" aria-label="Paired repetitions">{(config?.repetitions ?? [1, 3, 5]).map(n =>
              <button key={n} role="radio" aria-checked={reps === n} disabled={running} onClick={() => setReps(n)}><strong>{n}</strong><small>{n * (stageB ? runsPerRep : 8)} agent runs</small><small>{minutes(perRep * n)}</small></button>)}</div></li>}
          <li><span className="ws-step">03 · Run</span>
            {operatorOnly && config?.available && <div className="ws-operator">
              <label htmlFor="ws-operator-token">{judgeAccess ? 'Access code' : 'Operator token'} <span className="ws-operator-badge">{judgeAccess ? 'judges and operators' : 'operators only'}</span></label>
              <div className="ws-operator-row">
                <input id="ws-operator-token" type="password" aria-label={judgeAccess ? 'Access code' : 'Operator token'} aria-describedby="ws-operator-help" autoComplete="off" spellCheck={false} value={token}
                  placeholder={judgeAccess ? 'Paste your access code' : 'Paste the operator token'} onChange={e => setToken(e.target.value.trim())} />
                {token && <button type="button" className="ws-link" onClick={() => setToken('')}>Clear</button>}
              </div>
              <p id="ws-operator-help" className="ws-operator-help">Held in this page's memory only (never saved; re-enter it after a reload) and sent only as an authorization header when you start. The server checks it.</p>
            </div>}
            <button className="btn btn-signal ws-run" disabled={!canRun} aria-describedby="ws-run-note" onClick={() => void start()}>{busy ? 'Starting…' : running ? 'Evaluation running' : liveRun ? 'Run live evaluation' : 'Run evaluation'}</button>
            <p className="ws-note" id="ws-run-note">{note}</p></li>
        </ol>
        {stageB && config?.spending && <Budget s={config.spending} ev={ev} history={recent} />}
        {stageB && <details className="ws-method"><summary>Methodology &amp; provenance</summary>
          <p><strong>Tasks.</strong> {ev ? <>The frozen task set <code>{ev.frozen_suite}</code> (<code>{ev.frozen_suite_sha256.slice(0, 12)}…</code>), approved by the owner; the questions are the customers’ own words, generated and checked in the <a className="ws-link" href="#/lifecycle">journey</a>.</> : 'none open.'}</p>
          <p><strong>Agent.</strong> Browser Use agent driven by <code>{ev?.agent.model ?? config?.model}</code>, reasoning <code>{show(ev?.agent.reasoning_effort)}</code>, {show(ev?.agent.max_completion_tokens)} completion tokens, profile <code>{ev?.agent.profile}</code>; each task limited to {config?.tasks[0]?.limits?.max_model_requests ?? 14} model requests; no retries.</p>
          <p><strong>Spending.</strong> The owner authorised a fixed number of live runs in advance. Each run reserves its worst case against the service budget before it starts, and every model request is reserved against the run’s own cap before it is sent.</p>
          <p><strong>Grading.</strong> Every answer is checked against the site’s own records, which the agent never sees. The report shows correct answers, exact matches, requests, time and cost per agent, and its recommendations cite the evidence.</p>
          <p><strong>Isolation.</strong> Each browser runs in its own network namespace that can reach only the frozen website copy; model credentials never enter the browser.</p>
        </details>}
        {!stageB && job && job.engine !== 'stage-b' && <details className="ws-method"><summary>Methodology &amp; provenance (historical Ironbark evaluation)</summary>
          <p><strong>Agent.</strong> Browser Use agent driven by <code>{config?.model ?? 'unavailable'}</code> with the frozen profile <code>{config?.agent_settings?.profile ?? config?.agent_profile ?? 'unavailable'}</code>{config?.agent_settings && <> (reasoning_effort <code>{show(config.agent_settings.reasoning_effort)}</code>, max_completion_tokens <code>{show(config.agent_settings.max_completion_tokens)}</code>, read from the profile file)</>}; each task is limited to {config?.tasks[0]?.limits?.max_steps ?? 14} steps and {config?.tasks[0]?.limits?.timeout_seconds ?? 240} seconds; no retries.</p>
          {job?.reps.find(r => r.provenance)?.provenance && <ProvenanceNote p={job.reps.find(r => r.provenance)!.provenance!} />}
          <p><strong>Tasks.</strong> The same four frozen tasks run on both versions, in a counterbalanced order, for every repetition:</p>
          <ol>{(config?.tasks ?? []).map(t => <li key={t.task}>{t.question}</li>)}</ol>
          <p><strong>Grading.</strong> An independent grader checks each answer against ground truth the agent never sees. “Evidence-supported” also requires that the agent actually viewed the pages holding the answer. Agent self-assessment is ignored. Official grades use grader v1 (the version pre-registered for these tasks). Grader v2, shown separately as a post-hoc rescore, also accepts a correct answer that adds detail consistent with the site, and still rejects wrong, hedged, contradictory or multiple-candidate answers.</p>
          <p><strong>Sites.</strong> Original and Modified are frozen snapshots of a controlled test site; Modified shows the refundable deposit, minimum hire and delivery fields on the listing cards (an owner-selected change).</p>
          <p><strong>Live view.</strong> Pages, screenshots, actions and the agent’s stated goals are an allowlisted projection of each run’s own trace; prompts, page source and credentials are never shown.</p>
          <p><strong>Isolation.</strong> Each browser runs in its own network namespace that can reach only the snapshot mirror; it has no internet, DNS, local-service or provider access. Model credentials never enter the browser.</p>
          <p><strong>Limits.</strong> Each repetition is capped at US$1.60 of calculated model spend (US$0.80 per version), enforced before every model request. Calculated spend is not a bill.</p>
          <p><strong>Interpretation.</strong> Each completed repetition is also assessed with the pre-registered paired rule and the exploratory listing rule; small samples are often inconclusive. Insights are derived from observed telemetry; suggestions are not measured outcomes unless marked as tested. No difference here is a general claim about real websites.</p>
        </details>}
      </aside>

      <div className="ws-main" ref={top}>
        {message && <p role="alert" className="ws-alert">{message}</p>}
        {!job && <div className="ws-empty">
          <p className="eyebrow">No evaluation open</p>
          <h2>Start an evaluation, or open one from the history below.</h2>
          {latest && <button className="btn btn-ghost" onClick={() => select(latest.id)}>Open the latest evaluation · {when(latest.created_at)} <span className="arr" aria-hidden="true">→</span></button>}
        </div>}

        {job && <section className="ws-job" aria-label={`Evaluation ${job.id.slice(0, 13)}`}>
          <div className="ws-jobbar">
          <header className="ws-job-head">
            <div className="ws-status" aria-live="polite"><span className={`ws-dot ${shown}`} aria-hidden="true" /><strong>{label(shown)}</strong>
              {shown !== job.state && <span className="ws-record" title="The job record is kept exactly as it was written">Job record: {label(job.state).toLowerCase()}</span>}
              <span>{done} / {total || '–'} agent runs finished</span>{job.started_at && <span>{clock(elapsed)} elapsed</span>}</div>
            <div className="ws-job-meta"><span>{job.repetitions} repetition{job.repetitions === 1 ? '' : 's'} · started {when(job.created_at)}</span><code title={job.id}>{job.id.slice(0, 13)}</code></div>
          </header>
          <div className="ws-bar" role="progressbar" aria-label="Agent runs finished" aria-valuemin={0} aria-valuemax={total} aria-valuenow={done}><i style={{ width: `${total ? 100 * done / total : 0}%` }} /></div>
          <div className="ws-tabs" role="tablist" aria-label="Evaluation views">{(job.engine === 'stage-b' ? [['watch', running ? 'Watch live' : 'Agent runs'], ['results', 'Readiness report']] as const : [['watch', running ? 'Watch live' : 'Agent runs'], ['results', 'Results'], ['insights', 'Insights']] as const).map(([k, l]) =>
            <button key={k} role="tab" id={`ws-tab-${k}`} aria-controls={`ws-panel-${k}`} aria-selected={tab === k} onClick={() => setTab(k)}>{k === 'watch' && running && <span className="ws-live" aria-hidden="true" />}{l}</button>)}</div>
          </div>
          {job.recovery_required && <p className="ws-alert">This evaluation lost its worker and will be marked interrupted.</p>}
          {job.state === 'interrupted' && <p className="ws-alert">This evaluation was interrupted by a service restart. Finished repetitions remain available.</p>}
          {job.mode === 'rehearsal' && <p className="ws-alert">Rehearsal: real browsers and grading, but a scripted agent instead of a model. These are not Muse Spark results.</p>}
          {job.engine === 'stage-b' && job.error && <p className="ws-alert">{job.error}</p>}
          {job.record_note && <p className="ws-note-info" role="note">{job.record_note}</p>}
          {job.engine === 'stage-b' && job.execution?.state === 'completed' && job.report_status?.state === 'withheld' && <p className="ws-alert">Every agent run finished; only the readiness report is withheld (it did not pass the publication leak audit).</p>}

          {tab === 'watch' && <div className="ws-watch" role="tabpanel" id="ws-panel-watch" aria-labelledby="ws-tab-watch">
            <div ref={agent} className="ws-agent-anchor"><AgentPanel jobId={job.id} active={running} selection={selection} scripted={job.mode === 'rehearsal'} onClear={() => setSelection(null)} focus={focus} onFocus={toggleFocus} host={job.engine === 'stage-b' ? SITE_HOST[ev?.site ?? ''] ?? ev?.site ?? 'website' : 'ironbark-hire'} names={lowerNames} /></div>
            {(() => {
              const focus = selection?.repetition ?? (job.reps.find(r => ['preparing', 'running'].includes(r.state)) ?? job.reps[job.reps.length - 1])?.index;
              const grid = (rep: Rep) => <article key={rep.index} className="ws-rep">
                <header><strong>Repetition {rep.index}</strong><span className={`ws-pill ${rep.state}`}>{label(rep.state)}</span><small>Select a run to inspect it</small></header>
                <ProgressGrid rep={rep} questions={questions} onSelect={watch} selected={selection} names={names} /></article>;
              const others = job.reps.filter(r => r.index !== focus);
              return <div className="ws-rep-list">{job.reps.filter(r => r.index === focus).map(grid)}
                {others.length > 0 && <details className="ws-more"><summary>Other repetitions ({others.map(r => `${r.index}: ${label(r.state).toLowerCase()}`).join(' · ')})</summary>
                  <div className="ws-rep-list">{others.map(grid)}</div></details>}</div>;
            })()}
          </div>}

          {tab === 'results' && job.engine === 'stage-b' && <div role="tabpanel" id="ws-panel-results" aria-labelledby="ws-tab-results" className="ws-panel"><StageBReport job={job} /></div>}
          {tab === 'results' && job.engine !== 'stage-b' && <div role="tabpanel" id="ws-panel-results" aria-labelledby="ws-tab-results" className="ws-panel">
            {job.summary.Original.completed + job.summary.Modified.completed > 0 ? <Metrics job={job} /> : <p className="ws-empty-note">Results appear as agent runs are graded.</p>}
            <Analytics job={job} questions={questions} />
            <div className="ws-rep-list">{job.reps.map(rep => <article key={rep.index} className="ws-rep">
              <header><strong>Repetition {rep.index}</strong><span className={`ws-pill ${rep.state}`}>{label(rep.state)}</span>
                {rep.assessment && <span className="ws-rep-actions">
                  <button className="ws-link" onClick={() => void open(rep)}>Inspect evidence &amp; replay →</button>
                  <a className="ws-link" href={`/api/ironbark/jobs/${job.id}/repetitions/${rep.index}/export`} download={`${job.id.slice(0, 13)}-rep${rep.index}.json`}>Export JSON</a></span>}</header>
              <ProgressGrid rep={rep} questions={questions} onSelect={watch} />
              {rep.assessment && <p className="ws-verdicts">Frozen comparison rule: <strong>{rep.assessment.frozen_rule ?? 'unavailable'}</strong> · Exploratory listing rule: <strong>{rep.assessment.exploratory ?? 'unavailable'}</strong> · Evidence: {rep.assessment.evidence_origin === 'real_model' ? 'real model' : rep.assessment.evidence_origin ?? 'unverified'}</p>}
              {rep.grading_v2?.faithful && rep.grading_v2.assessment && <p className="ws-verdicts ws-v2-verdicts" title={rep.grading_v2.label}>Grader v2, post-hoc (not pre-registered): frozen rule applied to v2 grades <strong>{rep.grading_v2.assessment.frozen_rule ?? 'unavailable'}</strong> · exploratory rule <strong>{rep.grading_v2.assessment.exploratory ?? 'unavailable'}</strong></p>}
              {rep.provenance && <ProvenanceNote p={rep.provenance} />}
            </article>)}</div>
          </div>}

          {tab === 'insights' && job.engine !== 'stage-b' && <div role="tabpanel" id="ws-panel-insights" aria-labelledby="ws-tab-insights" className="ws-panel"><Insights jobId={job.id} active={running} /></div>}
        </section>}

        {recent.length > 0 && <section className="ws-history" aria-labelledby="ws-history-h"><div className="ws-section-head"><h2 id="ws-history-h">Evaluation history</h2><p>Select two finished evaluations to compare them side by side.</p></div><History items={recent} current={job?.id ?? null} open={select} /></section>}
      </div>
    </div>
  </div>;
}
