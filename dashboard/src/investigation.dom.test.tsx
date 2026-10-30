// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { InvestigationPage } from "./pages/Investigation";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement, root: Root;
beforeEach(() => { sessionStorage.clear(); host = document.createElement("div"); document.body.append(host); root = createRoot(host); });
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

import { THEME_CSS, THEME_MARK } from "./components/storefrontTheme";
import { frame } from "./components/Storefront";
import publicFixture from "./fixtures/investigation-synthetic-expb-public.json";

// A page shaped like the real Site 5 pages (captured HTML with its own inline <style>, nav, cards, a table).
const LAKEVIEW = '<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8"/><title>Tools</title><style>body{font:16px/1.5 system-ui;margin:0}.card{border:1px solid #ccc}</style></head><body><header><nav><a href="/">Home</a><a href="/tools">Tools</a><a href="/faq">Borrowing rules</a></nav></header><main><h1>Tools</h1><ul><li class="card"><a href="/tools/cordless-drill"><h3>Cordless Drill</h3></a><p>18V drill and driver set.</p><p>Daily fee: $6</p></li><li class="card"><a href="/tools/circular-saw"><h3>Circular Saw</h3></a><p>7-inch corded saw.</p></li></ul><table><tr><th>Deposit</th><td>$40</td></tr></table></main><footer>© 2026</footer></body></html>';

const parse = (html: string) => new DOMParser().parseFromString(html, "text/html");
const withoutTheme = (d: Document) => { d.querySelectorAll(`style[${THEME_MARK.split("=")[0]}]`).forEach((e) => e.remove()); d.querySelectorAll("style").forEach((e) => { if (e.textContent === "a{pointer-events:none;cursor:default}") e.remove(); }); return d; };

