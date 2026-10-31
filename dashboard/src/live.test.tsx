import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { LivePanel } from "./pages/LivePanel";
import { isActive, startJob } from "./lib/liveApi";
import { setToken } from "./lib/scannerApi";

describe("live evaluation panel (M0)", () => {
  it("without a service address it says so instead of pretending to evaluate", () => {
    const html = renderToStaticMarkup(<LivePanel onOpen={() => true} />);
    expect(html).toContain("needs the evaluation service");
    expect(html).toContain("VITE_SCANNER_API_URL");
    expect(html).not.toContain("Start mock evaluation");
  });
  it("only queued and running jobs are polled", () => {
    expect(["queued", "running"].every((s) => isActive(s as never))).toBe(true);
    expect(["completed", "failed", "cancelled", "timed_out"].some((s) => isActive(s as never))).toBe(false);
  });
  it("starting a job sends a registered target id and a goal, always as a mock job, with the session token and no URL field", async () => {
    setToken("tok");
    const f = vi.fn(async () => new Response(JSON.stringify({ id: "live-1" }), { status: 202 }));
    vi.stubGlobal("fetch", f);
    await startJob("ironbark", "Compare prices");
    const [, init] = f.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({ target_id: "ironbark", goal: "Compare prices", mode: "mock" });
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer tok");
    vi.unstubAllGlobals(); setToken(null);
  });
});

import fixture from "./fixtures/investigation-synthetic.json";
import { Proposals } from "./pages/Investigation";

describe("recommendation provenance", () => {
  it("every proposal, whatever its basis, is shown as unvalidated with no measured effect", () => {
    const d = fixture as any;
    expect(d.proposals.length).toBeGreaterThan(0);
    const html = renderToStaticMarkup(<Proposals d={d} />);
    expect((html.match(/UNVALIDATED PROPOSAL/g) ?? []).length).toBe(d.proposals.length);
    expect(html).toContain("Hypothesised effect (not measured)");
    expect(html).not.toContain("Expected:");
  });
});

describe("website context in the start request", () => {
  it("is sent only when non-empty, trimmed, and never changes the mode or the budget fields", async () => {
    const f = vi.fn(async () => new Response(JSON.stringify({ id: "live-1" }), { status: 202 }));
    vi.stubGlobal("fetch", f);
    await startJob("ironbark", "Compare prices", undefined, "  We hire to tradies.  ");
    await startJob("ironbark", "Compare prices", { confirm_budget_usd: 2 }, "   ");
    const body = (i: number) => JSON.parse((f.mock.calls[i] as unknown as [string, RequestInit])[1].body as string);
    expect(body(0)).toEqual({ target_id: "ironbark", goal: "Compare prices", mode: "mock", context: "We hire to tradies." });
    expect(body(1)).toEqual({ target_id: "ironbark", goal: "Compare prices", mode: "live", confirm_budget_usd: 2 });
    vi.unstubAllGlobals();
  });
});
