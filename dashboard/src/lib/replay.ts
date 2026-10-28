// Types and helpers for the "Recorded experiment replay" (Task 008 Stage B, development-only data).
// The replay JSON files are produced locally by dashboard/scripts/export_replay.py into dashboard/public/replays/ (Git-ignored);
// they are NOT committed until the exact files and fields have been approved. Nothing here is live inference.

export const REPLAY_LABEL = "Recorded experiment replay — not live inference";

export interface ReplayAction { name: string; params: Record<string, unknown>; params_omitted?: boolean }
export interface ReplayToolResult { action: string | null; result_excerpt: string | null; result_truncated: boolean; error: string | null; is_done: boolean }
export interface ReplayStep {
  step: number;
  page: "listing" | "filtered listing" | "product detail";
  path: string;
  title: string | null;
  model_visible_dom: string;
  model_visible_last_result: string | null;
  actions: ReplayAction[];
  tool_results: ReplayToolResult[];
  result_visible_to_model_next_request: string | null;
  protocol: "raw_valid" | "recovered";
  guard: { schema: "full" | "done_only"; budget_warning: boolean; final_step: boolean };
  usage: { prompt_tokens: number; completion_tokens: number; reasoning_tokens: number | null };
  latency_s: number;
  finish_reason: string;
  estimated_cost_usd: number;
}
export interface ReplayRun {
  id: string; scope: string; arm: "A" | "B"; rank: number; task: string;
  evaluator: { passed: boolean; reasons: string[] };
  answer_submitted: { product_id: string; price_cents: number; available: boolean };
  required_visits: number; observed_visits: number; overhead: number | null;
  verification_shortfall: { required_visits: number; actual_visits: number; detail_visit_shortfall: number; higher_priced_candidates: number; higher_priced_checked: number | null; higher_priced_unchecked: number | null } | null;
  attribution: { required_path_requests: number; tool_loop_requests: number; residual_requests: number; total_requests: number };
  totals: { requests: number; prompt_tokens: number; completion_tokens: number; estimated_cost_usd: number; elapsed_s: number };
}
export interface Replay { schema: string; label: string; run: ReplayRun; steps: ReplayStep[]; notes: { cost: string; excluded: string } }
export interface Manifest { schema: string; development_only: boolean; label: string; replays: { file: string; id: string; entry_id: string; sha256: string; bytes: number }[]; schedule_sha256: string; execution_commit: string }

/** True when the harness-side tool output carried product links (hrefs) but the model's next request did not show them. */
export const hasVisibilityGap = (s: ReplayStep): boolean => {
  const tool = s.tool_results.map((t) => t.result_excerpt ?? "").join("\n");
  const seen = s.result_visible_to_model_next_request;
  return /href="/.test(tool) && seen !== null && !/href/.test(seen);
};

/** Consecutive steps with the same action name and a visibility gap form a loop; returns the longest one when it has >= 3 steps. */
export const visibilityLoop = (steps: ReplayStep[]): { first: number; last: number; length: number } | null => {
  let best: { first: number; last: number; length: number } | null = null;
  let run: ReplayStep[] = [];
  const flush = () => {
    if (run.length && (!best || run.length > best.length)) best = { first: run[0].step, last: run[run.length - 1].step, length: run.length };
    run = [];
  };
  for (const s of steps) {
    if (hasVisibilityGap(s) && (run.length === 0 || s.actions[0]?.name === run[0].actions[0]?.name)) run.push(s);
    else { flush(); if (hasVisibilityGap(s)) run = [s]; }
  }
  flush();
  const found = best as { first: number; last: number; length: number } | null;
  return found && found.length >= 3 ? found : null;
};

export const cumulative = (steps: ReplayStep[], upTo: number) => {
  const done = steps.filter((s) => s.step <= upTo);
  return {
    requests: done.length,
    cost: done.reduce((a, s) => a + s.estimated_cost_usd, 0),
    prompt: done.reduce((a, s) => a + s.usage.prompt_tokens, 0),
    completion: done.reduce((a, s) => a + s.usage.completion_tokens, 0),
    latency: done.reduce((a, s) => a + s.latency_s, 0),
  };
};

export const describeAction = (a: ReplayAction): string => {
  const entries = Object.entries(a.params).map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : String(v)}`);
  return a.params_omitted ? `${a.name} (parameters omitted)` : `${a.name}${entries.length ? ` (${entries.join(", ")})` : ""}`;
};

export const base = (): string => (typeof document !== "undefined" ? new URL("./replays/", document.baseURI).toString() : "./replays/");

export async function loadReplays(fetcher: typeof fetch = fetch): Promise<{ manifest: Manifest; replays: Replay[] } | null> {
  const res = await fetcher(`${base()}manifest.json`).catch(() => null);
  if (!res || !res.ok) return null;
  const type = res.headers.get("content-type") ?? "";
  if (!type.includes("json")) return null; // SPA fallbacks return HTML when the file does not exist
  const manifest = (await res.json()) as Manifest;
  const replays = await Promise.all(manifest.replays.map(async (r) => (await (await fetcher(`${base()}${r.file}`)).json()) as Replay));
  return { manifest, replays };
}
