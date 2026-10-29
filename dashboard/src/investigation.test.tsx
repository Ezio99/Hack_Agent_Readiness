import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import fixture from "./fixtures/investigation-synthetic.json";
import { compare, parseInvestigation, tally, type InvestigationExport } from "./lib/investigation";
import { InvestigationPage, InvestigationView } from "./pages/Investigation";

const base = () => structuredClone(fixture) as unknown as InvestigationExport;
const html = (d: InvestigationExport) => renderToStaticMarkup(<InvestigationView d={d} />);

describe("investigation export parsing", () => {
  it("accepts the synthetic fixture and refuses other schemas, bad JSON and private fields", () => {
    expect(parseInvestigation(JSON.stringify(fixture)).ok).toBe(true);
    expect(parseInvestigation("{nope").ok).toBe(false);
    expect(parseInvestigation(JSON.stringify({ schema: "run-v1" })).ok).toBe(false);
    const { ok, ...rest } = parseInvestigation(JSON.stringify({ ...fixture, tasks: undefined })) as any;
    expect(ok).toBe(false); expect(rest.error).toContain("tasks");
    const leaky = parseInvestigation(JSON.stringify({ ...fixture, tasks: [{ answer: "x" }] }));
    expect(leaky.ok).toBe(false);
    expect(parseInvestigation(JSON.stringify({ ...fixture, criteria: {} })).ok).toBe(false);
  });
  it("tallies void trials separately and only compares tasks usable in both arms", () => {
    const d = base();
    const t5 = d.tasks.find((t) => t.task_id === "syn-t5")!;
    expect(tally(t5.baseline)).toMatchObject({ usable: 0, void: 1 });
    const pid = Object.keys(d.tasks[0].patched)[0];
    const c = compare(d.tasks, pid);
    expect(c.tasks).toBe(5); expect(c.skipped).toBe(1); expect(c.baseline.passed).toBe(2); expect(c.patched.passed).toBe(5);
  });
});

describe("investigation view", () => {
  it("labels synthetic scripted data, separates verified findings from unverified hypotheses and shows the timeline and tasks", () => {
    const h = html(base());
    expect(h).toContain("SYNTHETIC FIXTURE");
    expect(h).toContain("SCRIPTED");
    expect(h).toContain("Verified finding");
    expect(h).toContain("Novel hypothesis — UNVERIFIED");
    expect(h).toContain("EXPERIMENTAL");
    expect(h).toContain("Hypothesis — refuted");
    expect(h).toContain("Pipeline stages"); expect(h).toContain("final report");
    expect(h).toContain("Which listed cabins have a fireplace?");
    expect(h).toContain(">void<");
    expect(h).toContain("Amenities appear only on cabin detail pages");     // finding evidence resolved to the observation text
  });
  it("never presents scripted effects as measured", () => {
    const h = html(base());
    expect(h).toContain("NOT MEASURED");
    expect(h).not.toContain("MEASURED (live)");
    expect(h).toContain("fixed before any trial ran");
    expect(h).toContain("it is not evidence about agent behaviour");
  });
  it("shows MEASURED only for live effects", () => {
    const d = base();
    d.evaluation.results[0].measured = true; d.evaluation.results[0].effect_mode = "live"; d.modes = ["live"];
    expect(html(d)).toContain("MEASURED (live)");
  });
  it("handles an incomplete investigation with no evaluation or report", () => {
    const d = base();
    d.run.complete = false; d.run.report_source = "evidence"; d.run.missing_artifacts = ["report-final"];
    d.evaluation = { state: "missing", reason: "no evaluation artifact", rule: null, results: [] };
    d.stages = d.stages.map((s, i) => (i === 4 ? { ...s, status: "awaiting_approval" as const, manifest_sha256: "ab".repeat(32) } : i > 4 ? { ...s, status: "pending" as const } : s));
    const h = html(d);
    expect(h).toContain("Incomplete investigation"); expect(h).toContain("report-final");
    expect(h).toContain("No evaluation data"); expect(h).toContain("owner approval needed");
    expect(h).not.toContain("Baseline versus patched for");
  });
  it("handles an empty export (no tasks, findings or proposals)", () => {
    const d = base();
    Object.assign(d, { tasks: [], findings: [], hypotheses: [], proposals: [], observations: [], effects: [], synthetic: false, statement: null });
    d.trials = { baseline: 0, patched: 0, void: 0, note: "" };
    d.evaluation = { state: "not_evaluated", reason: "no fix was applied", rule: null, results: [] };
    const h = html(d);
    expect(h).toContain("No frozen tasks"); expect(h).toContain("No verified findings"); expect(h).toContain("No proposals"); expect(h).toContain("Not evaluated"); expect(h.indexOf("inspect")).toBeLessThan(h.indexOf("final report"));
    expect(h).not.toContain("SYNTHETIC FIXTURE");
  });
  it("flags unresolved evidence references instead of hiding them", () => {
    const d = base();
    d.findings[0].unresolved_observation_ids = ["obs-missing"]; d.findings[0].support[0].resolved = false;
    const h = html(d);
    expect(h).toContain("Unresolved observation"); expect(h).toContain("Unresolved trial reference");
  });
  it("renders a regression honestly and never leaks local addresses or private keys", () => {
    const d = base();
    d.evaluation.results[0].verdict = "regression";
    const h = html(d);
    expect(h).toContain("regression");
    expect(h).not.toMatch(/127\.0\.0\.1:\d+|localhost:\d+|\/home\/|"truth"|api_key/i);
  });
  it("starts empty with a loader and the export instructions (no data bundled eagerly)", () => {
    const h = renderToStaticMarkup(<InvestigationPage />);
    expect(h).toContain("No report loaded"); expect(h).toContain("readiness investigate export"); expect(h).toContain("Load synthetic example"); expect(h).toContain("nothing is uploaded");
  });
});
