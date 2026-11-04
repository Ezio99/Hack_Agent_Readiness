import React from 'react';
import { Img, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { Box } from '../evidence';
import { C, F, ease } from '../theme/tokens';

/** A page image placed in CSS-pixel space: `scale` = on-screen px per CSS px; `cssWidth` = the image's width in CSS px. */
export function PageImage({ src, cssWidth, scale, scrollY = 0, opacity = 1 }: { src: string; cssWidth: number; scale: number; scrollY?: number; opacity?: number }) {
  return <Img src={staticFile(src)} style={{ position: 'absolute', left: 0, top: -scrollY * scale, width: cssWidth * scale, opacity }} />;
}

/** Highlight of a RECORDED action's target (the box comes from the frozen page, the action from the agent's step record): an outline that
 *  draws itself, a cursor that arrives, and a click pulse at `clickAt`. Nothing here is an action the agent did not take. */
export function ActionHighlight({ box, scale, start, clickAt }: { box: Box; scale: number; start: number; clickAt: number }) {
  const f = useCurrentFrame();
  const pad = 8, x = (box.x - pad) * scale, y = (box.y - pad) * scale, w = (box.width + 2 * pad) * scale, h = (box.height + 2 * pad) * scale;
  const per = 2 * (w + h);
  const draw = interpolate(f, [start, start + 18], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease });
  const cx = x + w * 0.62, cy = y + h * 0.62;
  const arrive = interpolate(f, [clickAt - 22, clickAt - 2], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease });
  const curX = interpolate(arrive, [0, 1], [cx + 140, cx]), curY = interpolate(arrive, [0, 1], [cy + 90, cy]);
  const pulse = interpolate(f, [clickAt, clickAt + 20], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const press = f >= clickAt && f < clickAt + 4 ? 0.88 : 1;
  return <svg style={{ position: 'absolute', inset: 0, overflow: 'visible', pointerEvents: 'none' }} width="100%" height="100%">
    <rect x={x} y={y} width={w} height={h} rx={10} fill="rgba(43,59,230,.07)" stroke={C.signalStrong} strokeWidth={3}
      strokeDasharray={per} strokeDashoffset={per * (1 - draw)} opacity={draw > 0 ? 1 : 0} />
    {f >= clickAt && pulse < 1 && <circle cx={cx} cy={cy} r={10 + 46 * pulse} fill="none" stroke={C.signalStrong} strokeWidth={3} opacity={1 - pulse} />}
    {arrive > 0 && <g transform={`translate(${curX} ${curY}) scale(${press})`} opacity={Math.min(1, arrive * 3)}>
      <path d="M0 0 L0 26 L7 20 L12 31 L17 29 L12 18 L21 18 Z" fill="#121211" stroke="#fff" strokeWidth={2} strokeLinejoin="round" />
    </g>}
  </svg>;
}

/** Text that types itself from `start` at `cps` characters per second, with a caret while typing. */
export function Typed({ text, start, cps = 55, style }: { text: string; start: number; cps?: number; style?: React.CSSProperties }) {
  const f = useCurrentFrame();
  const n = Math.max(0, Math.min(text.length, Math.floor(((f - start) / 30) * cps)));
  const typing = n > 0 && n < text.length;
  return <span style={style}>{text.slice(0, n)}{typing && <span style={{ color: C.signal }}>▍</span>}
    <span style={{ visibility: 'hidden' }}>{text.slice(n)}</span></span>;
}

/** The interaction budget: `max` segments, `used` lit. (Signature animation 1 builds on this in Act 2.) */
export function StepBudget({ used, max, label }: { used: number; max: number; label: string }) {
  return <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
    <span style={{ fontFamily: F.mono, fontSize: 15, letterSpacing: '.14em', color: C.ink2, textTransform: 'uppercase', whiteSpace: 'nowrap' }}>{label}</span>
    <div style={{ display: 'flex', gap: 5 }}>{Array.from({ length: max }, (_, i) =>
      <span key={i} style={{ width: 18, height: 8, borderRadius: 2, background: i < used ? C.signal : 'rgba(237,234,227,.14)' }} />)}</div>
  </div>;
}
