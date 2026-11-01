// Typed contract for `investigation-dashboard-v1`, the sanitized read-only export written by `readiness investigate export` (Task 016 M7).
// The dashboard never receives private criteria, agent answers, traces or credentials; `parseInvestigation` refuses anything that is not this schema.
export type Mode = "scripted" | "mock" | "recorded" | "live";
export type StageStatus = "pending" | "running" | "done" | "failed" | "awaiting_approval";
export interface Prov { mode: Mode; source: string }
export interface StageInfo { name: string; status: StageStatus; updated_at: string | null; skipped: boolean; reason: string | null; manifest_sha256: string | null; summary: Record<string, string | number | boolean | null> }
export interface TrialRow { trial_id: string; repeat: number; run_status: string | null; void: boolean; passed: boolean | null; evidence_backed: boolean | null; model_requests: number | null; page_views: number | null; mode: Mode | null; attribution?: string; why?: string }
export interface TaskInfo { tags?: string[]; task_id: string; question: string; kind: string; source: string; partition: "investigation" | "holdout"; start_path: string; limits: Record<string, number> | null; baseline: TrialRow[]; patched: Record<string, TrialRow[]>; placebo?: Record<string, TrialRow[]> }
export interface Observation { id: string; kind: string; summary: string; refs: string[]; provenance: Prov }
export interface Hypothesis { id: string; tier: "verifiable" | "novel"; statement: string; claim_kind: string | null; prediction: string | null; status: "unverified" | "supported" | "refuted" | "unverifiable"; observation_ids: string[]; verification: { verifier: string; result: string; evidence: string[] } | null; promoted: boolean; provenance: Prov }
export interface Finding { id: string; hypothesis_id: string; statement: string; attribution: string; structural_proof: boolean; provenance: Prov; observation_ids: string[]; unresolved_observation_ids: string[]; support: { ref: string; resolved: boolean }[] }
export interface Proposal { id: string; basis: "verified_finding" | "unverified_hypothesis"; source_id: string; label: string; status: string; validation: string; expected_effect: string; risks: string[]; auto_applicable: boolean; owner_selected?: boolean; exploratory?: boolean; change: { manual: string } | { ops: string[] }; approved: boolean; provenance: Prov }
export interface EvalResult { proposal_id: string; verdict: "improvement" | "regression" | "inconclusive"; reason: string | null; pairs: number | null; pass_delta: number | null; request_change: number | null; p_pass: number | null; p_requests: number | null; holdout_consistent: boolean | null; by_partition: Record<string, { pairs: number; pass_delta: number | null }> | null; rule_preregistered_at_freeze: boolean | null; excluded: { task_id: string; reason: string }[]; measured: boolean; effect_mode: Mode | null }
export type ExploratoryVerdict = "consistent_with_h1" | "not_supported" | "inconclusive_conflicting_comparisons" | "uninterpretable";
export interface ArmRow { requests: number; page_views: number; pass: boolean }
export interface AffectedCheck { placebo_requests: number; historical_requests: number; patched_requests: number; primary_meets_floor: boolean; secondary_meets_floor: boolean; exceeds_noise: boolean; page_views_lower: boolean; pass_not_lost: boolean; drift_flag: boolean }
/** The separate, labelled EXP-B analysis. It never replaces the frozen verdict in `Evaluation.results`. */
export interface Exploratory {
  rules_id: string; rules_sha256: string; label: string; verdict: ExploratoryVerdict; reasons: string[];
  tasks: { baseline: Record<string, ArmRow | null>; placebo: Record<string, ArmRow | null>; patched: Record<string, ArmRow | null> };
  missing_or_void: string[]; noise_estimate_requests?: number; controls_within_tolerance?: boolean; affected?: Record<string, AffectedCheck>;
  plan: { placebo_tasks?: string[]; affected?: string[]; same_shape_controls?: string[]; detail_controls?: string[] };
  rules: { effect_floor: number; claims: string; same_shape_control_tolerance_requests: number; detail_control_tolerance_requests: number } & Record<string, unknown> | null; rules_match_code: boolean;
}
export interface Evaluation { state: "evaluated" | "not_evaluated" | "missing"; reason: string | null; rule: Record<string, string | number | null> | null; results: EvalResult[]; exploratory?: Exploratory | null }
export interface Effect { id: string; proposal_id: string; verdict: string; n_pairs: number; note: string; measured: boolean; mode: Mode }
export interface GoalCoverage {
  status: "complete" | "partial" | "insufficient"; selected_tasks: number; gate_accepted_tasks: number; relevant_tasks: number; asked_aspects: string[]; covered_aspects: string[]; missing_supported_aspects: string[];
  entities: { path: string; name: string; covered: boolean }[]; entities_total: number; entities_covered: number; partial_because: string[]; limitations: { aspect: string; kind: string; detail: string }[];
  first_page_answerable_selected: number; note: string;
}
export interface InsightEffort { task_id: string; question: string; source: string; partition: string; trial_id: string; passed: boolean; requests: number; steps_used: number | null; step_limit: number; page_views: number; minimum_page_views: number;
  extra_page_views: number; attribution: string; strict_grade: string; names_mentioned_in_answer: string; friction: boolean; fields_needed: string[]; needs_field_absent_from_cards: string[]; notes: string[] }
