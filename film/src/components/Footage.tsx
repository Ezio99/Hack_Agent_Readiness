import { Img, staticFile, useCurrentFrame } from 'remotion';
import { C, F } from '../theme/tokens';

/** A screen recording of the production application (scripts/capture_screen.py): real frames, shown at their real timestamps. At film frame
 *  `start + n` it shows the last frame recorded at or before `from + n/30 * speed` seconds; speed > 1 is labelled where it is used. */
export type Recording = { frames: { t: number; file: string }[]; events: { t: number; event: string }[] };
/** `cuts`: optional [recording second, film frame] pairs: from each film frame on, play from that recording second (a plain edit cut).
 *  `redact`: boxes in the recording's device pixels to cover with the page's own background (internal identifiers only). */
export function Footage({ rec, dir, from, start, speed = 1, width, cuts = [], redact = [], srcWidth = 3198, zoom }: { rec: Recording; dir: string; from: number; start: number;
  speed?: number; width: number; cuts?: [number, number][]; redact?: { x: number; y: number; w: number; h: number; color: string }[]; srcWidth?: number;
  /** a closer framing of the same footage: the recording's device-pixel point to centre on, and how much closer (a crop, nothing added) */
  zoom?: { x: number; y: number; scale: number } }) {
  const f = useCurrentFrame();
  const cut = [...cuts].reverse().find(([, at]) => f >= at);
  const t = cut ? cut[0] + (f - cut[1]) / 30 * speed : from + Math.max(0, f - start) / 30 * speed;
  const k = width / srcWidth;
  let lo = 0, hi = rec.frames.length - 1;
  while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (rec.frames[mid].t <= t) lo = mid; else hi = mid - 1; }
  const H = width * 1800 / srcWidth, z = zoom?.scale ?? 1;
  const tx = zoom ? Math.min(0, Math.max(width - width * z, width / 2 - zoom.x * k * z)) : 0, ty = zoom ? Math.min(0, Math.max(H - H * z, H / 2 - zoom.y * k * z)) : 0;
  return <div style={{ position: 'relative', width, height: H, overflow: 'hidden' }}>
    <div style={{ position: 'absolute', left: 0, top: 0, width, transform: `translate(${tx}px, ${ty}px) scale(${z})`, transformOrigin: '0 0' }}>
      <Img src={staticFile(`captures/screen/${dir}/${rec.frames[lo].file}`)} style={{ width, display: 'block' }} />
      {redact.map((r, i) => <div key={i} style={{ position: 'absolute', left: r.x * k, top: r.y * k, width: r.w * k, height: r.h * k, background: r.color }} />)}
    </div>
  </div>;
}
/** Seconds into the recording at which an event was logged (e.g. "clicked Run (one launch)"). */
export const eventAt = (rec: Recording, startsWith: string) => {
  const e = rec.events.find(x => x.event.startsWith(startsWith)); if (!e) throw new Error(`recording has no event "${startsWith}"`); return e.t;
};

/** The two labels that keep the evidence apart: a separate live demonstration vs the canonical paired evaluation. Shown for the whole clip. */
export function EvidenceLabel({ kind, detail }: { kind: 'live' | 'canonical'; detail: string }) {
  const live = kind === 'live';
  return <div style={{ display: 'inline-flex', alignItems: 'center', gap: 12, padding: '7px 16px', borderRadius: 999, background: 'rgba(11,11,10,.88)',
    border: `1.5px solid ${live ? '#E0B54F' : C.pass}`, fontFamily: F.mono, fontSize: 15, letterSpacing: '.12em', color: live ? '#F2C14E' : C.pass, textTransform: 'uppercase' }}>
    {live && <span style={{ width: 9, height: 9, borderRadius: 9, background: '#E0B54F' }} />}
    <span>{live ? 'Separate live demonstration' : 'Canonical paired evaluation'}</span><span style={{ color: C.ink2 }}>{detail}</span>
  </div>;
}
