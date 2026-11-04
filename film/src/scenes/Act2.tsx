import type React from 'react';
import { AbsoluteFill, Img, interpolate, Sequence, staticFile, useCurrentFrame } from 'remotion';
import product from '../../data/product.json';
import { BrowserWindow } from '../components/BrowserWindow';
import { PageImage } from '../components/Evidence';
import { Sfx } from '../components/Sound';
import { actionLabel, after, before, courses, excerpt, runDate, type Step } from '../evidence';
import { ACT2, cue } from '../narration';
import { C, F, camera, ease } from '../theme/tokens';
import { Captions } from './Opening';

/** Act 2, the investigation (50 s). The hero task's recorded Before run, step by step: the facts the agent needs are on 14 separate course pages;
 *  it opens them one at a time while its 14-step budget drains; it stops ("Out of steps", with 3 steps unused, as recorded) and names 2 of the 4
 *  right courses. Then Agent Readiness's own report, as the product shows it, traces the failure to its cause.
 *  Every screen is the agent's recorded screenshot of that step; every note is a verbatim excerpt (checked against the record at build time);
 *  nothing is shown for an action the agent did not take. */
export const ACT2_FRAMES = ACT2.frames;

const MAX = before.task.max_model_requests;                       // 14
const steps = before.steps;                                        // 11 recorded steps
const st = (n: number) => steps[n - 1];
/** When each recorded step takes the screen (act-local frames). The tempo rises as the budget drains. */
const AT: Record<number, number> = { 2: 0, 3: 300, 4: 410, 5: 500, 6: 585, 7: 665, 8: 735, 9: 795, 10: 850, 11: 905 };
const STOP = cue('a2.stops') - 10, ANSWER = STOP + 62, DIAG = cue('a2.recorded') - 10, CAUSE = cue('a2.cause');
/** The headline excerpt of each step's note (verbatim). */
const NOTE: Record<number, string> = {
  2: excerpt(st(2), 'Need to check each for Beginner level + Sat/Sun meeting.'),
  3: excerpt(st(3), 'Checked 1/14: Watercolour foundations (Beginner, Tuesday) excluded.'),
  4: excerpt(st(4), 'Got listing of 14 courses, need hrefs to visit systematically.'),
  5: excerpt(st(5), 'Now checking beginners-yoga.'),
  6: excerpt(st(6), 'Beginners yoga qualifies (Beginner Sat). Need to check remaining 12 efficiently.'),
  7: excerpt(st(7), 'Need remaining 12 courses details.'),
  8: excerpt(st(8), 'Need to check remaining 12 for Beginner + Sat/Sun with limited steps.'),
  9: excerpt(st(9), 'Wheel-thrown pottery qualifies (Beginner Sat).'),
  10: excerpt(st(10), 'Need remaining 11 but low on steps (step 10/14).'),
  11: excerpt(st(11), 'Out of steps, returning confirmed 2 weekend Beginner courses.'),
};
/** Courses the agent's notes record as checked, the step whose note first records it, and the verdict in the note's words. */
const CHECKED: { name: string; step: number; ok: boolean; day: string }[] = [
  { name: 'Watercolour foundations', step: 3, ok: false, day: 'Tue' },
  { name: 'Beginners yoga', step: 6, ok: true, day: 'Sat' },
  { name: 'Wheel-thrown pottery', step: 9, ok: true, day: 'Sat' },
];
CHECKED.forEach(c => excerpt(st(c.step), c.ok ? `${c.name.split(' ')[0]}` : 'excluded'));
/** The four right courses: the After run's answer to the same task, which the official grader matched to the college's own records. */
if (!after.official_v1 || !after.correct_v2) throw new Error('the After task-2 answer is no longer graded correct');
const RIGHT = after.answer;
const FOUND = new Set(before.answer);
const PAGE = product.pages['report-before-t2'];

const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;
const k = (f: number, i: readonly number[], o: number[], easing = ease) => interpolate(f, i as number[], o, { ...clamp, easing });
const W = 1000, S = W / 1265, H = Math.round(960 * S);