export interface InsightProperty { field: string; listing: string; item_pages_with_field: number; listing_items: number; shown_on_listing_items: number; absent_from_cards: boolean; evidence: string }
export interface InsightCause { text: string; fields: string[]; claim_kind: string | null; status: string; refs: string[]; source: string; label: string }
export interface InsightSuggestion { text: string; fields: string[]; tasks: string[]; basis: string[]; expected_benefit: string; risks: string[]; label: string; source: string; patch: null }
/** Derived, model-free owner view: measurements, hypotheses and unvalidated text suggestions. Never VERIFIED. Absent in older exports. */
export interface Insights { schema: "owner-insights-v1"; summary: string; site_properties: InsightProperty[]; task_effort: InsightEffort[]; friction_tasks: string[]; possible_causes: InsightCause[]; suggestions: InsightSuggestion[]; strict_findings: number;
  provenance: { run_id: string; mode: string; source_run: string | null; task_sources: Record<string, number>; investigator_model: string | null; investigation_status: string | null; frozen_tasks: number; note: string } }
export interface InvestigationExport {
  evidence_origin?: { provider: "real_model" | "dev_fixture" | "scripted" | "unknown"; presentation: "recorded" };
  demo_case?: { id: string; label: string; recorded_on: string; note: string };
  storyboard?: { task_id: string; arm: string; steps: { event: number; category: string; text: string; ok: boolean }[]; strict_pass: boolean; evidence_supported: boolean; note: string } | null;
  insights?: Insights | null;
  /** live evaluations only: the user's goal, the client briefing and how well the selected tasks serve the goal (absent in older exports and in non-live modes) */
  goal?: string | null; client_context?: { text: string; sha256: string | null; label: string } | null; goal_coverage?: GoalCoverage | null;
  schema: "investigation-dashboard-v1"; exported_at: string | null; synthetic?: boolean; audience?: "public-demo";
  run: { id: string; target: string; mode: Mode; created_at: string | null; outcome: "findings" | "experimental_only" | "no_supported_issue" | "not_investigated" | "incomplete_due_to_infrastructure_error" | "incomplete_unusable_model_output" | "incomplete_no_finish"; investigation_status: "completed" | "not_run" | "incomplete_due_to_infrastructure_error" | "incomplete_unusable_model_output" | "incomplete_no_finish" | null; report_source: "report-final" | "report" | "evidence"; complete: boolean; missing_artifacts: string[] };
  modes: Mode[]; notices: string[]; stages: StageInfo[]; tasks: TaskInfo[];
  trials: { baseline: number; patched: number; placebo?: number; quarantined?: number; void: number; note: string };
  observations: Observation[]; hypotheses: Hypothesis[]; findings: Finding[]; proposals: Proposal[]; evaluation: Evaluation; effects: Effect[];
  investigation: { skipped: boolean | null; reason: string | null; finished: boolean | null; incomplete: boolean | null; tool_calls: number | null; model_requests: number | null; model: string | null; mode: string | null; cost_usd: number | null; rejected_hypotheses: number };
  statement: string | null;
  storefront?: Storefront;
  spend?: { state: "ok" | "missing"; basis?: string; committed_usd?: number; ceiling_usd?: number | null; remaining_usd?: number | null; open_reservations?: number; by_arm_usd?: Record<string, number>; by_trial_usd?: Record<string, number> };
}

