import { AbsoluteFill, interpolate, Sequence, useCurrentFrame } from 'remotion';
import { BrowserWindow } from '../components/BrowserWindow';
import { ActionHighlight, PageImage, StepBudget } from '../components/Evidence';
import { Mark } from '../components/Mark';
import { Sfx } from '../components/Sound';
import { actionLabel, before, boxes, runDate } from '../evidence';
import { ACT1, cue, cueEnd, warp } from '../narration';
import { C, F, camera, ease } from '../theme/tokens';

/** Act 1, the opening (25 s). A: the Larkspur website, floating in the dark. B: beautifully designed, easy for people. Q: "But what happens when
 *  an AI agent tries?" C: a recorded Meta Muse Spark agent takes its first two real steps; its own note becomes the headline. D: Agent Readiness.
 *  Website = the frozen Before snapshot rendered at 2x (scripts/capture.py); agent view = the agent's own recorded screenshots.
 *  Beats are anchored to narration cues (src/narration.ts) so they follow the recorded voice. */
export const OPENING_FRAMES = ACT1.frames;

const T = (() => {
  const q = cue('a1.question'), wipe = cueEnd('a1.question'), click2 = cue('a1.browsing') + 5, watch = cue('a1.watching');
  const w = (x: number) => warp(ACT1, x);   // beats between narration lines follow the recorded voice
  return { aIn: 6, bMove: w(108), bCourses: w(116), bScroll: [w(150), w(236)] as const, bText: cue('a1.designed'), q, wipe,
    c1Hi: wipe + 28, c1Click: wipe + 52, c2Cut: wipe + 76, obs: wipe + 96, c2Hi: click2 - 26, c2Click: click2,
    dOut: watch - 22, mark: watch, word: watch + 26, end: ACT1.frames - 34 };
})();

const W = 1100, S = W / 1265, H = Math.round(960 * S);      // window content: one agent viewport, 1265 CSS px wide
const step1 = before.steps[0], step2 = before.steps[1];
/** The agent's step-2 note, split for typography: both halves are verbatim and together are the whole recorded note. */
const [OBS_LEAD, OBS] = (() => { const m = step2.memory; const i = m.indexOf('Need to check each'); if (i < 0) throw new Error('step 2 note changed'); return [m.slice(0, i).trim(), m.slice(i).trim()]; })();

const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;
const k = (f: number, input: readonly number[], output: number[], easing = ease) => interpolate(f, input as number[], output, { ...clamp, easing });

