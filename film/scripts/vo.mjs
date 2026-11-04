// Voiceover integration: measure the recorded voice and write data/vo.json, which src/narration.ts uses to place every line (the animation follows
// the voice; the voice is never stretched, sped up or re-ordered).
//
//   node scripts/vo.mjs align              the five act files in public/audio/vo/ (act1..act5 .wav/.mp3/.m4a/.flac)
//   node scripts/vo.mjs align --src DIR --source scratch     the same from another folder (e.g. a scratch voice for timing tests only)
//   node scripts/vo.mjs audition           every clip in public/audio/vo/audition/ (dan-1.mp3, haseeb-2.wav, ...) -> data/audition.json
//   node scripts/vo.mjs clear              back to placeholder timing (no voice)
//
// For each file:
//   1. Loudness: measured (EBU R128) and brought to -16 LUFS integrated with ONE fixed gain; a transparent look-ahead peak limiter keeps the
//      rare peaks under -2 dBFS (no compression, no time change). The levelled copy is written to public/audio/vo/mix/ and is what the film plays.
//   2. Lines: if ElevenLabs character timestamps sit beside the file (<name>.alignment.json, from the API's with-timestamps endpoint), each line's
//      start and end are read from them. Otherwise speech is found from the waveform (10 ms energy frames) and the speech runs are grouped into the
//      act's lines by a small dynamic programme: cut at the pauses, with each line's duration close to its share of the text.
//   3. Checks: every line's speaking rate is compared with the act's median; an outlier is reported (likely a mis-cut) so it can be fixed by hand in
//      public/audio/vo/overrides.json: { "a2.facts": { "from": 1.20, "to": 6.85 } } (seconds in the file).
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { AUDITION, FILM, loadNarration } from './lib/narration.mjs';

const FF = join(FILM, 'node_modules/@remotion/compositor-linux-x64-gnu/ffmpeg');
const FPS = 30, TARGET_LUFS = -16, CEILING_DB = -1.5, MAX_LIMIT = 1;
const VO = join(FILM, 'public/audio/vo'), MIX = join(VO, 'mix'), TMP = join(FILM, 'out/vo-tmp');
const args = process.argv.slice(2), cmd = args[0], opt = k => { const i = args.indexOf(k); return i > 0 ? args[i + 1] : undefined; };

const ff = (...a) => execFileSync(FF, ['-hide_banner', '-nostats', '-y', ...a], { stdio: ['ignore', 'pipe', 'pipe'], maxBuffer: 1 << 28 });

/** Integrated loudness and true peak (ffmpeg loudnorm, analysis pass only; it reports on stderr). */
function loudness(file) {
  const out = execFileSync('/bin/sh', ['-c', `"${FF}" -hide_banner -nostats -i "${file}" -af loudnorm=print_format=json -f null - 2>&1`], { maxBuffer: 1 << 26 }).toString();
  const j = JSON.parse(out.slice(out.lastIndexOf('{'), out.lastIndexOf('}') + 1));
  return { lufs: Number(j.input_i), tp: Number(j.input_tp) };
}

const readWav = path => { const b = readFileSync(path); let p = 12;
  while (p < b.length) { const id = b.toString('ascii', p, p + 4), n = b.readUInt32LE(p + 4); if (id === 'data') { p += 8; break; } p += 8 + n; }
  const x = new Float32Array((b.length - p) >> 1); for (let i = 0; i < x.length; i++) x[i] = b.readInt16LE(p + 2 * i) / 32768; return x; };
const writeWav = (path, x, sr) => { const b = Buffer.alloc(44 + x.length * 2);
  b.write('RIFF', 0); b.writeUInt32LE(36 + x.length * 2, 4); b.write('WAVE', 8); b.write('fmt ', 12); b.writeUInt32LE(16, 16); b.writeUInt16LE(1, 20);
  b.writeUInt16LE(1, 22); b.writeUInt32LE(sr, 24); b.writeUInt32LE(sr * 2, 28); b.writeUInt16LE(2, 32); b.writeUInt16LE(16, 34); b.write('data', 36);
  b.writeUInt32LE(x.length * 2, 40); for (let i = 0; i < x.length; i++) b.writeInt16LE(Math.max(-32767, Math.min(32767, Math.round(x[i] * 32767))), 44 + 2 * i);
  writeFileSync(path, b); };
