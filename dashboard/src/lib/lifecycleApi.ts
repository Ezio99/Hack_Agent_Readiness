// Client types for the lifecycle API (M8). Every value is computed server-side from the lifecycle store, launched runs or a sanitized dataset;
// the UI only renders what it is told. No request body carries a task, URL, model, limit or spending field.

export interface StepInfo { id: string; label: string; available: boolean; action_available?: boolean; detail: string }
export interface Unavailable { available: boolean; reason: string; detail: string }
export interface ArmedEvaluation { arming_id: string; arming_sha256: string; mode: 'paid' | 'rehearsal'; site: string; suite: string; frozen_suite: string; frozen_suite_sha256: string;
  variants: string[]; armed_at: string; launches: { max: number; used: number; left: number };
  options: { repetitions: number; trials: number; reservation_usd: number; manifest_sha256: string; available: boolean; fits_hosted_ceiling: boolean | null }[];
  agent: { model: string; reasoning_effort: string | null; max_completion_tokens: number; profile: string } }
export interface Overview { steps: StepInfo[]; onboarding: Unavailable; approval: Unavailable; sources: { datasets: string[]; store: boolean; jobs: boolean };
  evaluation: { engine: string; armed: boolean; reason: string | null; evaluation: ArmedEvaluation | null; repetitions: number[] } | null }
export interface Persona { id: string; name: string; needs: string; constraints: string }
export interface Journey { id: string; name: string; attributes: string[]; weight: number }
export interface Context { label: string; business: string; goals: string[]; personas: Persona[]; journeys: Journey[]; weights_note: string }
export interface Variant { name: string; label: string; description: string | null; snapshot_sha256?: string }
export interface Site { id: string; label: string; domain: string; controlled: boolean; listings: string[]; variants: Variant[]; context: Context | null;
  context_label: string | null; note: string | null; source: string; suites?: SuiteSummary[]; generations?: GenerationSummary[] }

export interface GenerationSummary { id: string; dataset: string; site: string; created_at: string; mode: string; stop_reason: string; admissions: Record<string, number>;
  proposals: number; rounds: number; cost: { requests: number; calculated_usd: number; unsettled: number; basis: string }; suite_sha256: string; generator: Record<string, unknown> }
export interface Proposal { id: string; round: number; persona: string | null; journey: string | null; capability: string; kind: string; admission: string; category: string | null;
  customer_wording: string | null; withheld: string | null; executed_wording: string | null; assumptions: string[]; unresolved: string[]; rejection_reasons: string[];
  gates: Record<string, boolean>; nl_traces: { component: string; decision: string; status: string }[]; soft: Record<string, number> | null }
export interface Round { round: number; sent: boolean; model: string; latency_seconds: number; prompt_tokens: number; completion_tokens: number; reasoning_tokens: number;
  cost_usd: number; candidates: number; admissions: Record<string, number>; targets_met: boolean; gaps_after: string[]; stop: string | null }
export interface Generation { id: string; site: string; created_at: string; mode: string; generator: Record<string, string | number>; limits: Record<string, number>;
  stop_reason: string; suite_sha256: string; suite_name: string; cost: GenerationSummary['cost']; rounds: Round[]; proposals: Proposal[]; admissions: Record<string, number>;
  post_fix_reevaluation: { admissions: Record<string, number>; note: string } | null;
  feedback: { for_round: number; coverage_gaps: string[]; missing_capabilities: string[]; avoid_signatures: number; note: string }[];
  gap_report: { gaps: string[]; missing_capabilities: string[]; thresholds_lowered: boolean; note: string } | null }

export interface SuiteSummary { sha256: string; name: string; version: number; site: string; tasks: number; state: 'proposed' | 'approved' | 'rejected' | 'frozen'; refs: string[];
  synthetic: boolean; created_at: string; created_by: string; gaps: number; source: string }
export interface SuiteTask { task_id: string; sha256: string; persona: string | null; journey: string | null; capability: string; category: string; condition: string | null;
  verifiability: string; customer_wording: string; executed_wording: string | null; interpretation_decisions: string[]; assumptions: string[]; unresolved: string[];
  limits: { max_steps: number; max_model_requests: number; timeout_seconds: number } }
export interface CoverageStatus { actual: unknown; met: boolean; target: string }
export interface Suite { sha256: string; suite_name: string; version: number; site: string; selection_rule: string; gaps: string[]; synthetic: boolean; state: SuiteSummary['state'];
  approvals: { sha256: string; decision: string; role: string; decided_at: string; synthetic: boolean }[]; frozen: { sha256: string; approval_sha256: string; frozen_at: string }[];
  refs: string[]; created_at: string; created_by: string; inputs: { kind: string; name: string; sha256: string }[];
  coverage: { status?: Record<string, CoverageStatus>; per_persona?: Record<string, number>; per_journey?: Record<string, number>; capabilities?: Record<string, number> };
  counts: { tasks: number; by_condition: Record<string, number>; by_category: Record<string, number> }; tasks: SuiteTask[]; checklist: string[];
  attestation: { approve: string; reject: string }; owner_terminal_command: string; web_decision: Unavailable; source: string }

