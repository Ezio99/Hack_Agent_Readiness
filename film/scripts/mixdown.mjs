// The delivery audio master, mixed offline at sample accuracy from the same decisions the film uses (src/narration.ts placement, src/Voice.tsx MIX).
// Why: inside the renderer, volume automation is applied per video frame (30 steps a second), so the music dip under the voice moves in small steps
// that can be heard as zipper noise, and a second mastering pass re-encodes the AAC. Here every gain curve is continuous, nothing is compressed, and
// the result is encoded once.
//
//   1. render the SFX alone:  npx remotion render Preview out/final-v2/sfx-stem.wav --codec=wav --props='{"captions":false,"sfxOnly":true}'
//   2. node scripts/mixdown.mjs out/final-v2/sfx-stem.wav out/final-v2/audio-master.wav
//
// Mix: music (public/audio/music/score.wav) with the MIX dip under every recorded line (smoothstep, MIX.attack before the first word, MIX.release after
// the last); voice lines cut from the levelled act files exactly as Voice.tsx does (same pads and fades); SFX stem as rendered. Then ONE gain towards
// -16 LUFS integrated, capped so the 4x-oversampled true peak stays at or below -2.0 dBTP (leaving room for the AAC encode to land under -1.5).
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { FILM, loadNarration } from './lib/narration.mjs';

const FF = join(FILM, 'node_modules/@remotion/compositor-linux-x64-gnu/ffmpeg');
const SR = 48000, FPS = 30, SPF = SR / FPS;
const MIX = { music: 0.75, musicUnderVoice: 0.27, attack: 8, release: 20 };   // = src/Voice.tsx MIX
const TARGET_LUFS = -16, MAX_TP = -2.0;
const PAN = Math.SQRT1_2;   // the mono voice sits centre at -3 dB per channel, exactly as the renderer places it (the approved balance)
const [sfxPath, outPath] = process.argv.slice(2);
if (!sfxPath || !outPath) { console.log('usage: node scripts/mixdown.mjs SFX.wav OUT.wav'); process.exit(1); }

function wav(path) {   // s16 PCM -> Float32 channels (resampled to 48 kHz by ffmpeg if needed)
  const tmp = join(FILM, 'out/vo-tmp/mixdown-in.wav');
  execFileSync(FF, ['-hide_banner', '-loglevel', 'error', '-y', '-i', path, '-ar', String(SR), '-c:a', 'pcm_s16le', tmp]);
  const b = readFileSync(tmp); let p = 12, ch = 1;
  while (p < b.length) { const id = b.toString('ascii', p, p + 4), n = b.readUInt32LE(p + 4); if (id === 'fmt ') ch = b.readUInt16LE(p + 10); if (id === 'data') { p += 8; break; } p += 8 + n; }
  const n = Math.floor((b.length - p) / 2 / ch), out = Array.from({ length: ch }, () => new Float32Array(n));
  for (let i = 0; i < n; i++) for (let c = 0; c < ch; c++) out[c][i] = b.readInt16LE(p + (i * ch + c) * 2) / 32768;
  return out;
}

const { ACTS } = await loadNarration();
const frames = ACTS.reduce((s, a) => s + a.frames, 0), N = frames * SPF;
const L = new Float32Array(N), R = new Float32Array(N);

// ---- voice: every recorded line, placed as in Voice.tsx ----
const spoken = []; let off = 0;
for (const a of ACTS) {
  if (a.status !== 'recorded') { off += a.frames; continue; }
  const [vo] = wav(join(FILM, 'public', a.vo));
  a.lines.forEach((l, i) => {
    spoken.push([off + l.at, off + l.end]);
    const prevTo = i ? a.lines[i - 1].src.to : 0, nextFrom = a.lines[i + 1]?.src.from ?? Infinity;
    const pre = Math.min(4, Math.floor((l.src.from - prevTo) / 2)), post = Math.min(9, Math.floor((nextFrom - l.src.to) / 2));
    const from = Math.max(0, l.src.from - pre), to = l.src.to + post, len = (to - from) * SPF;
    const dst = (off + l.at - (l.src.from - from)) * SPF, src = from * SPF;
    for (let k = 0; k < len; k++) {
      const f = k / SPF, g = Math.max(0, Math.min(1, (f + 1) / 3, (len / SPF - f) / 4));     // Voice.tsx fades, continuous
      const v = (vo[src + k] ?? 0) * g * PAN, j = dst + k; if (j < 0 || j >= N) continue;
      L[j] += v; R[j] += v;
    }
  });
  off += a.frames;
}

