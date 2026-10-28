import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { cumulative, describeAction, hasVisibilityGap, visibilityLoop, type Replay, type ReplayStep } from "./replay";
import { runs } from "../data/task007";

// ---- DEVELOPMENT-ONLY TEST FIXTURE — NOT EXPERIMENT EVIDENCE --------------------------------------------------------------
// Synthetic steps used only to exercise the replay helpers when the locally generated export is absent (e.g. in CI).
const step = (n: number, over: Partial<ReplayStep> = {}): ReplayStep => ({
  step: n, page: "listing", path: "/", title: "t", model_visible_dom: "dom", model_visible_last_result: null,
  actions: [{ name: "find_elements", params: { selector: "a" } }],
  tool_results: [{ action: "find_elements", result_excerpt: 'Found 3 elements:\n[0] <a> "x" {href="/products/abc"}', result_truncated: false, error: null, is_done: false }],
  result_visible_to_model_next_request: 'Found 3 elements matching "a".', protocol: "recovered",
  guard: { schema: "full", budget_warning: false, final_step: false }, usage: { prompt_tokens: 100, completion_tokens: 10, reasoning_tokens: 4 },
  latency_s: 1, finish_reason: "stop", estimated_cost_usd: 0.001, ...over,
});
const FIXTURE_NOT_EVIDENCE: ReplayStep[] = [
  step(1, { actions: [{ name: "click", params: { index: 3 } }], tool_results: [{ action: "click", result_excerpt: "Clicked", result_truncated: false, error: null, is_done: false }], result_visible_to_model_next_request: "Clicked" }),
  step(2), step(3), step(4), step(5, { actions: [{ name: "click", params: { index: 1 } }], tool_results: [{ action: "click", result_excerpt: "Clicked", result_truncated: false, error: null, is_done: false }], result_visible_to_model_next_request: "Clicked" }),
];

describe("replay helpers (synthetic development fixture, not evidence)", () => {
  it("detects the tool-output visibility gap only when hrefs were returned but not shown", () => {
    expect(hasVisibilityGap(FIXTURE_NOT_EVIDENCE[1])).toBe(true);
    expect(hasVisibilityGap(FIXTURE_NOT_EVIDENCE[0])).toBe(false);
    expect(hasVisibilityGap(step(9, { result_visible_to_model_next_request: 'Found 3 {href="/products/abc"}' }))).toBe(false);
    expect(hasVisibilityGap(step(9, { result_visible_to_model_next_request: null }))).toBe(false);
  });
  it("finds a loop of >= 3 consecutive same-action gap steps and ignores shorter runs", () => {
    expect(visibilityLoop(FIXTURE_NOT_EVIDENCE)).toEqual({ first: 2, last: 4, length: 3 });
    expect(visibilityLoop(FIXTURE_NOT_EVIDENCE.slice(0, 3))).toBeNull();
  });
  it("accumulates requests, tokens, cost and latency up to a step", () => {
    const c = cumulative(FIXTURE_NOT_EVIDENCE, 3);
    expect([c.requests, c.prompt, c.completion, +c.cost.toFixed(3), c.latency]).toEqual([3, 300, 30, 0.003, 3]);
  });
  it("describes actions without free text", () => {
    expect(describeAction({ name: "click", params: { index: 5 } })).toBe("click (index=5)");
    expect(describeAction({ name: "go_back", params: {} })).toBe("go_back");
    expect(describeAction({ name: "weird", params: {}, params_omitted: true })).toBe("weird (parameters omitted)");
  });
});

// ---- Tests against the locally generated, sanitized export (skipped when it is not present, e.g. in CI) ------------------------
const dir = resolve(__dirname, "../../public/replays");
const present = existsSync(resolve(dir, "manifest.json"));
const FORBIDDEN = ["thinking", "memory", "next_goal", "evaluation_previous_goal", "description", "request_id", "content", "prose_prefix", "messages", "screenshot", "expected", "artifact_path"];
const keysOf = (o: unknown): string[] => (Array.isArray(o) ? o.flatMap(keysOf) : o && typeof o === "object" ? Object.entries(o).flatMap(([k, v]) => [k, ...keysOf(v)]) : []);

describe.skipIf(!present)("local sanitized export reconciles with the committed per-run data", () => {
  const manifest = present ? JSON.parse(readFileSync(resolve(dir, "manifest.json"), "utf8")) : null;
  const replays: Replay[] = present ? manifest.replays.map((r: { file: string }) => JSON.parse(readFileSync(resolve(dir, r.file), "utf8"))) : [];
  it("contains exactly the three approved runs", () => {
    expect(replays.map((r) => r.run.id)).toEqual(["25-s02-A1", "26-s02-B1", "27-s02-B2"]);
    expect(manifest.development_only).toBe(true);
  });
  it("matches requests, tokens, cost, visits and evaluator verdict in per-run-reconciled.json", () => {
    for (const rp of replays) {
      const run = runs.find((r) => r.id === rp.run.id)!;
      expect(rp.steps.length).toBe(run.requests);
      expect(rp.run.totals.prompt_tokens).toBe(run.prompt);
      expect(rp.run.totals.completion_tokens).toBe(run.completion);
      expect(Math.abs(rp.run.totals.estimated_cost_usd - run.cost)).toBeLessThan(1e-5);
      expect(rp.run.observed_visits).toBe(run.visits_trace.length);
      expect(rp.run.evaluator.passed).toBe(run.passed);
      expect(rp.steps.map((s) => s.protocol)).toEqual(run.categories.map((c) => (c === "raw_valid" ? "raw_valid" : "recovered")));
    }
  });
  it("contains no excluded fields or model-written text keys", () => {
    for (const rp of replays) expect(keysOf(rp).filter((k) => FORBIDDEN.includes(k))).toEqual([]);
    const blob = JSON.stringify(replays);
    expect(blob).not.toMatch(/127\.0\.0\.1|\/home\/|\/tmp\/|runs\/pilot/);
  });
  it("run 27 shows the visibility gap on steps 3–9 only (seven calls) and the final step in done-only schema", () => {
    const r27 = replays.find((r) => r.run.id === "27-s02-B2")!;
    expect(r27.steps.filter(hasVisibilityGap).map((s) => s.step)).toEqual([3, 4, 5, 6, 7, 8, 9]);
    expect(visibilityLoop(r27.steps)).toEqual({ first: 3, last: 9, length: 7 });
    expect(r27.steps[2].tool_results[0].result_excerpt).toContain('href="/products/');
    expect(r27.steps[3].model_visible_last_result).toBe('Found 11 elements matching "a".');
    const last = r27.steps[r27.steps.length - 1];
    expect([last.guard.final_step, last.guard.schema]).toEqual([true, "done_only"]);
    expect(r27.run.verification_shortfall?.detail_visit_shortfall).toBe(2);
  });
  it("successful runs have no visibility gaps", () => {
    for (const id of ["25-s02-A1", "26-s02-B1"]) expect(replays.find((r) => r.run.id === id)!.steps.some(hasVisibilityGap)).toBe(false);
  });
});
