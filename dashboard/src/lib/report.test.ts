// Reconciles the dashboard's computed numbers with the prose of Report 007 (so the UI cannot silently diverge from the report).
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { allRuns, byArm, meanAttribution, protocol, stats, sd } from "./metrics";
import { provenance } from "../data/task007";

const report = readFileSync(resolve(__dirname, "../../../", provenance.reportPath), "utf8");
const A = stats(byArm(allRuns, "A")), B = stats(byArm(allRuns, "B"));

describe("Report 007 states what the dashboard computes", () => {
  it("per-arm requests, cost, time, SD", () => {
    expect(report).toContain(`${A.requests.toFixed(2)} (SD ${A.requestsSd.toFixed(2)})`);
    expect(report).toContain(`${B.requests.toFixed(2)} (SD ${B.requestsSd.toFixed(2)})`);
    expect(report).toContain(`US$${A.cost.toFixed(4)} (SD ${A.costSd.toFixed(4)})`);
    expect(report).toContain(`US$${B.cost.toFixed(4)} (SD ${B.costSd.toFixed(4)})`);
    expect(report).toContain(`| Run time (s) | ${A.elapsed.toFixed(1)} | ${B.elapsed.toFixed(1)} |`);
    expect(sd([1, 2, 3])).toBe(1);
  });
  it("pilot total and protocol reconciliation", () => {
    expect(report).toContain(`**US$${stats(allRuns).totalCost.toFixed(4)}**`);
    const p = protocol(allRuns);
    expect(report).toContain(`| Raw-valid (strict JSON, no recovery needed) | **${p.rawValid}** |`);
    expect(report).toContain(`**${p.recovered}**`);
  });
  it("attribution table", () => {
    const a = meanAttribution(byArm(allRuns, "A")), b = meanAttribution(byArm(allRuns, "B"));
    const row = (name: string, x: ReturnType<typeof meanAttribution>) => `| ${name} (n = 15) | ${x.required.toFixed(2)} | ${x.tool.toFixed(2)} | ${x.residual.toFixed(2)} | ${x.total.toFixed(2)} |`;
    expect(report).toContain(row("Arm A", a));
    expect(report).toContain(row("Arm B", b));
  });
  it("run 27 and the overhead run IDs", () => {
    expect(report).toContain("required 3, actual 1, shortfall 2");
    for (const r of allRuns.filter((x) => (x.overhead ?? 0) > 0)) expect(report).toContain(r.id);
    expect(report).toContain(provenance.executionCommit);
  });
});
