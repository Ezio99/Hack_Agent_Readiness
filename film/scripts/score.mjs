// Original temp score + sound effects for the film, synthesised from scratch (no samples, no third-party audio, no service): a restrained
// electronic ambient bed and soft UI sounds. Deterministic. Writes public/audio/music/score.wav (the music track, film time 0:00 onwards) and
// public/audio/sfx/*.wav. Music and SFX are separate tracks; voiceover goes in public/audio/vo/<act>.wav. Replaceable by a licensed score later.
//   node scripts/score.mjs
// Section times (seconds, film time) mirror the narration cue sheet (src/narration.ts): Act 1 = 0-25 s, Act 2 = 25-75 s, Act 3 = 75-115 s, Act 4 = 115-155 s, Act 5 = 155-180 s.
import { mkdirSync, writeFileSync } from 'node:fs';
import { loadNarration } from './lib/narration.mjs';

// Every time below is written on the DESIGNED timeline; W() moves it to the actual one, so once the voice is recorded (and an act runs longer or a
// line lands later) the harmony changes, bells and pulse stay on the picture. Notes themselves are never stretched. Identity without a voice.
const { filmWarp: W, ACTS } = await loadNarration();

const SR = 48000;
const DUR = ACTS.reduce((s, a) => s + a.frames, 0) / 30;
const N = SR * DUR;
const midi = m => 440 * 2 ** ((m - 69) / 12);
let seed = 7; const rnd = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296);

// ---- sections: [start s, chord (midi), brightness, level] ----
const SECTIONS = [
  [0.0,  [50, 57, 61, 64, 66], 2.2, 0.75],   // D maj9 (add6): the human website, warm and curious
  [10.5, [47, 54, 57, 62, 64], 1.4, 0.70],   // B m(add9): into the recorded agent, darker
  [19.2, [43, 50, 57, 59, 66], 1.8, 0.62],   // G maj7(#11)-ish: brand, open, suspended
  [25.0, [47, 54, 57, 62, 64], 1.3, 0.60],   // Act 2: the hunt
  [37.0, [43, 50, 55, 59, 61], 1.5, 0.62],   // G(#11): the loop
  [47.0, [45, 52, 55, 60, 62], 1.7, 0.66],   // A m(add9)/: tension rising
  [58.6, [38, 45, 50],         0.9, 0.45],   // "out of steps": everything drops to a low drone
  [64.0, [50, 57, 62, 64, 69], 2.6, 0.62],   // diagnosis: clarity, D(add9) bright
  [75.0, [45, 52, 57, 59, 64], 1.7, 0.55],   // Act 3 bridge: the diagnosis isolated, A sus2, still
  [81.0, [50, 57, 61, 64, 66], 2.6, 0.70],   // the transformation: warm D maj9 returns (the human website, now for agents too)
  [88.0, [43, 50, 54, 59, 66], 2.8, 0.74],   // G maj9: facts land, the catalogue resolves
  [94.5, [47, 54, 59, 62, 66], 2.8, 0.72],   // B m11: all four courses, visible
  [98.6, [45, 52, 57, 61, 64], 2.2, 0.60],   // A: the dead end, fixed
  [104.6, [42, 50, 54, 57, 62], 2.2, 0.60],  // D/F#: structured data
  [110.3, [47, 54, 57, 62, 66], 1.9, 0.62],  // B m(add9): same task again, anticipation
  [120.0, [47, 54, 57, 62, 64], 1.3, 0.60],  // Act 4, Before (busy, tense)
  [129.3, [50, 57, 61, 64, 69], 2.8, 0.72],  // After: release, bright D maj9
  [138.3, [43, 50, 54, 59, 62, 66], 3.0, 0.80], // 0/3 -> 3/3: the lift, G maj9 (wide)
  [143.7, [45, 52, 57, 59, 64], 2.6, 0.72],  // the reductions: A sus, forward motion
  [150.3, [50, 57, 62, 66, 69], 2.8, 0.74],  // "a website that finally works for it": home, D
  [155.0, [50, 57, 61, 64, 69], 2.4, 0.62],  // Act 5, today: the product, calm
  [160.0, [43, 50, 55, 61, 66], 2.6, 0.66],  // tomorrow: G lydian, open, expansive
  [167.0, [40, 47, 54, 59, 62], 2.6, 0.66],  // E m11: which sites, reliable, where to succeed
  [173.0, [50, 57, 62, 64, 66, 69], 2.8, 0.70], // the mark and tagline: D maj9, long tail
].map(([t, ...r]) => [W(t), ...r]);
const secAt = t => { let i = 0; for (let j = 0; j < SECTIONS.length; j++) if (t >= SECTIONS[j][0]) i = j; return i; };

const L = new Float32Array(N), R = new Float32Array(N);