export interface StorefrontDiff { pages_changed: string[]; pages_unchanged: number; inserted_text: Record<string, string[]>; elements_added: number; inserted_text_chars: number; net_bytes_added: number }
export interface StorefrontVariant { proposal_id: string; pages: Record<string, string>; diff: StorefrontDiff }
/** Captured pages of the evaluated site (and of each patched mirror) for the static, inert in-dashboard browser. */
export type Storefront = { state: "ok"; note: string; original: { pages: Record<string, string> }; variants: StorefrontVariant[] } | { state: "missing" | "omitted"; reason: string };

export type Parsed = { ok: true; data: InvestigationExport } | { ok: false; error: string };
const ARRAYS = ["modes", "notices", "stages", "tasks", "observations", "hypotheses", "findings", "proposals", "effects"] as const;
const FORBIDDEN = /"(truth|criteria|criterion|expected|evidence_texts|evidence_paths|expected_answer|answer|answers|transcript|journey|tool_log|api_key|authorization|raw_trace|raw_traces|messages|dom|model_output|proposed_actions)"\s*:/i;

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
export function tally(rows: TrialRow[]): { passed: number; usable: number; supported: number; void: number; requests: number | null } {
  const usable = rows.filter((r) => !r.void);
  const reqs = usable.map((r) => r.model_requests).filter((x): x is number => typeof x === "number");
  return { supported: usable.filter((r) => r.passed && r.evidence_backed).length, passed: usable.filter((r) => r.passed).length, usable: usable.length, void: rows.length - usable.length, requests: reqs.length ? reqs.reduce((a, b) => a + b, 0) / reqs.length : null };
}

/** Baseline vs patched over tasks that have a usable trial in BOTH arms. Descriptive only: the verdict comes from the pre-registered rule in `evaluation`. */
export function compare(tasks: TaskInfo[], proposalId: string) {
  const paired = tasks.filter((t) => tally(t.baseline).usable > 0 && tally(t.patched[proposalId] ?? []).usable > 0);
  const flat = (pick: (t: TaskInfo) => TrialRow[]) => tally(paired.flatMap(pick));
  return { tasks: paired.length, baseline: flat((t) => t.baseline), patched: flat((t) => t.patched[proposalId] ?? []), skipped: tasks.length - paired.length };
}

export const EXPLORATORY_VERDICT: Record<ExploratoryVerdict, { label: string; tone: "good" | "warn" | "info" | "bad" }> = {
  consistent_with_h1: { label: "Consistent with the hypothesis", tone: "good" },
  not_supported: { label: "Not supported", tone: "bad" },
  inconclusive_conflicting_comparisons: { label: "Inconclusive — the comparisons conflict, no support claimed", tone: "warn" },
  uninterpretable: { label: "Uninterpretable", tone: "warn" },
};

export type Role = "Affected" | "Same-shape control" | "Detail-page control";
/** Task roles fixed by the pre-registered plan, in display order. */
export function roles(x: Exploratory): { task_id: string; role: Role }[] {
  const p = x.plan;
  return [...(p.affected ?? []).map((task_id) => ({ task_id, role: "Affected" as const })), ...(p.same_shape_controls ?? []).map((task_id) => ({ task_id, role: "Same-shape control" as const })),
    ...(p.detail_controls ?? []).map((task_id) => ({ task_id, role: "Detail-page control" as const }))];
}


/** The three honesty classes of a report, computed from the export alone (so older exports degrade gracefully).
 *  VERIFIED: a promoted finding (deterministic checker + independent task support or a structural proof), and trial results graded against answers computed by code from the captured site.
 *  OBSERVED: recorded facts that no checker promoted: a claim the checker supported without enough independent support, and measured effort/outcomes of trials.
 *  INCONCLUSIVE: ideas nothing verified (open-ended hypotheses, unverifiable or refuted claims), void trials and failures not attributable to the website. */
