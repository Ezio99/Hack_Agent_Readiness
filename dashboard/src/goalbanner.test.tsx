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
    expect(h).toContain(d.goal!); expect(h).toContain("Goal coverage: PARTIAL"); expect(h).toContain("2 of 2 strict passes; 2 evidence-supported passes");
    expect(h).toContain("goal coverage <strong class=\"cov-word cov-partial\">PARTIAL</strong>");
    expect(h).toContain("1 of 3 of the goal&#x27;s items covered"); expect(h).toContain("✓ Saw A"); expect(h).toContain("✗ Saw B");
    expect(h).toContain("ordering (verifier limitation)"); expect(h).toContain("not proof that the goal was achieved");
    expect(h).not.toContain("baseline pass rate 100%"); expect(h).toContain("Baseline: strict / evidence-supported");
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
    expect(h2).not.toContain("Evaluation goal"); expect(h2).toContain("baseline strict passes");
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

describe("verified / observed / inconclusive classes", () => {
  const withEvidence = () => {
    const d = live(); d.goal_coverage = cov();
    d.findings = [{ id: "fnd-1", hypothesis_id: "hyp-1", statement: "Field X is only on item pages.", attribution: "website", structural_proof: false, provenance: { mode: "live", source: "code:promote" }, observation_ids: ["obs-1"], unresolved_observation_ids: [],
      support: [{ ref: "trial:t1", resolved: true }, { ref: "trial:t2", resolved: true }] }];
    d.hypotheses = [
      { id: "hyp-1", tier: "verifiable", statement: "Field X is only on item pages.", claim_kind: "info_absent_on_template", prediction: null, status: "supported", observation_ids: ["obs-1"], promoted: true, verification: { verifier: "deterministic:info_absent_on_template", result: "supported", evidence: ["page:/hire", "trial:t1", "trial:t2"] }, provenance: { mode: "live", source: "llm" } },
      { id: "hyp-2", tier: "verifiable", statement: "Field Y is only on item pages.", claim_kind: "info_absent_on_template", prediction: null, status: "supported", observation_ids: [], promoted: false, verification: { verifier: "deterministic:info_absent_on_template", result: "supported", evidence: ["trial:t1"] }, provenance: { mode: "live", source: "llm" } },
      { id: "hyp-3", tier: "novel", statement: "Agents prefer sorted lists.", claim_kind: null, prediction: "if sorted, fewer steps", status: "unverified", observation_ids: [], promoted: false, verification: null, provenance: { mode: "live", source: "llm" } }] as any;
    d.proposals = [{ id: "prp-1", basis: "verified_finding", source_id: "fnd-1", label: "x", status: "proposed", validation: "unvalidated", expected_effect: "", risks: [], auto_applicable: true, approved: false, change: { ops: [] }, provenance: { mode: "live", source: "rule:template" } }] as any;
    d.tasks[0].source = "owner";
    return d;
  };
  it("places a promoted finding under VERIFIED, a supported-but-unpromoted claim under OBSERVED and open-ended ideas under INCONCLUSIVE, each with evidence references", () => {
    const h = html(withEvidence());
    expect(h).toContain("What this evaluation can and cannot claim");
    const v = h.slice(h.indexOf("oc oc-verified"), h.indexOf("oc oc-observed")), o = h.slice(h.indexOf("oc oc-observed"), h.indexOf("oc oc-inconclusive")), i = h.slice(h.indexOf("oc oc-inconclusive"), h.indexOf("Proposed changes:"));
    expect(v).toContain("Field X is only on item pages."); expect(v).toContain("trial:t1"); expect(v).toContain("2 independent supporting task(s)"); expect(v).toContain("graded against answers computed by code");
    expect(o).toContain("Field Y is only on item pages."); expect(o).toContain("below the promotion rule"); expect(o).not.toContain("Field X");
    expect(i).toContain("Agents prefer sorted lists."); expect(i).toContain("UNVERIFIED, never a finding"); expect(i).not.toContain("Field Y is only");
  });
  it("labels every proposal UNVALIDATED and owner-authored tasks as such, and shows nothing for exports without a goal", () => {
    const h = html(withEvidence());
    expect(h).toContain("all UNVALIDATED"); expect(h).toContain("until the frozen tasks are retested"); expect(h).toContain("owner-authored");
    const none = withEvidence(); delete none.goal; expect(html(none)).not.toContain("What this evaluation can and cannot claim");
  });
  it("is honest when nothing was found: empty classes say None, and void or agent-attributed trials are INCONCLUSIVE", () => {
    const empty = live(); empty.goal_coverage = cov(); empty.tasks = []; empty.hypotheses = []; empty.findings = []; empty.proposals = [];
    expect((html(empty).match(/None\./g) ?? []).length).toBeGreaterThanOrEqual(3);
    const d = live(); d.goal_coverage = cov(); d.tasks[1].baseline = [{ ...d.tasks[1].baseline[0], void: true, passed: null }]; d.tasks[0].baseline = [{ ...d.tasks[0].baseline[0], passed: false, attribution: "agent", why: "path existed" }];
    const h = html(d);
    expect(h).toContain("void"); expect(h).toContain("automatic label “agent”");
  });
});

