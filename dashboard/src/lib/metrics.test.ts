import { describe, expect, it } from "vitest";
import { runs } from "../data/task007";
import {
  allRuns, attribution, byArm, byScope, diffBA, failedRuns, meanAttribution, protocol, scopes, signed, signedUsd, stats, sum, toolLoopCalls, usd,
} from "./metrics";

const A = stats(byArm(allRuns, "A")), B = stats(byArm(allRuns, "B"));

describe("dataset integrity", () => {
  it("has 30 unique runs, 15 per arm, 6 per scope, 3 per cell", () => {
    expect(runs).toHaveLength(30);
    expect(new Set(runs.map((r) => r.id)).size).toBe(30);
    expect(byArm(runs, "A")).toHaveLength(15);
    for (const s of scopes) {
      expect(s.runs).toHaveLength(6);
      expect(byArm(s.runs, "A")).toHaveLength(3);
      expect(byArm(s.runs, "B")).toHaveLength(3);
    }
  });
  it("detail-page visit counts agree across the three independent sources for every run", () => {
    expect(runs.every((r) => r.sources_agree)).toBe(true);
    expect(runs.every((r) => r.last_action.length === 1 && r.last_action[0] === "done")).toBe(true);
  });
  it("ranks are 1,2,3,3,3 for Kitchen, Bags, Home, Outdoors, Fern", () => {
    expect(scopes.map((s) => [s.scope, s.rank])).toEqual([["Kitchen", 1], ["Bags", 2], ["Home", 3], ["Outdoors", 3], ["Fern", 3]]);
  });
});

describe("headline numbers reconcile to Report 007", () => {
  it("success: 29/30 independent evaluator PASS (A 15/15, B 14/15)", () => {
    expect([stats(allRuns).passes, A.passes, B.passes]).toEqual([29, 15, 14]);
  });
  it("means per run: requests, cost, time", () => {
    expect(A.requests.toFixed(2)).toBe("4.67");
    expect(B.requests.toFixed(2)).toBe("7.47");
    expect(A.cost.toFixed(4)).toBe("0.0621");
    expect(B.cost.toFixed(4)).toBe("0.0974");
    expect(A.elapsed.toFixed(1)).toBe("22.9");
    expect(B.elapsed.toFixed(1)).toBe("27.2");
  });
  it("total calculated cost is about US$2.3918 and per-arm totals add up", () => {
    expect(stats(allRuns).totalCost.toFixed(4)).toBe("2.3918");
    expect((A.totalCost + B.totalCost).toFixed(4)).toBe("2.3918");
  });
  it("protocol: 50 raw-valid + 132 recovered + 0 rejected = 182; all 30 first steps recovered", () => {
    const p = protocol(allRuns);
    expect([p.rawValid, p.recovered, p.rejected, p.total, p.firstStepsRecovered]).toEqual([50, 132, 0, 182, 30]);
  });
  it("per-scope B − A request differences match the report", () => {
    const d = (s: string) => diffBA(byScope(allRuns, s as never)).requests;
    expect(["Kitchen", "Bags", "Home", "Outdoors", "Fern"].map((s) => +d(s).toFixed(2))).toEqual([-2, 3, 4.33, 6, 2.67]);
  });
  it("per-scope B − A cost differences match the report (US$)", () => {
    const d = (s: string) => diffBA(byScope(allRuns, s as never)).cost;
    expect(["Kitchen", "Bags", "Home", "Outdoors", "Fern"].map((s) => +d(s).toFixed(3))).toEqual([-0.028, 0.04, 0.055, 0.078, 0.031]);
  });
});

