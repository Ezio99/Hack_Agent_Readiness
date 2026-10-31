import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import fixture from "./fixtures/investigation-synthetic.json";
import { parseInvestigation, type GoalCoverage, type InvestigationExport } from "./lib/investigation";
import { InvestigationView } from "./pages/Investigation";

const live = (): InvestigationExport => {
  const d = structuredClone(fixture) as unknown as InvestigationExport;
  delete (d.evaluation as any).exploratory;
  d.run.mode = "live"; d.modes = ["live"]; d.tasks = d.tasks.slice(0, 2);
  d.tasks.forEach((t) => { t.baseline = [{ trial_id: t.task_id + "-r1", repeat: 1, run_status: "completed", void: false, passed: true, evidence_backed: true, model_requests: 3, page_views: 3, mode: "live" }]; t.patched = {}; });
  d.proposals = []; d.findings = []; d.hypotheses = []; d.effects = []; d.evaluation = { state: "not_evaluated", reason: "no fix was applied", rule: null, results: [] };
  delete d.storefront;
  d.goal = "Can a shopper compare the hire price and availability of the two cheapest cutting tools?";
  return d;
};
const cov = (over: Partial<GoalCoverage> = {}): GoalCoverage => ({
  status: "partial", selected_tasks: 2, gate_accepted_tasks: 7, relevant_tasks: 2, asked_aspects: ["availability", "price"], covered_aspects: ["availability", "price"], missing_supported_aspects: [],
  entities: [{ path: "/a", name: "Saw A", covered: true }, { path: "/b", name: "Saw B", covered: false }, { path: "/c", name: "Saw C", covered: false }], entities_total: 3, entities_covered: 1,
  partial_because: ["entities not covered: 2 of 3"], limitations: [{ aspect: "ordering", kind: "verifier", detail: "an exact top-N ranking is not a criterion kind" }], first_page_answerable_selected: 0,
  note: "Coverage describes the verified tasks that were SELECTED.", ...over });
const html = (d: InvestigationExport) => renderToStaticMarkup(<InvestigationView d={d} />);

describe("goal and coverage in the rendered report", () => {
  it("states the goal, PARTIAL coverage, covered and uncovered items and the named limitation near the top, and never presents task success as goal success", () => {
    const d = live(); d.goal_coverage = cov();
    const h = html(d);
    expect(h).toContain(d.goal!); expect(h).toContain("Goal coverage: PARTIAL"); expect(h).toContain("2 of 2 selected tasks passed");
    expect(h).toContain("goal coverage <strong class=\"cov-word cov-partial\">PARTIAL</strong>");
    expect(h).toContain("1 of 3 of the goal&#x27;s items covered"); expect(h).toContain("✓ Saw A"); expect(h).toContain("✗ Saw B");
    expect(h).toContain("ordering (verifier limitation)"); expect(h).toContain("not proof that the goal was achieved");
    expect(h).not.toContain("baseline pass rate 100%"); expect(h).toContain("Selected tasks passed");
    expect(h.indexOf("Goal coverage: PARTIAL")).toBeLessThan(h.indexOf("1 · The website being evaluated"));
  });
  it("marks tasks answerable from the home page as easy and says so in the banner", () => {
    const d = live(); d.goal_coverage = cov({ first_page_answerable_selected: 1 }); d.tasks[0].tags = ["first_page_answerable"];
    const h = html(d);
    expect(h).toContain("easy · answer on the home page"); expect(h).toContain("answerable from the home page");
  });
  it("falls back honestly when an older export has a goal but no coverage details, and shows nothing for exports without a goal", () => {
    const d = live(); const h = html(d);
    expect(h).toContain("goal coverage not recorded in this export"); expect(h).toContain("Goal coverage is not recorded in this export"); expect(h).not.toContain("Goal coverage: PARTIAL");
    const none = live(); delete none.goal; const h2 = html(none);
    expect(h2).not.toContain("Evaluation goal"); expect(h2).toContain("baseline pass rate");
    expect(parseInvestigation(JSON.stringify(d)).ok).toBe(true);
  });
  it("shows an insufficient coverage status and the client context as unverified", () => {
    const d = live(); d.goal_coverage = cov({ status: "insufficient", entities_covered: 0 }); d.client_context = { text: "We are a family hire business.", sha256: "abc", label: "CLIENT-SUPPLIED" };
    const h = html(d);
    expect(h).toContain("Goal coverage: INSUFFICIENT"); expect(h).toContain("unverified"); expect(h).toContain("We are a family hire business.");
  });
  it("keeps a live report short when no fix was applied: no error-looking callouts, one line each, honest empty states preserved", () => {
    const h = html(live());
    expect(h).not.toContain("Site pages not included"); expect(h).not.toContain("Storefront pages not available");
    expect(h).toContain("Captured pages are stored with the run"); expect(h).toContain("No change was proposed or applied in this run."); expect(h).toContain("Not evaluated.");
    expect(h).toContain("No verified findings"); expect(h).toContain("No proposals");
  });
});
