/** The narration cue sheet: the single source of truth for voiceover text and timing.
 *
 *  Each act has its own lines, its own voiceover file (public/audio/vo/<act>.wav, recorded per act) and its own frame clock (frame 0 = start of
 *  the act, 30 fps). Scenes anchor their key beats to cue ids (`cue('a1.question')`), never to hard-coded frames, so when the real voiceover is
 *  recorded the timings are re-measured from the audio (e.g. ElevenLabs' character timestamps, or by ear in Remotion Studio) and ONLY `at` /
 *  `end` below change: the animation follows the voice.
 *
 *  `at`/`end` are PLACEHOLDERS estimated at ~140 words per minute until a voice is recorded (status: 'placeholder').
 */
import VO from '../data/vo.json';

/** `src` = where this line's speech sits in the act's voiceover file (frames into the file, speech onset to offset), once recorded. */
export type Line = { id: string; at: number; end: number; text: string; src?: { from: number; to: number } };
/** `design` keeps the picture's designed timing (the approved cut); `at`/`end`/`frames` are the timing actually used, i.e. the design moved to
 *  where the recorded voice puts each line. `warp` maps any designed frame of the act onto the recorded timeline. */
export type Act = { id: string; vo: string; status: 'placeholder' | 'recorded'; frames: number; lines: Line[];
  design?: { frames: number; lines: { at: number; end: number }[] }; source?: string };

export const ACT1: Act = {
  id: 'act1', vo: 'audio/vo/act1.wav', status: 'placeholder', frames: 750, lines: [
    { id: 'a1.college', at: 12, end: 78, text: 'This is Larkspur Community College.' },
    { id: 'a1.designed', at: 118, end: 214, text: 'Beautifully designed. Easy for people to browse.' },
    { id: 'a1.question', at: 250, end: 316, text: 'But what happens when an AI agent tries?' },
    { id: 'a1.task', at: 330, end: 500, text: 'We gave a Meta Muse Spark agent a simple task: find beginner courses that meet on weekends.' },
    { id: 'a1.browsing', at: 515, end: 560, text: 'It started browsing.' },
    { id: 'a1.watching', at: 596, end: 668, text: 'And Agent Readiness was watching.' },
  ],
};

export const ACT2: Act = {
  id: 'act2', vo: 'audio/vo/act2.wav', status: 'placeholder', frames: 1500, lines: [
    { id: 'a2.facts', at: 20, end: 130, text: 'To answer, the agent needs two facts about every course: its level, and the day it meets.' },
    { id: 'a2.pages', at: 150, end: 250, text: 'The catalogue doesn’t show them. They’re on fourteen separate course pages.' },
    { id: 'a2.opens', at: 285, end: 345, text: 'So it opens them. One at a time.' },
    { id: 'a2.cost', at: 470, end: 580, text: 'Every page costs a step. Every trip back to the catalogue costs another.' },
    { id: 'a2.low', at: 800, end: 900, text: 'Three courses checked. Eleven to go. And its interaction budget is running low.' },
    { id: 'a2.stops', at: 1010, end: 1130, text: 'So it stops itself, before finding all four matching courses. It names just two.' },
    { id: 'a2.recorded', at: 1180, end: 1320, text: 'Agent Readiness recorded every step, every screenshot, every decision, and traced the failure to its cause.' },
    { id: 'a2.cause', at: 1350, end: 1480, text: 'The facts the agent needed are on every course page, and on none of the catalogue cards.' },
  ],
};

export const ACT3: Act = {
  id: 'act3', vo: 'audio/vo/act3.wav', status: 'placeholder', frames: 1200, lines: [
    { id: 'a3.diagnosis', at: 12, end: 120, text: 'The diagnosis was clear. The facts agents need are missing from the catalogue.' },
    { id: 'a3.three', at: 135, end: 215, text: 'Agent Readiness recommended three changes. The first matters most.' },
    { id: 'a3.cards', at: 232, end: 350, text: 'Take each course’s facts off its own page, and put them on its catalogue card.' },
    { id: 'a3.same', at: 440, end: 545, text: 'Same design. Same pages. But now every card shows its level, day, fee and seats.' },
    { id: 'a3.visible', at: 585, end: 680, text: 'All four weekend beginner courses, visible from one page.' },
    { id: 'a3.deadend', at: 712, end: 820, text: 'It also fixed a dead end, where an agent’s guessed address led nowhere.' },
    { id: 'a3.data', at: 892, end: 1010, text: 'And it described every course in structured data that agents can read directly.' },
    { id: 'a3.again', at: 1068, end: 1150, text: 'Then the same agent got the same task, on the improved website.' },
  ],
};

export const ACT4: Act = {
  id: 'act4', vo: 'audio/vo/act4.wav', status: 'placeholder', frames: 1200, lines: [
    { id: 'a4.again', at: 12, end: 125, text: 'We ran the same tasks again, this time with both versions side by side, in a new evaluation.' },
    { id: 'a4.before', at: 165, end: 255, text: 'Before, the agent found just one of four matching courses.' },
    { id: 'a4.after', at: 445, end: 610, text: 'After, it found all four, in three requests, without opening a single course page.' },
    { id: 'a4.correct', at: 720, end: 805, text: 'Across the three tasks, correct answers went from zero to three.' },
    { id: 'a4.metrics', at: 875, end: 1020, text: 'Seventy-four percent fewer requests. Eighty-three percent less time. Seventy-seven percent lower cost.' },
    { id: 'a4.works', at: 1070, end: 1170, text: 'Same agent. Same tasks. A website that finally works for it.' },
  ],
};

