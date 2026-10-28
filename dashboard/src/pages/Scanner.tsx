import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, call, configured, factorsOf, getToken, setToken, type Finding, type Registry, type ScanResult, type ScanSummary } from "../lib/scannerApi";

const CATEGORY: Record<string, string> = {
  task_outcome: "Outcome", website: "Website", agent_reasoning: "Agent reasoning", agent_tool_interface: "Agent–tool interface", infrastructure: "Infrastructure", security: "Security", undetermined: "Undetermined",
};
const CONF: Record<string, string> = { observed: "Observed fact", inferred: "Inferred by rule", hypothesis: "Hypothesis — not validated" };

export function Notice({ result }: { result: ScanResult }) {
  return <p className={result.mock ? "badge scan-mock" : "badge scan-live"} role="note"><span className="sr-only">{result.mock ? "mock" : "live"} scan: </span>{result.inference_label}</p>;
}

export function FindingCard({ f }: { f: Finding }) {
  return (
    <article className={`finding conf-${f.confidence}`} aria-label={f.title}>
      <p className="muted"><span className="pill">{CATEGORY[f.category] ?? f.category}</span> <span className="pill">{CONF[f.confidence]}</span></p>
      <h4>{f.title}</h4>
      <p>{f.summary}</p>
      {f.evidence.length > 0 && <p className="muted">Evidence: {f.evidence.slice(0, 6).map((e, i) => <span key={i}>{e.step ? `step ${e.step}` : e.path ?? e.note}{i < Math.min(f.evidence.length, 6) - 1 ? "; " : ""}</span>)}</p>}
      {f.recommendation && (
        <div className="reco">
          <p><strong>Possible change (hypothesis, unvalidated):</strong> {f.recommendation.text}</p>
          {f.recommendation.validate_with && <p className="muted">To test it, re-scan <code>{f.recommendation.validate_with.task}</code> changing only <code>{f.recommendation.validate_with.factor}</code>: {f.recommendation.validate_with.from} → {f.recommendation.validate_with.to}.</p>}
        </div>
      )}
    </article>
  );
}

export function ResultView({ result }: { result: ScanResult }) {
  if (!result.verdict || !result.metrics) return <p role="status">Scan {result.status}{result.error ? ` (${result.error})` : ""}.</p>;
  const v = result.verdict, m = result.metrics, d = result.diagnostics;
  return (
    <section aria-label="Scan result">
      <Notice result={result} />
      <h3>Result</h3>
      <p className="muted">{result.task?.objective}</p>
      <div className="kpis">
        <div className="card"><h3>Independent evaluator</h3><p><span className={`pill ${v.passed ? "pill-pass" : "pill-fail"}`}>{v.passed ? "PASS" : "FAIL"}</span> {v.evidence_backed ? "evidence shown" : "required evidence NOT shown"}</p><p className="muted">{v.reasons.join("; ")}</p></div>
        <div className="card"><h3>Effort</h3><p>{m.model_requests} model requests · {m.page_views} page views · {m.elapsed_seconds}s</p><p className="muted">limits {m.limits.max_model_requests} requests / {m.limits.max_steps} steps / {m.limits.timeout_seconds}s</p></div>
        <div className="card"><h3>Estimated cost</h3><p>US${m.calculated_cost_usd.toFixed(4)}</p><p className="muted">{m.cost_basis}</p></div>
      </div>
      <h3>What the agent did</h3>
      <ol className="journey">
        {result.journey?.map((j) => (
          <li key={j.step}><code>{j.path}{j.query ? `?${j.query}` : ""}</code> → {j.actions.map((a) => `${a.name}${a.params.url ? ` ${a.params.url}` : a.params.selector ? ` ${a.params.selector}` : ""}`).join(", ") || "—"}
            {j.executed.filter((x) => x.error).map((x, i) => <span key={i} className="muted"> · error: {x.error}</span>)}</li>
        ))}
      </ol>
      <p className="muted">A page appearing here means the agent loaded it; the evaluator separately checks that the facts the task needs appeared in what it was shown.</p>
      <h3>Findings</h3>
      {d && <p className="muted">{d.attribution_note}</p>}
      {d?.mode_notice && <p className="muted"><em>{d.mode_notice}</em></p>}
      {d?.findings.map((f) => <FindingCard key={f.id} f={f} />)}
    </section>
  );
}

