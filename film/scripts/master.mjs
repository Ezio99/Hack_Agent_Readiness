// Master the rendered film's audio for delivery: measure the whole mix (EBU R128) and apply ONE gain towards -16 LUFS integrated, capped so the
// true peak stays at or below -1 dBTP. The picture is copied untouched; every relationship inside the mix (voice, music, SFX) is preserved.
//   node scripts/master.mjs out/film.mp4 out/film-master.mp4
import { execFileSync } from 'node:child_process';
import { join } from 'node:path';
import { FILM } from './lib/narration.mjs';

const FF = join(FILM, 'node_modules/@remotion/compositor-linux-x64-gnu/ffmpeg');
const TARGET = -16, MAX_TP = -1;
const [src, dst] = process.argv.slice(2);
if (!src || !dst) { console.log('usage: node scripts/master.mjs IN.mp4 OUT.mp4'); process.exit(1); }
const measure = f => { const o = execFileSync('/bin/sh', ['-c', `"${FF}" -hide_banner -nostats -i "${f}" -vn -af loudnorm=print_format=json -f null - 2>&1`], { maxBuffer: 1 << 26 }).toString();
  const j = JSON.parse(o.slice(o.lastIndexOf('{'), o.lastIndexOf('}') + 1)); return { i: Number(j.input_i), tp: Number(j.input_tp), lra: Number(j.input_lra) }; };
const m = measure(src), gain = Math.min(TARGET - m.i, MAX_TP - m.tp);
execFileSync(FF, ['-hide_banner', '-nostats', '-y', '-i', src, '-c:v', 'copy', '-af', `volume=${gain.toFixed(2)}dB`, '-c:a', 'libfdk_aac', '-b:a', '320k', '-movflags', '+faststart', dst], { stdio: ['ignore', 'ignore', 'pipe'] });
const r = measure(dst);
console.log(`${src}: ${m.i.toFixed(1)} LUFS, ${m.tp.toFixed(1)} dBTP, LRA ${m.lra.toFixed(1)} -> gain ${gain >= 0 ? '+' : ''}${gain.toFixed(1)} dB -> ${dst}: ${r.i.toFixed(1)} LUFS, ${r.tp.toFixed(1)} dBTP`);
