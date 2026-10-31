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