describe("navigation overhead is reported for successful runs only", () => {
  it("never reports negative overhead and none for failed runs", () => {
    for (const r of allRuns) {
      if (r.passed) { expect(r.overhead).not.toBeNull(); expect(r.overhead as number).toBeGreaterThanOrEqual(0); expect(r.shortfall).toBeNull(); }
      else { expect(r.overhead).toBeNull(); expect(r.shortfall).not.toBeNull(); }
    }
  });
  it("10 runs have positive overhead (A 8, B 2), all of them re-opened pages; 14 extra openings", () => {
    const pos = allRuns.filter((r) => (r.overhead ?? 0) > 0);
    expect(pos.map((r) => r.id).sort()).toEqual(["04-s00-A2", "05-s00-A3", "08-s04-A1", "12-s04-A3", "19-s03-B1", "23-s03-B3", "24-s03-A3", "25-s02-A1", "28-s02-A2", "29-s02-A3"]);
    expect(pos.every((r) => r.revisits === r.overhead)).toBe(true);
    expect(sum(allRuns.map((r) => r.revisits))).toBe(14);
    expect([byArm(pos, "A").length, byArm(pos, "B").length]).toEqual([8, 2]);
    expect(allRuns.filter((r) => r.passed && r.overhead === 0).map((r) => r.arm).sort().join("")).toBe("A".repeat(7) + "B".repeat(12));
  });
  it("run 27 is the only failure: required 3, observed 1, shortfall 2, 1 of 2 higher-priced candidates checked, answer wrong", () => {
    const f = failedRuns();
    expect(f.map((r) => r.id)).toEqual(["27-s02-B2"]);
    const r = f[0];
    expect([r.required_visits, r.visits_trace.length, r.shortfall?.detail_visit_shortfall]).toEqual([3, 1, 2]);
    expect([r.shortfall?.higher_priced_checked, r.shortfall?.higher_priced_candidates]).toEqual([1, 2]);
    expect(r.answer.product_id).not.toBe(r.expected);
    expect(r.answer.available).toBe(false);
  });
});

describe("request attribution", () => {
  it("three tool-loop runs with 18 repeated calls in total (6, 5, 7)", () => {
    const loops = allRuns.filter((r) => toolLoopCalls(r) > 0);
    expect(loops.map((r) => [r.id, toolLoopCalls(r)])).toEqual([["12-s04-A3", 6], ["15-s01-B2", 5], ["27-s02-B2", 7]]);
    expect(sum(loops.map(toolLoopCalls))).toBe(18);
  });
  it("the tool output contained hrefs but the model-visible history did not (run 27)", () => {
    const r = failedRuns()[0];
    expect(r.find_elements.every((c) => c.tool_output_contains_product_hrefs && !c.next_model_request_shows_hrefs && c.next_model_request_shows_count_line)).toBe(true);
  });
  it("per-arm means: A 2.00/0.40/2.27 = 4.67; B 4.80/0.80/1.87 = 7.47; B − A required +2.80", () => {
    const a = meanAttribution(byArm(allRuns, "A")), b = meanAttribution(byArm(allRuns, "B"));
    expect([a.required, a.tool, a.residual, a.total].map((x) => +x.toFixed(2))).toEqual([2, 0.4, 2.27, 4.67]);
    expect([b.required, b.tool, b.residual, b.total].map((x) => +x.toFixed(2))).toEqual([4.8, 0.8, 1.87, 7.47]);
    expect(+diffBA(allRuns).required.toFixed(2)).toBe(2.8);
  });
  it("components always sum to the run's requests; agent-induced is negative only for the truncated run 27", () => {
    for (const r of allRuns) { const t = attribution(r); expect(t.required + t.tool + t.residual).toBe(r.requests); }
    expect(allRuns.filter((r) => attribution(r).residual < 0).map((r) => r.id)).toEqual(["27-s02-B2"]);
  });
  it("Kitchen's B − A request gap is fully explained by the single arm-A tool loop", () => {
    const d = diffBA(byScope(allRuns, "Kitchen"));
    expect([d.requests, d.required, d.tool, +d.residual.toFixed(6)]).toEqual([-2, 0, -2, 0]);
  });
});

describe("formatting", () => {
  it("uses explicit units and true minus signs", () => {
    expect(usd(0.0621)).toBe("US$0.0621");
    expect(signed(-2)).toBe("−2.00");
    expect(signed(4.333)).toBe("+4.33");
    expect(signedUsd(-0.0282)).toBe("−US$0.028");
  });
});