/** One fixed gain, then a transparent look-ahead peak limiter (5 ms look-ahead, 80 ms release, ceiling CEILING_DB), so the voice reaches its
 *  loudness target without clipping. It only touches the rare peaks above the ceiling; timing is untouched (the delay is compensated). */
function limit(x, gain) {
  const sr = 48000, look = Math.round(0.005 * sr), rel = Math.exp(-1 / (0.08 * sr)), ceil = 10 ** (CEILING_DB / 20), n = x.length;
  const need = new Float32Array(n); for (let i = 0; i < n; i++) { const a = Math.abs(x[i] * gain); need[i] = a > ceil ? ceil / a : 1; }
  const out = new Float32Array(n); let g = 1, hit = 0, worst = 1;
  for (let i = 0; i < n; i++) {
    let m = 1; for (let j = i; j < Math.min(n, i + look); j++) if (need[j] < m) m = need[j];   // the lowest gain needed in the look-ahead
    g = m < g ? g + (m - g) / Math.max(1, look / 4) : m + (g - m) * rel;                      // fast attack within the look-ahead, slow release
    g = Math.min(g, need[i]);
    if (g < 0.98) hit++; worst = Math.min(worst, g);
    out[i] = x[i] * gain * g;
  }
  return { x: out, share: hit / n, maxDb: 20 * Math.log10(worst) };
}

/** Decode to 16 kHz mono PCM and return the samples. */
function pcm(file) {
  mkdirSync(TMP, { recursive: true });
  const wav = join(TMP, 'probe.wav');
  ff('-i', file, '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', wav);
  const b = readFileSync(wav);
  let p = 12; while (p < b.length) { const id = b.toString('ascii', p, p + 4), n = b.readUInt32LE(p + 4); if (id === 'data') { p += 8; break; } p += 8 + n; }
  const n = Math.floor((b.length - p) / 2), x = new Float32Array(n);
  for (let i = 0; i < n; i++) x[i] = b.readInt16LE(p + i * 2) / 32768;
  return { x, sr: 16000, seconds: n / 16000 };
}

/** Speech runs [start, end] in seconds: 10 ms energy frames above an adaptive threshold, small gaps (stops, plosives) bridged. */
function speech({ x, sr }) {
  const hop = sr / 100, db = [];
  for (let i = 0; i + hop <= x.length; i += hop) { let e = 0; for (let j = 0; j < hop; j++) e += x[i + j] ** 2; db.push(10 * Math.log10(e / hop + 1e-12)); }
  const sorted = [...db].sort((a, b) => a - b), floor = sorted[Math.floor(sorted.length * 0.05)], loud = sorted[Math.floor(sorted.length * 0.95)];
  const th = Math.max(floor + 12, loud - 32);
  const runs = []; let s = -1;
  db.forEach((d, i) => { if (d > th && s < 0) s = i; if (d <= th && s >= 0) { runs.push([s, i]); s = -1; } });
  if (s >= 0) runs.push([s, db.length]);
  const merged = [];
  for (const r of runs) { const last = merged[merged.length - 1]; if (last && r[0] - last[1] < 18) last[1] = r[1]; else merged.push([...r]); }   // < 180 ms: same phrase
  return merged.filter(r => r[1] - r[0] >= 6).map(([a, b]) => [a / 100, b / 100]);                                                              // drop < 60 ms blips
}

