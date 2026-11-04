import { Easing } from 'remotion';
/** Colours and type from the product's dark theme (dashboard/src/site/site.css, `.ar-night`), plus the Larkspur site's own violet. */
export const C = {
  bg: '#0B0B0A', paper: '#0E0E0D', sheet: '#1B1B19', ink: '#EDEAE3', ink2: '#B9B5AC', ink3: '#8D8981',
  rule: 'rgba(237,234,227,.12)', signal: '#7280F2', signalStrong: '#2B3BE6', signal2: '#9AA4FF',
  rust: '#D86C45', pass: '#5FBF88', larkspur: '#3D2A7A',
};
export const F = { serif: "'AR Newsreader', Georgia, serif", sans: "'AR Geist', system-ui, sans-serif", mono: "'AR Geist Mono', ui-monospace, monospace" };
/** The product's motion curve (--ease: cubic-bezier(.2,.7,.1,1)) and a softer in-out for camera moves. */
export const ease = Easing.bezier(0.2, 0.7, 0.1, 1);
export const camera = Easing.bezier(0.65, 0, 0.35, 1);
export const FPS = 30;
