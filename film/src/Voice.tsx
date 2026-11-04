import { AbsoluteFill, Audio, Sequence, staticFile } from 'remotion';
import AUD from '../data/audition.json';
import { ACT1, ACT2, ACT5, cue, cueEnd, type Line } from './narration';
import { C, F } from './theme/tokens';

/** The mix. Voice is the lead: levelled to -16 LUFS by scripts/vo.mjs and played at unity. Music sits under it and dips while a line is spoken
 *  (an 8-frame dip before the first word, a 20-frame recovery after the last), so the narration stays clear without the score pumping between
 *  words. Sound effects are placed in the scenes, at the recorded events. */
export const MIX = { music: 0.75, musicUnderVoice: 0.27, attack: 8, release: 20 } as const;

export function musicVolume(spoken: [number, number][]) {
  return (f: number) => {
    let d = 0;
    for (const [a, b] of spoken) d = Math.max(d, Math.min(1, (f - (a - MIX.attack)) / MIX.attack, (b + MIX.release - f) / MIX.release));
    const x = Math.max(0, d), s = x * x * (3 - 2 * x);                                   // smoothstep: no audible corners
    return MIX.music + (MIX.musicUnderVoice - MIX.music) * s;
  };
}

/** One act's voice: each line is cut from the act's own file at its natural pauses (keeping a little of the file's own room tone either side)
 *  and placed where the cue sheet puts it. Nothing is re-ordered, stretched or sped up; the words inside a line keep the narrator's own timing. */
export function Voice({ lines, file }: { lines: Line[]; file: string }) {
  return <>{lines.map((l, i) => {
    if (!l.src) return null;
    const prevTo = i ? lines[i - 1].src?.to ?? 0 : 0, nextFrom = lines[i + 1]?.src?.from ?? Infinity;
    const pre = Math.min(4, Math.floor((l.src.from - prevTo) / 2)), post = Math.min(9, Math.floor((nextFrom - l.src.to) / 2));
    const from = Math.max(0, l.src.from - pre), to = l.src.to + post, len = to - from;
    return <Sequence key={l.id} from={l.at - (l.src.from - from)} durationInFrames={len} layout="none">
      <Audio src={staticFile(file)} startFrom={from} endAt={to} volume={f => Math.max(0, Math.min(1, (f + 1) / 3, (len - f) / 4))} />
    </Sequence>;
  })}</>;
}

/** Shown on every frame rendered with a stand-in voice, so a timing test can never be mistaken for the film. */
export function ScratchMark() {
  return <div style={{ position: 'absolute', right: 24, top: 18, padding: '4px 10px', borderRadius: 4, background: 'rgba(200,40,40,.85)',
    fontFamily: F.mono, fontSize: 13, letterSpacing: '.12em', color: '#fff' }}>SCRATCH VOICE (LOCAL TTS) · TIMING TEST, NOT FOR RELEASE</div>;
}

// ---- auditions: each candidate's three clips laid under the pictures they belong to ----
type Clip = { file: string; lines: Record<string, { from: number; to: number; gap: number }> };
const AUDITIONS = AUD as Record<string, Record<string, Clip>>;
export const VOICES = Object.keys(AUDITIONS);
/** The three excerpts (act, first frame, last frame) and the narration lines each clip reads (scripts/vo.mjs AUDITION). */
export const EXCERPTS = [
  { act: ACT1, n: '1', start: 0, end: cueEnd('a1.question') + 50, ids: ['a1.college', 'a1.designed', 'a1.question'], label: 'Act 1 · curious' },
  { act: ACT2, n: '2', start: cue('a2.low') - 75, end: cueEnd('a2.stops') + 60, ids: ['a2.low', 'a2.stops'], label: 'Act 2 · tense' },
  { act: ACT5, n: '3', start: cue('a5.brand') - 70, end: ACT5.frames, ids: ['a5.brand', 'a5.tagline'], label: 'Act 5 · optimistic' },
];
export const excerptFrames = (e: typeof EXCERPTS[number]) => e.end - e.start;

/** Lines of one audition clip, placed at their cue (or right after the previous line, if the voice runs long), on the excerpt's clock. */
export function auditionLines(voice: string, e: typeof EXCERPTS[number]): Line[] {
  const clip = AUDITIONS[voice]?.[e.n]; if (!clip) return [];
  let prevEnd = -Infinity;
  return e.ids.map(id => { const l = e.act.lines.find(x => x.id === id)!, s = clip.lines[id];
    const at = Math.max(l.at - e.start, prevEnd + Math.max(8, Math.min(15, s.gap))); prevEnd = at + s.to - s.from;
    return { ...l, at, end: prevEnd, src: { from: s.from, to: s.to } }; });
}
export const auditionFile = (voice: string, n: string) => AUDITIONS[voice]?.[n]?.file;

export function AuditionLabel({ voice, label }: { voice: string; label: string }) {
  return <AbsoluteFill style={{ pointerEvents: 'none' }}>
    <div style={{ position: 'absolute', left: 24, top: 18, padding: '4px 10px', borderRadius: 4, background: 'rgba(0,0,0,.7)', border: `1px solid ${C.rule}`,
      fontFamily: F.mono, fontSize: 13, letterSpacing: '.12em', color: '#F2C14E' }}>VOICE AUDITION · {voice.toUpperCase()} · {label.toUpperCase()}</div>
  </AbsoluteFill>;
}