// ---- pad: additive, 3 detuned voices per note, harmonic roll-off = brightness; 2.5 s crossfades between sections ----
for (let s = 0; s < SECTIONS.length; s++) {
  const [t0, chord, bright, level] = SECTIONS[s];
  const t1 = s + 1 < SECTIONS.length ? SECTIONS[s + 1][0] : DUR;
  const a = Math.max(0, Math.floor((t0 - (s ? 1.25 : 0)) * SR)), b = Math.min(N, Math.floor((t1 + 1.25) * SR));
  const fadeIn = s ? 2.5 : 4.0, fadeOut = 2.5;
  for (const m of chord) {
    for (const det of [-0.07, 0, 0.06]) {
      const f0 = midi(m + det), ph = rnd() * 6.28, pan = 0.5 + det * 4 + (rnd() - 0.5) * 0.3;
      const harms = [];
      for (let h = 1; h <= 7; h++) harms.push([h, (1 / h) * Math.exp(-(h - 1) / bright)]);
      for (let i = a; i < b; i++) {
        const t = i / SR;
        const env = Math.min(1, (t - (t0 - (s ? 1.25 : 0))) / fadeIn) * Math.min(1, ((t1 + 1.25) - t) / fadeOut);
        if (env <= 0) continue;
        const trem = 1 + 0.08 * Math.sin(2 * Math.PI * 0.13 * t + ph);
        let v = 0;
        for (const [h, amp] of harms) v += amp * Math.sin(2 * Math.PI * f0 * h * t + ph * h);
        v *= env * trem * level * 0.022;
        L[i] += v * (1 - pan * 0.6); R[i] += v * (0.4 + pan * 0.6);
      }
    }
  }
}

// ---- bells: sparse pentatonic notes in the human-website section and the diagnosis ----
const bell = (t, m, g) => { const f = midi(m), i0 = Math.floor(W(t) * SR), len = Math.floor(2.2 * SR), pan = rnd();
  for (let i = 0; i < len && i0 + i < N; i++) { const x = i / SR, e = Math.exp(-x * 2.2) * Math.min(1, x / 0.004);
    const v = g * e * (Math.sin(2 * Math.PI * f * x) + 0.25 * Math.sin(2 * Math.PI * f * 2.76 * x) * Math.exp(-x * 4));
    L[i0 + i] += v * (1 - pan * 0.5); R[i0 + i] += v * (0.5 + pan * 0.5); } };
[[1.2, 74], [2.9, 78], [4.4, 81], [5.9, 76], [7.2, 83], [8.6, 78]].forEach(([t, m]) => bell(t, m, 0.035));
[[65.0, 74], [66.6, 78], [68.1, 81], [69.8, 86], [71.4, 83], [73.0, 81]].forEach(([t, m]) => bell(t, m, 0.03));
// Act 3: a rising cascade as the facts land on the card (~86.7 s), and when the whole catalogue resolves (~91 s)
[[130.8, 74], [131.6, 78], [132.6, 81], [138.6, 86], [138.9, 90], [139.2, 93], [162, 74], [163.4, 79], [164.8, 83], [166.2, 86], [168, 81], [169.6, 83], [171.2, 86], [175.3, 86], [176.1, 90], [176.9, 93]].forEach(([t, m]) => bell(t, m, 0.028));
[[86.2, 74], [86.4, 76], [86.6, 78], [86.8, 81], [87.0, 83], [87.2, 85], [87.4, 86], [91.2, 86], [91.9, 90], [92.6, 93]].forEach(([t, m]) => bell(t, m, 0.03));

// ---- pulse: a soft low heartbeat from the recorded agent onwards; in Act 2 it speeds up as the budget drains, and stops at "out of steps" ----
const kick = (t, g) => { const i0 = Math.floor(W(t) * SR), len = Math.floor(0.35 * SR);
  for (let i = 0; i < len && i0 + i < N; i++) { const x = i / SR, f = 45 + 70 * Math.exp(-x * 30), e = Math.exp(-x * 9) * Math.min(1, x / 0.002);
    const v = g * e * Math.sin(2 * Math.PI * f * x * (1 + 0)); L[i0 + i] += v; R[i0 + i] += v; } };
const tick = (t, g) => { const i0 = Math.floor(W(t) * SR), len = Math.floor(0.05 * SR); let lp = 0;
  for (let i = 0; i < len && i0 + i < N; i++) { const x = i / SR, n = rnd() * 2 - 1; const hp = n - lp; lp += 0.35 * (n - lp);
    const v = g * hp * Math.exp(-x * 120); L[i0 + i] += v * 0.8; R[i0 + i] += v; } };
const bpmAt = t => t < 25 ? 72 : t < 37 ? 76 : t < 58.6 ? 76 + (t - 37) / 21.6 * 44 : t < 120 ? 72 : t < 129.3 ? 112 : t < 143.7 ? 72 : 84;   // Act 2 loop 72 -> 120; Act 4 Before 112; the reductions 84
{ let t = 10.6; while (t < 115) {
  if (t >= 58.6 && t < 111.5) { t = 111.5; continue; }   // silence after 'out of steps'; the heartbeat returns only for the re-run set-up
  if (t >= 129.3 && t < 143.7) { t = 143.7; continue; }   // After + 0/3 -> 3/3: no pulse, just harmony
  if (t >= 150.3) break;                                   // Act 5: no pulse
  if (!(t > 19.4 && t < 25.0)) {                       // rest under the brand reveal
    const g = t < 25 ? 0.10 : t > 110 ? 0.12 : 0.12 + 0.08 * Math.min(1, (t - 25) / 33);
    kick(t, g);
    if ((t > 37 && t < 58.6) || (t > 120 && t < 129.3)) tick(t + 30 / bpmAt(t), t < 60 ? 0.012 + 0.02 * (t - 37) / 21.6 : 0.03);
  }
  t += 60 / bpmAt(t); } }

