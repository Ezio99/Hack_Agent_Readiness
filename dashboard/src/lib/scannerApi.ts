// Client for the protected scanner API (Task 011). The base URL is build-time configuration (VITE_SCANNER_API_URL); when it is absent the UI says so
// honestly instead of pretending to scan. The session token lives in sessionStorage only (cleared when the tab closes) and is never logged.
export const API_BASE: string = ((import.meta as any).env?.VITE_SCANNER_API_URL ?? "").replace(/\/$/, "");
const KEY = "ar-scanner-session";

export type Confidence = "observed" | "inferred" | "hypothesis";
export interface Finding {
  id: string; category: string; title: string; summary: string; confidence: Confidence;
  evidence: { step?: number; path?: string; note?: string }[];
  recommendation?: { text: string; status: "hypothesis_unvalidated"; validate_with?: { factor: string; from: string; to: string; task: string } | null };
}
export interface JourneyStep { step: number; path: string; query: string; actions: { name: string; params: Record<string, unknown> }[]; executed: { result: string; error: string | null }[] }
export interface ScanSummary { scan_id: string; task_id: string; variant_id: string; mode: "mock" | "live"; mock_behavior: string | null; status: string; created_at: number; finished_at: number | null; error: string | null }
export interface ScanResult extends ScanSummary {
  mock: boolean; inference_label: string;
  task?: { objective: string; template_id: string; evidence_policy: string; limits: { max_steps: number; max_model_requests: number; timeout_seconds: number } };
  variant?: { id: string; factors: Record<string, string> | [string, string][] };
  verdict?: { passed: boolean; evidence_backed: boolean; answer_valid: boolean; reasons: string[]; missing_evidence: string[]; evaluator: string };
  outcome?: { run_status: string; stop_reason: string; answer: unknown; errors: string[] };
  metrics?: { model_requests: number; page_views: number; elapsed_seconds: number; prompt_tokens: number; completion_tokens: number; calculated_cost_usd: number; cost_basis: string; limits: { max_steps: number; max_model_requests: number; timeout_seconds: number } };
  journey?: JourneyStep[];
  diagnostics?: { findings: Finding[]; mode_notice: string; attribution_note: string; metrics: { reference_page_views: number | null; reference_note: string } };
}
export interface Registry {
  environments: { environment_id: string; data_version: string; variants: { variant_id: string; factors: [string, string][]; default: boolean }[] }[];
  tasks: { task_id: string; template_id: string; environment_id: string; objective: string; outcome_type: string; limits: { max_steps: number; max_model_requests: number; timeout_seconds: number } }[];
  providers: { mock: boolean; live: boolean }; mock_behaviors: string[]; kill_switch: boolean;
}
export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }

export const configured = () => API_BASE !== "";
let memory: string | null = null;      // fallback where sessionStorage is unavailable (tests, SSR)
const store = () => (typeof sessionStorage === "undefined" ? null : sessionStorage);
const safe = <T,>(f: () => T, fallback: T): T => { try { return f(); } catch { return fallback; } };      // storage may be blocked (privacy mode): fall back to memory, never throw
export const getToken = () => safe(() => store()?.getItem(KEY) ?? null, null) ?? memory;
export const setToken = (t: string | null) => { memory = t; safe(() => { if (t) store()?.setItem(KEY, t); else store()?.removeItem(KEY); }, undefined); };

export async function call<T>(path: string, init: RequestInit & { json?: unknown } = {}, fetcher: typeof fetch = fetch): Promise<T> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (init.json !== undefined) { headers["Content-Type"] = "application/json"; init = { ...init, body: JSON.stringify(init.json) }; }
  let res: Response;
  try { res = await fetcher(`${API_BASE}${path}`, { ...init, headers }); } catch { throw new ApiError(0, "The scanner service is unreachable."); }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, typeof body.message === "string" ? body.message : `Request failed (${res.status}).`);
  return body as T;
}
export const factorsOf = (v: ScanResult["variant"]) => (Array.isArray(v?.factors) ? Object.fromEntries(v!.factors) : (v?.factors ?? {}));
