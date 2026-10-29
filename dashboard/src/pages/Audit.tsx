import { useCallback, useEffect, useState } from "react";
import { ApiError, call } from "../lib/scannerApi";

export interface AuditFinding { fingerprint: string; kind: string; attribute: string | null; category: string; confidence: string; title: string; summary: string; evidence: { type: string; url?: string; excerpt?: string; cue?: string | null; locator?: string | null }[] }
export interface AuditRec { id: string; title: string; change: string; change_id: string | null; rationale: string; expected_benefit: string; risks: string; status: string; validation: string; task_relevance: string;
  confidence: { level: string; statement: string }; supporting_evidence: AuditFinding["evidence"]; how_to_validate: { resolution_check: string; effect_measurement: string } }
export interface AuditReport {
  audit_id: string; target: string; objective: string | null; findings: AuditFinding[]; recommendations: AuditRec[];
  agent_execution: null | { scan_mode: string; mode_notice: string; items: { id: string; category: string; title: string; summary: string }[]; corroborates: { statement: string }[] };
  discovery_candidates: { id: string; title: string; summary: string; note?: string }[];
  lifecycle: null | { previous_audit_id: string; statement: string; items: { fingerprint: string; status: string; current_summary: string }[]; new_findings: string[] };
  measured_effects: { status: string; effects: unknown[] };
}
const STATUS: Record<string, string> = { resolved: "Resolved — no longer observed", persisting: "Still observed", partially_resolved: "Partly resolved", indeterminate: "Cannot tell" };
const CAT: Record<string, string> = { website_property: "Website property (observed)", website_property_positive: "Website property (observed, in place)", probe_limitation: "Probe limitation" };

export function AuditReportView({ report }: { report: AuditReport }) {
  const problems = report.findings.filter((f) => f.category !== "website_property_positive");
  return (
    <section aria-label="Site audit report" className="card">
      <h3>Audit of {report.target}</h3>
      {report.objective && <p className="muted">Shopper task considered: {report.objective}</p>}
      <h4>1 · Observed website properties</h4>
      {report.findings.length === 0 && <p className="muted">Nothing noteworthy observed.</p>}
      {report.findings.map((f) => (
        <article key={f.fingerprint} className={`finding conf-${f.confidence}`} aria-label={f.title}>
          <p className="muted"><span className="pill">{CAT[f.category] ?? f.category}</span> <span className="pill">Observed fact</span></p>
          <p>{f.summary}</p>
          {f.evidence.slice(0, 2).map((e, i) => <p key={i} className="muted">Evidence: {e.type.replace("_", " ")} {e.url ? <code>{e.url.replace(/^https?:\/\/[^/]+/, "")}</code> : null} {e.excerpt ? <>“{e.excerpt}”</> : null}</p>)}
        </article>
      ))}
      {report.agent_execution && (
        <>
          <h4>2 · What an agent did (execution evidence — separate from the website)</h4>
          <p className="badge" role="note">{report.agent_execution.mode_notice}</p>
          <ul>{report.agent_execution.items.map((i) => <li key={i.id}><span className="pill">{i.category.replace(/_/g, " ")}</span> {i.summary}</li>)}</ul>
          {report.agent_execution.corroborates.map((c, i) => <p key={i} className="muted"><span className="pill">Inferred</span> {c.statement}</p>)}
        </>
      )}
      {report.discovery_candidates.length > 0 && (<><h4>Candidate patterns (no recommendation yet)</h4><ul>{report.discovery_candidates.map((c) => <li key={c.id}>{c.title}: {c.summary}</li>)}</ul></>)}
      <h4>3 · Proposed interventions</h4>
      {report.recommendations.length === 0 ? <p className="muted">{problems.length ? "No library recommendation matches the observed properties." : "No problems observed, so nothing is proposed."}</p> : report.recommendations.map((r) => (
        <article key={r.id} className="reco" aria-label={r.title}>
          <p><span className="pill">Proposed</span> <span className="pill">Validation: {r.validation.replace(/_/g, " ")}</span> <span className="pill">{r.task_relevance.replace(/_/g, " ")}</span></p>
          <h4>{r.title}</h4>
          <p><strong>Change:</strong> {r.change}</p>
          <p><strong>Why:</strong> {r.rationale}</p>
          <p><strong>Expected benefit:</strong> {r.expected_benefit}</p>
          <p className="muted"><strong>Confidence:</strong> {r.confidence.statement}</p>
          <p className="muted"><strong>Risks:</strong> {r.risks}</p>
          <p className="muted"><strong>To validate:</strong> {r.how_to_validate.resolution_check}; then {r.how_to_validate.effect_measurement}.</p>
        </article>
      ))}
      {report.lifecycle && (
        <>
          <h4>4 · Re-audit lifecycle</h4>
          <ul>{report.lifecycle.items.map((i) => <li key={i.fingerprint}><span className={`pill ${i.status === "resolved" ? "pill-pass" : ""}`}>{STATUS[i.status] ?? i.status}</span> <code>{i.fingerprint}</code> — {i.current_summary}</li>)}</ul>
          {report.lifecycle.new_findings.length > 0 && <p>New: {report.lifecycle.new_findings.join(", ")}</p>}
          <p className="muted">{report.lifecycle.statement}</p>
        </>
      )}
      <h4>5 · Measured effects</h4>
      <p className="muted">{report.measured_effects.status === "not_measured" ? "Not measured. A resolved finding shows the property changed; it does not show that agent outcomes improved." : `${report.measured_effects.effects.length} controlled experiment result(s) attached.`}</p>
    </section>
  );
}