export function Opening({ captions = false }: { captions?: boolean }) {
  const f = useCurrentFrame();

  // ---- the window (camera) ----
  const rise = k(f, [T.aIn, 72], [0, 1]);
  const toSide = k(f, [T.bMove, T.bMove + 42], [0, 1], camera);
  const recede = k(f, [T.dOut, T.dOut + 36], [0, 1], camera);
  const qDim = k(f, [T.q - 6, T.q + 14], [0, 1]) * (1 - k(f, [T.wipe, T.wipe + 16], [0, 1]));
  const push = interpolate(f, [0, T.bMove], [0, 0.035], clamp);
  const scale = (0.9 + 0.1 * rise + push) * (1 - 0.2 * toSide) + 0.02 * k(f, [T.wipe, T.dOut], [0, 1], camera) * (1 - recede) - 0.1 * recede;
  const x = 330 * toSide * (1 - recede), y = 70 * (1 - rise) + 8 * toSide;
  const winOpacity = Math.min(rise * 1.4, 1) * (1 - 0.45 * qDim) * (1 - recede);
  const blur = 14 * (1 - rise) + 4 * qDim + 8 * recede;

  // ---- window content ----
  const coursesIn = k(f, [T.bCourses, T.bCourses + 22], [0, 1]);
  const scroll = k(f, [T.bScroll[0], T.bScroll[1]], [0, 440], camera);
  const wipe = k(f, [T.wipe, T.wipe + 20], [0, 1], camera);
  const cut2 = k(f, [T.c2Cut, T.c2Cut + 8], [0, 1]);
  const recorded = f >= T.wipe, inC2 = f >= T.c2Cut;
  const step = inC2 ? step2 : step1;
  const path = f < T.bCourses + 10 ? '/' : !recorded ? '/courses' : step.path;
  const badge = recorded ? <span style={{ opacity: wipe, display: 'inline-flex', alignItems: 'center', gap: 8, padding: '4px 12px', borderRadius: 999,
    background: 'rgba(114,128,242,.16)', color: C.signal2, fontFamily: F.mono, fontSize: 13, letterSpacing: '.12em' }}>
    <span style={{ width: 7, height: 7, borderRadius: 4, background: C.signal }} />RECORDED</span> : null;

  const bText = (d: number) => k(f, [T.bText + d, T.bText + d + 26], [0, 1]) * (1 - k(f, [T.q - 22, T.q - 6], [0, 1]));
  const cIn = (d: number) => k(f, [T.wipe + 8 + d, T.wipe + 30 + d], [0, 1]) * (1 - recede);
  const actionIn = k(f, [(inC2 ? T.c2Click : T.c1Click) - 10, (inC2 ? T.c2Click : T.c1Click)], [0, 1]) * (inC2 || f < T.c2Cut - 4 ? 1 : 0);
  const obsWords = OBS.split(' ');

  return <AbsoluteFill style={{ background: C.bg, overflow: 'hidden' }}>
    <AbsoluteFill style={{ background: 'radial-gradient(ellipse 60% 55% at 55% 50%, rgba(237,234,227,.055), rgba(0,0,0,0) 70%)' }} />

    <AbsoluteFill style={{ transform: `translate(${x}px, ${y}px) scale(${scale})`, opacity: winOpacity, filter: blur > 0.05 ? `blur(${blur}px)` : undefined }}>
      <BrowserWindow width={W} height={H} path={path} badge={badge} style={{ left: 960 - W / 2, top: 540 - (H + 46) / 2 }}>
        <PageImage src="captures/site/before-home-view.png" cssWidth={1265} scale={S} opacity={1 - coursesIn} />
        <PageImage src="captures/site/before-courses-full.png" cssWidth={1265} scale={S} scrollY={scroll} opacity={coursesIn} />
        {recorded && <div style={{ position: 'absolute', inset: 0, clipPath: `inset(0 0 ${100 - 100 * wipe}% 0)` }}>
          <PageImage src={step1.screenshot} cssWidth={1280} scale={S} />
          <PageImage src={step2.screenshot} cssWidth={1280} scale={S} opacity={cut2} />
          {!inC2 && <ActionHighlight box={boxes['home.browse_all'][0]} scale={S} start={T.c1Hi} clickAt={T.c1Click} />}
          {inC2 && <ActionHighlight box={boxes['courses.watercolour_link'][0]} scale={S} start={T.c2Hi} clickAt={T.c2Click} />}
        </div>}
        {recorded && wipe < 1 && <div style={{ position: 'absolute', left: 0, right: 0, top: `${100 * wipe}%`, height: 2, background: C.signal, boxShadow: `0 0 18px ${C.signal}` }} />}
      </BrowserWindow>
    </AbsoluteFill>

    {/* B: made for people */}
    {f >= T.bText && f < T.q && <div style={{ position: 'absolute', left: 120, top: 380, width: 700 }}>
      <p style={{ margin: 0, fontFamily: F.mono, fontSize: 16, letterSpacing: '.16em', color: C.ink3, opacity: bText(0), textTransform: 'uppercase' }}>
        Larkspur Community College · a fictional college</p>
      {['Beautifully designed.', 'Easy for people to browse.'].map((t, i) =>
        <p key={t} style={{ margin: '22px 0 0', fontFamily: F.serif, fontSize: 68, lineHeight: 1.04, letterSpacing: '-.015em', color: i === 1 ? C.ink : C.ink2,
          fontStyle: i === 1 ? 'italic' : 'normal', opacity: bText(8 + 40 * i), transform: `translateY(${18 * (1 - bText(8 + 40 * i))}px)` }}>{t}</p>)}
    </div>}

    {/* Q: the question, before we see the agent */}
    {f >= T.q - 4 && f < T.wipe + 20 && <div style={{ position: 'absolute', left: 120, top: 330, width: 760, opacity: k(f, [T.q, T.q + 20], [0, 1]) * (1 - k(f, [T.wipe, T.wipe + 18], [0, 1])) }}>
      <p style={{ margin: 0, fontFamily: F.serif, fontSize: 96, lineHeight: 1.04, letterSpacing: '-.02em', color: C.ink }}>But what happens when an <em>AI agent</em> tries?</p>
    </div>}

    {/* C: the recorded agent */}
    {f >= T.wipe && f < T.dOut + 40 && <div style={{ position: 'absolute', left: 110, top: 128, width: 700 }}>
      <p style={{ margin: 0, fontFamily: F.mono, fontSize: 14, letterSpacing: '.16em', color: C.ink3, opacity: cIn(0) * 0.9, textTransform: 'uppercase' }}>
        Recorded · Meta Muse Spark agent · {runDate(before.started_at)}</p>
      <p style={{ margin: '20px 0 0', fontFamily: F.serif, fontSize: 30, lineHeight: 1.25, color: C.ink2, opacity: cIn(6) }}>“{before.task.customer_wording}”</p>
      <div style={{ marginTop: 26, opacity: cIn(14) }}><StepBudget used={step.step} max={before.task.max_model_requests} label={`Step ${step.step} of ${before.task.max_model_requests}`} /></div>
      <p style={{ margin: '16px 0 0', fontFamily: F.mono, fontSize: 17, color: C.signal2, opacity: actionIn * (1 - recede) }}>→ {actionLabel(step)}</p>
    </div>}
    {f >= T.obs && f < T.dOut + 40 && <div style={{ position: 'absolute', left: 110, top: 560, width: 730, opacity: 1 - recede }}>
      <p style={{ margin: 0, fontFamily: F.mono, fontSize: 14, letterSpacing: '.16em', color: C.ink3, textTransform: 'uppercase', opacity: k(f, [T.obs, T.obs + 14], [0, 1]) }}>
        The agent’s own note · step {step2.step}</p>
      <p style={{ margin: '14px 0 0', fontFamily: F.mono, fontSize: 19, color: C.ink3, opacity: k(f, [T.obs + 4, T.obs + 18], [0, 1]) }}>{OBS_LEAD}</p>
      <p style={{ margin: '14px 0 0', fontFamily: F.serif, fontSize: 64, lineHeight: 1.08, letterSpacing: '-.015em', color: C.ink }}>
        {obsWords.map((w, i) => { const o = k(f, [T.obs + 12 + i * 4, T.obs + 24 + i * 4], [0, 1]);
          return <span key={i} style={{ opacity: o, display: 'inline-block', transform: `translateY(${10 * (1 - o)}px)`, marginRight: '0.24em',
            color: /^(each|Beginner|Sat\/Sun)$/.test(w) ? C.signal2 : undefined }}>{w}</span>; })}
      </p>
    </div>}

    {/* D: Agent Readiness (no tagline; the narration leads into Act 2) */}
    {f >= T.mark && <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', opacity: 1 - k(f, [T.end, T.end + 26], [0, 1]) }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 34 }}>
        <Mark size={112} start={T.mark} />
        <span style={{ fontFamily: F.sans, fontWeight: 500, fontSize: 84, letterSpacing: '-.02em', color: C.ink, opacity: k(f, [T.word, T.word + 24], [0, 1]),
          transform: `translateX(${-16 * (1 - k(f, [T.word, T.word + 24], [0, 1]))}px)` }}>Agent Readiness</span>
      </div>
    </AbsoluteFill>}

    {/* sound: soft clicks on the two recorded clicks */}
    <Sequence from={T.c1Click} durationInFrames={20}><Sfx name="click" volume={0.5} /></Sequence>
    <Sequence from={T.c2Click} durationInFrames={20}><Sfx name="click" volume={0.5} /></Sequence>
    <Sequence from={T.mark + 20} durationInFrames={60}><Sfx name="chime" volume={0.35} /></Sequence>
    {captions && <Captions act={ACT1} f={f} />}
  </AbsoluteFill>;
}

export function Captions({ act, f }: { act: typeof ACT1; f: number }) {
  const line = act.lines.find(l => f >= l.at - 2 && f <= l.end + 12);   // subtitles: on with the first word, off just after the last
  return <div style={{ position: 'absolute', left: 0, right: 0, bottom: 30, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
    {act.status !== 'recorded' && <span style={{ fontFamily: F.mono, fontSize: 12, letterSpacing: '.16em', color: '#F2C14E' }}>NARRATION · PLACEHOLDER TIMING, NOT RECORDED</span>}
    {line && <span style={{ fontFamily: F.sans, fontSize: 30, color: '#fff', background: 'rgba(0,0,0,.72)', padding: '6px 16px', borderRadius: 6, maxWidth: 1500, textAlign: 'center' }}>{line.text}</span>}
  </div>;
}
