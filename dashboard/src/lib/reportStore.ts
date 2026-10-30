// Optional persistence of an explicitly loaded report for the current browser TAB session only (sessionStorage): it survives a reload, is cleared when the tab or window closes,
// is never sent anywhere, and is never written for the built-in synthetic fixtures. Every function fails soft: storage may be disabled, full or throw.
export const KEY = "agent-readiness.loaded-report.v1";
export const MAX_BYTES = 2_000_000;                                           // sessionStorage quotas are ~5 MB per origin; a public export is ~50 KB

export interface Stored { name: string; text: string }
export type SaveResult = { ok: true } | { ok: false; reason: "unavailable" | "too-large" | "quota" };

const store = (): Storage | null => { try { return typeof window === "undefined" ? null : window.sessionStorage; } catch { return null; } };

export function saveReport(name: string, text: string): SaveResult {
  const s = store();
  if (!s) return { ok: false, reason: "unavailable" };
  if (text.length > MAX_BYTES) return { ok: false, reason: "too-large" };
  try { s.setItem(KEY, JSON.stringify({ name, text } satisfies Stored)); return { ok: true }; } catch { return { ok: false, reason: "quota" }; }
}

export function loadStored(): Stored | null {
  const s = store();
  if (!s) return null;
  try {
    const o = JSON.parse(s.getItem(KEY) ?? "null");
    return o && typeof o.name === "string" && typeof o.text === "string" ? o : null;
  } catch { return null; }
}

export function clearStored(): boolean {
  const s = store();
  if (!s) return false;
  try { s.removeItem(KEY); return true; } catch { return false; }
}

export const SAVE_PROBLEM: Record<Exclude<SaveResult, { ok: true }>["reason"], string> = {
  unavailable: "This browser is not allowing session storage here.",
  "too-large": "This report is too large to keep in session storage.",
  quota: "Session storage is full or refused the write.",
};
