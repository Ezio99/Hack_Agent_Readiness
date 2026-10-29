import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { AuditReportView, type AuditReport } from "./pages/Audit";

const ev = { type: "listing_card", url: "http://x.test/c/headphones", excerpt: "Aurel Pulse Buds A$199.00", cue: null };
const report = (over: Partial<AuditReport> = {}): AuditReport => ({
  audit_id: "a1", target: "demo-shop", objective: "every in-stock ANC headphone",
  findings: [{ fingerprint: "attribute_detail_only:availability", kind: "attribute_detail_only", attribute: "availability", category: "website_property", confidence: "observed", title: "t", summary: "0 of 54 listing cards show stock; 6 of 6 product pages do.", evidence: [ev] }],
  recommendations: [{ id: "rec-1", title: "Show stock status on listing cards", change: "Print In stock on cards", change_id: "availability-on-listing-cards", rationale: "Observed: 0 of 54 …", expected_benefit: "Fewer product-page visits", risks: "denser cards",
    status: "proposed", validation: "unvalidated", task_relevance: "task_depends_on_attribute", confidence: { level: "prior_evidence_other_site", statement: "Supported by descriptive evidence from a different site/task; NOT validated for this site." },
    supporting_evidence: [ev], how_to_validate: { resolution_check: "re-audit and confirm the finding is gone", effect_measurement: "controlled rescan measuring requests" } }],
  agent_execution: null, discovery_candidates: [], lifecycle: null, measured_effects: { status: "not_measured", effects: [] }, ...over,
});

describe("site audit view", () => {
  it("separates observed properties, proposals and measured effects, and labels proposals unvalidated", () => {
    const html = renderToStaticMarkup(<AuditReportView report={report()} />);
    expect(html).toContain("Observed fact");
    expect(html).toContain("Proposed");
    expect(html).toContain("Validation: unvalidated");
    expect(html).toContain("NOT validated for this site");
    expect(html).toContain("Not measured");
    expect(html).not.toMatch(/will improve|proven|guarantee/i);
    expect(html).not.toMatch(/127\.0\.0\.1:\d+|localhost:\d+/);
  });
  it("shows resolution from the re-audit and says it is not an effect measurement", () => {
    const html = renderToStaticMarkup(<AuditReportView report={report({ findings: [], recommendations: [], lifecycle: { previous_audit_id: "a0", statement: "Resolution means the property is no longer observed by the probe. It does not show that agent outcomes improved; see measured_effects.", items: [{ fingerprint: "attribute_detail_only:availability", status: "resolved", current_summary: "54 of 54 listing cards show stock" }], new_findings: [] } })} />);
    expect(html).toContain("Resolved — no longer observed");
    expect(html).toContain("does not show that agent outcomes improved");
    expect(html).toContain("nothing is proposed");
  });
  it("keeps agent execution evidence in its own section with the mock notice and inferred links", () => {
    const html = renderToStaticMarkup(<AuditReportView report={report({ agent_execution: { scan_mode: "mock", mode_notice: "MOCK scan: the agent's decisions were scripted.", items: [{ id: "effort", category: "agent_execution", title: "Effort", summary: "7 requests" }], corroborates: [{ statement: "consistent with lookups, intent not observed" }] } })} />);
    expect(html).toContain("separate from the website");
    expect(html).toContain("MOCK scan");
    expect(html).toContain("Inferred");
  });
});
