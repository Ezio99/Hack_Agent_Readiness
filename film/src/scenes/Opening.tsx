import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { BrowserWindow } from '../components/BrowserWindow';
import { ActionHighlight, PageImage, StepBudget, Typed } from '../components/Evidence';
import { Mark } from '../components/Mark';
import { actionLabel, before, boxes, runDate } from '../evidence';
import { C, F, camera, ease } from '../theme/tokens';

/** Act 1, the opening (25 s). A: the Larkspur website, floating in the dark. B: it is beautiful and made for people. C: a recorded Meta Muse
 *  Spark agent receives the hero task and takes its first two real steps. D: the question, then Agent Readiness.
 *  Website = the frozen Before snapshot rendered at 2x (scripts/capture.py); agent view = the agent's own recorded screenshots. */
export const OPENING_FRAMES = 750;

const T = { aIn: 6, bMove: 120, bCourses: 128, bScroll: [160, 282], cWipe: 284, c1Note: 318, c1Hi: 342, c1Click: 366, c2Cut: 392, c2Note: 402,
  c2Hi: 462, c2Click: 488, dOut: 525, q1: 545, q2: 585, qOut: 645, mark: 668, word: 694 } as const;

const W = 1100;                      // window content width, px
const S = W / 1265;                  // px per CSS px (the agents' layout is 1265 CSS px wide)
const H = Math.round(960 * S);       // content height: one agent viewport
const step1 = before.steps[0], step2 = before.steps[1];

const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;
const k = (f: number, input: readonly number[], output: number[], easing = ease) => interpolate(f, input as number[], output, { ...clamp, easing });

/** Proposed narration (not recorded yet), shown only in the captions render. ~140 wpm. */
export const NARRATION: [number, number, string][] = [
  [12, 112, 'This is Larkspur Community College.'],
  [128, 280, 'Its new website is beautiful, clear, and easy for people to use.'],
  [296, 398, 'Now, AI agents browse for us.'],
  [402, 522, 'We asked one, powered by Meta Muse Spark: which beginner courses meet on weekends?'],
  [536, 642, 'It works for people. But can an agent actually use it?'],
  [668, 742, 'Agent Readiness finds out.'],
];

