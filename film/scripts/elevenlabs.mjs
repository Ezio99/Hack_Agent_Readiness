// Optional: generate the voice through the ElevenLabs API instead of the website. Same voice, model and settings as vo/AUDITION.md, and the API
// also returns per-character timestamps, so scripts/vo.mjs places every line exactly (no waveform guessing).
//
// The key is read from the environment (ELEVENLABS_API_KEY) or film/.env (gitignored); it is never printed or written anywhere else.
// Nothing is generated without --confirm: without it the script only prints what it would send and how many characters (credits) that costs.
//
//   node scripts/elevenlabs.mjs account                                 plan and remaining credits
//   node scripts/elevenlabs.mjs voices                                  the voices in "My voices" (add Dan / Haseeb from the Voice Library first)
//   node scripts/elevenlabs.mjs audition --voice Dan [--confirm]        the three audition clips -> public/audio/vo/audition/dan-1.mp3 ...
//   node scripts/elevenlabs.mjs acts --voice Dan [--take 2] [--confirm] one file per act -> public/audio/vo/act1.mp3 ... (take 2: act1-take2.mp3)
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { AUDITION, FILM, loadNarration } from './lib/narration.mjs';

const API = 'https://api.elevenlabs.io/v1';
const MODEL = 'eleven_multilingual_v2';
const SETTINGS = { stability: 0.5, similarity_boost: 0.75, style: 0.05, use_speaker_boost: true, speed: 1.0 };
const args = process.argv.slice(2), cmd = args[0], opt = k => { const i = args.indexOf(k); return i > 0 ? args[i + 1] : undefined; };
const KEY = process.env.ELEVENLABS_API_KEY ?? (existsSync(join(FILM, '.env'))
  ? readFileSync(join(FILM, '.env'), 'utf8').match(/^ELEVENLABS_API_KEY=(.+)$/m)?.[1]?.trim() : undefined);

async function api(path, init = {}) {
  if (!KEY) throw new Error('no ELEVENLABS_API_KEY (environment or film/.env)');
  const r = await fetch(API + path, { ...init, headers: { 'xi-api-key': KEY, 'content-type': 'application/json', ...init.headers } });
  if (!r.ok) throw new Error(`${path.split('?')[0]}: HTTP ${r.status} ${(await r.text()).slice(0, 400)}`);
  return r.json();
}
async function voiceId(name) {
  if (!name) throw new Error('--voice <name or id> is required');
  const { voices } = await api('/voices');
  const v = voices.find(v => v.voice_id === name) ?? voices.find(v => v.name.toLowerCase().startsWith(name.toLowerCase()));
  if (!v) throw new Error(`"${name}" is not in My voices: add it from the Voice Library first (voices: ${voices.map(v => v.name).join(', ')})`);
  return { id: v.voice_id, name: v.name };
}
async function speak(voice, text, out) {
  const j = await api(`/text-to-speech/${voice.id}/with-timestamps?output_format=mp3_44100_192`, { method: 'POST',
    body: JSON.stringify({ text, model_id: MODEL, voice_settings: SETTINGS }) });
  writeFileSync(out, Buffer.from(j.audio_base64, 'base64'));
  writeFileSync(out.replace(/\.mp3$/, '.alignment.json'), JSON.stringify(j.alignment) + '\n');
  console.log('  wrote', out.replace(FILM + '/', ''));
}

async function main() {
  if (cmd === 'account') { const s = await api('/user/subscription');
    console.log(`plan: ${s.tier}; credits used ${s.character_count} of ${s.character_limit}; commercial licence: ${s.tier === 'free' ? 'NO (free plan)' : 'yes'}`); return; }
  if (cmd === 'voices') { const { voices } = await api('/voices'); for (const v of voices) console.log(`${v.name.padEnd(40)} ${v.voice_id}  ${v.category}`); return; }
  const { ACTS } = await loadNarration(), byId = new Map(ACTS.flatMap(a => a.lines.map(l => [l.id, l.text])));
  let jobs = [];
  if (cmd === 'audition') {
    jobs = AUDITION.map((ids, i) => ({ n: i + 1, text: ids.map(x => typeof x === 'string' ? byId.get(x) : x.text).join('\n\n') }));
  } else if (cmd === 'acts') {
    jobs = ACTS.map(a => ({ n: a.id, text: a.lines.map(l => l.text).join('\n\n') }));
  } else { console.log('usage: account | voices | audition --voice NAME [--confirm] | acts --voice NAME [--take N] [--confirm]'); return; }
  const chars = jobs.reduce((s, j) => s + j.text.length, 0);
  console.log(`${cmd}: ${jobs.length} generations, ${chars} characters (about ${chars} credits on ${MODEL}); settings ${JSON.stringify(SETTINGS)}`);
  if (!args.includes('--confirm')) { console.log('dry run: nothing sent. Add --confirm to generate.'); return; }
  const voice = await voiceId(opt('--voice')), tag = voice.name.split(/[\s-]/)[0].toLowerCase(), take = opt('--take');
  const dir = cmd === 'audition' ? join(FILM, 'public/audio/vo/audition') : join(FILM, 'public/audio/vo');
  mkdirSync(dir, { recursive: true });
  console.log(`voice: ${voice.name}`);
  for (const j of jobs) await speak(voice, j.text, join(dir, cmd === 'audition' ? `${tag}-${j.n}.mp3` : `${j.n}${take ? '-take' + take : ''}.mp3`));
  console.log(`next: node scripts/vo.mjs ${cmd === 'audition' ? 'audition' : 'align'}`);
}
main().catch(e => { console.error(String(e.message ?? e)); process.exit(1); });
