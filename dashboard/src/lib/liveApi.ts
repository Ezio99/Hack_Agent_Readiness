// Client types for the live evaluation API (M0). Everything is derived server-side from the durable run directory; the UI only renders what it is told.
import { call } from "./scannerApi";

export type JobState = "queued" | "running" | "completed" | "failed" | "cancelled" | "timed_out" | "awaiting_approval" | "stopped";
export interface LiveStage { name: string; status: "pending" | "running" | "done" | "failed" | "awaiting_approval"; detail: string | null; updated_at?: string | null }
export interface LiveEvent { t: number | null; kind: "job" | "stage" | "trace" | "trial" | "approval" | "stop"; text: string }
export interface LiveTrial { trial_id: string; status: string; passed: boolean | null; evidence_backed: boolean | null; model_requests: number | null; page_views: number | null; cost_usd: number | null }
export interface LiveJob {
  id: string; target_id: string; goal: string; mode: "mock" | "live"; mock: boolean; dev_provider: boolean; notice: string | null; state: JobState; error: string | null;
  until: string | null; smoke: SmokeReport | null;
  stop: { kind: string; stage: string | null; reason: string; manifest_sha256?: string } | null; grant: { budget_usd: number; stages: string[]; model: string; confirmed_at: number; grant_sha256: string } | null;
  created_at: number; started_at: number | null; finished_at: number | null; timeout_seconds: number;
  stages: LiveStage[]; progress: number; trials: LiveTrial[]; tasks_planned: number | null; events: LiveEvent[];
  spend: { committed_usd: number; hard_cap_usd: number | null; basis: string; stages: Record<string, number> }; opened: boolean;
}
export interface SmokeReport {
  yield: { requests_made: number; max_requests: number; tasks_proposed: number; tasks_accepted: number; tasks_rejected: number; needed: number; meets_minimum: boolean; rule_topup_tasks: number };
  independent_verification: { how: string; rejection_reasons: Record<string, number> };
  accepted_tasks: { question: string; criterion_kind: string; source: string }[];
  relevance_to_goal: { method: string; tasks_sharing_a_goal_term: number; of: number };
  cost: { calculated_usd: number; cap_usd: number; basis: string };
  provider_compatibility: { batch: number; status: string; usage_has_prompt_and_completion_tokens?: boolean; error?: string | null }[];
}
export interface LiveSummary { id: string; target_id: string; goal: string; mode: string; state: JobState; created_at: number; finished_at: number | null }
export interface LiveTarget { id: string; label: string; description: string }

export const isActive = (s: JobState) => s === "queued" || s === "running";
export const needsPerson = (s: JobState) => s === "awaiting_approval";
export interface LiveInfo { cap_usd: number; model: string; targets: string[]; dev_provider: boolean; smoke: string | null }
export const liveTargets = () => call<{ targets: LiveTarget[]; modes: { mock: boolean; live: boolean }; live: LiveInfo | null }>("/api/live/targets");
export const startJob = (target_id: string, goal: string, live?: { confirm_budget_usd: number }) =>
  call<LiveJob>("/api/live/jobs", { method: "POST", json: live ? { target_id, goal, mode: "live", confirm_budget_usd: live.confirm_budget_usd } : { target_id, goal, mode: "mock" } });
export const listJobs = () => call<{ jobs: LiveSummary[] }>("/api/live/jobs");
export const getJob = (id: string) => call<LiveJob>(`/api/live/jobs/${id}`);
export const cancelJob = (id: string) => call<LiveJob>(`/api/live/jobs/${id}/cancel`, { method: "POST" });
export const exportJob = (id: string) => call<unknown>(`/api/live/jobs/${id}/export`);
