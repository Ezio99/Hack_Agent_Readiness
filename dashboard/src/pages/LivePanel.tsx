import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, call, configured, getToken, setToken } from "../lib/scannerApi";
import { Callout, Pill } from "../components/ui";
import { LiveInfo, LiveJob, LiveSummary, LiveTarget, cancelJob, exportJob, getJob, isActive, listJobs, liveTargets, startJob } from "../lib/liveApi";

const POLL_MS = 2000;                                                      // well inside the API rate limit (60 requests/minute per client)
const STAGE_LABEL: Record<string, string> = { inspect: "Explore the website", taskgen: "Generate customer tasks", freeze: "Freeze tasks", baseline_trials: "Agents attempt the tasks", trace: "Analyse traces", investigate: "Investigator", recommend: "Recommendations", report: "Report", apply_fix: "Apply a fix", post_trials: "Retest", evaluate: "Evaluate", final_report: "Final report" };

const STATE_LABEL: Record<string, string> = { queued: "Queued", running: "Running", completed: "Completed", failed: "Failed", cancelled: "Cancelled", timed_out: "Timed out",
  awaiting_approval: "Stopped: waiting for an approval this evaluation may not grant", stopped: "Stopped safely" };

/** Live evaluation: start a bounded backend job on a registered demo site, watch the real pipeline stages, trace events and recorded cost, then open the result in the page below (the same
 *  view that replays any exported run). A MOCK job spends nothing; a LIVE job needs the user's explicit confirmation of its maximum spend, which the server enforces independently. */
