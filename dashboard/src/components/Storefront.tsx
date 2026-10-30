import { useState } from "react";
import { Pill } from "./ui";

/** Static, inert view of captured HTML. Display-only changes (stated in the UI): links are made unclickable so nothing navigates; optional highlight of inserted text. The page content itself is never edited. */
const INERT = "<style>a{pointer-events:none;cursor:default}</style>";
const HIGHLIGHT_STYLE = "background:#ffe066;outline:2px solid #d9480f;border-radius:2px";

export function frame(html: string, highlight: string[] = []): string {
  let out = html;
  for (const frag of new Set(highlight)) out = out.split(`>${frag}<`).join(`><mark style="${HIGHLIGHT_STYLE}">${frag}</mark><`);
  return out.includes("</head>") ? out.replace("</head>", `${INERT}</head>`) : INERT + out;
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

export function StorefrontFrame({ html, path, label, highlight }: { html: string; path: string; label: string; highlight?: string[] }) {
  return (
    <figure className="sf-frame">
      <figcaption><strong>{label}</strong> <code>{path}</code></figcaption>
      <iframe title={`${label}: ${path}`} sandbox="" srcDoc={frame(html, highlight)} loading="lazy" />
    </figure>
  );
}

export function StorefrontBrowser({ pages, label = "Original pages", initial }: { pages: Record<string, string>; label?: string; initial?: string }) {
  const paths = Object.keys(pages);
  const [path, setPath] = useState(initial && pages[initial] ? initial : paths.includes("/") ? "/" : paths[0]);
  return (
    <div className="sf-browser">
      <PageSelector paths={paths} pages={pages} value={path} onChange={setPath} />
      <StorefrontFrame html={pages[path] ?? ""} path={path} label={label} />
      <p className="muted">Static view of captured pages: links are inactive here, so use the page selector above. Nothing is loaded from the site.</p>
    </div>
  );
}

export function SideBySide({ original, patched, changed, highlightText }: { original: Record<string, string>; patched: Record<string, string>; changed: string[]; highlightText: Record<string, string[]> }) {
  const paths = Object.keys(original);
  const [path, setPath] = useState(changed[0] ?? paths[0]);
  const [mark, setMark] = useState(true);
  const hl = mark ? highlightText[path] ?? [] : [];
  return (
    <div className="sf-side">
      <PageSelector paths={paths} pages={original} value={path} onChange={setPath} changed={changed} />
      <label className="sf-toggle"><input type="checkbox" checked={mark} onChange={(e) => setMark(e.target.checked)} /> Highlight the added text (display only)</label>
      <div className="sf-pair">
        <StorefrontFrame html={original[path] ?? ""} path={path} label="Original (evaluated)" />
        <StorefrontFrame html={patched[path] ?? ""} path={path} label="Patched (retest)" highlight={hl} />
      </div>
    </div>
  );
}