export interface Grade { passed: boolean; evidence_backed?: boolean; reasons: string[]; review?: boolean; official?: boolean; status?: string }
export interface Trial { id: string; task_id: string; task: number; variant: string; condition: string; repetition: number; status: string; stop_reason: string | null; void: boolean;
  answer: string | string[] | null; answer_withheld?: string;
  grades: { v1: Grade; v2: Grade | null; v2_1_contrast: Grade | null };
  answer_coverage: { expected_items: number; named_expected: number; named_other: number; unrecognised: number } | null;
  evidence: { satisfied: boolean; required_pages: number; missing_pages: number; missing_texts: number;
    ranked_subset_rule_2: { applies: boolean; required_pages?: number; shown_pages?: number; satisfied?: boolean; status?: string } };
  metrics: { model_requests: number | null; request_limit: number | null; steps: number | null; page_views: number | null; elapsed_seconds: number | null; prompt_tokens: number | null; completion_tokens: number | null; cost_usd: number | null };
  navigation: { visits: string[]; distinct_pages: number; revisits: number; item_pages_opened: number };
  reliability: { http_errors: { path: string; status: number }[]; failed_action_steps: number[]; blocked_requests: number; dead_end: boolean; recovered: boolean; near_request_limit: boolean;
    limit_stop: boolean; empty_answer: boolean; partial_answer: boolean; protocol: { responses: number | null; noncompliant: number | null; recovered: number | null } } }
export interface EvTask { n: number; task_id: string; sha256: string; persona: string | null; journey: string | null; capability: string; kind: string; category: string; condition: string | null;
  customer_wording: string; executed_wording: string | null; assumptions: string[]; facts: string[]; limits: SuiteTask['limits']; executed: boolean; min_hops: Record<string, number | null> | null }
export interface Finding { id: string; layer: string; rule: string; title: string; variant: string; severity: string; impact: string; status: string; basis: 'observed' | 'hypothesis';
  recommendation: string; verify: string; tasks: number[]; evidence_origin: string; evidence: { type: string; ref: string; detail: string }[]; detail: Record<string, unknown> }
export interface Diagnostics { available: boolean; reason?: string; rules?: Record<string, string>; evidence_origin?: string; summary?: { observed: number; hypotheses: number };
  structural_changes?: Record<string, { resolved: number; introduced: number; persisting: number; resolved_titles: string[] }>; findings?: Finding[] }
type ByVariant<T> = { variants: Record<string, T>; basis: string }
export interface Dimensions {
  task_success: ByVariant<{ trials: number; v1_passed: number; v1_evidence_backed: number; v2_passed: number; v2_evidence_backed: number; v2_1_contrast_review_passes: number }>;
  navigation_efficiency: ByVariant<{ model_requests_total: number | null; model_requests_mean: number | null; steps_mean: number | null; page_views_mean: number | null; elapsed_seconds_total: number | null;
    elapsed_seconds_mean: number | null; revisits_total: number | null; item_pages_opened_mean: number | null; cost_usd_total: number | null }>;
  evidence_quality: ByVariant<{ evidence_satisfied: number; trials: number; correct_but_unsupported_v2: number; missing_pages_total: number;
    ranked_subset_rule_2: { task: number; required_pages: number; shown_pages: number; satisfied: boolean }[] }> & { prospective_rule: { id: string; status: string } };
  information_accessibility: { basis: string; facts: Record<string, Record<string, { items: number; on_listing_cards: number; on_item_pages: number }>>;
    tasks: { task: number; facts: string[]; placement: Record<string, Record<string, string>>; min_link_steps: Record<string, number | null> | null }[] };
  agent_reliability: ByVariant<{ dead_ends: number; recovered_after_dead_end: number; partial_answers: number; empty_answers: number; near_request_limit: number; limit_stops: number; void: number; protocol_recoveries: number | null }>;
  coverage: { basis: string; personas: Record<string, number> | null; journeys: Record<string, number> | null; capabilities: Record<string, number> | null;
    status: Record<string, CoverageStatus> | null; gaps: string[]; executed_tasks: number; tasks: number; context: Context | null } }
export interface Analysis { label: string; outcome: string; official_v1: AnalysisPart; post_hoc_v2: AnalysisPart }
export interface AnalysisPart { designation: string; test: string; alpha: number; pairs: number; planned_pairs: number; mean_difference: number | null; p_value: number | null;
  per_task: ({ task: number; difference: number } & Record<string, number>)[] }
