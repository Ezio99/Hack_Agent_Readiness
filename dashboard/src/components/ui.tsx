import type { ReactNode } from "react";
import type { Attribution } from "../lib/metrics";

export const ARM_LABEL = { A: "Arm A — availability on listing cards", B: "Arm B — availability only on detail pages" } as const;

export function Kpi({ label, value, note, tone }: { label: string; value: ReactNode; note?: ReactNode; tone?: "a" | "b" | "neutral" | "bad" | "good" }) {
  return (
    <div className={`kpi kpi-${tone ?? "neutral"}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {note ? <div className="kpi-note">{note}</div> : null}
    </div>
  );
}

export function Callout({ title, children, tone = "info" }: { title: string; children: ReactNode; tone?: "info" | "warn" | "bad" | "good" }) {
  return (
    <aside className={`callout callout-${tone}`}>
      <h3>{title}</h3>
      <div>{children}</div>
    </aside>
  );
}

/** Paired horizontal bars (A vs B) with a text alternative. Values are numbers in `unit`; `format` renders labels. */
export function PairedBars({ title, a, b, format, max }: { title: string; a: number; b: number; format: (x: number) => string; max?: number }) {
  const top = max ?? Math.max(a, b, 1e-9);
  const row = (arm: "A" | "B", v: number) => (
    <div className="bar-row" key={arm}>
      <span className="bar-label">{arm === "A" ? "A · cards" : "B · detail only"}</span>
      <span className="bar-track" aria-hidden="true">
        <span className={`bar bar-${arm}`} style={{ width: `${Math.max(2, (v / top) * 100)}%` }} />
      </span>
      <span className="bar-value">{format(v)}</span>
    </div>
  );
  return (
    <figure className="paired" role="group" aria-label={`${title}: arm A ${format(a)}, arm B ${format(b)}`}>
      <figcaption>{title}</figcaption>
      {row("A", a)}
      {row("B", b)}
    </figure>
  );
}

const SEG = [
  { key: "required", label: "Website-required navigation", cls: "seg-required" },
  { key: "agent", label: "Agent-induced extra requests", cls: "seg-agent" },
  { key: "tool", label: "Agent–tool interface loop", cls: "seg-tool" },
] as const;

export function AttributionLegend() {
  return (
    <ul className="legend" aria-label="Legend">
      {SEG.map((s) => (
        <li key={s.key}><span className={`swatch ${s.cls}`} aria-hidden="true" />{s.label}</li>
      ))}
    </ul>
  );
}

/** Stacked bar of mean model requests per run split into the three sources; negative agent share is clamped in the graphic only
 *  (the table of numbers beside it always shows the true value). */
export function AttributionBar({ arm, att, max }: { arm: "A" | "B"; att: Attribution; max: number }) {
  const parts = SEG.map((s) => ({ ...s, v: Math.max(0, att[s.key]) }));
  return (
    <div className="stack-row">
      <span className="bar-label">{arm === "A" ? "A · cards" : "B · detail only"}</span>
      <span className="stack-track" role="img" aria-label={`Arm ${arm} mean requests per run: ${att.required.toFixed(2)} website-required, ${att.agent.toFixed(2)} agent-induced, ${att.tool.toFixed(2)} agent-tool loop, total ${att.total.toFixed(2)}`}>
        {parts.map((p) => (p.v > 0 ? <span key={p.key} className={`seg ${p.cls}`} style={{ width: `${(p.v / max) * 100}%` }} title={`${p.label}: ${p.v.toFixed(2)}`} /> : null))}
      </span>
      <span className="bar-value">{att.total.toFixed(2)}</span>
    </div>
  );
}

export function Pill({ children, tone }: { children: ReactNode; tone: "pass" | "fail" | "neutral" | "warn" }) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}