export function Act2({ captions = false }: { captions?: boolean }) {
  const f = useCurrentFrame();
  const cur = Math.max(...Object.keys(AT).map(Number).filter(n => f >= AT[n]));
  const used = cur;                                                // one recorded step = one model request (11 steps, 11 requests)
  const loopOut = k(f, [DIAG - 30, DIAG], [0, 1]);
  const stopDim = k(f, [STOP, STOP + 20], [0, 1]);
  const intro = k(f, [0, 24], [0, 1]);

  return <AbsoluteFill style={{ background: C.bg, overflow: 'hidden' }}>
    <AbsoluteFill style={{ background: 'radial-gradient(ellipse 55% 60% at 32% 55%, rgba(237,234,227,.05), rgba(0,0,0,0) 70%)' }} />

    {/* HUD: provenance + the draining budget */}
    <div style={{ position: 'absolute', left: 90, right: 80, top: 44, display: 'flex', alignItems: 'center', justifyContent: 'space-between', opacity: intro * (1 - loopOut) }}>
      <span style={{ fontFamily: F.mono, fontSize: 15, letterSpacing: '.14em', color: C.ink3, textTransform: 'uppercase' }}>
        <span style={{ color: C.signal2 }}>●</span>{'  '}Recorded · a real Meta Muse Spark browser agent · {runDate(before.started_at)}</span>
      <Budget f={f} used={used} stepAt={AT[cur]} final={f >= STOP} />
    </div>

    {/* the stack of recorded browser windows: each step's own screenshot; earlier ones pile up behind */}
    <AbsoluteFill style={{ opacity: intro * (1 - loopOut) * (1 - 0.78 * stopDim), filter: stopDim > 0 ? `blur(${6 * stopDim}px)` : undefined }}>
      {Object.keys(AT).map(Number).filter(n => n <= cur && n >= cur - 3).map(n => {
        const d = cur - n, enter = k(f, [AT[n], AT[n] + (n >= 7 ? 7 : 11)], [0, 1]);
        const dx = -30 * d + 70 * (1 - enter), dy = -26 * d, sc = (0.965 ** d) * (0.985 + 0.015 * enter);
        return <BrowserWindow key={n} width={W} height={H} path={st(n).path}
          badge={<span style={{ fontFamily: F.mono, fontSize: 13, letterSpacing: '.12em', color: C.signal2 }}>STEP {n}</span>}
          style={{ left: 120, top: 156, transform: `translate(${dx}px, ${dy}px) scale(${sc})`, transformOrigin: 'top left', opacity: (d === 0 ? enter : 1) * 0.62 ** d, zIndex: 10 - d }}>
          <PageImage src={st(n).screenshot} cssWidth={1280} scale={S} />
        </BrowserWindow>;
      })}
    </AbsoluteFill>

    {/* opening beat: the facts it needs live on 14 separate pages */}
    {f < AT[3] + 20 && <RightColumn opacity={intro * (1 - k(f, [AT[3] - 20, AT[3]], [0, 1]))}>
      <p style={label}>To answer, it needs two facts per course</p>
      <p style={{ margin: '16px 0 0', fontFamily: F.serif, fontSize: 56, lineHeight: 1.05, color: C.ink, opacity: k(f, [cue('a2.facts') + 30, cue('a2.facts') + 50], [0, 1]) }}>
        Level. <span style={{ color: C.ink2 }}>Meeting day.</span></p>
      <p style={{ ...label, marginTop: 34, opacity: k(f, [cue('a2.pages'), cue('a2.pages') + 20], [0, 1]) }}>Where they are: one page per course</p>
      <div style={{ marginTop: 14, display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 12 }}>
        {courses.map((c, i) => { const o = k(f, [cue('a2.pages') + 20 + i * 3, cue('a2.pages') + 34 + i * 3], [0, 1]);
          return <figure key={c.path} style={{ margin: 0, opacity: o, transform: `translateY(${16 * (1 - o)}px)` }}>
            <Img src={staticFile(c.image)} style={{ width: '100%', borderRadius: 6, outline: `1px solid ${C.rule}`, display: 'block' }} />
            <figcaption style={{ marginTop: 5, fontFamily: F.mono, fontSize: 11, color: C.ink3, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.name}</figcaption>
          </figure>; })}
      </div>
    </RightColumn>}

    {/* the loop: a ledger of what it has checked + its own note, large */}
    {f >= AT[3] - 10 && f < DIAG && <RightColumn opacity={k(f, [AT[3] - 10, AT[3] + 10], [0, 1]) * (1 - loopOut) * (1 - stopDim)}>
      <Ledger f={f} />
      <div style={{ marginTop: 36 }}>
        <p style={label}>The agent’s own note · step {cur}</p>
        <p key={cur} style={{ margin: '12px 0 0', fontFamily: F.serif, fontSize: cur >= 10 ? 46 : 40, lineHeight: 1.14, color: cur >= 10 ? C.ink : C.ink2,
          opacity: k(f, [AT[cur] + 2, AT[cur] + 12], [0, 1]), transform: `translateY(${12 * (1 - k(f, [AT[cur] + 2, AT[cur] + 12], [0, 1]))}px)` }}>“{NOTE[cur]}”</p>
        <p style={{ margin: '16px 0 0', fontFamily: F.mono, fontSize: 17, color: C.signal2, opacity: k(f, [AT[cur] + 10, AT[cur] + 18], [0, 1]) }}>→ {actionLabel(st(cur))}</p>
      </div>
    </RightColumn>}

    {/* out of steps: the agent's words, then its answer */}
    {f >= STOP && f < DIAG && <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', opacity: 1 - loopOut }}>
      <div style={{ textAlign: 'center', transform: `translateY(${-90 * k(f, [ANSWER, ANSWER + 24], [0, 1], camera)}px)` }}>
        <p style={{ margin: 0, fontFamily: F.serif, fontSize: 150, letterSpacing: '-.025em', color: C.ink, opacity: k(f, [STOP + 6, STOP + 22], [0, 1]) }}>“Out of steps.”</p>
        <p style={{ margin: '6px 0 0', fontFamily: F.mono, fontSize: 18, letterSpacing: '.12em', color: C.ink3, textTransform: 'uppercase', opacity: k(f, [STOP + 22, STOP + 36], [0, 1]) }}>
          The agent’s own note, step 11 · it stopped itself with {MAX - 11} of {MAX} steps left</p>
      </div>
      <div style={{ position: 'absolute', top: 640, display: 'flex', gap: 18, opacity: k(f, [ANSWER, ANSWER + 20], [0, 1]) }}>
        {RIGHT.map((name, i) => { const ok = FOUND.has(name), o = k(f, [ANSWER + 10 + i * 8, ANSWER + 26 + i * 8], [0, 1]);
          return <div key={name} style={{ width: 360, padding: '18px 22px', borderRadius: 12, opacity: o, border: `1px solid ${ok ? 'rgba(95,191,136,.5)' : 'rgba(216,108,69,.5)'}`,
            background: ok ? 'rgba(95,191,136,.08)' : 'rgba(216,108,69,.06)' }}>
            <p style={{ margin: 0, fontFamily: F.mono, fontSize: 13, letterSpacing: '.14em', color: ok ? C.pass : C.rust }}>{ok ? '✓ FOUND' : '✕ MISSED'}</p>
            <p style={{ margin: '8px 0 0', fontFamily: F.serif, fontSize: 28, whiteSpace: 'nowrap', color: ok ? C.ink : C.ink3 }}>{name}</p>
          </div>; })}
      </div>
      <p style={{ position: 'absolute', top: 790, margin: 0, fontFamily: F.sans, fontSize: 30, color: C.ink2, opacity: k(f, [ANSWER + 50, ANSWER + 66], [0, 1]) }}>
        It named <b style={{ color: C.ink }}>2 of the 4</b> beginner weekend courses.</p>
    </AbsoluteFill>}

    {/* diagnosis: Agent Readiness's own report, as the product shows it */}
    {f >= DIAG - 20 && <Diagnosis f={f} />}

    {/* sound: a tick for every recorded step as it spends the budget; a low stop */}
    {Object.keys(AT).map(Number).filter(n => n >= 3).map(n => <Sequence key={n} from={AT[n]} durationInFrames={12}><Sfx name="tick" volume={0.32 + 0.03 * (n - 3)} /></Sequence>)}
    <Sequence from={STOP + 4} durationInFrames={40}><Sfx name="stop" volume={0.5} /></Sequence>
    {captions && <Captions act={ACT2} f={f} />}
  </AbsoluteFill>;
}

const label = { margin: 0, fontFamily: F.mono, fontSize: 14, letterSpacing: '.16em', color: C.ink3, textTransform: 'uppercase' } as const;

function RightColumn({ opacity, children }: { opacity: number; children: React.ReactNode }) {
  return <div style={{ position: 'absolute', left: 1180, top: 150, width: 660, opacity }}>{children}</div>;
}

/** The interaction budget, draining: the remaining steps are bright; each recorded step spends one. Below 5 left they turn rust. */
function Budget({ f, used, stepAt, final }: { f: number; used: number; stepAt: number; final: boolean }) {
  const left = MAX - used, flash = 1 - k(f, [stepAt, stepAt + 12], [0, 1]);
  return <div style={{ display: 'flex', alignItems: 'center', gap: 22 }}>
    <span style={{ fontFamily: F.mono, fontSize: 15, letterSpacing: '.14em', color: C.ink3, textTransform: 'uppercase' }}>Steps left</span>
    <div style={{ display: 'flex', gap: 6 }}>{Array.from({ length: MAX }, (_, i) => {
      const spent = i < used, justSpent = i === used - 1;
      const bg = spent ? (justSpent ? `rgba(237,234,227,${0.12 + 0.6 * flash})` : 'rgba(237,234,227,.08)') : left <= 4 ? C.rust : C.signal;
      return <span key={i} style={{ width: 30, height: 14, borderRadius: 3, background: bg, opacity: spent ? 1 : final ? 0.55 : 1 }} />; })}</div>
    <span style={{ fontFamily: F.mono, fontSize: 30, color: left <= 4 ? C.rust : C.ink, minWidth: 110, textAlign: 'right' }}>{left}<span style={{ fontSize: 16, color: C.ink3 }}> / {MAX}</span></span>
  </div>;
}

/** The 14 courses and what the agent's notes record about each so far. */
function Ledger({ f }: { f: number }) {
  const checked = CHECKED.filter(c => f >= AT[c.step]);
  return <div>
    <p style={label}>Courses checked: <span style={{ color: C.ink, fontSize: 18 }}>{checked.length}</span> of {courses.length}</p>
    <div style={{ marginTop: 14, display: 'grid', gridTemplateColumns: '1fr 1fr', columnGap: 26, rowGap: 6 }}>
      {courses.map(c => { const r = checked.find(x => x.name === c.name); const o = r ? k(f, [AT[r.step], AT[r.step] + 10], [0, 1]) : 0;
        return <div key={c.path} style={{ display: 'flex', justifyContent: 'space-between', gap: 10, fontFamily: F.sans, fontSize: 17, padding: '5px 0', whiteSpace: 'nowrap', borderBottom: `1px solid ${C.rule}`,
          color: r ? C.ink : 'rgba(237,234,227,.34)' }}>
          <span>{c.name}</span>
          <span style={{ fontFamily: F.mono, fontSize: 15, color: r ? (r.ok ? C.pass : C.rust) : 'rgba(237,234,227,.3)', opacity: r ? o : 1 }}>{r ? `${r.ok ? '✓' : '✕'} ${r.day}` : '—'}</span>
        </div>; })}
    </div>
  </div>;
}

/** The product's readiness report for this run (captured read-only from the deployed product): camera moves between what it recorded
 *  (2 of 4, 11 of 14 requests), where the facts were (level, class day: item pages only) and its finding + recommendation. */
function Diagnosis({ f }: { f: number }) {
  const RW = 1280, RS = RW / 1440, RH = 760;
  const b = PAGE.boxes;
  // camera: [frame, scrollY, zoom, focus x, focus y] (CSS px of the report page); the focus point is brought to the frame's centre
  const mid = (bx: { x: number; y: number; width: number; height: number }) => [bx.x + bx.width / 2, bx.y + bx.height / 2];
  const [sx, sy] = [b.stats.x + b.stats.width / 2, (b.stats.y + b.answer.y + b.answer.height) / 2];
  const [px, py] = [b.places.x + 380, mid(b.places)[1]];
  const [fx_, fy_] = mid(b.finding_class_day);
  const shots: [number, number, number, number, number, number, number][] = [     // ..., target x, target y on screen
    [DIAG, b.side.y - 40, 1.3, sx, sy, 780, 500], [DIAG + 96, b.side.y - 40, 1.38, sx, sy, 780, 500],
    [DIAG + 116, b.places.y - 14, 1.45, px, py, 900, 250], [CAUSE - 24, b.places.y - 14, 1.5, px, py, 900, 250],
    [CAUSE, b.finding_class_day.y - 220, 1.5, fx_, fy_, 820, 500], [ACT2.frames, b.finding_class_day.y - 220, 1.58, fx_, fy_, 820, 500]];
  const at = (i: 1 | 2 | 3 | 4 | 5 | 6) => interpolate(f, shots.map(s => s[0]), shots.map(s => s[i]), { ...clamp, easing: camera });
  const scrollY = at(1), zoom = at(2), focusX = at(3), focusY = at(4), targetX = at(5), targetY = at(6);
  const L0 = 320, T0 = 110;
  const tx = targetX - (L0 + zoom * focusX * RS), ty = targetY - (T0 + zoom * (46 + (focusY - scrollY) * RS));
  const appear = k(f, [DIAG - 20, DIAG + 10], [0, 1], camera);
  const hi = (box: { x: number; y: number; width: number; height: number }, from: number, to: number) => {
    const o = k(f, [from, from + 14], [0, 1]) * (1 - k(f, [to, to + 10], [0, 1]));
    return o > 0 && <div style={{ position: 'absolute', left: (box.x - 10) * RS, top: (box.y - 10 - scrollY) * RS, width: (box.width + 20) * RS, height: (box.height + 20) * RS,
      border: `3px solid ${C.signalStrong}`, borderRadius: 10, background: 'rgba(43,59,230,.05)', opacity: o }} />;
  };
  return <AbsoluteFill style={{ opacity: appear }}>
    <div style={{ position: 'absolute', left: L0, top: T0, transform: `translate(${tx}px, ${ty + 30 * (1 - appear)}px) scale(${zoom})`, transformOrigin: '0 0' }}>
      <BrowserWindow width={RW} height={RH} site="Agent Readiness" path="/ live report · Before · task 2" style={{ position: 'relative' }}>
        <div style={{ position: 'absolute', inset: 0, background: '#F2F0EB' }} />
        <PageImage src={PAGE.image} cssWidth={1440} scale={RS} scrollY={scrollY} />
        {hi(b.stats, DIAG + 24, DIAG + 96)}{hi(b.answer, DIAG + 34, DIAG + 96)}
        {hi(b.places, DIAG + 118, CAUSE - 26)}
        {hi(b.finding_class_day, CAUSE + 24, ACT2.frames)}
      </BrowserWindow>
    </div>
    <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: 120, background: 'linear-gradient(rgba(11,11,10,.96) 45%, rgba(11,11,10,0))' }} />
    <p style={{ position: 'absolute', left: 90, top: 44, ...label, color: C.signal2 }}>Agent Readiness · the readiness report for this run, as the product shows it</p>
    <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: 230, background: 'linear-gradient(rgba(11,11,10,0), rgba(11,11,10,.96) 55%)' }} />
    <div style={{ position: 'absolute', left: 90, bottom: 44, width: 1740, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
      {[['Evidence', 'Every step, screenshot and note, recorded', DIAG + 20, DIAG + 100], ['Diagnosis', 'Level and class day: on course pages only', DIAG + 110, CAUSE - 20],
        ['Finding', 'Cards omit ‘class day’: state it on each card', CAUSE + 10, ACT2.frames]].map(([t, d, a, z]) =>
        <div key={t as string} style={{ opacity: 0.35 + 0.65 * k(f, [a as number, (a as number) + 14], [0, 1]) * (1 - k(f, [z as number, (z as number) + 10], [0, 1])) }}>
          <p style={{ ...label, color: C.signal2 }}>{t}</p>
          <p style={{ margin: '8px 0 0', fontFamily: F.serif, fontSize: 30, color: C.ink }}>{d}</p>
        </div>)}
    </div>
  </AbsoluteFill>;
}
