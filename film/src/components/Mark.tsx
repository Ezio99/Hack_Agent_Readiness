import { interpolate, useCurrentFrame } from 'remotion';
import { C, ease } from '../theme/tokens';
/** The Agent Readiness mark (dashboard/src/site/Shell.tsx `Mark`): an outlined square that draws itself, then the signal square settles in. */
export function Mark({ size, start }: { size: number; start: number }) {
  const f = useCurrentFrame();
  const draw = interpolate(f, [start, start + 28], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease });
  const inner = interpolate(f, [start + 22, start + 40], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease });
  const per = 4 * 16.5;
  return <svg width={size} height={size} viewBox="0 0 18 18">
    <rect x=".75" y=".75" width="16.5" height="16.5" rx="2.5" fill="none" stroke={C.ink} strokeWidth="1.1" strokeDasharray={per} strokeDashoffset={per * (1 - draw)} />
    <rect x={9 + 3.25 * (1 - inner)} y={9 + 3.25 * (1 - inner)} width={6.5 * inner} height={6.5 * inner} rx="1" fill={C.signal} />
  </svg>;
}