describe("goals without named items", () => {
  it("never shows COMPLETE or '0 of 0 items' when only attribute coverage was assessed", () => {
    const d = live(); d.goal = "Can an AI agent compare the refundable deposit, minimum hire period, and delivery requirements across the hire machines?";
    d.goal_coverage = cov({ status: "complete", entities: [], entities_total: 0, entities_covered: 0, covered_aspects: ["attribute:refundable deposit", "attribute:minimum hire"], partial_because: [], limitations: [] });
    const h = html(d);
    expect(h).toContain("Attribute-level coverage only"); expect(h).toContain("not assessed"); expect(h).toContain("fields covered: refundable deposit, minimum hire");
    expect(h).not.toContain("COMPLETE"); expect(h).not.toContain("0 of 0"); expect(h).not.toContain("attribute:refundable");
    expect(h).toContain("attribute-level coverage only"); expect(h).toContain("catalogue-wide coverage was not assessed");
  });
  it("still shows the status and the item counts when the goal names items", () => {
    const d = live(); d.goal_coverage = cov({ status: "partial" });
    const h = html(d);
    expect(h).toContain("Goal coverage: PARTIAL"); expect(h).toContain("1 of 3 of the goal&#x27;s items covered"); expect(h).not.toContain("Attribute-level coverage only");
  });
});

