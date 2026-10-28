import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Overview } from "./pages/Overview";
import { Scopes } from "./pages/Scopes";
import { Evidence } from "./pages/Evidence";
import { RunTable } from "./components/RunTable";
import { allRuns, byScope } from "./lib/metrics";

describe("rendered pages", () => {
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
    expect(html).toContain("Website-required navigation");
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
    expect(html).toContain("planned for Stage B");
  });
});
