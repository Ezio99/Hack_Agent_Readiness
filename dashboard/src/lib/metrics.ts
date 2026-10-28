import { runs as allRuns, scopeOrder, type Arm, type Run, type Scope } from "../data/task007";

export const mean = (xs: number[]): number => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : NaN);
export const sd = (xs: number[]): number => {
  if (xs.length < 2) return 0;
  const m = mean(xs);
  return Math.sqrt(xs.reduce((a, x) => a + (x - m) ** 2, 0) / (xs.length - 1));
};
export const sum = (xs: number[]): number => xs.reduce((a, b) => a + b, 0);

export const usd = (x: number, dp = 4): string => `US$${x.toFixed(dp)}`;
export const signed = (x: number, dp = 2): string => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(dp)}`;
export const signedUsd = (x: number, dp = 3): string => `${x >= 0 ? "+" : "−"}US$${Math.abs(x).toFixed(dp)}`;
export const secs = (x: number): string => `${x.toFixed(1)} s`;

export const byArm = (rs: Run[], arm: Arm): Run[] => rs.filter((r) => r.arm === arm);
export const byScope = (rs: Run[], scope: Scope): Run[] => rs.filter((r) => r.scope === scope);

/** A "tool-interface loop" is >= 3 identical consecutive find_elements calls (the three loop runs in Task 007). */
export const toolLoopCalls = (r: Run): number => (r.find_elements.length >= 3 ? r.find_elements.length : 0);

/** Request accounting: assumed website-required path, agent–tool interface loop calls, and the residual (see Attribution). */
/** Accounting assumption: `residual` is NOT a per-request classification. It is total requests − the assumed website-required path
 *  (A: 2; B: 2×rank) − the repeated find_elements calls in loop runs. It therefore bundles every other agent behaviour (re-opening
 *  pages, filtering, backtracking, "be thorough" detours) and can be negative for a run that never completed the required path (run 27). */
export interface Attribution { required: number; tool: number; residual: number; total: number }
export const attribution = (r: Run): Attribution => {
  const required = r.arm === "A" ? 2 : 2 * r.rank;
  const tool = toolLoopCalls(r);
  return { required, tool, residual: r.requests - required - tool, total: r.requests };
};
export const meanAttribution = (rs: Run[]): Attribution => ({
  required: mean(rs.map((r) => attribution(r).required)),
  tool: mean(rs.map((r) => attribution(r).tool)),
  residual: mean(rs.map((r) => attribution(r).residual)),
  total: mean(rs.map((r) => r.requests)),
});

export interface ArmStats {
  n: number; passes: number; requests: number; requestsSd: number; requestsMin: number; requestsMax: number;
  cost: number; costSd: number; costMin: number; costMax: number; totalCost: number; elapsed: number; modelSeconds: number;
  prompt: number; completion: number; visits: number; required: number;
  overheadMean: number | null; overheadRuns: number; successfulRuns: number; revisitRuns: number; extraOpenings: number; loopRuns: number;
  shortfallRuns: number;
}
export const stats = (rs: Run[]): ArmStats => {
  const ok = rs.filter((r) => r.passed);
  return {
    n: rs.length, passes: ok.length,
    requests: mean(rs.map((r) => r.requests)), requestsSd: sd(rs.map((r) => r.requests)),
    requestsMin: Math.min(...rs.map((r) => r.requests)), requestsMax: Math.max(...rs.map((r) => r.requests)),
    cost: mean(rs.map((r) => r.cost)), costSd: sd(rs.map((r) => r.cost)),
    costMin: Math.min(...rs.map((r) => r.cost)), costMax: Math.max(...rs.map((r) => r.cost)),
    totalCost: sum(rs.map((r) => r.cost)), elapsed: mean(rs.map((r) => r.elapsed)), modelSeconds: mean(rs.map((r) => r.model_s)),
    prompt: mean(rs.map((r) => r.prompt)), completion: mean(rs.map((r) => r.completion)),
    visits: mean(rs.map((r) => r.visits_trace.length)), required: mean(rs.map((r) => r.required_visits)),
    // overhead (actual − required) is defined for SUCCESSFUL runs only; failed runs carry a verification shortfall instead
    overheadMean: ok.length ? mean(ok.map((r) => r.overhead as number)) : null,
    overheadRuns: ok.filter((r) => (r.overhead ?? 0) > 0).length, successfulRuns: ok.length,
    revisitRuns: rs.filter((r) => r.revisits > 0).length, extraOpenings: sum(rs.map((r) => r.revisits)),
    loopRuns: rs.filter((r) => toolLoopCalls(r) > 0).length, shortfallRuns: rs.filter((r) => r.shortfall !== null).length,
  };
};

export interface Protocol { total: number; rawValid: number; recovered: number; rejected: number; firstSteps: number; firstStepsRecovered: number }
export const protocol = (rs: Run[]): Protocol => {
  const all = rs.flatMap((r) => r.categories);
  return {
    total: all.length, rawValid: all.filter((c) => c === "raw_valid").length, recovered: all.filter((c) => c === "recovered").length,
    rejected: all.filter((c) => c === "rejected").length, firstSteps: rs.length,
    firstStepsRecovered: rs.filter((r) => r.categories[0] === "recovered").length,
  };
};

/** Short, evidence-derived flags for a run row. */
export const runFlags = (r: Run): string[] => {
  const flags: string[] = [];
  if (!r.passed) flags.push("evaluator FAIL");
  if (r.revisits > 0) flags.push(`re-opened answer page ×${r.revisits}`);
  if (toolLoopCalls(r) > 0) flags.push(`agent–tool loop (${toolLoopCalls(r)} find_elements calls)`);
  if (r.narrowed) flags.push("reached final step (12/12)");
  return flags;
};

export const scopeInfo = (scope: Scope) => {
  const rs = byScope(allRuns, scope);
  return { scope, rank: rs[0].rank, runs: rs, answerId: rs[0].expected };
};
export const scopes = scopeOrder.map(scopeInfo);

/** B − A differences for a set of runs (means of unrounded per-run values). */
export const diffBA = (rs: Run[]) => {
  const a = stats(byArm(rs, "A")), b = stats(byArm(rs, "B"));
  const attrA = meanAttribution(byArm(rs, "A")), attrB = meanAttribution(byArm(rs, "B"));
  return {
    requests: b.requests - a.requests, cost: b.cost - a.cost, elapsed: b.elapsed - a.elapsed,
    required: attrB.required - attrA.required, tool: attrB.tool - attrA.tool, residual: attrB.residual - attrA.residual,
  };
};

export const failedRuns = (): Run[] => allRuns.filter((r) => !r.passed);
export { allRuns };
