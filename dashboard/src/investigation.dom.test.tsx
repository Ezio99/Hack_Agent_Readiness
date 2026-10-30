// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { InvestigationPage } from "./pages/Investigation";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement, root: Root;
beforeEach(() => { host = document.createElement("div"); document.body.append(host); root = createRoot(host); });
afterEach(() => { act(() => root.unmount()); host.remove(); });

const settle = async () => { for (let i = 0; i < 6; i++) await act(async () => { await new Promise((r) => setTimeout(r, 10)); }); };
const selectedPaths = (scope: string) => [...host.querySelectorAll(`${scope} .pagesel .on`)].map((b) => b.querySelector("code")!.textContent);
const click = (el: Element) => act(() => { (el as HTMLElement).click(); });

describe("loading a second report", () => {
  it("resets the selected storefront pages instead of inheriting the previous report's selection", async () => {
    await act(async () => { root.render(<InvestigationPage />); });
    await settle();                                                             // default demo data (EXP-B synthetic, public view) loads
    expect(host.querySelector("#inv-website .sf-browser")).not.toBeNull();
    expect(selectedPaths("#inv-website")).toEqual(["/"]);
    expect(selectedPaths("#inv-changes")).toEqual(["/cabins"]);                 // the changed page is selected first in the side-by-side view

    // the user moves both viewers away from their defaults
    click([...host.querySelectorAll("#inv-website .pagesel button")].find((b) => b.textContent!.includes("/cabins/pine"))!);
    click([...host.querySelectorAll("#inv-changes .pagesel button")].find((b) => b.textContent!.includes("/cabins/lake"))!);
    expect(selectedPaths("#inv-website")).toEqual(["/cabins/pine"]);
    expect(selectedPaths("#inv-changes")).toEqual(["/cabins/lake"]);
    expect(host.querySelector("#inv-changes iframe")!.getAttribute("title")).toContain("/cabins/lake");

    // load a second report (the private EXP-B synthetic view) through the demo-data selector
    const select = host.querySelector("select")!;
    await act(async () => {
      select.value = "expb-synthetic";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await settle();
    expect(selectedPaths("#inv-website")).toEqual(["/"]);                       // back to the new report's defaults
    expect(selectedPaths("#inv-changes")).toEqual(["/cabins"]);
    expect(host.querySelector("#inv-changes iframe")!.getAttribute("title")).toContain("/cabins");
  });

  it("shows the neutral pattern summary prominently and keeps the investigator's original wording available", async () => {
    await act(async () => { root.render(<InvestigationPage />); });
    await settle();
    const left = host.querySelector(".prov-inv")!;
    expect(left.textContent).toContain("Pattern observed: information shown on the detail pages is not shown on the listing page");
    expect(left.textContent).toContain("whether it affects agents is untested");
    expect(left.querySelector("details")!.textContent).toContain("Investigator’s original wording (unchanged)");
    expect(left.querySelector("details")!.textContent).toContain("Detail fields are present on every detail page but absent from every listing card");
  });
});
