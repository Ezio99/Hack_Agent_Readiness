/** Typed access to the recorded live Muse Spark evaluation `eval-9aaac35c` (one paired repetition,
 *  2 Nov 2026). The JSON is the hosted API's public projection, exported by scripts/export_demo_evidence.py.
 *  Nothing here is simulated: every step, quote, number and screenshot comes from that recording. */
import raw from './eval-9aaac35c.json';

export interface Action { name: string; target: string | null }
export interface Step { step: number; path: string | null; goal: string | null; memory: string | null; assessment: string | null; actions: Action[]; error: string | null; done: boolean; frame: string | null }
export interface Trial { arm: 'original' | 'modified'; task: number; question: string; state: string; errors: string[]; steps: Step[] }
export interface Row { arm: 'Original' | 'Modified'; task: number; state: string; outcome: string; requests: number; page_views: number; steps: number; elapsed_seconds: number }

const frameUrls = import.meta.glob('./frames/*.webp', { eager: true, query: '?url', import: 'default' }) as Record<string, string>;

export const evidence = raw as unknown as {
  source: { job: string; repetition: number; mode: string; evidence_origin: string; model: string; agent_profile: string; created_at: number; started_at: number; finished_at: number };
  tasks: { task: number; question: string; limits: { max_model_requests: number; max_steps: number; timeout_seconds: number } }[];
  rows: Row[];
  summary: Record<'Original' | 'Modified', { completed: number; evidence_supported_passes: number; strict_passes: number; requests_total: number; requests_mean: number; page_views_mean: number; steps_mean: number; elapsed_mean: number }>;
  assessment: { frozen_rule: string; exploratory: string; evidence_origin: string };
  frozen_rule: { id: string; verdict: string; reason: string; pairs: number; pass_delta: number; request_change: number; p_pass: number; p_requests: number; alpha: number; min_pairs: number };
  exploratory_rule: { id: string; verdict: string };
  change: { label: string; owner_selected: boolean; exploratory: boolean; validation: string };
  insights: {
    runs: { Original: number; Modified: number };
    stats: Record<'Original' | 'Modified', Record<string, number>>;
    findings: { id: string; severity: 'high' | 'medium' | 'low' | 'info'; title: string; observed: string }[];
    suggestions: { for: string; text: string; status: string }[];
    method: string;
  };
  trials: Trial[];
  frames: Record<string, { width: number; height: number }>;
};

export const frame = (key: string | null | undefined): string | undefined => key ? frameUrls[`./frames/${key}.webp`] : undefined;
export const trial = (arm: Trial['arm'], task: number) => evidence.trials.find(t => t.arm === arm && t.task === task)!;
export const row = (arm: Row['arm'], task: number) => evidence.rows.find(r => r.arm === arm && r.task === task)!;
export const shortId = evidence.source.job.slice(0, 13);
export const recordedOn = new Date(evidence.source.started_at * 1000).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Australia/Sydney' });

const S = evidence.summary;
export const headline = {
  passes: { original: S.Original.evidence_supported_passes, modified: S.Modified.evidence_supported_passes, of: S.Original.completed },
  requests: { original: S.Original.requests_total, modified: S.Modified.requests_total, fewerPct: Math.round(100 * (S.Original.requests_total - S.Modified.requests_total) / S.Original.requests_total) },
  seconds: { original: Math.round(S.Original.elapsed_mean), modified: Math.round(S.Modified.elapsed_mean) },
  steps: { original: S.Original.steps_mean, modified: S.Modified.steps_mean },
};

/** Item (detail) pages are `/hire/<slug>`; the listing is `/hire`. */
export const isItemPage = (path: string | null) => !!path && /^\/hire\/[^/]+$/.test(path);
export const ITEMS = 16;   // stated on the recorded site: "All 16 machines in our yard"

export const ACTION_GLYPH: Record<string, string> = { Navigate: '↗', Click: '◉', Scroll: '↕', 'Find elements': '⌕', 'Search page': '⌕', Extract: '⇲', 'Go back': '←', Answer: '✓', Type: '⌨', Wait: '…' };
export function describe(a: Action): string {
  if (!a.target) return a.name;
  return `${a.name} · ${a.target}`;
}
