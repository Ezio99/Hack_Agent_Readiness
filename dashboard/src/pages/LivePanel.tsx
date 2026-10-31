import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, call, configured, getToken, setToken } from "../lib/scannerApi";
import { Callout, Pill } from "../components/ui";
import { LiveJob, LiveSummary, LiveTarget, cancelJob, exportJob, getJob, isActive, listJobs, liveTargets, startJob } from "../lib/liveApi";

const POLL_MS = 2000;                                                      // well inside the API rate limit (60 requests/minute per client)
const STAGE_LABEL: Record<string, string> = { inspect: "Explore the website", taskgen: "Generate customer tasks", freeze: "Freeze tasks", baseline_trials: "Agents attempt the tasks", trace: "Analyse traces", investigate: "Investigator", recommend: "Recommendations", report: "Report", apply_fix: "Apply a fix", post_trials: "Retest", evaluate: "Evaluate", final_report: "Final report" };

/** Live evaluation (M0): start a bounded backend job on a registered demo site, watch the real pipeline stages, trace events and recorded cost, then open the result in the page below (the same
 *  view that replays any exported run). M0 jobs run in MOCK mode; the panel says so on every screen. */
export function LivePanel({ onOpen }: { onOpen: (report: unknown, label: string) => boolean }) {
  const [authed, setAuthed] = useState<boolean>(!!getToken());
  const [code, setCode] = useState("");
  const [targets, setTargets] = useState<LiveTarget[]>([]);
  const [target, setTarget] = useState("");
  const [goal, setGoal] = useState("Can an agent compare hire prices and availability across the catalogue?");
  const [job, setJob] = useState<LiveJob | null>(null);
  const [history, setHistory] = useState<LiveSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  const fail = useCallback((e: unknown) => {
    if (e instanceof ApiError && e.status === 401 && getToken()) { setToken(null); setAuthed(false); setError("Your session expired. Enter a code again."); }
    else setError(e instanceof Error ? e.message : "Unexpected error.");
  }, []);
  const refreshHistory = useCallback(async () => { try { setHistory((await listJobs()).jobs); } catch (e) { fail(e); } }, [fail]);

  useEffect(() => { if (configured() && authed) liveTargets().then((r) => { setTargets(r.targets); setTarget((t) => t || r.targets[0]?.id || ""); void refreshHistory(); }).catch(fail); }, [authed, fail, refreshHistory]);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  const follow = useCallback((id: string) => {
    window.clearTimeout(timer.current);
    const tick = async () => {
      try {
        const j = await getJob(id);
        setJob(j);
        if (isActive(j.state)) timer.current = window.setTimeout(tick, POLL_MS); else void refreshHistory();
      } catch (e) { fail(e); }
    };
    void tick();
  }, [fail, refreshHistory]);

  if (!configured()) return <Callout title="Live evaluation needs the evaluation service" tone="warn"><p>This build has no service address (<code>VITE_SCANNER_API_URL</code>). Start the service with <code>readiness scanner serve</code> and rebuild the dashboard with that address to run live evaluations; the recorded reports below work without it.</p></Callout>;

  const redeem = async () => {
    setError(null); setBusy(true);
    try { const r = await call<{ token: string }>("/api/session", { method: "POST", json: { code: code.trim() } }); setToken(r.token); setCode(""); setAuthed(true); } catch (e) { fail(e); }
    setBusy(false);
  };
  const start = async () => {
    setError(null); setBusy(true);
    try { const j = await startJob(target, goal); setJob(j); follow(j.id); } catch (e) { fail(e); }
    setBusy(false);
  };
  const cancel = async () => { if (!job) return; try { setJob(await cancelJob(job.id)); window.clearTimeout(timer.current); void refreshHistory(); } catch (e) { fail(e); } };
  const open = async (id: string, label: string) => { setError(null); try { if (!onOpen(await exportJob(id), label)) setError("The returned report could not be displayed."); } catch (e) { fail(e); } };

  if (!authed) return (
    <section className="livepanel" aria-label="Live evaluation">
      <h2>Live evaluation</h2>
      {error && <p role="alert" className="scan-error">{error}</p>}
      <p className="muted">Enter your invitation code to start evaluations.</p>
      <p><input aria-label="Invitation code" value={code} onChange={(e) => setCode(e.target.value)} onKeyDown={(e) => e.key === "Enter" && code.trim() && void redeem()} autoComplete="off" />{" "}
        <button type="button" className="primary" disabled={busy || !code.trim()} onClick={() => void redeem()}>Continue</button></p>
    </section>
  );

  const active = job ? isActive(job.state) : false;
  const tone = (s: string) => (s === "done" ? "pass" : s === "failed" ? "fail" : s === "running" ? "warn" : "neutral") as "pass" | "fail" | "warn" | "neutral";
  return (
    <section className="livepanel" aria-label="Live evaluation">
      <h2>Live evaluation</h2>
      <p className="badge" role="note">M0 · MOCK execution: a real backend job runs the real pipeline (site capture, task generation, browser agent, trace analysis, investigator) with scripted stand-ins for the language model. Nothing is spent.</p>
      {error && <p role="alert" className="scan-error">{error}</p>}
      <div className="liveform">
        <label>Website <select aria-label="Website to evaluate" value={target} onChange={(e) => setTarget(e.target.value)} disabled={active}>{targets.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}</select></label>
        <label>Evaluation goal <textarea aria-label="Evaluation goal" value={goal} maxLength={300} rows={2} onChange={(e) => setGoal(e.target.value)} disabled={active} /></label>
        <button type="button" className="primary" disabled={busy || active || !target || goal.trim().length < 5} onClick={() => void start()}>Start mock evaluation</button>
        {active && <button type="button" onClick={() => void cancel()}>Cancel</button>}
      </div>
      {targets.find((t) => t.id === target) && <p className="muted">{targets.find((t) => t.id === target)!.description}</p>}
      {job && (
        <div className="livejob" aria-live="polite">
          <p><strong>{job.state === "completed" ? "Completed" : job.state === "running" || job.state === "queued" ? "Running" : job.state.replace("_", " ")}</strong> · {Math.round(job.progress * 100)}% · <progress max={1} value={job.progress} aria-label="Progress" /> · recorded cost US${job.spend.committed_usd.toFixed(4)} <span className="muted">({job.spend.basis})</span></p>
          {job.notice && <p className="muted" role="note">{job.notice}</p>}
          {job.error && <p role="alert" className="scan-error">{job.error}</p>}
          <ol className="stages">{job.stages.map((s) => <li key={s.name}><Pill tone={tone(s.status)}>{s.status}</Pill> {STAGE_LABEL[s.name] ?? s.name}{s.detail ? <span className="muted"> — {s.detail}</span> : null}</li>)}</ol>
          {job.trials.length > 0 && <p className="muted">Trials: {job.trials.length}{job.tasks_planned ? ` of ${job.tasks_planned}` : ""} · {job.trials.filter((t) => t.passed).length} passed · {job.trials.reduce((n, t) => n + (t.page_views ?? 0), 0)} page views</p>}
          <details open><summary>Trace and events ({job.events.length})</summary><ul className="events" aria-label="Events">{job.events.slice(-60).map((e, i) => <li key={i} className={`ev-${e.kind}`}>{e.text}</li>)}</ul></details>
          {(job.state === "completed" || (!active && job.opened)) && <p><button type="button" className="primary" onClick={() => void open(job.id, `${job.target_id} · ${job.id}`)}>Open results</button> <span className="muted">Evidence, findings and recommendations open in the report below, labelled as mock.</span></p>}
        </div>
      )}
      {history.length > 0 && (
        <details><summary>Your evaluations ({history.length})</summary>
          <ul className="history">{history.map((h) => <li key={h.id}><code>{h.id}</code> · {h.target_id} · {h.state} · {new Date(h.created_at * 1000).toLocaleString()} <button type="button" className="linklike" onClick={() => { setJob(null); follow(h.id); }}>View</button>
            {h.state !== "queued" && h.state !== "running" && <> <button type="button" className="linklike" onClick={() => void open(h.id, `${h.target_id} · ${h.id}`)}>Replay results</button></>}</li>)}</ul>
        </details>
      )}
    </section>
  );
}