/** Group speech runs into the given lines: minimise (log duration error)^2 per line, reward cutting at long pauses. */
function group(runs, texts) {
  const n = texts.length, m = runs.length;
  if (m < n) throw new Error(`found ${m} speech runs for ${n} lines: check the file (or add overrides)`);
  const chars = texts.map(t => t.replace(/[^\p{L}\p{N}]/gu, '').length), total = chars.reduce((a, b) => a + b, 0);
  const gaps = runs.slice(1).map((r, i) => r[0] - runs[i][1]);
  const big = [...gaps].sort((a, b) => b - a).slice(0, n - 1).reduce((a, b) => a + b, 0);
  const rate = (runs[m - 1][1] - runs[0][0] - big) / total;                                       // seconds per character, pauses between lines excluded
  const cost = (i, j, k) => { const d = runs[k][1] - runs[j][0]; return 3 * Math.log(d / (chars[i] * rate)) ** 2; };
  const cut = k => -Math.log(Math.max(0.05, gaps[k]) / 0.05);                                    // cutting after run k
  const best = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(Infinity)), from = best.map(r => r.map(() => -1));
  best[0][0] = 0;
  for (let i = 1; i <= n; i++) for (let k = i; k <= m - (n - i); k++) for (let j = i - 1; j < k; j++) {
    if (best[i - 1][j] === Infinity) continue;
    const c = best[i - 1][j] + cost(i - 1, j, k - 1) + (i < n ? cut(k - 1) : 0);
    if (c < best[i][k]) { best[i][k] = c; from[i][k] = j; }
  }
  const out = []; let k = m;
  for (let i = n; i >= 1; i--) { const j = from[i][k]; out.unshift([runs[j][0], runs[k - 1][1]]); k = j; }
  return out;
}

