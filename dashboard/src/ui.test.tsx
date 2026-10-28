import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Overview } from "./pages/Overview";
import { Scopes } from "./pages/Scopes";
import { Evidence } from "./pages/Evidence";
import { RunTable } from "./components/RunTable";
import { allRuns, byScope } from "./lib/metrics";

describe("rendered pages", () => {
  it("overview states the residual accounting assumption explicitly", () => {
    const html = renderToStaticMarkup(<Overview go={() => undefined} />);
    expect(html).toContain("How this accounting works");
    expect(html).toContain("not classified one by one");
    expect(html).toContain("unclassified remainder");
    expect(html).toContain("required path was <em>not completed</em>");
  });
  it("overview shows the recorded-data banner, estimated-cost wording and key numbers", () => {
    const html = renderToStaticMarkup(<Overview go={() => undefined} />);
    expect(html).toContain("Recorded experiment data");
    expect(html).toContain("calculated estimates");
    expect(html).toContain("29 / 30");
    expect(html).toContain("4.67");
    expect(html).toContain("US$0.0974");
    expect(html).toContain("Muse Spark");
    expect(html).toContain("50 / 182");
    expect(html).toContain("132 / 182");
    expect(html).not.toMatch(/live inference result|readiness score of/i);
  });
  it("run 27 is shown as an independent evaluator FAIL with a verification shortfall, never as negative overhead or efficiency", () => {
    const html = renderToStaticMarkup(<RunTable runs={byScope(allRuns, "Fern")} caption="Fern" />);
    const row = html.split("<tr").find((r) => r.includes("27-s02-B2"))!;
    expect(row).toContain("FAIL");
    expect(row).toContain("verification shortfall 2");
    expect(row).toContain("not an efficiency gain");
    expect(row).not.toMatch(/overhead\s*[-−]/i);
    expect(row).toContain("1 / 3");
    expect(html).not.toMatch(/overhead −/);
  });
  it("scope page for Fern includes the FAIL callout and the three-source split", () => {
    const html = renderToStaticMarkup(<Scopes initial="Fern" />);
    expect(html).toContain("Independent evaluator FAIL: 27-s02-B2");
    expect(html).toContain("verification shortfall 2");
    expect(html).toContain("Assumed website-required path");
    expect(html).toContain("Residual agent overhead");
    expect(html).toContain("not an efficiency");
    expect(html).toContain("includes failed run");
    expect(html).toContain("Detail pages observed (successful runs only)");
    expect(html).toContain("incomplete verification, not better efficiency");
    expect(html).toContain("Agent–tool interface loop");
  });
  it("Kitchen explains that the control was not a clean null", () => {
    const html = renderToStaticMarkup(<Scopes initial="Kitchen" />);
    expect(html).toContain("did not behave like a clean null");
    expect(html).toContain("12-s04-A3");
  });
  it("evidence page states the run 27 mechanism and attributes it to the agent–tool interface, with replay planned (not simulated)", () => {
    const html = renderToStaticMarkup(<Evidence />);
    expect(html).toContain("incorrect, insufficiently verified outcome");
    expect(html).toContain("Agent–tool interface");
    expect(html).toContain("Found 11 elements matching");
    expect(html).toContain("Recorded experiment replay");
    expect(html).toContain("not published");
    expect(html).toContain("residual (");
  });
});

import { Missing, ReplayViewer } from "./pages/Replay";
import type { Replay, ReplayStep } from "./lib/replay";

// DEVELOPMENT-ONLY SYNTHETIC FIXTURE — NOT EXPERIMENT EVIDENCE (exercises rendering when the local export is absent)
const mk = (n: number, gap: boolean): ReplayStep => ({
  step: n, page: "filtered listing", path: "/?brand=Fern", model_visible_dom: "DOM TEXT", model_visible_last_result: gap ? 'Found 11 elements matching "a".' : null,
  actions: [{ name: gap ? "find_elements" : "done", params: {} }],
  tool_results: [{ action: "find_elements", result_excerpt: gap ? 'Found 11:\n[3] <a> "x" {href="/products/abc"}' : "ok", result_truncated: false, error: null, is_done: !gap }],
  result_visible_to_model_next_request: gap ? 'Found 11 elements matching "a".' : null, protocol: "recovered",
  guard: { schema: "full", budget_warning: false, final_step: false }, usage: { prompt_tokens: 9000, completion_tokens: 300 }, latency_s: 2, estimated_cost_usd: 0.013,
});
const FIXTURE: Replay = {
  schema: "task009-replay-v2", label: "Recorded experiment replay — not live inference", notes: { cost: "", excluded: "" },
  run: { id: "FIXTURE-NOT-EVIDENCE", scope: "Fern", arm: "B", rank: 3, task: "task text", evaluator: { passed: false, reasons: ["r"] },
    answer_submitted: { product_id: "X", price_cents: 100, available: false }, required_visits: 3, observed_visits: 1, overhead: null,
    verification_shortfall: { required_visits: 3, actual_visits: 1, detail_visit_shortfall: 2, higher_priced_candidates: 2, higher_priced_checked: 1, higher_priced_unchecked: 1 },
    attribution: { required_path_requests: 6, tool_loop_requests: 3, residual_requests: null, total_requests: 5, required_path_completed: false, residual_note: "not meaningful" },
    totals: { requests: 5, prompt_tokens: 45000, completion_tokens: 1500, estimated_cost_usd: 0.065, elapsed_s: 10 } },
  steps: [mk(1, false), mk(2, true), mk(3, true), mk(4, true), mk(5, false)],
};

describe("recorded replay UI (rendered with a synthetic development fixture)", () => {
  it("is labelled as recorded, not live, with a FAIL verdict and a verification shortfall", () => {
    const html = renderToStaticMarkup(<ReplayViewer replays={[FIXTURE]} />);
    expect(html).toContain("Recorded run");
    expect(html).toContain("verification shortfall 2");
    expect(html).toContain("incomplete verification, not an efficient short path");
    expect(html).toContain("FAIL");
    expect(html).toContain("not a per-request classification");
    expect(html).toContain("not reported — not meaningful: the required path was not completed");
    expect(html).not.toContain("residual -1");
    expect(html).not.toContain("residual overhead -");
    expect(html).toContain("agent–tool interface");
    expect(html).toContain("Model reasoning, plans and goal text are intentionally not part of this export");
    expect(html).not.toMatch(/\bthinking\b|next goal/i);
  });
  it("shows what the model saw versus what the tool returned, and attributes the gap to the agent–tool interface", () => {
    const html = renderToStaticMarkup(<ReplayViewer replays={[{ ...FIXTURE, steps: FIXTURE.steps.slice(1) }]} />);
    expect(html).toContain("What the model saw");
    expect(html).toContain("What the tool returned");
    expect(html).toContain("Agent–tool interface gap at this step");
    expect(html).toContain("problem, not a storefront (website) problem");
    expect(html).toContain("Why run FIXTURE-NOT-EVIDENCE failed");
  });
  it("the missing-data state says nothing is faked and gives the local generation command", () => {
    const html = renderToStaticMarkup(<Missing />);
    expect(html).toContain("not included in this build");
    expect(html).toContain("Nothing is faked");
    expect(html).toContain("export_replay.py");
  });
});