// ---- reverb (Schroeder: 4 combs + 2 allpasses per channel) ----
const reverb = (x, delays, fb = 0.78, wet = 0.32) => {
  const out = new Float32Array(x.length);
  for (const d of delays) { const buf = new Float32Array(d); let p = 0, lp = 0;
    for (let i = 0; i < x.length; i++) { const y = buf[p]; lp = y * 0.6 + lp * 0.4; buf[p] = x[i] + lp * fb; p = (p + 1) % d; out[i] += y / delays.length; } }
  for (const d of [556, 441]) { const buf = new Float32Array(d); let p = 0;
    for (let i = 0; i < x.length; i++) { const b = buf[p], y = -out[i] * 0.5 + b; buf[p] = out[i] + b * 0.5; p = (p + 1) % d; out[i] = y; } }
  for (let i = 0; i < x.length; i++) out[i] = x[i] * (1 - wet) + out[i] * wet * 2.2;
  return out;
};
const Lw = reverb(L, [1557, 1617, 1491, 1422]), Rw = reverb(R, [1580, 1640, 1516, 1445]);

// ---- master: gentle saturation, normalise to -3 dBFS peak, 1.5 s fade at the end ----
const write = (path, chans, sr = SR) => {
  const n = chans[0].length, ch = chans.length, buf = Buffer.alloc(44 + n * ch * 2);
  buf.write('RIFF', 0); buf.writeUInt32LE(36 + n * ch * 2, 4); buf.write('WAVE', 8); buf.write('fmt ', 12); buf.writeUInt32LE(16, 16);
  buf.writeUInt16LE(1, 20); buf.writeUInt16LE(ch, 22); buf.writeUInt32LE(sr, 24); buf.writeUInt32LE(sr * ch * 2, 28); buf.writeUInt16LE(ch * 2, 32);
  buf.writeUInt16LE(16, 34); buf.write('data', 36); buf.writeUInt32LE(n * ch * 2, 40);
  for (let i = 0; i < n; i++) for (let c = 0; c < ch; c++) buf.writeInt16LE(Math.max(-32767, Math.min(32767, Math.round(chans[c][i] * 32767))), 44 + (i * ch + c) * 2);
  writeFileSync(path, buf);
};
const master = (chans, peakDb = -3) => {
  let peak = 1e-9; for (const c of chans) for (let i = 0; i < c.length; i++) { c[i] = Math.tanh(c[i] * 1.4) / 1.4; peak = Math.max(peak, Math.abs(c[i])); }
  const g = 10 ** (peakDb / 20) / peak; for (const c of chans) for (let i = 0; i < c.length; i++) c[i] *= g; return chans;
};
for (let i = 0; i < 1.5 * SR; i++) { const g = i / (1.5 * SR); Lw[N - 1 - i] *= g; Rw[N - 1 - i] *= g; }
mkdirSync('public/audio/music', { recursive: true }); mkdirSync('public/audio/sfx', { recursive: true }); mkdirSync('public/audio/vo', { recursive: true });
write('public/audio/music/score.wav', master([Lw, Rw]));

// ---- sound effects (mono) ----
const sfx = (dur, fn) => { const n = Math.floor(dur * SR), x = new Float32Array(n); for (let i = 0; i < n; i++) x[i] = fn(i / SR); return x; };
let lp2 = 0;
write('public/audio/sfx/click.wav', master([sfx(0.08, x => { const n = rnd() * 2 - 1; lp2 += 0.2 * (n - lp2);
  return 0.6 * lp2 * Math.exp(-x * 400) + 0.5 * Math.sin(2 * Math.PI * 1750 * x) * Math.exp(-x * 90); })], -3));
write('public/audio/sfx/tick.wav', master([sfx(0.12, x => Math.sin(2 * Math.PI * 1180 * x) * Math.exp(-x * 45) + 0.4 * Math.sin(2 * Math.PI * 2360 * x) * Math.exp(-x * 80))], -5));
write('public/audio/sfx/chime.wav', master([sfx(2.4, x => [62, 69, 74].reduce((v, m, j) => v + Math.sin(2 * Math.PI * midi(m) * x) * Math.exp(-(x - j * 0.09) * 2.4) * (x > j * 0.09 ? 1 : 0), 0))], -6));
write('public/audio/sfx/stop.wav', master([sfx(1.2, x => Math.sin(2 * Math.PI * (300 * Math.exp(-x * 1.2)) * x) * Math.exp(-x * 3.2) * Math.min(1, x / 0.01)
  + 0.6 * Math.sin(2 * Math.PI * (55) * x) * Math.exp(-x * 4))], -3));
console.log('score.wav', DUR, 's; sfx: click tick chime stop');
