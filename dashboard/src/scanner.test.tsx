import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { FindingCard, ResultView, Unconfigured, ScannerPage } from "./pages/Scanner";
import { ApiError, call, setToken, type ScanResult } from "./lib/scannerApi";

const result = (over: Partial<ScanResult> = {}): ScanResult => ({
  scan_id: "s1", task_id: "t", variant_id: "electronics-v1/a", mode: "mock", mock_behavior: "correct", status: "complete", created_at: 0, finished_at: 1, error: null, mock: true,
  inference_label: "MOCK — scripted agent behaviour, not a model; nothing was sent to any provider",
  task: { objective: "Find the cheapest monitor", template_id: "x", evidence_policy: "p", limits: { max_steps: 12, max_model_requests: 12, timeout_seconds: 240 } },
  verdict: { passed: true, evidence_backed: false, answer_valid: true, reasons: ["ok"], missing_evidence: ["observed_text:USB-C"], evaluator: "e v1" },
  outcome: { run_status: "completed", stop_reason: "agent_done", answer: {}, errors: [] },
  metrics: { model_requests: 4, page_views: 4, elapsed_seconds: 12.3, prompt_tokens: 1, completion_tokens: 1, calculated_cost_usd: 0.0526, cost_basis: "MOCK tokens at published prices — not billed, not a model result", limits: { max_steps: 12, max_model_requests: 12, timeout_seconds: 240 } },
  journey: [{ step: 1, path: "/", query: "", actions: [{ name: "navigate", params: { url: "/c/monitors" } }], executed: [] }],
  diagnostics: { findings: [{ id: "F1", category: "website", title: "T", summary: "S", confidence: "hypothesis", evidence: [{ step: 2 }], recommendation: { text: "Show stock on cards", status: "hypothesis_unvalidated", validate_with: { factor: "availability", from: "detail", to: "listing", task: "t" } } }], mode_notice: "MOCK scan: …", attribution_note: "Categories separate…", metrics: { reference_page_views: 3, reference_note: "n" } },
  ...over,
});

describe("scanner UI", () => {
  it("public build with no API configured says nothing can be scanned and claims no deployment", () => {
    const html = renderToStaticMarkup(<ScannerPage />);
    expect(html).toContain("not connected to a scanner service");
    expect(html).toContain("No live scanner is deployed");
    expect(html).not.toContain("Invitation code");
    expect(renderToStaticMarkup(<Unconfigured />)).toContain("VITE_SCANNER_API_URL");
  });
  it("results are labelled MOCK, show the evaluator verdict and missing-evidence state, and calculated (not billed) cost", () => {
    const html = renderToStaticMarkup(<ResultView result={result()} />);
    expect(html).toContain("MOCK");
    expect(html).toContain("PASS");
    expect(html).toContain("required evidence NOT shown");
    expect(html).toContain("not billed");
    expect(html).toContain("loaded it; the evaluator separately checks");
  });
  it("a LIVE result is labelled LIVE, not MOCK", () => {
    const html = renderToStaticMarkup(<ResultView result={result({ mock: false, mode: "live", inference_label: "LIVE — Meta model inference (single run)" })} />);
    expect(html).toContain("scan-live");
    expect(html).not.toContain("MOCK —");
  });
  it("recommendations are always shown as unvalidated hypotheses with a controlled-rescan instruction", () => {
    const html = renderToStaticMarkup(<FindingCard f={result().diagnostics!.findings[0]} />);
    expect(html).toContain("hypothesis, unvalidated");
    expect(html).toContain("Hypothesis — not validated");
    expect(html).toContain("changing only");
    expect(html).not.toMatch(/will improve|fixes the problem|proven/i);
  });
  it("pending results render a status instead of a verdict", () => {
    const html = renderToStaticMarkup(<ResultView result={result({ status: "running", verdict: undefined, metrics: undefined })} />);
    expect(html).toContain("Scan running");
  });
  it("api client sends the bearer token, surfaces server messages and maps network failure", async () => {
    setToken("tok");
    const f = vi.fn(async () => new Response(JSON.stringify({ message: "quota" }), { status: 429 }));
    await expect(call("/x", {}, f as any)).rejects.toMatchObject({ status: 429, message: "quota" });
    expect((f.mock.calls[0] as any)[1].headers.Authorization).toBe("Bearer tok");
    await expect(call("/x", {}, (async () => { throw new Error("net"); }) as any)).rejects.toBeInstanceOf(ApiError);
    setToken(null);
  });
});