describe("owner insights", () => {
  const withInsights = (over: Partial<NonNullable<InvestigationExport["insights"]>> = {}) => {
    const d = live(); d.goal_coverage = cov({ entities_total: 0, entities: [], entities_covered: 0 });
    d.insights = { schema: "owner-insights-v1", summary: "2 of 2 measured task(s) showed friction on a field that the listing cards do not show.",
      site_properties: [{ field: "refundable deposit", listing: "/hire", item_pages_with_field: 16, listing_items: 16, shown_on_listing_items: 0, absent_from_cards: true, evidence: "site profile" }],
      task_effort: [{ task_id: "t1", question: "Which hire machines have a deposit below $200?", source: "owner", partition: "investigation", trial_id: "t1-r1", passed: false, requests: 13, steps_used: 14, step_limit: 14, page_views: 13, minimum_page_views: 6, extra_page_views: 7,
        attribution: "tool_interface", strict_grade: "strict name match: recall 0.0, precision 0.0", names_mentioned_in_answer: "1 of 4", friction: true, fields_needed: ["refundable deposit"], needs_field_absent_from_cards: ["refundable deposit"], notes: ["The answer text mentions 1 of the 4 expected names; the strict grade is not a measure of how much the agent understood."] }],
      friction_tasks: ["t1"], possible_causes: [{ text: "Possible cause (rule-based, untested): the cards do not show the field.", fields: ["refundable deposit"], claim_kind: null, status: "derived by a fixed rule", refs: ["t1-r1"], source: "rule", label: "POSSIBLE CAUSE (hypothesis, not established)" },
        { text: "Deposit is only visible after 1 hop.", fields: ["refundable deposit"], claim_kind: "info_only_after_k_hops", status: "could not be checked: needs integer `k` >= 2. Treated as an unverified idea, not as a finding.", refs: ["hyp-1"], source: "the investigator (model)", label: "POSSIBLE CAUSE (hypothesis, not established)" }],
      suggestions: [{ text: "Consider showing refundable deposit on each listing card on /hire.", fields: ["refundable deposit"], tasks: ["t1"], basis: ["t1-r1"], expected_benefit: "HYPOTHESIS, not measured: fewer page views.", risks: ["Cards become busier"], label: "SUGGESTED IMPROVEMENT (UNVALIDATED)", source: "rule", patch: null }],
      strict_findings: 0, provenance: { run_id: "live-x", mode: "live", source_run: null, task_sources: { owner: 1 }, investigator_model: "muse-spark-1.3", investigation_status: "completed", frozen_tasks: 1, note: "n" }, ...over };
    return d;
  };
  const section = (h: string) => h.slice(h.indexOf('class="insights"'), h.indexOf('class="outcomeclasses"'));
  it("shows measurements, hypotheses and an UNVALIDATED text suggestion above the strict results, with the owner-authored label, and never the word VERIFIED", () => {
    const h = html(withInsights()), s = section(h);
    expect(h.indexOf('class="insights"')).toBeLessThan(h.indexOf('class="outcomeclasses"'));
    expect(s).toContain("Details: what was measured"); expect(s).toContain("on none of the"); expect(s).toContain("not by itself a usability problem"); expect(s).toMatch(/minimum[^0-9]*6[^0-9]*\+[^0-9]*7/);
    expect(s).toContain("strict name match: recall 0.0"); expect(s).toContain("not a measure of how much the agent understood");
    expect(s).toContain("HYPOTHESES"); expect(s).toContain("could not be checked"); expect(s).toContain("UNVALIDATED"); expect(s).toContain("no change was generated or applied");
    expect(s).toContain("owner-authored"); expect(s).toContain("not autonomous task generation"); expect(s).not.toContain("VERIFIED");
  });
  it("says so when nothing was suggested and renders nothing for exports without insights", () => {
    const h = html(withInsights({ suggestions: [], possible_causes: [], summary: "No friction was observed on these 1 task(s). No friction-based suggestion is made." }));
    expect(section(h)).toContain("None: no friction on a measured property was observed"); expect(section(h)).toContain("None proposed.");
    const d = withInsights(); d.insights = null; expect(html(d)).not.toContain("Details: what was measured");
    const old = withInsights(); delete old.insights; expect(html(old)).not.toContain("Details: what was measured");
  });
});