// ---- music, with the dip computed per sample (the same curve as Voice.tsx musicVolume, without its per-frame steps) ----
const music = wav(join(FILM, 'public/audio/music/score.wav'));
const dip = f => { let d = 0; for (const [a, b] of spoken) { if (f < a - MIX.attack - 1 || f > b + MIX.release + 1) continue;
  d = Math.max(d, Math.min(1, (f - (a - MIX.attack)) / MIX.attack, (b + MIX.release - f) / MIX.release)); }
  const x = Math.max(0, d), s = x * x * (3 - 2 * x); return MIX.music + (MIX.musicUnderVoice - MIX.music) * s; };
for (let i = 0; i < N; i++) { const g = dip(i / SPF); L[i] += (music[0][i] ?? 0) * g; R[i] += (music[1]?.[i] ?? music[0][i] ?? 0) * g; }

// ---- SFX stem ----
const sfx = wav(sfxPath);
for (let i = 0; i < N; i++) { L[i] += sfx[0][i] ?? 0; R[i] += sfx[1]?.[i] ?? sfx[0][i] ?? 0; }

// ---- measure: 4x-oversampled true peak, and integrated loudness (ffmpeg EBU R128) ----
function truePeak(chs) {
  const taps = 48, os = 4, h = [];
  for (let ph = 1; ph < os; ph++) { const r = []; for (let k = -taps / 2; k < taps / 2; k++) { const t = k - ph / os;
    r.push((Math.abs(t) < 1e-9 ? 1 : Math.sin(Math.PI * t) / (Math.PI * t)) * (0.5 + 0.5 * Math.cos(Math.PI * t / (taps / 2)))); } h.push(r); }
  let tp = 0, sp = 0;
  for (const y of chs) for (let i = 0; i < y.length; i++) { const a = Math.abs(y[i]); sp = Math.max(sp, a); if (a < 0.25) continue;
    for (const r of h) { let v = 0; for (let k = 0; k < taps; k++) { const j = i + k - taps / 2 + 1; if (j >= 0 && j < y.length) v += y[j] * r[k]; } tp = Math.max(tp, Math.abs(v)); } }
  return { sp: 20 * Math.log10(sp), tp: 20 * Math.log10(Math.max(tp, sp)) };
}
function write(path, chs, gain) {   // s16 with TPDF dither
  const n = chs[0].length, buf = Buffer.alloc(44 + n * 4); let seed = 1;
  const rnd = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296);
  buf.write('RIFF', 0); buf.writeUInt32LE(36 + n * 4, 4); buf.write('WAVE', 8); buf.write('fmt ', 12); buf.writeUInt32LE(16, 16); buf.writeUInt16LE(1, 20);
  buf.writeUInt16LE(2, 22); buf.writeUInt32LE(SR, 24); buf.writeUInt32LE(SR * 4, 28); buf.writeUInt16LE(4, 32); buf.writeUInt16LE(16, 34); buf.write('data', 36); buf.writeUInt32LE(n * 4, 40);
  let clipped = 0;
  for (let i = 0; i < n; i++) for (let c = 0; c < 2; c++) { let v = chs[c][i] * gain * 32767 + (rnd() - rnd()); if (Math.abs(v) > 32767) clipped++;
    buf.writeInt16LE(Math.max(-32767, Math.min(32767, Math.round(v))), 44 + (i * 2 + c) * 2); }
  writeFileSync(path, buf); return clipped;
}
const lufs = path => { const o = execFileSync('/bin/sh', ['-c', `"${FF}" -hide_banner -nostats -i "${path}" -af loudnorm=print_format=json -f null - 2>&1`], { maxBuffer: 1 << 26 }).toString();
  const j = JSON.parse(o.slice(o.lastIndexOf('{'), o.lastIndexOf('}') + 1)); return { i: Number(j.input_i), tp: Number(j.input_tp), lra: Number(j.input_lra) }; };

const pre = truePeak([L, R]);
write(outPath, [L, R], 1);
const m0 = lufs(outPath);
const gainDb = Math.min(TARGET_LUFS - m0.i, MAX_TP - pre.tp);
const clipped = write(outPath, [L, R], 10 ** (gainDb / 20));
const m1 = lufs(outPath);
console.log(`mix (unity): ${m0.i.toFixed(1)} LUFS, sample peak ${pre.sp.toFixed(2)} dBFS, true peak ${pre.tp.toFixed(2)} dBTP, LRA ${m0.lra.toFixed(1)}`);
console.log(`master: gain ${gainDb >= 0 ? '+' : ''}${gainDb.toFixed(2)} dB (one gain, no compression or limiting) -> ${m1.i.toFixed(1)} LUFS, true peak ${m1.tp.toFixed(2)} dBTP (ffmpeg), ${clipped} clipped samples; ${(N / SR).toFixed(3)} s`);