export interface ClassItem { text: string; refs: string[]; note?: string }
export interface OutcomeClasses { verified: ClassItem[]; observed: ClassItem[]; inconclusive: ClassItem[]; proposals: { label: string; basis: string; validation: string }[]; sources: { owner: number; model: number } }

export function classifyOutcome(d: InvestigationExport): OutcomeClasses {
  const trialRefs = (h: Hypothesis) => (h.verification?.evidence ?? []).filter((e) => e.startsWith("trial:"));
  const verified: ClassItem[] = d.findings.map((f) => ({ text: f.statement, refs: [f.id, ...f.support.map((s) => s.ref), ...f.observation_ids], note: `attributed to the ${f.attribution}; ${f.structural_proof ? "structural proof" : `${f.support.length} independent supporting task(s)`}` }));
  const rows = d.tasks.flatMap((t) => t.baseline.filter((r) => !r.void).map((r) => ({ t, r })));
  const passed = rows.filter((x) => x.r.passed).length;
  const supported = rows.filter((x) => x.r.passed && x.r.evidence_backed).length;
  if (rows.length) verified.push({ text: `${passed} of ${rows.length} strict passes; ${supported} evidence-supported passes, graded against answers computed by code from the captured copy of the site`, refs: rows.map((x) => x.r.trial_id), note: "a graded outcome of those tasks only; not a statement about the whole goal" });
  const observed: ClassItem[] = d.hypotheses.filter((h) => h.tier === "verifiable" && h.status === "supported" && !h.promoted).map((h) => ({ text: h.statement, refs: [h.id, ...trialRefs(h)], note: `the checker supported it, but only ${trialRefs(h).length} task(s) show a cost, below the promotion rule; not a finding` }));
  if (d.insights) { if (rows.length) observed.push({ text: `Measured effort and strict grades for ${rows.length} task(s) are in the table above`, refs: rows.map((x) => x.r.trial_id) }); }
  else for (const x of rows) if (x.r.model_requests != null) observed.push({ text: `${x.t.question} — ${x.r.model_requests} model request(s), ${x.r.page_views ?? "?"} page view(s), ${x.r.passed ? "passed" : "failed"}${x.r.attribution && x.r.attribution !== "success" ? ` (${x.r.attribution})` : ""}`, refs: [x.r.trial_id], note: "observed effort; not a cause" });
  const inconclusive: ClassItem[] = d.hypotheses.filter((h) => !(h.tier === "verifiable" && h.status === "supported"))
    .map((h) => ({ text: h.statement, refs: [h.id, ...h.observation_ids], note: h.tier === "novel" ? "open-ended idea: UNVERIFIED, never a finding" : `checker result: ${h.verification?.result ?? h.status}` }));
  const voidN = d.tasks.flatMap((t) => t.baseline.filter((r) => r.void)).length;
  if (voidN) inconclusive.push({ text: `${voidN} trial(s) were void (provider, budget or infrastructure) and say nothing about the website`, refs: [] });
  const failedRows = rows.filter((x) => x.r.passed === false && x.r.attribution && x.r.attribution !== "website" && x.r.attribution !== "success");
  if (d.insights && failedRows.length > 1) inconclusive.push({ text: `${failedRows.length} tasks did not match the strict grading and were not attributed to the website by the automatic heuristic (labels such as “tool_interface” or “agent” can misfire and are not treated as causes)`, refs: failedRows.map((x) => x.r.trial_id) });
  else for (const x of failedRows) inconclusive.push({ text: `${x.t.question} — did not match the strict grading; the automatic label “${x.r.attribution}” is a heuristic, not an established cause, and does not point to the website`, refs: [x.r.trial_id] });
  return { verified, observed, inconclusive, proposals: d.proposals.map((p) => ({ label: p.label, basis: p.basis, validation: p.validation })), sources: { owner: d.tasks.filter((t) => t.source === "owner").length, model: d.tasks.filter((t) => t.source === "model").length } };
}