describe("owner-facing summary and simplified trial table", () => {
  const base = () => {
    const d = live(); d.goal_coverage = cov({ entities_total: 0, entities: [], entities_covered: 0 });
    const eff = (id: string, extra: number, passed: boolean, attr: string) => ({ task_id: id, question: `Question ${id}?`, source: "owner", partition: "investigation", trial_id: `${id}-r1`, passed, requests: 13, steps_used: 14, step_limit: 14, page_views: 6 + extra, minimum_page_views: 6, extra_page_views: extra,
      attribution: attr, strict_grade: "strict name match: recall 0.5, precision 1.0", names_mentioned_in_answer: "2 of 4", friction: extra >= 2, fields_needed: ["refundable deposit"], needs_field_absent_from_cards: extra >= 2 ? ["refundable deposit"] : [], notes: ["The answer text mentions 2 of the 4 expected names; the strict grade is not a measure of how much the agent understood."] });
    d.insights = { schema: "owner-insights-v1", summary: "s", site_properties: ["refundable deposit", "minimum hire"].map((f) => ({ field: f, listing: "/hire", item_pages_with_field: 16, listing_items: 16, shown_on_listing_items: 0, absent_from_cards: true, evidence: "e" })),
      task_effort: [eff("a", 7, false, "tool_interface"), eff("b", 8, false, "tool_interface"), eff("c", 0, true, "success")], friction_tasks: ["a", "b"],
      possible_causes: [{ text: "Possible cause (rule-based, untested): the cards do not show the fields.", fields: ["refundable deposit"], claim_kind: null, status: "derived by a fixed rule", refs: ["a-r1"], source: "rule", label: "POSSIBLE CAUSE (hypothesis, not established)" }],
      suggestions: [{ text: "Consider showing refundable deposit and minimum hire on each listing card on /hire.", fields: ["refundable deposit"], tasks: ["a"], basis: ["a-r1"], expected_benefit: "HYPOTHESIS, not measured: fewer page views.", risks: ["Cards become busier"], label: "SUGGESTED IMPROVEMENT (UNVALIDATED)", source: "rule", patch: null }],
      strict_findings: 0, provenance: { run_id: "live-x", mode: "live", source_run: null, task_sources: { owner: 3 }, investigator_model: "m", investigation_status: "completed", frozen_tasks: 3, note: "n" } };
    return d;
  };
  it("opens with a short owner summary: what the agent experienced, a hypothesis, an UNVALIDATED suggestion and a few metrics", () => {
    const h = html(base()); const s = h.slice(h.indexOf('class="diagsummary'), h.indexOf('class="goalbanner'));
    expect(h.indexOf('class="diagsummary')).toBeLessThan(h.indexOf('class="goalbanner'));
    expect(s).toContain("Summary for the site owner"); expect(s).toContain("What the agent experienced"); expect(s).toContain("2 of 3"); expect(s).toContain("8 extra page views");
    expect(s).toContain("Possible cause"); expect(s).toContain("HYPOTHESIS"); expect(s).toContain("Not an established cause"); expect(s).toContain("Suggested improvement"); expect(s).toContain("UNVALIDATED");
    expect(s).toContain("tasks measured"); expect(s).toContain("verified findings"); expect(s).not.toContain("VERIFIED"); expect(s).not.toContain("tool_interface");
  });
  it("shows a clear no-friction state with no cause or suggestion", () => {
    const d = base(); d.insights!.task_effort = d.insights!.task_effort.map((e) => ({ ...e, friction: false, extra_page_views: 0, page_views: 6, passed: true, attribution: "success" })); d.insights!.possible_causes = []; d.insights!.suggestions = [];
    const h = html(d); const s = h.slice(h.indexOf('class="diagsummary'), h.indexOf('class="goalbanner'));
    expect(s).toContain("No friction observed"); expect(s).toContain("diag-clear"); expect(s).not.toContain("Possible cause"); expect(s).not.toContain("Suggested improvement");
  });
  it("keeps the trial table scannable (task, outcome, page views with extra effort) and moves grading detail, attribution and evidence ids into expandable details", () => {
    const h = html(base()); const t = h.slice(h.indexOf('class="runs triage"'), h.indexOf("</table>", h.indexOf('class="runs triage"')));
    const heads = [...t.matchAll(/<th scope="col">([^<]*)<\/th>/g)].map((m) => m[1]);
    expect(heads).toEqual(["Task", "Outcome", "Page views (extra beyond the minimum)"]);
    expect(t).toContain("<details>"); expect(t).toContain("details and evidence"); expect(t).toContain("a-r1"); expect(t).toContain("Strict grade");
    expect(t.split("not a measure of how much the agent understood").length - 1).toBe(3);                         // the caveat lives in each row's details, not in the visible row
    const visible = t.replace(/<details>[\s\S]*?<\/details>/g, "");
    expect(visible).not.toContain("tool_interface"); expect(visible).not.toContain("recall"); expect(visible).not.toContain("a-r1");
    expect(h).toContain("Outcomes use strict name matching");                                                      // one shared note under the table
  });
  it("never presents a tool_interface label as a cause: it is a heuristic, in details only, and the strict INCONCLUSIVE class says so once", () => {
    const d = base(); d.tasks.forEach((t) => { t.baseline = [{ ...t.baseline[0], passed: false, attribution: "tool_interface" }]; });
    const h = html(d);
    expect(h).toContain("a heuristic that can misfire; it is not treated as a cause here"); expect(h).not.toContain("attributed to “tool_interface”"); expect(h).toContain("labels such as “tool_interface” or “agent” can misfire");
  });
  it("groups fields that share the same measurement into one line and one suggestion", () => {
    const h = html(base()); const s = h.slice(h.indexOf('class="insights"'), h.indexOf('class="outcomeclasses"'));
    expect(s).toContain("<strong>refundable deposit, minimum hire</strong>"); expect((s.match(/Consider showing/g) ?? []).length).toBe(1);
  });
});