export function Unconfigured() {
  return (
    <section aria-label="Scanner unavailable">
      <h1>Protected scanner</h1>
      <p className="lead">The scanner lets an invited developer run a registered task on a registered storefront variant and inspect what the agent did, why it succeeded or struggled, and what could be changed.</p>
      <p role="status" className="badge">This public build is not connected to a scanner service, so nothing can be scanned here. No live scanner is deployed.</p>
      <p className="muted">To try it locally: <code>readiness scanner invite --label me</code>, <code>readiness scanner serve</code>, then build the dashboard with <code>VITE_SCANNER_API_URL=http://127.0.0.1:8100</code>. Local scans use a deterministic mock agent unless live inference has been separately approved and enabled.</p>
    </section>
  );
}

export function ScannerPage() {
  const [authed, setAuthed] = useState<boolean>(!!getToken());
  const [registry, setRegistry] = useState<Registry | null>(null);
  const [code, setCode] = useState("");
  const [task, setTask] = useState("");
  const [variant, setVariant] = useState("");
  const [behavior, setBehavior] = useState("correct");
  const [scans, setScans] = useState<ScanSummary[]>([]);
  const [current, setCurrent] = useState<ScanResult | null>(null);
  const [baseline, setBaseline] = useState<ScanResult | null>(null);
  const [comparison, setComparison] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  const fail = useCallback((e: unknown) => {
    if (e instanceof ApiError && e.status === 401 && getToken()) { setToken(null); setAuthed(false); setError("Your session expired. Enter a code again."); } else setError(e instanceof Error ? e.message : "Unexpected error.");
  }, []);
  const refresh = useCallback(async () => { try { setScans((await call<{ scans: ScanSummary[] }>("/api/scans")).scans); } catch (e) { fail(e); } }, [fail]);

  useEffect(() => { if (configured()) call<Registry>("/api/registry").then((r) => { setRegistry(r); setTask(r.tasks[0]?.task_id ?? ""); setVariant(r.environments[0]?.variants.find((v) => v.default)?.variant_id ?? ""); }).catch(fail); }, [fail]);
  useEffect(() => { if (authed) void refresh(); }, [authed, refresh]);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  if (!configured()) return <Unconfigured />;

  const poll = (id: string) => {
    window.clearTimeout(timer.current);
    const tick = async () => {
      try {
        const r = await call<ScanResult>(`/api/scans/${id}`);
        setCurrent(r);
        if (r.status === "queued" || r.status === "running") timer.current = window.setTimeout(tick, 1500); else { setBusy(false); void refresh(); }
      } catch (e) { setBusy(false); fail(e); }
    };
    void tick();
  };
  const redeem = async () => {
    setError(null); setBusy(true);
    try { const r = await call<{ token: string }>("/api/session", { method: "POST", json: { code: code.trim() } }); setToken(r.token); setCode(""); setAuthed(true); } catch (e) { fail(e); }
    setBusy(false);
  };
  const launch = async () => {
    setError(null); setBusy(true); setComparison(null);
    try {
      const r = await call<{ scan_id: string }>("/api/scans", { method: "POST", json: { task_id: task, variant_id: variant, mode: "mock", mock_behavior: behavior }, headers: { "Idempotency-Key": crypto.randomUUID() } });
      poll(r.scan_id);
    } catch (e) { setBusy(false); fail(e); }
  };
  const open = async (id: string) => { try { setCurrent(await call<ScanResult>(`/api/scans/${id}`)); setComparison(null); } catch (e) { fail(e); } };
  const compareWith = async () => {
    if (!baseline || !current) return;
    try { setComparison(await call(`/api/compare?baseline=${baseline.scan_id}&rescan=${current.scan_id}`)); } catch (e) { fail(e); }
  };

  const spec = registry?.tasks.find((t) => t.task_id === task);
  const variants = registry?.environments.find((e) => e.environment_id === spec?.environment_id)?.variants ?? [];
  return (
    <section aria-label="Protected scanner">
      <h1>Protected scanner</h1>
      <p className="lead">Run a registered task on a registered storefront variant, then inspect what the agent did, whether the independent evaluator accepted the result, and where effort or failure came from.</p>
      <p className="badge" role="note">Local/credential-free: scans use a deterministic MOCK agent. Mock results demonstrate the diagnostic pipeline; they say nothing about how a real model would behave.</p>
      {registry?.kill_switch && <p role="alert" className="badge">Scanning is paused by the operator.</p>}
      {error && <p role="alert" className="scan-error">{error}</p>}
      {!authed ? (
        <form onSubmit={(e) => { e.preventDefault(); void redeem(); }} className="scan-form">
          <label htmlFor="code">Invitation code</label>
          <input id="code" value={code} onChange={(e) => setCode(e.target.value)} autoComplete="off" spellCheck={false} placeholder="AR-XXXX-XXXX-XXXX-XXXX" />
          <button type="submit" disabled={busy || code.trim().length < 4}>Start session</button>
          <p className="muted">Codes are issued by the operator, are verified by the server, and give a short-lived session with a small scan quota.</p>
        </form>
      ) : (
        <>
          <form onSubmit={(e) => { e.preventDefault(); void launch(); }} className="scan-form" aria-label="New scan">
            <label htmlFor="task">Task</label>
            <select id="task" value={task} onChange={(e) => setTask(e.target.value)}>{registry?.tasks.map((t) => <option key={t.task_id} value={t.task_id}>{t.task_id}</option>)}</select>
            {spec && <p className="muted">{spec.objective}</p>}
            <label htmlFor="variant">Storefront variant</label>
            <select id="variant" value={variant} onChange={(e) => setVariant(e.target.value)}>{variants.map((v) => <option key={v.variant_id} value={v.variant_id}>{v.factors.map(([k, l]) => `${k}: ${l}`).join(" · ")}</option>)}</select>
            <label htmlFor="behavior">Mock agent scenario</label>
            <select id="behavior" value={behavior} onChange={(e) => setBehavior(e.target.value)}>{(registry?.mock_behaviors ?? ["correct"]).map((b) => <option key={b}>{b}</option>)}</select>
            <button type="submit" disabled={busy || !task || !variant || registry?.kill_switch}>{busy ? "Running…" : "Run mock scan"}</button>
          </form>
          {current && (current.status === "queued" || current.status === "running") && <p role="status">Scan {current.status}… the browser agent is working.</p>}
          {current && <ResultView result={current} />}
          {current && current.status === "complete" && (
            <p>
              <button type="button" onClick={() => setBaseline(current)}>Use this scan as baseline</button>{" "}
              {baseline && baseline.scan_id !== current.scan_id && <button type="button" onClick={() => void compareWith()}>Compare with baseline ({Object.values(factorsOf(baseline.variant)).join("/")})</button>}
            </p>
          )}
          {comparison && (
            <section aria-label="Comparison" className="card">
              <h3>Baseline vs re-scan</h3>
              <p>{comparison.controlled ? "Controlled: one factor changed — " : "Not controlled — "}<code>{JSON.stringify(comparison.factors_changed)}</code></p>
              <ul>{Object.entries(comparison.metrics).map(([k, m]: [string, any]) => <li key={k}>{k}: {m.baseline} → {m.rescan} (Δ {m.delta})</li>)}</ul>
              <ul className="muted">{comparison.caveats.map((c: string) => <li key={c}>{c}</li>)}</ul>
            </section>
          )}
          <h3>Your scans</h3>
          {scans.length === 0 ? <p className="muted">None yet.</p> : (
            <ul>{scans.map((s) => <li key={s.scan_id}><button type="button" className="linklike" onClick={() => void open(s.scan_id)}>{s.task_id}</button> · {s.variant_id.split("/")[1]} · {s.mode.toUpperCase()} · {s.status}</li>)}</ul>
          )}
          <p><button type="button" onClick={() => { setToken(null); setAuthed(false); setCurrent(null); setScans([]); }}>End session</button></p>
        </>
      )}
    </section>
  );
}