export interface Evaluation { id: string; title: string; mode: 'paid' | 'rehearsal'; mode_label: string; execution_provider: string; notice: string | null;
  site: { id: string; label: string; domain: string }; suite: { name: string; version: number; sha256: string; created_by: string };
  approval: { sha256: string; decision: string; role: string; decided_at: string; method: string; synthetic: boolean }; frozen_suite: { sha256: string; frozen_at: string };
  manifest: { sha256: string; variants: { name: string; snapshot_sha256: string }[]; conditions: string[]; repetitions: number; seed: number; plan: string;
    budget: { worst_case_reservation_usd: number; hard_cap_usd: number; per_request_cap_usd: number } };
  agent: { model: string; reasoning_effort: string | null; max_completion_tokens: number; profile: string };
  graders: { official: string; post_hoc: string; prospective: { id: string; status: string }[] }; started_at: string | null; finished_at: string | null;
  execution: Record<string, { planned: number | null; executed: number; stopped: string | null; jail_selftest_ok: boolean; authorization_verified: boolean | null; invalidated: Record<string, { task: number; reason: string }[]> }>;
  cost: { by_variant: Record<string, number | null> | null; total_usd: number | null; basis: string; settled_spend?: { settled_usd: number; settled_requests: number; unsettled_requests: number; basis: string } | null };
  exploratory: boolean; caveat: string | null; tasks: EvTask[]; trials: Trial[]; analysis: Record<string, Analysis>; dimensions: Dimensions; diagnostics: Record<string, Diagnostics>;
  source?: { kind: 'dataset' | 'launched'; id?: string; version?: number; built_at?: string; description?: string; runs?: string[]; job?: string; state?: string } }
export interface EvaluationSummary { id: string; title: string | null; mode: string; mode_label?: string; state: string; source: 'dataset' | 'launched'; site?: string; suite?: string;
  variants?: string[]; finished_at?: string | number | null; created_at?: number; tasks?: number; trials?: number; exploratory?: boolean; dataset_version?: number;
  success?: Dimensions['task_success']['variants']; requests?: Record<string, number | null>; cost_usd?: number | null }
export interface Step { step: number; path: string | null; title: string | null; screenshot: string | null; assessment: string | null; memory: string | null; goal: string | null;
  actions: { name: string; target: string | null }[]; error: string | null; done: boolean }
export interface Timeline { id: string; mode?: string; steps: Step[]; errors: string[]; screenshots: string[] }
export class ApiError extends Error { constructor(message: string, public status: number, public code?: string) { super(message); } }

export async function get<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, { cache: 'no-store', ...init });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = body?.detail;
    const msg = typeof d === 'string' ? d : typeof d?.message === 'string' ? d.message : r.status === 404 ? 'Not found.' : 'The evaluation service is unavailable.';
    throw new ApiError(msg, r.status, typeof d?.code === 'string' ? d.code : undefined);
  }
  return body as T;
}

const B = '/api/lifecycle';
export const api = {
  overview: () => get<Overview>(`${B}/overview`),
  sites: () => get<Site[]>(`${B}/sites`),
  site: (id: string) => get<Site>(`${B}/sites/${encodeURIComponent(id)}`),
  generations: () => get<GenerationSummary[]>(`${B}/generations`),
  generation: (id: string) => get<Generation>(`${B}/generations/${encodeURIComponent(id)}`),
  suites: () => get<SuiteSummary[]>(`${B}/suites`),
  suite: (sha: string) => get<Suite>(`${B}/suites/${sha}`),
  evaluations: () => get<EvaluationSummary[]>(`${B}/evaluations`),
  evaluation: (id: string) => get<Evaluation>(`${B}/evaluations/${encodeURIComponent(id)}`),
  timeline: (id: string, trial: string) => get<Timeline>(`${B}/evaluations/${encodeURIComponent(id)}/trials/${encodeURIComponent(trial)}`),
  shot: (id: string, trial: string, name: string) => `${B}/evaluations/${encodeURIComponent(id)}/trials/${encodeURIComponent(trial)}/screenshots/${encodeURIComponent(name)}`,
};

export const short = (sha: string | undefined | null, n = 12) => (sha ?? '').slice(0, n);
export const VARIANT_LABEL = (v: string) => v.charAt(0).toUpperCase() + v.slice(1);
export const variantClass = (v: string) => v === 'original' ? 'o' : v === 'modified' ? 'm' : 'x';
export const fmtUsd = (n: number | null | undefined, d = 3) => n == null ? '–' : `US$${n.toFixed(d)}`;
export const fmtSec = (n: number | null | undefined) => n == null ? '–' : `${Math.round(n)} s`;
export const words = (s: string) => s.replaceAll('_', ' ');
