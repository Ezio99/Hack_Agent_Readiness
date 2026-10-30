import { useState } from "react";
import { Callout, Kpi, Pill } from "../components/ui";
import { MODE_LABEL, compare, parseInvestigation, tally, type EvalResult, type InvestigationExport, type Mode, type TrialRow } from "../lib/investigation";

const pct = (a: number, b: number) => (b ? `${Math.round((100 * a) / b)}%` : "—");
const num = (x: number | null | undefined, d = 2) => (typeof x === "number" ? x.toFixed(d) : "—");
const short = (id: string) => (id.length > 14 ? `${id.slice(0, 14)}…` : id);

export function ModeBadge({ mode }: { mode: Mode }) {
  return <span className={`mode mode-${mode}`} title={`Evidence mode: ${MODE_LABEL[mode]}`}>{MODE_LABEL[mode]}</span>;
}

const STAGE_TONE = { done: "pass", failed: "fail", awaiting_approval: "warn", running: "warn", pending: "neutral" } as const;

export function Timeline({ d }: { d: InvestigationExport }) {
  return (
    <ol className="timeline" aria-label="Pipeline stages">
      {d.stages.map((s) => (
        <li key={s.name} className={`tl tl-${s.status}${s.skipped ? " tl-skipped" : ""}`}>
          <span className="tl-name">{s.name.replace(/_/g, " ")}</span>
          <Pill tone={STAGE_TONE[s.status] ?? "neutral"}>{s.skipped ? "skipped" : s.status.replace(/_/g, " ")}</Pill>
          {s.skipped && s.reason ? <span className="muted tl-note">{s.reason}</span> : null}
          {s.status === "awaiting_approval" && s.manifest_sha256 ? <span className="muted tl-note">owner approval needed · <code>{short(s.manifest_sha256)}</code></span> : null}
        </li>
      ))}
    </ol>
  );
}

function Cell({ rows }: { rows: TrialRow[] }) {
  if (!rows.length) return <span className="muted">not run</span>;
  return (
    <>
      {rows.map((r) =>
        r.void ? <span key={r.trial_id} title={`${r.run_status}: void, not a website result`}><Pill tone="warn">void</Pill> </span>
          : <span key={r.trial_id} title={`${r.run_status}; ${r.model_requests ?? "?"} requests`}><Pill tone={r.passed ? "pass" : "fail"}>{r.passed ? "pass" : "fail"}</Pill> <span className="muted">{r.model_requests ?? "?"} req</span> </span>)}
    </>
  );
}

export function TaskTable({ d }: { d: InvestigationExport }) {
  const pids = [...new Set(d.tasks.flatMap((t) => Object.keys(t.patched)))];
  if (!d.tasks.length) return <p className="muted">No frozen tasks in this export (the task stages had not completed).</p>;
  return (
    <div className="table-wrap">
      <table className="runs">
        <caption className="sr-only">Task outcomes per arm</caption>
        <thead><tr><th scope="col">Task</th><th scope="col">Set</th><th scope="col">Baseline</th>{pids.map((p) => <th scope="col" key={p}>Patched <code>{short(p)}</code></th>)}</tr></thead>
        <tbody>
          {d.tasks.map((t) => (
            <tr key={t.task_id} className={t.baseline.some((r) => !r.void && !r.passed) ? "row-fail" : undefined}>
              <th scope="row"><span>{t.question}</span><br /><code>{t.task_id}</code> <span className="muted">{t.kind}</span></th>
              <td>{t.partition}</td>
              <td><Cell rows={t.baseline} />{t.baseline.some((r) => r.attribution && !["success", "infrastructure"].includes(r.attribution)) ? <div className="muted">{t.baseline.map((r) => r.attribution).filter(Boolean).join(", ")}</div> : null}</td>
              {pids.map((p) => <td key={p}><Cell rows={t.patched[p] ?? []} /></td>)}
            </tr>))}
        </tbody>
      </table>
      <p className="muted">Void trials (provider, budget, infrastructure or fidelity guard) are shown but never counted as website results. {d.trials.void} void trial(s) in this run.</p>
    </div>
  );
}