export function LivePanel({ onOpen }: { onOpen: (report: unknown, label: string) => boolean }) {
  const [authed, setAuthed] = useState<boolean>(!!getToken());
  const [code, setCode] = useState("");
  const [targets, setTargets] = useState<LiveTarget[]>([]);
  const [target, setTarget] = useState("");
  const [goal, setGoal] = useState("Can an agent compare hire prices and availability across the catalogue?");
  const [job, setJob] = useState<LiveJob | null>(null);
  const [live, setLive] = useState<LiveInfo | null>(null);
  const [mode, setMode] = useState<"mock" | "live">("mock");
  const [confirming, setConfirming] = useState(false);
  const [agreed, setAgreed] = useState(false);
  const [context, setContext] = useState("");
  const [history, setHistory] = useState<LiveSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  const fail = useCallback((e: unknown) => {
    if (e instanceof ApiError && e.status === 401 && getToken()) { setToken(null); setAuthed(false); setError("Your session expired. Enter a code again."); }
    else setError(e instanceof Error ? e.message : "Unexpected error.");
  }, []);
  const refreshHistory = useCallback(async () => { try { setHistory((await listJobs()).jobs); } catch (e) { fail(e); } }, [fail]);

  useEffect(() => { if (configured() && authed) liveTargets().then((r) => { setLive(r.live); setTargets(r.targets); setTarget((t) => t || r.targets[0]?.id || ""); void refreshHistory(); }).catch(fail); }, [authed, fail, refreshHistory]);
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
    try {
      const j = mode === "live" && live ? await startJob(target, goal, { confirm_budget_usd: live.cap_usd }, context) : await startJob(target, goal, undefined, context);
      setConfirming(false); setAgreed(false); setJob(j); follow(j.id);
    } catch (e) { fail(e); }
    setBusy(false);
  };
  const liveOk = !!live && live.targets.includes(target);
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
  const tone = (s: string) => (s === "done" ? "pass" : s === "failed" ? "fail" : s === "running" || s === "awaiting_approval" ? "warn" : "neutral") as "pass" | "fail" | "warn" | "neutral";
  return (
    <section className="livepanel" aria-label="Live evaluation">
      <h2>Live evaluation</h2>
      <p className="badge" role="note">{mode === "live" ? (live?.dev_provider ? "LIVE path · DEV PROVIDER: the real pipeline, spend gate and ledger against a loopback stand-in for the model. No real model, no real spend." : `LIVE · real model calls (${live?.model}), hard-capped at US$${live?.cap_usd.toFixed(2)} per evaluation.`) : "MOCK execution: a real backend job runs the real pipeline (site capture, task generation, browser agent, trace analysis, investigator) with scripted stand-ins for the language model. Nothing is spent."}</p>
      {error && <p role="alert" className="scan-error">{error}</p>}
      <div className="liveform">
        <label>Website <select aria-label="Website to evaluate" value={target} onChange={(e) => setTarget(e.target.value)} disabled={active}>{targets.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}</select></label>
        <label>Website context <span className="muted">(optional · a briefing about the business, its customers and priorities)</span>
          <textarea aria-label="Website context" value={context} maxLength={2000} rows={4} placeholder="e.g. who the customers are, what they compare, what the business cares about" onChange={(e) => setContext(e.target.value)} disabled={active} /></label>
        <p className="muted ctxnote">Client-supplied and <strong>unverified</strong>: it guides task generation and the investigator, but it is never treated as evidence about the website, and no finding rests on it. It is saved with the run and is part of what you approve.
          {targets.find((t) => t.id === target)?.sample_context && <> <button type="button" className="linklike" disabled={active} onClick={() => setContext(targets.find((t) => t.id === target)!.sample_context!)}>Use the sample briefing</button></>}{context && <> <button type="button" className="linklike" disabled={active} onClick={() => setContext("")}>Clear</button></>}</p>
        {live && <fieldset className="modes" disabled={active}><legend>Execution</legend>
          <label><input type="radio" name="mode" checked={mode === "mock"} onChange={() => { setMode("mock"); setConfirming(false); }} /> Mock (free, scripted stand-ins)</label>{" "}
          <label><input type="radio" name="mode" checked={mode === "live"} onChange={() => setMode("live")} disabled={!liveOk} /> Live (real model, maximum US${live.cap_usd.toFixed(2)}){!liveOk ? " — Ironbark only" : ""}</label>
        </fieldset>}
        <label>Evaluation goal <textarea aria-label="Evaluation goal" value={goal} maxLength={300} rows={2} onChange={(e) => setGoal(e.target.value)} disabled={active} /></label>
        {mode === "mock"
          ? <button type="button" className="primary" disabled={busy || active || !target || goal.trim().length < 5} onClick={() => void start()}>Start mock evaluation</button>
          : <button type="button" className="primary" disabled={busy || active || !liveOk || goal.trim().length < 5} onClick={() => setConfirming(true)}>Review and start live evaluation…</button>}
        {active && <button type="button" onClick={() => void cancel()}>Cancel</button>}
      </div>
      {confirming && mode === "live" && live && (
        <div className="confirm" role="dialog" aria-label="Confirm live evaluation spend">
          <h3>Confirm a paid evaluation</h3>
          <p>This starts a <strong>live</strong> evaluation of <strong>{targets.find((t) => t.id === target)?.label}</strong>: the model <code>{live.model}</code> will propose tasks for your goal, drive a browser through them and investigate the traces.</p>
          {live.smoke && <p><strong>Operator smoke test:</strong> the evaluation stops after task generation (at most 3 model requests, no retries); no browser trial runs.</p>}
          <p><strong>Maximum spend: US${live.cap_usd.toFixed(2)}.</strong> The server enforces this cap itself: every request is reserved against it before it is sent, and the evaluation stops safely if any stage would exceed it. Cost is calculated from reported tokens at published prices; it is not a bill.</p>
          {live.dev_provider && <p className="muted">This server uses the DEV PROVIDER (a loopback stand-in): no real model is called and nothing real is spent.</p>}
          <p>Goal: <q>{goal.trim()}</q></p>
          {context.trim() && <p className="muted">Website context included ({context.trim().length} characters): client-supplied, unverified; changing it later means a new approval.</p>}
          <label><input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} /> I authorize up to US${live.cap_usd.toFixed(2)} for this one evaluation.</label>
          <p><button type="button" className="primary" disabled={!agreed || busy} onClick={() => void start()}>Confirm and start live evaluation</button> <button type="button" onClick={() => { setConfirming(false); setAgreed(false); }}>Back</button></p>
        </div>
      )}
      {targets.find((t) => t.id === target) && <p className="muted">{targets.find((t) => t.id === target)!.description}</p>}
      {job && (
        <div className="livejob" aria-live="polite">
          <p><strong>{job.mock ? "MOCK" : job.dev_provider ? "LIVE path (dev provider)" : "LIVE"} · {STATE_LABEL[job.state] ?? job.state}</strong> · {Math.round(job.progress * 100)}% · <progress max={1} value={job.progress} aria-label="Progress" /> · recorded cost US${job.spend.committed_usd.toFixed(4)}{job.spend.hard_cap_usd ? ` of US$${job.spend.hard_cap_usd.toFixed(2)} cap` : ""} <span className="muted">({job.spend.basis})</span></p>
          {Object.keys(job.spend.stages ?? {}).length > 0 && <p className="muted">Spend by stage: {Object.entries(job.spend.stages).map(([k, v]) => `${STAGE_LABEL[k] ?? k} US$${v.toFixed(4)}`).join(" · ")}</p>}
          {job.smoke && <details open><summary>Smoke report: task generation only (stopped before any browser trial)</summary>
            <p>{job.smoke.yield.tasks_accepted} of {job.smoke.yield.tasks_proposed} proposed tasks passed the independent gate (need {job.smoke.yield.needed}) · {job.smoke.yield.requests_made} of at most {job.smoke.yield.max_requests} requests · cost US${job.smoke.cost.calculated_usd.toFixed(4)} of US${job.smoke.cost.cap_usd.toFixed(2)} · {job.smoke.relevance_to_goal.tasks_sharing_a_goal_term} of {job.smoke.relevance_to_goal.of} gate-accepted tasks serve your goal <span className="muted">(independent relevance check, separate from answerability; read the questions yourself)</span></p>
            <ul>{job.smoke.accepted_tasks.map((q, i) => <li key={i}>{q.question} <span className="muted">[{q.criterion_kind}, {q.source}]</span></li>)}</ul>
            {(job.smoke.relevance_to_goal.limitations ?? []).length > 0 && <p role="note"><strong>Goal coverage limits:</strong> {(job.smoke.relevance_to_goal.limitations ?? []).join("; ")}.</p>}
            <p className="muted">Provider compatibility: {job.smoke.provider_compatibility.map((c) => `batch ${c.batch} ${c.status}${c.usage_has_prompt_and_completion_tokens === false ? " (no usage)" : ""}`).join(" · ")}. Rejections: {Object.entries(job.smoke.independent_verification.rejection_reasons).map(([k, v]) => `${k} ×${v}`).join("; ") || "none"}.</p></details>}
          {job.client_context && <details><summary>Website context used (client-supplied, unverified)</summary><p className="ctxbox" role="note"><strong>{job.client_context.label}</strong><br />{job.client_context.text}</p><p className="muted">SHA-256 {job.client_context.sha256?.slice(0, 16) ?? "n/a"} · saved with the run and bound into the approval.</p></details>}
          {job.coverage && <div className={`coverage cov-${job.coverage.status}`} role="note"><strong>Goal coverage: {job.coverage.status.toUpperCase()}</strong>{job.coverage.status === "complete" ? <> — every aspect and entity of the goal is covered by verified tasks.</> : <> — {job.coverage.selected} verified task(s) selected ({job.coverage.entities_covered} of {job.coverage.entities_total} entities).</>}
            {job.coverage.partial_because.length > 0 && <ul>{job.coverage.partial_because.map((x, i) => <li key={i}>{x}</li>)}</ul>}
            {job.coverage.limitation_details.length > 0 && <ul>{job.coverage.limitation_details.map((d, i) => <li key={i}><em>{d.kind} limitation</em> · {d.aspect}: {d.detail}</li>)}</ul>}
            {job.coverage.missing_supported.length > 0 && <p>Supportable but not covered: {job.coverage.missing_supported.join(", ")}.</p>}</div>}
          {job.grant && <p className="muted">Approved by you: up to US${job.grant.budget_usd.toFixed(2)} on stages {job.grant.stages.join(", ")} (grant {job.grant.grant_sha256}). Each paid stage's manifest approval is recorded in the run's audit trail.</p>}
          {job.notice && <p className="muted" role="note">{job.notice}</p>}
          {job.state === "awaiting_approval" && job.stop && <Callout title="Waiting for an approval this evaluation is not permitted to grant" tone="warn"><p>{job.stop.reason}</p><p className="muted">Nothing further was spent. The run is preserved; only a person with access to the run can approve this stage ({job.stop.kind}).</p></Callout>}
          {job.error && job.state !== "awaiting_approval" && <p role="alert" className="scan-error">{job.error}</p>}
          <ol className="stages">{job.stages.map((s) => <li key={s.name}><Pill tone={tone(s.status)}>{s.status === "awaiting_approval" ? "needs approval" : s.status}</Pill> {STAGE_LABEL[s.name] ?? s.name}{s.detail ? <span className="muted"> — {s.detail}</span> : null}</li>)}</ol>
          {job.trials.length > 0 && <p className="muted">Trials: {job.trials.length}{job.tasks_planned ? ` of ${job.tasks_planned}` : ""} · {job.trials.filter((t) => t.passed).length} passed · {job.trials.reduce((n, t) => n + (t.page_views ?? 0), 0)} page views</p>}
          <details open><summary>Trace and events ({job.events.length})</summary><ul className="events" aria-label="Events">{job.events.slice(-60).map((e, i) => <li key={i} className={`ev-${e.kind}`}>{e.text}</li>)}</ul></details>
          {(job.state === "completed" || (!active && job.opened && job.state !== "awaiting_approval") || (job.state === "awaiting_approval" && job.opened)) && <p><button type="button" className="primary" onClick={() => void open(job.id, `${job.target_id} · ${job.id}`)}>Open results</button> <span className="muted">{job.mock ? "Evidence, findings and recommendations open in the report below, labelled as mock." : "Evidence, findings and recommendations open in the report below. Every proposal is unvalidated: only a retest measures an effect."}</span></p>}
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