describe("presentation theme is styling only", () => {
  const pages = [LAKEVIEW, ...Object.values((publicFixture as any).storefront.original.pages as Record<string, string>), ...Object.values((publicFixture as any).storefront.variants[0].pages as Record<string, string>)];
  it("changes no text, link, attribute or structure: removing the theme <style> yields the original-view DOM exactly", () => {
    for (const html of pages) {
      const orig = parse(frame(html, [], "original")), pres = parse(frame(html, [], "presentation"));
      expect(pres.querySelectorAll(`style[${THEME_MARK.split("=")[0]}]`)).toHaveLength(1);
      expect(withoutTheme(pres).documentElement.outerHTML).toBe(withoutTheme(orig).documentElement.outerHTML);
    }
  });
  it("renders identical visible text and an identical link set in both views", () => {
    for (const html of pages) {
      const orig = parse(frame(html, [], "original")), pres = parse(frame(html, [], "presentation"));
      expect(pres.body.textContent).toBe(orig.body.textContent);
      const links = (d: Document) => [...d.querySelectorAll("a")].map((a) => [a.getAttribute("href"), a.textContent]);
      expect(links(pres)).toEqual(links(orig));
    }
  });
  it("keeps the added daily-fee text visible and highlighted in the presentation view", () => {
    const pres = parse(frame(LAKEVIEW, ["Daily fee: $6"], "presentation"));
    expect(pres.querySelector("mark")!.textContent).toBe("Daily fee: $6");
    expect(pres.body.textContent).toContain("Daily fee: $6");
  });
  it("the stylesheet generates no visible text and loads nothing external", () => {
    const contents = [...THEME_CSS.matchAll(/content\s*:\s*([^;}]+)/g)].map((m) => m[1].trim());
    expect(contents.length).toBeGreaterThan(0);
    expect(contents.every((c) => c === '""')).toBe(true);
    expect(THEME_CSS).not.toMatch(/url\(|@import|https?:\/\//i);
  });
});

describe("storefront views in the journey", () => {
  const frames = (scope: string) => [...host.querySelectorAll<HTMLIFrameElement>(`${scope} iframe`)].map((f) => f.getAttribute("srcdoc") ?? "");
  const radio = (scope: string, label: string) => [...host.querySelectorAll(`${scope} .viewtoggle button`)].find((b) => b.textContent!.includes(label))!;
  it("shows the presentation theme by default in steps 1 and 4, labelled, with a toggle to the original appearance in each", async () => {
    await act(async () => { root.render(<InvestigationPage />); });
    await settle();
    for (const scope of ["#inv-website", "#inv-changes"]) {
      expect(frames(scope).every((h) => h.includes(THEME_MARK))).toBe(true);
      expect(host.querySelector(`${scope} .viewnote`)!.textContent).toContain("The experiment ran on the original pages");
      expect(host.querySelector(`${scope} .viewnote`)!.textContent).toContain("no claim is made that agents behave the same");
      expect(radio(scope, "Presentation view").getAttribute("aria-checked")).toBe("true");
      click(radio(scope, "Original evaluated appearance"));
      expect(frames(scope).every((h) => !h.includes(THEME_MARK))).toBe(true);
      expect(host.querySelector(`${scope} .viewnote`)!.textContent).toContain("exactly as the agents were given them");
      expect(host.querySelector(`${scope} iframe`)!.getAttribute("title")).not.toContain("Presentation view");
    }
  });
  it("marks the active step in the rail and starts on step 1", async () => {
    await act(async () => { root.render(<InvestigationPage />); });
    await settle();
    expect(host.querySelector('.steprail button[aria-current="step"]')!.textContent).toContain("1 · Website");
    expect(host.querySelectorAll(".steprail button")).toHaveLength(5);
  });
});

// ---- demo reliability: keeping an explicitly loaded report across reloads (this tab's session only) ----
import { KEY } from "./lib/reportStore";

const realText = () => { const d: any = structuredClone(publicFixture); delete d.synthetic; d.run.mode = "live"; d.modes = ["live"]; d.run.target = "site-5"; return JSON.stringify(d); };
const chooseFile = async (text: string, name = "export.json") => {
  const input = host.querySelector<HTMLInputElement>('.sourcebar input[type="file"]')!;
  const file = new File([text], name, { type: "application/json" });
  Object.defineProperty(input, "files", { value: [file], configurable: true });
  await act(async () => { input.dispatchEvent(new Event("change", { bubbles: true })); });
  await settle();
};
const mount = async () => { await act(async () => { root.render(<InvestigationPage />); }); await settle(); };
const remount = async () => { act(() => root.unmount()); root = createRoot(host); await mount(); };
const prov = () => host.querySelector('[aria-label="Report provenance"]')?.textContent;
const btn = (label: string) => [...host.querySelectorAll(".sourcebar button")].find((b) => b.textContent!.includes(label));

describe("report persistence for demo reliability", () => {
  it("starts on labelled synthetic data and offers a Load real export control that opens the file picker", async () => {
    await mount();
    expect(prov()).toBe("SYNTHETIC DEMO DATA");
    const input = host.querySelector<HTMLInputElement>('.sourcebar input[type="file"]')!;
    let opened = 0; input.click = () => { opened++; };
    click(btn("Load real export")!);
    expect(opened).toBe(1);
    expect(host.querySelector(".sourcebar")!.textContent).toContain("nothing is fetched, uploaded or published");
    expect(sessionStorage.getItem(KEY)).toBeNull();                              // fixtures are never stored
  });
  it("keeps an explicitly loaded real report across a reload and says so", async () => {
    await mount();
    await chooseFile(realText(), "public-export.json");
    expect(prov()).toBe("LIVE EXPERIMENT · real model trials");
    expect(host.textContent).not.toContain("SYNTHETIC FIXTURE");
    expect(host.querySelector(".srcstate")!.textContent).toContain("Kept in this tab's session storage only");
    await remount();                                                            // a page reload: nothing in memory survives, only sessionStorage
    expect(prov()).toBe("LIVE EXPERIMENT · real model trials");
    expect(host.querySelector(".hero2 h1")!.textContent).toContain("Make your website ready for AI agents");
    expect(host.querySelector(".srcstate")!.textContent).toContain("public-export.json");
  });
  it("clears the loaded report on request, so a reload shows synthetic data again", async () => {
    await mount(); await chooseFile(realText());
    expect(sessionStorage.getItem(KEY)).not.toBeNull();
    click(btn("Remove loaded report")!); await settle();
    expect(sessionStorage.getItem(KEY)).toBeNull();
    expect(prov()).toBe("SYNTHETIC DEMO DATA");
    expect(host.querySelector(".srcnotice")!.textContent).toContain("removed");
    await remount();
    expect(prov()).toBe("SYNTHETIC DEMO DATA");
  });
  it("fails gracefully when session storage is unavailable: still shows the report and says a reload needs the file again", async () => {
    const real = Object.getOwnPropertyDescriptor(window, "sessionStorage")!;
    Object.defineProperty(window, "sessionStorage", { configurable: true, get() { throw new DOMException("denied", "SecurityError"); } });
    try {
      await mount(); await chooseFile(realText());
      expect(prov()).toBe("LIVE EXPERIMENT · real model trials");
      expect(host.querySelector(".srcnotice")!.textContent).toContain("Reloading this page will require selecting the file again");
      expect(btn("Remove loaded report")).toBeUndefined();
      await remount();
      expect(prov()).toBe("SYNTHETIC DEMO DATA");
    } finally { Object.defineProperty(window, "sessionStorage", real); }
  });
  it("fails gracefully when the write is refused (quota) and when the report is too large", async () => {
    const proto = Object.getPrototypeOf(sessionStorage);
    const orig = proto.setItem;
    proto.setItem = () => { throw new DOMException("full", "QuotaExceededError"); };
    try {
      await mount(); await chooseFile(realText());
      expect(prov()).toBe("LIVE EXPERIMENT · real model trials");
      expect(host.querySelector(".srcnotice")!.textContent).toMatch(/full or refused the write\. Reloading this page will require selecting the file again/);
    } finally { proto.setItem = orig; }
    const big = JSON.parse(realText()); big.padding = "x".repeat(2_100_000);
    await chooseFile(JSON.stringify(big));
    expect(host.querySelector(".srcnotice")!.textContent).toContain("too large");
    expect(sessionStorage.getItem(KEY)).toBeNull();
  });
  it("switches between synthetic and real reports with matching labels, and can return to the kept report", async () => {
    await mount();
    await chooseFile(realText());
    expect(prov()).toBe("LIVE EXPERIMENT · real model trials");
    const select = host.querySelector("select")!;
    await act(async () => { select.value = "expb-synthetic"; select.dispatchEvent(new Event("change", { bubbles: true })); });
    await settle();
    expect(prov()).toBe("SYNTHETIC DEMO DATA");
    expect(host.textContent).toContain("SYNTHETIC FIXTURE");
    expect(sessionStorage.getItem(KEY)).not.toBeNull();                         // viewing a fixture does not discard the kept report
    click(btn("Switch back to loaded report")!); await settle();
    expect(prov()).toBe("LIVE EXPERIMENT · real model trials");
    expect(host.textContent).not.toContain("SYNTHETIC FIXTURE");
  });
  it("never stores or shows a file that fails validation, and discards a corrupt kept report", async () => {
    await mount();
    await chooseFile(JSON.stringify({ ...JSON.parse(realText()), criteria: { x: 1 } }));      // forbidden private field
    expect(sessionStorage.getItem(KEY)).toBeNull();
    expect(host.textContent).toContain("Cannot display this file");
    await chooseFile("{not json");
    expect(sessionStorage.getItem(KEY)).toBeNull();
    sessionStorage.setItem(KEY, JSON.stringify({ name: "x.json", text: "{broken" }));
    await remount();
    expect(prov()).toBe("SYNTHETIC DEMO DATA");
    expect(sessionStorage.getItem(KEY)).toBeNull();
    expect(host.querySelector(".srcnotice")!.textContent).toContain("could not be read and was discarded");
  });
});
