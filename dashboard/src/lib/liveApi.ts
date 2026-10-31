// Client types for the live evaluation API (M0). Everything is derived server-side from the durable run directory; the UI only renders what it is told.
import { call } from "./scannerApi";

export type JobState = "queued" | "running" | "completed" | "failed" | "cancelled" | "timed_out";
export interface LiveStage { name: string; status: "pending" | "running" | "done" | "failed" | "awaiting_approval"; detail: string | null; updated_at?: string | null }
export interface LiveEvent { t: number | null; kind: "job" | "stage" | "trace" | "trial"; text: string }
export interface LiveTrial { trial_id: string; status: string; passed: boolean | null; evidence_backed: boolean | null; model_requests: number | null; page_views: number | null; cost_usd: number | null }
export interface LiveJob {
  id: string; target_id: string; goal: string; mode: "mock" | "live"; mock: boolean; notice: string | null; state: JobState; error: string | null;
  created_at: number; started_at: number | null; finished_at: number | null; timeout_seconds: number;
  stages: LiveStage[]; progress: number; trials: LiveTrial[]; tasks_planned: number | null; events: LiveEvent[];
  spend: { committed_usd: number; hard_cap_usd: number | null; basis: string }; opened: boolean;
}
export interface LiveSummary { id: string; target_id: string; goal: string; mode: string; state: JobState; created_at: number; finished_at: number | null }
export interface LiveTarget { id: string; label: string; description: string }

export const isActive = (s: JobState) => s === "queued" || s === "running";
export const liveTargets = () => call<{ targets: LiveTarget[]; modes: { mock: boolean; live: boolean } }>("/api/live/targets");
export const startJob = (target_id: string, goal: string) => call<LiveJob>("/api/live/jobs", { method: "POST", json: { target_id, goal, mode: "mock" } });
export const listJobs = () => call<{ jobs: LiveSummary[] }>("/api/live/jobs");
export const getJob = (id: string) => call<LiveJob>(`/api/live/jobs/${id}`);
export const cancelJob = (id: string) => call<LiveJob>(`/api/live/jobs/${id}/cancel`, { method: "POST" });
export const exportJob = (id: string) => call<unknown>(`/api/live/jobs/${id}/export`);