export function Opening({ captions = false }: { captions?: boolean }) {
  const f = useCurrentFrame();

  // ---- the window (camera) ----
  const rise = k(f, [T.aIn, 72], [0, 1]);
  const toSide = k(f, [T.bMove, T.bMove + 42], [0, 1], camera);
  const recede = k(f, [T.dOut, T.dOut + 40], [0, 1], camera);
  const push = interpolate(f, [0, T.bMove], [0, 0.035], clamp);
  const scale = (0.9 + 0.1 * rise + push) * (1 - 0.2 * toSide) + 0.02 * k(f, [T.cWipe, T.dOut], [0, 1], camera) * (1 - recede) - 0.08 * recede;
  const x = 330 * toSide * (1 - recede);
  const y = 70 * (1 - rise) + 8 * toSide;
  const winOpacity = Math.min(rise * 1.4, 1) * (1 - 0.88 * recede) * (1 - k(f, [T.qOut, T.qOut + 18], [0, 1]));
  const blur = 14 * (1 - rise) + 7 * recede;

  // ---- window content ----
  const coursesIn = k(f, [T.bCourses, T.bCourses + 22], [0, 1]);
  const scroll = k(f, [T.bScroll[0], T.bScroll[1]], [0, 560], camera);
  const wipe = k(f, [T.cWipe, T.cWipe + 20], [0, 1], camera);            // website -> the agent's recorded view
  const cut2 = k(f, [T.c2Cut, T.c2Cut + 8], [0, 1]);
  const recorded = f >= T.cWipe;
  const path = f < T.bCourses + 10 ? '/' : !recorded ? '/courses' : f < T.c2Cut ? step1.path : step2.path;
  const badge = recorded ? <span style={{ opacity: wipe, display: 'inline-flex', alignItems: 'center', gap: 8, padding: '4px 12px', borderRadius: 999,
    background: 'rgba(114,128,242,.16)', color: C.signal2, fontFamily: F.mono, fontSize: 13, letterSpacing: '.12em' }}>
    <span style={{ width: 7, height: 7, borderRadius: 4, background: C.signal }} />RECORDED</span> : null;

  // ---- left column ----
  const bText = (d: number) => k(f, [T.bMove + 18 + d, T.bMove + 46 + d], [0, 1]) * (1 - k(f, [262, 280], [0, 1]));
  const cIn = (d: number) => k(f, [T.cWipe + 10 + d, T.cWipe + 34 + d], [0, 1]) * (1 - recede);
  const inC2 = f >= T.c2Cut;
  const step = inC2 ? step2 : step1;
  const noteStart = inC2 ? T.c2Note : T.c1Note, actionAt = (inC2 ? T.c2Click : T.c1Click) - 8;
  const noteSwap = inC2 ? k(f, [T.c2Cut - 6, T.c2Cut + 6], [0.35, 1]) : 1;

  return <AbsoluteFill style={{ background: C.bg, overflow: 'hidden' }}>
    <AbsoluteFill style={{ background: 'radial-gradient(ellipse 60% 55% at 55% 50%, rgba(237,234,227,.055), rgba(0,0,0,0) 70%)' }} />

    {/* the website */}
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
    {f >= T.bMove && f < 285 && <div style={{ position: 'absolute', left: 120, top: 340, width: 700 }}>
      <p style={{ margin: 0, fontFamily: F.mono, fontSize: 16, letterSpacing: '.16em', color: C.ink3, opacity: bText(0), textTransform: 'uppercase' }}>
        Larkspur Community College · a fictional college</p>
      {['Beautifully designed.', 'Easy to browse.', 'Made for people.'].map((t, i) =>
        <p key={t} style={{ margin: '22px 0 0', fontFamily: F.serif, fontSize: 68, lineHeight: 1.04, letterSpacing: '-.015em', color: i === 2 ? C.ink : C.ink2,
          fontStyle: i === 2 ? 'italic' : 'normal', opacity: bText(14 + 16 * i), transform: `translateY(${18 * (1 - bText(14 + 16 * i))}px)` }}>{t}</p>)}
    </div>}

    {/* C: a recorded agent takes the customer's task */}
    {f >= T.cWipe && f < T.dOut + 42 && <div style={{ position: 'absolute', left: 110, top: 205, width: 690 }}>
      <p style={{ margin: 0, fontFamily: F.mono, fontSize: 15, letterSpacing: '.16em', color: C.signal2, opacity: cIn(0), textTransform: 'uppercase' }}>
        Recorded run · {runDate(before.started_at)} · Meta Muse Spark agent</p>
      <div style={{ opacity: cIn(8), transform: `translateY(${14 * (1 - cIn(8))}px)`, marginTop: 30 }}>
        <p style={{ margin: 0, fontFamily: F.mono, fontSize: 14, letterSpacing: '.16em', color: C.ink3, textTransform: 'uppercase' }}>Customer task</p>
        <p style={{ margin: '12px 0 0', fontFamily: F.serif, fontSize: 38, lineHeight: 1.22, color: C.ink }}>“{before.task.customer_wording}”</p>
      </div>
      <div style={{ marginTop: 40, opacity: cIn(22) }}>
        <StepBudget used={step.step} max={before.task.max_model_requests} label={`Step ${step.step} of ${before.task.max_model_requests}`} />
      </div>
      <div style={{ marginTop: 26, padding: '22px 26px', borderRadius: 14, background: 'rgba(237,234,227,.045)', border: `1px solid ${C.rule}`,
        opacity: cIn(26) * noteSwap, minHeight: 190 }}>
        <p style={{ margin: 0, fontFamily: F.mono, fontSize: 13, letterSpacing: '.16em', color: C.ink3, textTransform: 'uppercase' }}>The agent’s own note · step {step.step}</p>
        <p style={{ margin: '14px 0 0', fontFamily: F.mono, fontSize: 21, lineHeight: 1.5, color: C.ink }}><Typed key={step.step} text={step.memory} start={noteStart} cps={62} /></p>
        <p style={{ margin: '16px 0 0', fontFamily: F.mono, fontSize: 18, color: C.signal2, opacity: k(f, [actionAt, actionAt + 10], [0, 1]) }}>→ {actionLabel(step)}</p>
      </div>
    </div>}

    {/* D: the question */}
    {f >= T.q1 - 5 && f < T.qOut + 25 && <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', opacity: 1 - k(f, [T.qOut, T.qOut + 16], [0, 1]) }}>
      <div style={{ textAlign: 'center' }}>
        <p style={{ margin: 0, fontFamily: F.serif, fontSize: 104, letterSpacing: '-.02em', color: C.ink2, opacity: k(f, [T.q1, T.q1 + 26], [0, 1]),
          transform: `translateY(${20 * (1 - k(f, [T.q1, T.q1 + 26], [0, 1]))}px)` }}>It works for people.</p>
        <p style={{ margin: '18px 0 0', fontFamily: F.serif, fontStyle: 'italic', fontSize: 104, letterSpacing: '-.02em', color: C.ink, opacity: k(f, [T.q2, T.q2 + 26], [0, 1]),
          transform: `translateY(${20 * (1 - k(f, [T.q2, T.q2 + 26], [0, 1]))}px)` }}>Can an AI agent actually use it?</p>
      </div>
    </AbsoluteFill>}

    {/* Agent Readiness */}
    {f >= T.mark && <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 34 }}>
        <Mark size={112} start={T.mark} />
        <span style={{ fontFamily: F.sans, fontWeight: 500, fontSize: 84, letterSpacing: '-.02em', color: C.ink, opacity: k(f, [T.word, T.word + 24], [0, 1]),
          transform: `translateX(${-16 * (1 - k(f, [T.word, T.word + 24], [0, 1]))}px)` }}>Agent Readiness</span>
      </div>
    </AbsoluteFill>}

    {captions && <Captions f={f} />}
  </AbsoluteFill>;
}

function Captions({ f }: { f: number }) {
  const line = NARRATION.find(([a, b]) => f >= a && f <= b);
  return <div style={{ position: 'absolute', left: 0, right: 0, bottom: 34, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
    <span style={{ fontFamily: F.mono, fontSize: 12, letterSpacing: '.16em', color: '#F2C14E' }}>PROPOSED NARRATION · NOT RECORDED</span>
    {line && <span style={{ fontFamily: F.sans, fontSize: 30, color: '#fff', background: 'rgba(0,0,0,.72)', padding: '6px 16px', borderRadius: 6 }}>{line[2]}</span>}
  </div>;
}