/** Lines from ElevenLabs character timestamps: locate each line's text in the generated text, in order. */
function fromTimestamps(al, texts) {
  const s = al.characters.join(''), norm = c => c.replace(/[’']/g, "'");
  const S = norm(s); let p = 0;
  return texts.map(t => { const i = S.indexOf(norm(t), p); if (i < 0) throw new Error(`line not found in timestamps: ${t}`); p = i + t.length;
    let e = i + t.length - 1; while (e > i && /[^\p{L}\p{N}]/u.test(S[e])) e--;          // the last spoken character, not the full stop
    return [al.character_start_times_seconds[i], al.character_end_times_seconds[e]]; });
}

/** Measure one file against its lines; write the levelled copy; return per-line spans in frames of the file. */
function measure(file, outName, lines, overrides = {}) {
  const { lufs, tp } = loudness(file);
  const gain = Math.min(12, TARGET_LUFS - lufs, CEILING_DB - tp + MAX_LIMIT);   // at most 1 dB of peak limiting (the master gain does the rest)
  mkdirSync(MIX, { recursive: true }); mkdirSync(TMP, { recursive: true });
  const mixed = join(MIX, outName + '.wav'), raw = join(TMP, 'raw48.wav');
  ff('-i', file, '-ac', '1', '-ar', '48000', '-c:a', 'pcm_s16le', raw);
  const limited = limit(readWav(raw), 10 ** (gain / 20));
  writeWav(mixed, limited.x, 48000);
  const audio = pcm(mixed), texts = lines.map(l => l.text);
  const alignFile = file.replace(/\.[a-z0-9]+$/i, '.alignment.json');
  const runs = speech(audio);
  // timestamps say which words belong to which line; the waveform says exactly where the sound starts and stops (character times are loose at the
  // edges): each span is snapped to the speech runs it overlaps
  const snap = ([a, b]) => { const o = runs.filter(([x, y]) => y > a + 0.02 && x < b - 0.02); return o.length ? [Math.max(a - 0.15, o[0][0]), Math.min(b + 0.25, o[o.length - 1][1])] : [a, b]; };
  const spans = existsSync(alignFile) ? fromTimestamps(JSON.parse(readFileSync(alignFile, 'utf8')), texts).map(snap) : group(runs, texts);
  lines.forEach((l, i) => { if (overrides[l.id]) spans[i] = [overrides[l.id].from, overrides[l.id].to]; });
  const rates = spans.map(([a, b], i) => texts[i].replace(/[^\p{L}\p{N}]/gu, '').length / (b - a));
  const med = [...rates].sort((a, b) => a - b)[Math.floor(rates.length / 2)];
  const out = {};
  spans.forEach(([a, b], i) => {
    const gap = i ? a - spans[i - 1][1] : a;
    out[lines[i].id] = { from: Math.max(0, Math.floor(a * FPS)), to: Math.ceil(b * FPS), gap: Math.round(gap * FPS) };
    const flag = rates[i] / med < 0.7 || rates[i] / med > 1.4 ? '  <-- check: speaking rate ' + (rates[i] / med).toFixed(2) + 'x the median' : '';
    console.log(`  ${lines[i].id.padEnd(13)} ${a.toFixed(2).padStart(6)}-${b.toFixed(2).padStart(6)} s  ${(b - a).toFixed(2)} s  ${lines[i].text.slice(0, 60)}${flag}`);
  });
  console.log(`  loudness ${lufs.toFixed(1)} LUFS, true peak ${tp.toFixed(1)} dBTP -> gain ${gain.toFixed(1)} dB, peaks limited on ${(limited.share * 100).toFixed(2)}% of samples (max ${limited.maxDb.toFixed(1)} dB); ${audio.seconds.toFixed(1)} s; ${existsSync(alignFile) ? 'ElevenLabs timestamps' : 'waveform'}`);
  return { file: `audio/vo/mix/${outName}.wav`, lines: out, seconds: audio.seconds };
}

const find = (dir, base) => ['wav', 'mp3', 'm4a', 'flac', 'ogg'].map(e => join(dir, `${base}.${e}`)).find(existsSync);
const overrides = () => { const p = join(VO, 'overrides.json'); return existsSync(p) ? JSON.parse(readFileSync(p, 'utf8')) : {}; };

async function main() {
  if (cmd === 'clear') { writeFileSync(join(FILM, 'data/vo.json'), '{}\n'); console.log('data/vo.json cleared: placeholder timing'); return; }
  if (cmd === 'align') {
    writeFileSync(join(FILM, 'data/vo.json'), '{}\n');                // measure against the DESIGNED cue sheet, never a previous placement
    const { ACTS } = await loadNarration(), src = opt('--src') ?? VO, source = opt('--source') ?? 'recorded', ov = overrides(), out = {};
    for (const a of ACTS) {
      const file = find(src, a.id);
      if (!file) { console.log(`${a.id}: no file, stays placeholder`); continue; }
      console.log(`${a.id}: ${file.replace(FILM + '/', '')}`);
      out[a.id] = { ...measure(file, a.id, a.lines, ov), source };
    }
    writeFileSync(join(FILM, 'data/vo.json'), JSON.stringify(out, null, 1) + '\n');
    const placed = await loadNarration();
    for (const a of placed.ACTS) if (a.design) {
      const moved = a.lines.map((l, i) => [l.id, l.at - a.design.lines[i].at]).filter(([, d]) => Math.abs(d) >= 6);
      console.log(`${a.id}: ${a.design.frames} -> ${a.frames} frames${a.frames > a.design.frames ? ' (the voice is longer than the picture: act extended)' : ''}; ` +
        (moved.length ? 'moved ' + moved.map(([id, d]) => `${id} ${d > 0 ? '+' : ''}${(d / FPS).toFixed(2)} s`).join(', ') : 'every line on its designed frame'));
    }
    console.log('wrote data/vo.json. Next: node scripts/score.mjs (re-times the score to the voice), then render.');
    return;
  }
  if (cmd === 'audition') {
    const { ACTS } = await loadNarration(), byId = new Map(ACTS.flatMap(a => a.lines.map(l => [l.id, l]))), dir = join(VO, 'audition'), out = {};
    for (const f of existsSync(dir) ? readdirSync(dir).sort() : []) {
      const m = f.match(/^([a-z0-9_]+)-([123])\.(wav|mp3|m4a|flac|ogg)$/i); if (!m) continue;
      const lines = AUDITION[Number(m[2]) - 1].map(x => typeof x === 'string' ? byId.get(x) : { ...byId.get(x.id), text: x.text });
      console.log(`${f}:`);
      (out[m[1].toLowerCase()] ??= {})[m[2]] = measure(join(dir, f), `audition-${m[1].toLowerCase()}-${m[2]}`, lines);
    }
    writeFileSync(join(FILM, 'data/audition.json'), JSON.stringify(out, null, 1) + '\n');
    console.log(Object.keys(out).length ? `wrote data/audition.json: ${Object.keys(out).join(', ')}. Render: npx remotion render Audition out/audition-<voice>.mp4 --props='{"voice":"<voice>"}'` : 'no clips in public/audio/vo/audition/');
    return;
  }
  console.log('usage: node scripts/vo.mjs align [--src DIR --source scratch] | audition | clear');
}
main();