export function Findings({ d }: { d: InvestigationExport }) {
  const obs = new Map(d.observations.map((o) => [o.id, o]));
  const novel = d.hypotheses.filter((h) => h.tier === "novel");
  const other = d.hypotheses.filter((h) => h.tier === "verifiable" && !h.promoted);
  return (
    <>
      <h3>Verified findings</h3>
      {d.findings.length === 0 ? <p className="muted">No verified findings. A hypothesis is promoted to a finding only after deterministic verification and independent trial support.</p> : (
        <ul className="findings">
          {d.findings.map((f) => (
            <li key={f.id} className="finding conf-observed">
              <span className="pill pill-pass">Verified finding</span> <ModeBadge mode={f.provenance.mode} /> <span className="muted">attribution: {f.attribution}{f.structural_proof ? " · structural proof" : ""}</span>
              <h4>{f.statement}</h4>
              <p className="muted">Evidence</p>
              <ul>
                {f.observation_ids.map((id) => <li key={id}><code>{short(id)}</code> {obs.get(id)?.summary}</li>)}
                {f.unresolved_observation_ids.map((id) => <li key={id} className="shortfall">Unresolved observation <code>{short(id)}</code></li>)}
                {f.support.map((s) => <li key={s.ref}>{s.resolved ? "Supporting trial" : <span className="shortfall">Unresolved trial reference</span>} <code>{s.ref}</code></li>)}
              </ul>
            </li>))}
        </ul>)}
      <h3>Hypotheses that are not findings</h3>
      <ul className="findings">
        {novel.map((h) => (
          <li key={h.id} className="finding conf-hypothesis">
            <span className="pill pill-warn">Novel hypothesis — UNVERIFIED</span> <ModeBadge mode={h.provenance.mode} />
            <h4>{h.statement}</h4>
            <p className="muted">Prediction to test: {h.prediction}</p>
          </li>))}
        {other.map((h) => (
          <li key={h.id} className="finding conf-inferred">
            <span className={`pill pill-${h.status === "refuted" ? "fail" : "neutral"}`}>Hypothesis — {h.status}</span> <ModeBadge mode={h.provenance.mode} />
            <h4>{h.statement}</h4>
            {h.verification ? <p className="muted">Checked by {h.verification.verifier}: {h.verification.result}</p> : null}
          </li>))}
        {novel.length + other.length === 0 ? <li className="muted">None recorded.</li> : null}
      </ul>
    </>
  );
}

function Bar({ label, cls, value, text }: { label: string; cls: "A" | "B"; value: number; text: string }) {
  return (
    <div className="bar-row">
      <span className="bar-label">{label}</span>
      <span className="bar-track" aria-hidden="true"><span className={`bar bar-${cls}`} style={{ width: `${Math.max(2, value * 100)}%` }} /></span>
      <span className="bar-value">{text}</span>
    </div>
  );
}