export function AuditPanel({ onError }: { onError: (e: unknown) => void }) {
  const [targets, setTargets] = useState<{ id: string; description: string }[]>([]);
  const [target, setTarget] = useState("");
  const [objective, setObjective] = useState("List every in-stock ANC headphone at or below A$250.00");
  const [report, setReport] = useState<AuditReport | null>(null);
  const [previous, setPrevious] = useState<AuditReport | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { call<{ targets: { id: string; description: string }[] }>("/api/targets").then((r) => { setTargets(r.targets); setTarget(r.targets[0]?.id ?? ""); }).catch(() => undefined); }, []);
  const run = useCallback(async (withPrevious: boolean) => {
    setBusy(true);
    try {
      const r = await call<AuditReport>("/api/audits", { method: "POST", json: { target_id: target, objective, ...(withPrevious && previous ? { previous_audit_id: previous.audit_id } : {}) } });
      setPrevious(r); setReport(r);
    } catch (e) { onError(e instanceof ApiError ? e : e); }
    setBusy(false);
  }, [target, objective, previous, onError]);
  if (targets.length === 0) return null;
  return (
    <section aria-label="Site audit">
      <h2>Site audit</h2>
      <p className="lead">Probe a registered site over plain HTTP, see which properties make decisions hard to read from list pages, and get evidence-linked proposals. No model call, no cost.</p>
      <form className="scan-form" onSubmit={(e) => { e.preventDefault(); void run(false); }}>
        <label htmlFor="audit-target">Target site</label>
        <select id="audit-target" value={target} onChange={(e) => setTarget(e.target.value)}>{targets.map((t) => <option key={t.id} value={t.id}>{t.id} — {t.description}</option>)}</select>
        <label htmlFor="audit-objective">Shopper task (optional)</label>
        <input id="audit-objective" value={objective} onChange={(e) => setObjective(e.target.value)} maxLength={300} />
        <button type="submit" disabled={busy || !target}>{busy ? "Auditing…" : "Audit site"}</button>{" "}
        <button type="button" disabled={busy || !previous} onClick={() => void run(true)}>Re-audit and compare with the previous audit</button>
      </form>
      <p className="muted">After the site owner applies a proposed change, re-audit to see whether the original finding is still observed.</p>
      {report && <AuditReportView report={report} />}
    </section>
  );
}
