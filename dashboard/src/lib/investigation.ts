// Typed contract for `investigation-dashboard-v1`, the sanitized read-only export written by `readiness investigate export` (Task 016 M7).
// The dashboard never receives private criteria, agent answers, traces or credentials; `parseInvestigation` refuses anything that is not this schema.
export type Mode = "scripted" | "mock" | "recorded" | "live";
export type StageStatus = "pending" | "running" | "done" | "failed" | "awaiting_approval";
export interface Prov { mode: Mode; source: string }
export interface StageInfo { name: string; status: StageStatus; updated_at: string | null; skipped: boolean; reason: string | null; manifest_sha256: string | null; summary: Record<string, string | number | boolean | null> }
export interface TrialRow { trial_id: string; repeat: number; run_status: string | null; void: boolean; passed: boolean | null; evidence_backed: boolean | null; model_requests: number | null; page_views: number | null; mode: Mode | null; attribution?: string; why?: string }
export interface TaskInfo { task_id: string; question: string; kind: string; source: string; partition: "investigation" | "holdout"; start_path: string; limits: Record<string, number> | null; baseline: TrialRow[]; patched: Record<string, TrialRow[]> }
export interface Observation { id: string; kind: string; summary: string; refs: string[]; provenance: Prov }
export interface Hypothesis { id: string; tier: "verifiable" | "novel"; statement: string; claim_kind: string | null; prediction: string | null; status: "unverified" | "supported" | "refuted" | "unverifiable"; observation_ids: string[]; verification: { verifier: string; result: string; evidence: string[] } | null; promoted: boolean; provenance: Prov }
export interface Finding { id: string; hypothesis_id: string; statement: string; attribution: string; structural_proof: boolean; provenance: Prov; observation_ids: string[]; unresolved_observation_ids: string[]; support: { ref: string; resolved: boolean }[] }
export interface Proposal { id: string; basis: "verified_finding" | "unverified_hypothesis"; source_id: string; label: string; status: string; validation: string; expected_effect: string; risks: string[]; auto_applicable: boolean; change: { manual: string } | { ops: string[] }; approved: boolean; provenance: Prov }
export interface EvalResult { proposal_id: string; verdict: "improvement" | "regression" | "inconclusive"; reason: string | null; pairs: number | null; pass_delta: number | null; request_change: number | null; p_pass: number | null; p_requests: number | null; holdout_consistent: boolean | null; by_partition: Record<string, { pairs: number; pass_delta: number | null }> | null; rule_preregistered_at_freeze: boolean | null; excluded: { task_id: string; reason: string }[]; measured: boolean; effect_mode: Mode | null }
export interface Evaluation { state: "evaluated" | "not_evaluated" | "missing"; reason: string | null; rule: Record<string, string | number | null> | null; results: EvalResult[] }
export interface Effect { id: string; proposal_id: string; verdict: string; n_pairs: number; note: string; measured: boolean; mode: Mode }
export interface InvestigationExport {
  schema: "investigation-dashboard-v1"; exported_at: string; synthetic?: boolean;
  run: { id: string; target: string; mode: Mode; created_at: string | null; outcome: "findings" | "experimental_only" | "no_supported_issue"; report_source: "report-final" | "report" | "evidence"; complete: boolean; missing_artifacts: string[] };
  modes: Mode[]; notices: string[]; stages: StageInfo[]; tasks: TaskInfo[];
  trials: { baseline: number; patched: number; void: number; note: string };
  observations: Observation[]; hypotheses: Hypothesis[]; findings: Finding[]; proposals: Proposal[]; evaluation: Evaluation; effects: Effect[];
  investigation: { skipped: boolean | null; reason: string | null; finished: boolean | null; incomplete: boolean | null; tool_calls: number | null; model_requests: number | null; model: string | null; mode: string | null; cost_usd: number | null; rejected_hypotheses: number };
  statement: string | null;
}

export type Parsed = { ok: true; data: InvestigationExport } | { ok: false; error: string };
const ARRAYS = ["modes", "notices", "stages", "tasks", "observations", "hypotheses", "findings", "proposals", "effects"] as const;
const FORBIDDEN = /"(truth|criteria|criterion|expected_answer|answer|answers|transcript|journey|tool_log|api_key|authorization)"\s*:/i;

/** Parse and validate an exported file. Refuses other schemas and files that contain forbidden private keys, so a raw run artifact can never be displayed by mistake. */
export function parseInvestigation(text: string): Parsed {
  if (FORBIDDEN.test(text)) return { ok: false, error: "This file contains fields that must never be exported (answers, criteria, traces or credentials). Use `readiness investigate export`." };
  let o: any;
  try { o = JSON.parse(text); } catch { return { ok: false, error: "Not valid JSON." }; }
  if (!o || o.schema !== "investigation-dashboard-v1") return { ok: false, error: "Not an investigation-dashboard-v1 export (use `readiness investigate export RUN_DIR --out FILE`)." };
  for (const k of ARRAYS) if (!Array.isArray(o[k])) return { ok: false, error: `Malformed export: "${k}" is missing.` };
  if (!o.run || typeof o.run.id !== "string" || !o.evaluation || !o.trials) return { ok: false, error: "Malformed export: run, trials or evaluation is missing." };
  return { ok: true, data: o as InvestigationExport };
}

export const MODE_LABEL: Record<Mode, string> = { scripted: "SCRIPTED", mock: "MOCK", recorded: "RECORDED", live: "LIVE" };

/** Descriptive pass tally for one arm over trials that are not void (void trials are never website results). */
export function tally(rows: TrialRow[]): { passed: number; usable: number; void: number; requests: number | null } {
  const usable = rows.filter((r) => !r.void);
  const reqs = usable.map((r) => r.model_requests).filter((x): x is number => typeof x === "number");
  return { passed: usable.filter((r) => r.passed).length, usable: usable.length, void: rows.length - usable.length, requests: reqs.length ? reqs.reduce((a, b) => a + b, 0) / reqs.length : null };
}

/** Baseline vs patched over tasks that have a usable trial in BOTH arms. Descriptive only: the verdict comes from the pre-registered rule in `evaluation`. */
export function compare(tasks: TaskInfo[], proposalId: string) {
  const paired = tasks.filter((t) => tally(t.baseline).usable > 0 && tally(t.patched[proposalId] ?? []).usable > 0);
  const flat = (pick: (t: TaskInfo) => TrialRow[]) => tally(paired.flatMap(pick));
  return { tasks: paired.length, baseline: flat((t) => t.baseline), patched: flat((t) => t.patched[proposalId] ?? []), skipped: tasks.length - paired.length };
}