function ResultCard({ d, r }: { d: InvestigationExport; r: EvalResult }) {
  const c = compare(d.tasks, r.proposal_id);
  const b = c.baseline, p = c.patched;
  const tone = r.verdict === "improvement" ? "good" : r.verdict === "regression" ? "bad" : "info";
  return (
    <section className="card" aria-label={`Baseline versus patched for ${r.proposal_id}`}>
      <h4>Patch <code>{short(r.proposal_id)}</code>{d.synthetic ? <> <span className="mode mode-scripted">ILLUSTRATIVE — synthetic numbers</span></> : null} <Pill tone={r.verdict === "improvement" ? "pass" : r.verdict === "regression" ? "fail" : "neutral"}>{r.verdict}</Pill>{" "}
        {r.measured ? <span className="mode mode-live">MEASURED (live)</span> : <span className="mode mode-unmeasured">NOT MEASURED — {r.effect_mode ? MODE_LABEL[r.effect_mode].toLowerCase() : "no"} evidence, a pipeline check only</span>}</h4>
      <figure className="paired" role="group" aria-label={`Evidence-backed pass rate: baseline ${pct(b.passed, b.usable)}, patched ${pct(p.passed, p.usable)}`}>
        <figcaption>Evidence-backed pass rate on {c.tasks} usable task{c.tasks === 1 ? "" : "s"} (descriptive)</figcaption>
        <Bar label="Baseline" cls="B" value={b.usable ? b.passed / b.usable : 0} text={`${b.passed}/${b.usable}`} />
        <Bar label="Patched" cls="A" value={p.usable ? p.passed / p.usable : 0} text={`${p.passed}/${p.usable}`} />
      </figure>
      <p className="muted">Mean model requests per trial: baseline {num(b.requests, 1)} → patched {num(p.requests, 1)}. {c.skipped ? `${c.skipped} task(s) lack a usable trial in one arm and are not compared.` : ""}</p>
      <dl className="facts">
        <dt>Pre-registered rule</dt><dd>{r.rule_preregistered_at_freeze ? "fixed before any trial ran" : "not recorded as pre-registered"}</dd>
        <dt>Pairs · pass Δ · request Δ</dt><dd>{r.pairs ?? "—"} · {num(r.pass_delta)} · {num(r.request_change)} (p = {num(r.p_pass)} / {num(r.p_requests)})</dd>
        <dt>Holdout consistent</dt><dd>{r.holdout_consistent == null ? "—" : r.holdout_consistent ? "yes" : "no — the improvement is withdrawn"}</dd>
        <dt>Reason</dt><dd>{r.reason ?? "—"}</dd>
        {r.excluded.length ? <><dt>Excluded</dt><dd>{r.excluded.map((e) => `${e.task_id}: ${e.reason}`).join("; ")}</dd></> : null}
      </dl>
      <Callout title="How to read this" tone={tone === "bad" ? "warn" : "info"}>
        <p>{r.measured ? "A measured effect is for these frozen tasks, this agent profile and this patched mirror only; it does not prove why the change worked." : "This effect was not measured with live trials. It shows the pipeline works end to end; it is not evidence about agent behaviour."}</p>
      </Callout>
    </section>
  );
}

export function Comparison({ d }: { d: InvestigationExport }) {
  const e = d.evaluation;
  if (e.state === "missing") return <Callout title="No evaluation data" tone="warn"><p>{e.reason} Baseline results are shown above; no before/after comparison is available.</p></Callout>;
  if (e.state === "not_evaluated") return <Callout title="Not evaluated" tone="info"><p>{e.reason ?? "No evaluation was run"}. Nothing was retested, so nothing is compared.</p></Callout>;
  return <>{e.results.map((r) => <ResultCard key={r.proposal_id} d={d} r={r} />)}{e.rule?.causal_scope ? <p className="muted">Scope: {e.rule.causal_scope}</p> : null}</>;
}

export function Proposals({ d }: { d: InvestigationExport }) {
  if (!d.proposals.length) return <p className="muted">No proposals.</p>;
  return (
    <ul className="findings">
      {d.proposals.map((p) => (
        <li key={p.id} className={`finding ${p.basis === "verified_finding" ? "conf-observed" : "conf-hypothesis"}`}>
          <span className={`pill ${p.basis === "verified_finding" ? "pill-pass" : "pill-warn"}`}>{p.label}</span> <span className="muted">status: {p.status}{p.approved ? " · owner-approved" : ""} · validation: {p.validation}</span>
          <p>{"manual" in p.change ? p.change.manual : `Patch operations: ${p.change.ops.join(", ")}`}</p>
          <p className="muted">Expected: {p.expected_effect}{p.risks.length ? ` · Risks: ${p.risks.join("; ")}` : ""}</p>
        </li>))}
    </ul>
  );
}

