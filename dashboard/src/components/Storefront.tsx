import { useState } from "react";
import { Pill } from "./ui";
import { themeStyleTag } from "./storefrontTheme";

/** Static, inert view of captured HTML. Display-only changes (stated in the UI): links are made unclickable so nothing navigates; optional highlight of inserted text. The page content itself is never edited. */
const INERT = "<style>a{pointer-events:none;cursor:default}</style>";
const HIGHLIGHT_STYLE = "background:#ffe066;outline:2px solid #d9480f;border-radius:2px";

export type View = "presentation" | "original";

/** `view = "original"` shows the captured page as it was served to the agents (plus the inert-links rule). `"presentation"` additionally appends the presentation-only stylesheet; text, links and structure are identical in both. */
export function frame(html: string, highlight: string[] = [], view: View = "original"): string {
  let out = html;
  for (const frag of new Set(highlight)) out = out.split(`>${frag}<`).join(`><mark style="${HIGHLIGHT_STYLE}">${frag}</mark><`);
  const extra = INERT + (view === "presentation" ? themeStyleTag() : "");
  return out.includes("</head>") ? out.replace("</head>", `${extra}</head>`) : extra + out;
}

export function ViewToggle({ view, onChange, where }: { view: View; onChange: (v: View) => void; where: string }) {
  const opts: [View, string][] = [["presentation", "Presentation view"], ["original", "Original evaluated appearance"]];
  return (
    <div className="viewtoggle" role="radiogroup" aria-label={`Storefront appearance (${where})`}>
      {opts.map(([v, label]) => <button key={v} type="button" role="radio" aria-checked={view === v} className={view === v ? "on" : ""} onClick={() => onChange(v)}>{label}</button>)}
      <span className="viewnote" role="note">{view === "presentation"
        ? "Presentation theme: styling only — same text and links. The experiment ran on the original pages, and no claim is made that agents behave the same on this appearance."
        : "As captured: the pages exactly as the agents were given them."}</span>
    </div>
  );
}

export const titleOf = (html: string, path: string) => /<title>([^<]*)<\/title>/i.exec(html)?.[1]?.trim() || path;

export function PageSelector({ paths, pages, value, onChange, changed = [] }: { paths: string[]; pages: Record<string, string>; value: string; onChange: (p: string) => void; changed?: string[] }) {
  return (
    <div className="pagesel" role="tablist" aria-label="Captured pages">
      {paths.map((p) => (
        <button key={p} type="button" role="tab" aria-selected={p === value} className={p === value ? "sel on" : "sel"} onClick={() => onChange(p)} title={titleOf(pages[p] ?? "", p)}>
          <code>{p}</code>{changed.includes(p) ? <> <Pill tone="warn">changed</Pill></> : null}
        </button>))}
    </div>
  );
}

export function StorefrontFrame({ html, path, label, highlight, view = "original" }: { html: string; path: string; label: string; highlight?: string[]; view?: View }) {
  return (
    <figure className="sf-frame">
      <figcaption><strong>{label}</strong> <code>{path}</code></figcaption>
      <iframe title={`${label}: ${path}`} sandbox="" srcDoc={frame(html, highlight, view)} loading="lazy" />
    </figure>
  );
}

export function StorefrontBrowser({ pages, label = "Original pages", initial }: { pages: Record<string, string>; label?: string; initial?: string }) {
  const paths = Object.keys(pages);
  const [path, setPath] = useState(initial && pages[initial] ? initial : paths.includes("/") ? "/" : paths[0]);
  const [view, setView] = useState<View>("presentation");
  return (
    <div className="sf-browser">
      <ViewToggle view={view} onChange={setView} where="step 1" />
      <PageSelector paths={paths} pages={pages} value={path} onChange={setPath} />
      <StorefrontFrame html={pages[path] ?? ""} path={path} label={view === "presentation" ? "Presentation view" : `${label} (as captured)`} view={view} />
      <p className="muted">Static view of captured pages: links are inactive here, so use the page selector above. Nothing is loaded from the site.</p>
    </div>
  );
}

export function SideBySide({ original, patched, changed, highlightText }: { original: Record<string, string>; patched: Record<string, string>; changed: string[]; highlightText: Record<string, string[]> }) {
  const paths = Object.keys(original);
  const [path, setPath] = useState(changed[0] ?? paths[0]);
  const [mark, setMark] = useState(true);
  const [view, setView] = useState<View>("presentation");
  const hl = mark ? highlightText[path] ?? [] : [];
  return (
    <div className="sf-side">
      <ViewToggle view={view} onChange={setView} where="step 4" />
      <PageSelector paths={paths} pages={original} value={path} onChange={setPath} changed={changed} />
      <label className="sf-toggle"><input type="checkbox" checked={mark} onChange={(e) => setMark(e.target.checked)} /> Highlight the added text (display only)</label>
      <div className="sf-pair">
        <StorefrontFrame html={original[path] ?? ""} path={path} label={`Original (evaluated)${view === "presentation" ? " · presentation view" : ""}`} view={view} />
        <StorefrontFrame html={patched[path] ?? ""} path={path} label={`Patched (retest)${view === "presentation" ? " · presentation view" : ""}`} highlight={hl} view={view} />
      </div>
    </div>
  );
}
