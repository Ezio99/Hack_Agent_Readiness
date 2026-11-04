/** The narration cue sheet: the single source of truth for voiceover text and timing.
 *
 *  Each act has its own lines, its own voiceover file (public/audio/vo/<act>.wav, recorded per act) and its own frame clock (frame 0 = start of
 *  the act, 30 fps). Scenes anchor their key beats to cue ids (`cue('a1.question')`), never to hard-coded frames, so when the real voiceover is
 *  recorded the timings are re-measured from the audio (e.g. ElevenLabs' character timestamps, or by ear in Remotion Studio) and ONLY `at` /
 *  `end` below change: the animation follows the voice.
 *
 *  `at`/`end` are PLACEHOLDERS estimated at ~140 words per minute until a voice is recorded (status: 'placeholder').
 */
export type Line = { id: string; at: number; end: number; text: string };
export type Act = { id: string; vo: string; status: 'placeholder' | 'recorded'; frames: number; lines: Line[] };

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

export const ACTS = [ACT1, ACT2, ACT3];
const ALL = new Map(ACTS.flatMap(a => a.lines.map(l => [l.id, l] as const)));
/** The frame (act-local) a narration line starts; throws on an unknown id so a renamed line can never silently desync a scene. */
export const cue = (id: string): number => { const l = ALL.get(id); if (!l) throw new Error(`unknown narration cue ${id}`); return l.at; };
export const cueEnd = (id: string): number => { const l = ALL.get(id); if (!l) throw new Error(`unknown narration cue ${id}`); return l.end; };