export function InvestigationView({ d }: { d: InvestigationExport }) {
  const t = d.tasks.flatMap((x) => x.baseline), bt = tally(t);
  return (
    <div className="investigation">
      {d.synthetic ? <p className="replay-banner" role="note">SYNTHETIC FIXTURE — hand-written test data, not produced by any model, agent or website.</p> : null}
      <div className="modes" role="note" aria-label="Evidence modes">
        {d.modes.map((m) => <ModeBadge key={m} mode={m} />)}
        <span className="muted">{d.notices.join(" ")}</span>
      </div>
      {d.run.investigation_status && !["completed"].includes(d.run.investigation_status) ? <Callout title={d.run.investigation_status === "not_run" ? "No investigator ran" : "The investigation did not complete"} tone="bad"><p>Status: <code>{d.run.investigation_status}</code>. Nothing was concluded about the website; this is <strong>not</strong> a finding that no problem exists.</p></Callout> : null}
      {!d.run.complete ? <Callout title="Incomplete investigation" tone="warn"><p>Not every stage finished{d.run.missing_artifacts.length ? ` (missing: ${d.run.missing_artifacts.join(", ")})` : ""}. Sections below show what exists; nothing is inferred for the rest.</p></Callout> : null}
      <h2>{d.run.target}</h2>
      <p className="muted">Run <code>{d.run.id}</code> · mode {d.run.mode} · report source: {d.run.report_source} · outcome: <strong>{d.run.outcome.replace(/_/g, " ")}</strong></p>
      <div className="kpis">
        <Kpi label="Frozen tasks" value={d.tasks.length} note={`${d.tasks.filter((x) => x.partition === "holdout").length} held out from the investigator`} />
        <Kpi label="Baseline pass rate" value={pct(bt.passed, bt.usable)} note={`${bt.passed}/${bt.usable} usable trials`} tone={bt.usable && bt.passed < bt.usable ? "bad" : "neutral"} />
        <Kpi label="Void trials" value={d.trials.void} note="excluded, never a website result" tone={d.trials.void ? "b" : "neutral"} />
        <Kpi label="Verified findings" value={d.findings.length} tone={d.findings.length ? "good" : "neutral"} />
      </div>
      <h3>Stage timeline</h3>
      <Timeline d={d} />
      <h3>Task outcomes</h3>
      <TaskTable d={d} />
      <Findings d={d} />
      <h3>Proposed changes</h3>
      <Proposals d={d} />
      <h3>Baseline versus patched</h3>
      <Comparison d={d} />
      {d.statement ? <p className="muted">{d.statement}</p> : null}
    </div>
  );
}

export function InvestigationPage() {
  const [data, setData] = useState<InvestigationExport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = (text: string) => { const p = parseInvestigation(text); if (p.ok) { setData(p.data); setError(null); } else { setData(null); setError(p.error); } };
  return (
    <>
      <h2>Investigation report</h2>
      <p className="lead">A read-only view of one autonomous investigation: what the agent could not do, what was verified, what is only a hypothesis, and whether a change helped.</p>
      <div className="loader">
        <label>Open an exported report <input type="file" accept="application/json,.json" onChange={async (e) => { const f = e.target.files?.[0]; if (f) load(await f.text()); }} /></label>
        <button type="button" onClick={async () => load(JSON.stringify((await import("../fixtures/investigation-synthetic.json")).default))}>Load synthetic example</button>
      </div>
      <p className="muted">Files are read in your browser only; nothing is uploaded. Create one with <code>readiness investigate export RUN_DIR --out report.json</code>.</p>
      {error ? <Callout title="Cannot display this file" tone="bad"><p>{error}</p></Callout> : null}
      {data ? <InvestigationView d={data} /> : !error ? <p className="muted">No report loaded.</p> : null}
    </>
  );
}
