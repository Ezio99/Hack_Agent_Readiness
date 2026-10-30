import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import fixture from "./fixtures/investigation-synthetic.json";
import expbFixture from "./fixtures/investigation-synthetic-expb.json";
import publicFixture from "./fixtures/investigation-synthetic-expb-public.json";
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
    expect(c.tasks).toBe(5); expect(c.skipped).toBe(1); expect(c.baseline.passed).toBe(0); expect(c.patched.passed).toBe(5);
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
  it("synthetic before/after numbers are internally consistent and labelled illustrative", () => {
    const d = base();
    const r = d.evaluation.results[0], c = compare(d.tasks, r.proposal_id);
    expect(r.pairs).toBe(c.tasks);
    expect(r.pass_delta).toBeCloseTo(c.patched.passed / c.patched.usable - c.baseline.passed / c.baseline.usable, 4);
    expect(r.request_change).toBeCloseTo((c.patched.requests! - c.baseline.requests!) / c.baseline.requests!, 3);
    expect(r.by_partition!.investigation.pairs + r.by_partition!.holdout.pairs).toBe(r.pairs);
    expect(r.excluded.map((e) => e.task_id)).toEqual(["syn-t5"]);
    const h = html(d);
    expect(h).toContain("ILLUSTRATIVE — synthetic numbers"); expect(h).toContain("ILLUSTRATIVE (synthetic data)"); expect(h).toContain("SYNTHETIC FIXTURE");
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

describe("terminal investigation status", () => {
  it("never presents an aborted investigation as a negative finding", () => {
    const d = base();
    d.run.outcome = "incomplete_due_to_infrastructure_error"; d.run.investigation_status = "incomplete_due_to_infrastructure_error"; d.findings = [];
    const h = html(d);
    expect(h).toContain("The investigation did not complete"); expect(h).toContain("incomplete_due_to_infrastructure_error"); expect(h).toContain("not</strong> a finding that no problem exists");
    expect(h).toContain("incomplete due to infrastructure error");
  });
  it("shows no incomplete warning for a completed investigation", () => {
    expect(html(base())).not.toContain("did not complete");
  });
});

describe("EXP-B journey: three arms, two verdicts", () => {
  const expb = () => structuredClone(expbFixture) as unknown as InvestigationExport;
  it("parses the EXP-B synthetic fixture and lays out the four-part journey", () => {
    expect(parseInvestigation(JSON.stringify(expbFixture)).ok).toBe(true);
    const h = html(expb());
    for (const label of ["1 · The website and how it was tested", "2 · What the agent did on each task", "3 · Findings and recommendations", "4 · Before and after"]) expect(h).toContain(label);
    for (const id of ["inv-website", "inv-activity", "inv-findings", "inv-results"]) expect(h).toContain(`href="#${id}"`);
    expect(h).toContain("SYNTHETIC FIXTURE");
  });
  it("shows historical baseline, unmodified repeat and patched side by side for each task role", () => {
    const h = html(expb());
    expect(h).toContain("Historical baseline"); expect(h).toContain("Unmodified repeat (control)"); expect(h).toContain("Unmodified repeat"); expect(h).toContain("Patched");
    for (const role of ["Affected", "Same-shape control", "Detail-page control"]) expect(h).toContain(role);
    expect(h).toContain("13 req · pass"); expect(h).toContain("12 req · pass"); expect(h).toContain("4 req · pass");
  });
  it("keeps the frozen verdict and the exploratory verdict distinct and unmerged", () => {
    const d = expb();
    const h = html(d);
    expect(d.evaluation.results[0].verdict).toBe("inconclusive");
    expect(h).toContain("Frozen pre-registered verdict"); expect(h).toContain("paired-signflip-v1"); expect(h).toContain("Reported unchanged");
    expect(h).toContain("Exploratory verdict"); expect(h).toContain("exploratory-listing-v1"); expect(h).toContain("Consistent with the hypothesis"); expect(h).toContain("not a replacement");
    expect(h.indexOf("Frozen pre-registered verdict")).toBeLessThan(h.indexOf("Exploratory verdict"));
  });
  it("labels the change as owner-selected and exploratory, never a verified finding", () => {
    const h = html(expb());
    expect(h).toContain("Owner-selected experiment"); expect(h).toContain("chosen by the site owner"); expect(h).toContain("Owner-authored hypothesis — UNVERIFIED"); expect(h).toContain("EXPERIMENTAL — OWNER-SELECTED");
    expect(h).toContain("No verified findings"); expect(h).not.toContain("Verified finding</span>");
    expect(h).toContain("not</strong> an investigator-verified finding"); expect(h).toContain("not blind to the owner");
  });
  it("never claims support when the comparisons conflict, and never as MEASURED (live) for scripted data", () => {
    const d = expb();
    d.evaluation.exploratory!.verdict = "inconclusive_conflicting_comparisons"; d.evaluation.exploratory!.reasons = ["no support is claimed"];
    const h = html(d);
    expect(h).toContain("the comparisons conflict, no support claimed"); expect(h).not.toContain("Consistent with the hypothesis");
    expect(h).toContain("NOT MEASURED"); expect(h).not.toContain("MEASURED (live)");
  });
  it("shows an uninterpretable run honestly, with missing trials listed", () => {
    const d = expb();
    const x = d.evaluation.exploratory!;
    x.verdict = "uninterpretable"; x.missing_or_void = ["placebo:syn-t2"]; x.tasks.placebo["syn-t2"] = null; x.controls_within_tolerance = false;
    const h = html(d);
    expect(h).toContain("Uninterpretable"); expect(h).toContain("placebo:syn-t2"); expect(h).toContain("no — the result is uninterpretable");
  });
  it("states the rules hash and degrades when the stored hash does not match this build", () => {
    const d = expb();
    expect(html(d)).toContain("matches the pre-registered rules");
    d.evaluation.exploratory!.rules = null; d.evaluation.exploratory!.rules_match_code = false;
    const h = html(d);
    expect(h).toContain("does NOT match the code"); expect(h).toContain("rules text unavailable");
  });
  it("older exports without placebo or exploratory fields still render", () => {
    const d = base();
    for (const t of d.tasks) delete (t as any).placebo;
    delete (d.evaluation as any).exploratory;
    const h = html(d);
    expect(h).not.toContain("Unmodified repeat"); expect(h).toContain("Baseline versus patched");
  });
  it("the page offers both labelled synthetic examples", () => {
    expect(renderToStaticMarkup(<InvestigationPage />)).toContain("Load EXP-B synthetic example");
  });
});

describe("EXP-B headline, control flip, holdout flag and spend", () => {
  const expb = () => structuredClone(expbFixture) as unknown as InvestigationExport;
  it("shows the affected-task request reductions (unmodified repeat → patched)", () => {
    const h = html(expb());
    expect(h).toContain("12 → 4"); expect(h).toContain("13 → 4"); expect(h).toContain("unmodified repeat → patched");
  });
  it("calls out a control whose pass status changed without changing the verdict", () => {
    const d = expb();
    d.evaluation.exploratory!.tasks.patched["syn-t3"] = { requests: 11, page_views: 10, pass: true };
    const h = html(d);
    expect(h).toContain("A control task changed outcome"); expect(h).toContain("same-shape control"); expect(h).toContain("tolerance"); expect(h).toContain("does not change the verdict");
    expect(html(expb())).not.toContain("A control task changed outcome");
  });
  it("explains the holdout flag from the partitions' pass changes, without claiming the holdout got worse", () => {
    const d = expb();
    const r = d.evaluation.results[0];
    r.holdout_consistent = false; r.by_partition = { investigation: { pairs: 4, pass_delta: 0 }, holdout: { pairs: 2, pass_delta: 1 } };
    const h = html(d);
    expect(h).toContain("investigation 0.00 (4 pairs)"); expect(h).toContain("holdout +1.00 (2 pairs)"); expect(h).toContain("different signs"); expect(h).toContain("does not by itself mean the holdout got worse");
  });
  it("shows calculated spend by arm labelled as not a bill, and nothing when the ledger is missing", () => {
    const d = expb();
    d.spend = { state: "ok", committed_usd: 1.5344, ceiling_usd: 2.05, remaining_usd: 0.5156, open_reservations: 0, by_arm_usd: { baseline: 0.6, patched: 0.4, placebo: 0.46, other: 0.07 } };
    const h = html(d);
    expect(h).toContain("not a bill"); expect(h).toContain("US$1.5344"); expect(h).toContain("placebo US$0.4600"); expect(h).toContain("task generation + investigator");
    d.spend = { state: "missing" };
    expect(html(d)).not.toContain("not a bill");
  });
});

describe("public-demo export", () => {
  const pub = () => structuredClone(publicFixture) as unknown as InvestigationExport;
  it("parses and renders with both verdicts, three arms, controls and owner-selected provenance", () => {
    expect(parseInvestigation(JSON.stringify(publicFixture)).ok).toBe(true);
    const h = html(pub());
    expect(h).toContain("Public demo view"); expect(h).toContain("paired-signflip-v1"); expect(h).toContain("exploratory-listing-v1"); expect(h).toContain("Consistent with the hypothesis"); expect(h).toContain("Unmodified repeat (control)");
    expect(h).toContain("12 → 4"); expect(h).toContain("EXPERIMENTAL — OWNER-SELECTED"); expect(h).toContain("Owner-selected experiment"); expect(h).toContain("No verified findings"); expect(h).toContain("SYNTHETIC FIXTURE");
  });
  it("shows no internal identifiers, hashes or attribution narratives", () => {
    const h = html(pub());
    expect(h).not.toMatch(/gen-[0-9a-f]{6,}|prp-[0-9a-f]{6,}|syn-t\d|trial-data|\/home\/|synthetic fixture attribution/);
    expect(h).toContain("task-1"); expect(h).toContain("change-1");
  });
  it("does not need the private-only fields (no attribution, stage hashes or per-trial spend)", () => {
    const d = pub();
    expect(JSON.stringify(d)).not.toMatch(/"(why|attribution|by_trial_usd)"/);
    expect(d.stages.every((s) => s.manifest_sha256 === null)).toBe(true);
    expect(() => html(d)).not.toThrow();
  });
});
