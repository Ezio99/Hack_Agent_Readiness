// Single source of truth for the dashboard's numbers: the committed, reconciled Task 007 per-run data.
// Nothing numeric is hand-maintained here. The provenance constants below are copied from Report 007 / the frozen schedule and are
// checked against the report text in src/lib/report.test.ts.
import raw from "../../../collaboration/reports/007-pilot-data/per-run-reconciled.json";

export type Arm = "A" | "B";
export type Scope = "Kitchen" | "Bags" | "Home" | "Outdoors" | "Fern";

export interface Shortfall {
  required_visits: number;
  actual_visits: number;
  detail_visit_shortfall: number;
  higher_priced_candidates: number;
  higher_priced_checked: number | null;
  higher_priced_unchecked: number | null;
}

export interface FindElementsCall {
  step: number;
  tool_output_contains_product_hrefs: boolean;
  next_model_request_shows_hrefs: boolean;
  next_model_request_shows_count_line: boolean;
}

export interface Run {
  id: string;
  run_id: string;
  seed: number;
  scope: Scope;
  arm: Arm;
  rep: number;
  passed: boolean;
  status: string;
  stop_reason: string;
  required_visits: number;
  rank: number;
  visits_trace: string[];
  sources_agree: boolean;
  last_action: string[];
  answer: { product_id: string; price_cents: number; available: boolean };
  expected: string;
  requests: number;
  http200: number;
  categories: ("raw_valid" | "recovered" | "rejected" | "other")[];
  prompt: number;
  completion: number;
  reasoning: number;
  cost: number;
  elapsed: number;
  model_s: number;
  narrowed: boolean;
  find_elements: FindElementsCall[];
  overhead: number | null;
  shortfall: Shortfall | null;
  revisits: number;
}

export const runs: Run[] = raw as unknown as Run[];

export const provenance = {
  executionCommit: "969d7d4",
  scheduleSha256: "a2cf749c809e9a905d445d06b87fdb3411fda30978f01c291c74824a656f5eaa",
  model: "muse-spark-1.3",
  profile: "natural-shopping-v3-compat1",
  pricePerMInputUsd: 1.25,
  pricePerMOutputUsd: 4.25,
  limits: "12 steps · 12 model requests · 240 s per run",
  reportPath: "collaboration/reports/007-availability-placement-pilot.md",
  dataPath: "collaboration/reports/007-pilot-data/per-run-reconciled.json",
} as const;

export const scopeOrder: Scope[] = ["Kitchen", "Bags", "Home", "Outdoors", "Fern"];