export const ACT5: Act = {
  id: 'act5', vo: 'audio/vo/act5.wav', status: 'placeholder', frames: 750, lines: [
    { id: 'a5.today', at: 15, end: 135, text: 'Today, Agent Readiness helps websites understand how AI agents experience them.' },
    { id: 'a5.tomorrow', at: 165, end: 290, text: 'Tomorrow, it could help agents discover which websites they can actually use.' },
    { id: 'a5.which', at: 330, end: 520, text: 'Which ones support their task. Which ones are reliable. And where they can succeed.' },
    { id: 'a5.brand', at: 560, end: 600, text: 'Agent Readiness.' },
    { id: 'a5.tagline', at: 615, end: 720, text: 'Building the discovery layer for the agentic web.' },
  ],
};

export const ACTS = [ACT1, ACT2, ACT3, ACT4, ACT5];

// ---- the recorded voice: data/vo.json (written by `node scripts/vo.mjs align` from the per-act files) ----
type VoAct = { file: string; source: string; lines: Record<string, { from: number; to: number; gap: number }> };
const EARLY = 12;                    // a line may start up to 0.4 s before its designed frame when it would otherwise run into the next line
const GAP_MIN = 8, GAP_MAX = 15;     // breath between consecutive lines: the voice's own pause, kept within 0.27-0.5 s when the picture is tight
/** Place each recorded line as close to its designed frame as the voice allows: never earlier than the previous line's end plus a breath, never
 *  overlapping the next line, and never stretched. If the act's voice is longer than its picture, the act grows (and so does its warp). */
function place(act: Act, vo: VoAct) {
  const design = { frames: act.frames, lines: act.lines.map(l => ({ at: l.at, end: l.end })) };
  const n = act.lines.length;
  for (const l of act.lines) if (!vo.lines[l.id]) throw new Error(`${act.id}: no recorded audio for ${l.id}`);
  const dur = act.lines.map(l => vo.lines[l.id].to - vo.lines[l.id].from);
  const gap = act.lines.map(l => Math.max(GAP_MIN, Math.min(GAP_MAX, vo.lines[l.id].gap)));
  let prevEnd = -Infinity;
  act.lines.forEach((l, i) => {
    let want = design.lines[i].at;
    if (i + 1 < n) { const over = want + dur[i] + gap[i + 1] - design.lines[i + 1].at; if (over > 0) want -= Math.min(over, EARLY); }
    const at = Math.max(i ? prevEnd + gap[i] : 4, want);
    l.src = { from: vo.lines[l.id].from, to: vo.lines[l.id].to };
    l.at = at; l.end = at + dur[i]; prevEnd = l.end;
  });
  const tail = Math.max(24, design.frames - design.lines[n - 1].end);
  act.frames = Math.max(design.frames, act.lines[n - 1].end + tail);
  act.design = design; act.status = 'recorded'; act.vo = vo.file; act.source = vo.source;
}
for (const a of ACTS) { const v = (VO as Record<string, VoAct>)[a.id]; if (v) place(a, v); }

/** Map a frame of the act's DESIGNED timeline onto its actual timeline, piecewise-linearly between the narration lines (identity until the act is
 *  recorded). Scene beats that are not tied to a narration line (e.g. the recorded steps landing between lines) go through this. */
export const warp = (act: Act, f: number): number => {
  if (!act.design) return f;
  const xs = [0, ...act.design.lines.map(l => l.at), act.design.frames], ys = [0, ...act.lines.map(l => l.at), act.frames];
  for (let i = 1; i < xs.length; i++) if (f <= xs[i] || i === xs.length - 1) { const t = (f - xs[i - 1]) / Math.max(1, xs[i] - xs[i - 1]); return Math.round(ys[i - 1] + t * (ys[i] - ys[i - 1])); }
  return f;
};
/** The same mapping for FILM time in seconds (designed film time -> actual), used by the score so its harmony changes stay on the picture. */
export const filmWarp = (t: number): number => {
  let o = 0, od = 0;
  for (const a of ACTS) { const df = a.design?.frames ?? a.frames;
    if (t * 30 <= od + df || a === ACTS[ACTS.length - 1]) return (o + warp(a, t * 30 - od)) / 30;
    o += a.frames; od += df; }
  return t;
};
const ALL = new Map(ACTS.flatMap(a => a.lines.map(l => [l.id, l] as const)));
/** The frame (act-local) a narration line starts; throws on an unknown id so a renamed line can never silently desync a scene. */
export const cue = (id: string): number => { const l = ALL.get(id); if (!l) throw new Error(`unknown narration cue ${id}`); return l.at; };
export const cueEnd = (id: string): number => { const l = ALL.get(id); if (!l) throw new Error(`unknown narration cue ${id}`); return l.end; };
