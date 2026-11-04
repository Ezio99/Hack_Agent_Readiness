import { AbsoluteFill, interpolate, Sequence, useCurrentFrame } from 'remotion';
import P from '../../data/paired.json';
import { BrowserWindow } from '../components/BrowserWindow';
import { PageImage } from '../components/Evidence';
import { Sfx } from '../components/Sound';
import { runDate } from '../evidence';
import { ACT4, cue } from '../narration';
import { C, F, camera, ease } from '../theme/tokens';
import { Captions } from './Opening';

/** Act 4, the proof (40 s). EXCLUSIVELY the paired verification run eval-1cf64d5e: Before and After evaluated together in one new evaluation,
 *  with the same 3 tasks, agent and 14-request limit. Hero task first (Before busy and draining; After clean and quick), then correct answers
 *  0/3 -> 3/3 and the three reductions, then the product's Live report for this run. Nothing from the earlier runs appears in this act.
 *  "Correct" = the product's Correct answers (post-hoc grader v2); exact match (official grader v1) is a separate metric and is not claimed. */
export const ACT4_FRAMES = ACT4.frames;

type Step = { step: number; path: string; memory: string; actions: { name: string; target: string | null }[]; screenshot: string };
const BEF = P.versions.Before, AFT = P.versions.After;
const HB = P.hero.Before as unknown as { steps: Step[]; answer: string[]; requests: number; seconds: number; course_pages_opened: number; correct: boolean };
const HA = P.hero.After as unknown as typeof HB;
const LIMIT = P.limit;
const pct = (a: number, b: number) => Math.round((1 - b / a) * 100);
const RED = { requests: pct(BEF.requests, AFT.requests), time: pct(BEF.seconds, AFT.seconds), cost: pct(BEF.cost_usd, AFT.cost_usd) };
// the narration states these numbers: fail the build if the record ever disagrees
if (RED.requests !== 74 || RED.time !== 83 || RED.cost !== 77 || BEF.correct !== 0 || AFT.correct !== 3 || HB.requests !== 13 || HA.requests !== 3 || HA.course_pages_opened !== 0)
  throw new Error(`paired-run figures changed: ${JSON.stringify(RED)}`);
const RIGHT = HA.answer;                                     // the After answer, graded correct
if (!HA.correct || HB.correct) throw new Error('hero grades changed');
const FOUND_B = new Set(HB.answer);
const ex = (s: Step, t: string) => { if (!s.memory.includes(t)) throw new Error(`step ${s.step}: "${t}" not in note`); return t; };
/** Before: the notes that tell its story (verbatim excerpts), by step. */
const NB: Record<number, string> = {
  2: ex(HB.steps[1], 'Need to check each course\'s level and meeting days for Beginner + Sat/Sun.'),
  4: ex(HB.steps[3], 'Checked 1/14: watercolour-foundations excluded (Tue).'),
  7: ex(HB.steps[6], 'Checked 2/14'),
  9: ex(HB.steps[8], 'Matches so far: Beginners yoga (Beginner Sat).'),
  12: ex(HB.steps[11], 'Excluded: watercolour Tue, life-drawing Thu, Italian1 Mon.'),
  13: ex(HB.steps[12], 'Remaining 10 unchecked due to step budget, returning partial verified result.'),
};
const NA2 = ex(HA.steps[1], 'Found 4 candidates: Wheel-thrown pottery (Sat), Beginners yoga (Sat), Mindful meditation (Sun), Home electrical basics (Sat) - all Beginner.');
const REPORT = P.product.live;

const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;
const k = (f: number, i: readonly number[], o: number[], easing = ease) => interpolate(f, i as number[], o, { ...clamp, easing });
const label = { margin: 0, fontFamily: F.mono, fontSize: 14, letterSpacing: '.16em', color: C.ink3, textTransform: 'uppercase' } as const;
const when = new Date(P.started_at).toLocaleString('en-AU', { timeZone: 'Australia/Sydney', day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit' });

const B = { title: 0, before: cue('a4.before') - 15, bStep0: cue('a4.before') + 5, after: cue('a4.after') - 15, correct: cue('a4.correct') - 20,
  metrics: cue('a4.metrics') - 10, works: cue('a4.works') - 15 };
const BSTEP = Math.min(16, Math.floor((B.after - 26 - B.bStep0) / HB.steps.length));   // Before: one recorded step every ~16 frames (fast, busy), done before After starts
const ASTEP = [B.after + 10, B.after + 50, B.after + 110];     // After: three steps, unhurried

export function Act4({ captions = false }: { captions?: boolean }) {
  const f = useCurrentFrame();
  return <AbsoluteFill style={{ background: C.bg, overflow: 'hidden' }}>
    <AbsoluteFill style={{ background: 'radial-gradient(ellipse 60% 55% at 50% 50%, rgba(237,234,227,.05), rgba(0,0,0,0) 70%)' }} />
    {f < B.before + 20 && <Title f={f} />}
    {f >= B.before - 10 && f < B.correct + 20 && <Hero f={f} />}
    {f >= B.correct - 10 && f < B.metrics + 20 && <Correct f={f} />}
    {f >= B.metrics - 10 && f < B.works + 20 && <Metrics f={f} />}
    {f >= B.works - 10 && <Live f={f} />}
    {HB.steps.map((_, i) => <Sequence key={i} from={B.bStep0 + i * BSTEP} durationInFrames={10}><Sfx name="tick" volume={0.2} /></Sequence>)}
    {ASTEP.map((t, i) => <Sequence key={'a' + i} from={t} durationInFrames={20}><Sfx name="click" volume={0.35} /></Sequence>)}
    <Sequence from={cue('a4.correct') + 6} durationInFrames={70}><Sfx name="chime" volume={0.4} /></Sequence>
    {captions && <Captions act={ACT4} f={f} />}
  </AbsoluteFill>;
}

/** A new evaluation, not a continuation of the diagnostic run. */
function Title({ f }: { f: number }) {
  const o = k(f, [4, 28], [0, 1]) * (1 - k(f, [B.before - 10, B.before + 10], [0, 1]));
  const chips = [`Same ${P.tasks.length} customer tasks`, 'Same Meta Muse Spark agent', `Same ${LIMIT}-step limit`];
  return <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', opacity: o }}>
    <div style={{ textAlign: 'center' }}>
      <p style={{ ...label, color: C.pass }}>A new live evaluation · {when}</p>
      <p style={{ margin: '22px 0 0', fontFamily: F.serif, fontSize: 100, letterSpacing: '-.02em', color: C.ink, lineHeight: 1.04 }}>Before and After,<br /><em>side by side.</em></p>
      <div style={{ marginTop: 40, display: 'flex', gap: 16, justifyContent: 'center' }}>
        {chips.map((c, i) => { const co = k(f, [30 + i * 10, 46 + i * 10], [0, 1]);
          return <span key={c} style={{ opacity: co, padding: '10px 20px', borderRadius: 999, border: `1px solid ${C.rule}`, fontFamily: F.sans, fontSize: 22, color: C.ink2 }}>{c}</span>; })}
      </div>
      <p style={{ margin: '28px 0 0', fontFamily: F.mono, fontSize: 15, letterSpacing: '.1em', color: C.ink3, opacity: k(f, [70, 90], [0, 1]) }}>
        Both versions in one evaluation · run {P.evaluation.slice(5, 13)}</p>
    </div>
  </AbsoluteFill>;
}

/** The hero task, both versions of the same new evaluation. Left: Before, busy and draining. Right: After, clean and quick. */
function Hero({ f }: { f: number }) {
  const o = k(f, [B.before - 10, B.before + 14], [0, 1]) * (1 - k(f, [B.correct - 26, B.correct - 6], [0, 1]));
  const W = 800, S = W / 1265, H = Math.round(960 * S * 0.74);
  const bi = Math.max(0, Math.min(HB.steps.length - 1, Math.floor((f - B.bStep0) / BSTEP)));
  const bDone = f >= B.bStep0 + HB.steps.length * BSTEP;
  const bUsed = f < B.bStep0 ? 0 : bi + 1;
  const ai = ASTEP.filter(t => f >= t).length - 1;
  const aOn = f >= B.after - 10;
  const aDone = f >= ASTEP[2] + 30;
  const bDim = 1 - 0.55 * k(f, [B.after - 10, B.after + 10], [0, 1]);
  const bNoteKey = Math.max(...Object.keys(NB).map(Number).filter(n => n <= bUsed), 2);
  return <AbsoluteFill style={{ opacity: o }}>
    <p style={{ position: 'absolute', left: 90, top: 40, ...label, color: C.ink2 }}>Task 2 · “{P.tasks[1].customer_wording}”</p>
    {/* Before */}
    <div style={{ position: 'absolute', left: 90, top: 100, width: W, opacity: bDim }}>
      <Side name="Before" color={C.rust} used={bUsed} limit={LIMIT} />
      <div style={{ position: 'relative', height: H + 46 + 44, marginTop: 14 }}>
        {HB.steps.slice(Math.max(0, bi - 4), bi + 1).map((s, j, arr) => { const d = arr.length - 1 - j; const enter = d === 0 ? k(f, [B.bStep0 + bi * BSTEP, B.bStep0 + bi * BSTEP + 6], [0, 1]) : 1;
          return <BrowserWindow key={s.step} width={W} height={H} path={s.path} site=""
            badge={<span style={{ fontFamily: F.mono, fontSize: 12, color: C.rust }}>STEP {s.step}</span>}
            style={{ left: 18 * 4, top: 44, transform: `translate(${-18 * d + 60 * (1 - enter)}px, ${-11 * d}px) scale(${0.97 ** d})`, transformOrigin: 'top left', opacity: d ? 0.55 ** d : 1, zIndex: 10 - d }}>
            <PageImage src={s.screenshot} cssWidth={1280} scale={S} />
          </BrowserWindow>; })}
      </div>
      <p key={bNoteKey} style={{ margin: '18px 0 0', fontFamily: F.serif, fontSize: 30, lineHeight: 1.2, color: C.ink2, minHeight: 76 }}>“{NB[bNoteKey]}”</p>
      <Result found={HB.answer} show={bDone} f={f} at={B.bStep0 + HB.steps.length * BSTEP} stats={`${HB.requests} of ${LIMIT} requests · ${Math.round(HB.seconds)} s · ${HB.course_pages_opened} course pages opened`} />
    </div>
    {/* After */}
    <div style={{ position: 'absolute', left: 1030, top: 100, width: W, opacity: aOn ? 1 : 0.25 }}>
      <Side name="After" color={C.pass} used={aOn ? Math.max(0, ai + 1) : 0} limit={LIMIT} />
      <div style={{ position: 'relative', height: H + 46 + 44, marginTop: 14 }}>
        <BrowserWindow width={W} height={H} path={ai >= 0 ? HA.steps[ai].path : '/'} site="" style={{ left: 0, top: 44 }}
          badge={<span style={{ fontFamily: F.mono, fontSize: 12, color: C.pass }}>{ai >= 0 ? `STEP ${ai + 1}` : 'WAITING'}</span>}>
          {ai >= 0 && HA.steps.slice(0, ai + 1).map((s, j) => <PageImage key={s.step} src={s.screenshot} cssWidth={1280} scale={S}
            opacity={j === ai ? k(f, [ASTEP[j], ASTEP[j] + 10], [0, 1]) : 1} />)}
        </BrowserWindow>
      </div>
      <p style={{ margin: '18px 0 0', fontFamily: F.serif, fontSize: 30, lineHeight: 1.2, color: C.ink, minHeight: 76, opacity: k(f, [ASTEP[1] + 10, ASTEP[1] + 24], [0, 1]) }}>“{NA2}”</p>
      <Result found={HA.answer} show={aDone} f={f} at={ASTEP[2] + 30} stats={`${HA.requests} of ${LIMIT} requests · ${Math.round(HA.seconds)} s · no course pages opened`} />
    </div>
  </AbsoluteFill>;
}

function Side({ name, color, used, limit }: { name: string; color: string; used: number; limit: number }) {
  return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
    <span style={{ fontFamily: F.serif, fontSize: 40, color: C.ink }}><span style={{ display: 'inline-block', width: 14, height: 14, borderRadius: 3, background: color, marginRight: 14 }} />{name}</span>
    <span style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <span style={{ display: 'flex', gap: 4 }}>{Array.from({ length: limit }, (_, i) =>
        <span key={i} style={{ width: 22, height: 10, borderRadius: 2, background: i < used ? 'rgba(237,234,227,.1)' : limit - used <= 3 ? C.rust : C.signal }} />)}</span>
      <span style={{ fontFamily: F.mono, fontSize: 22, color: limit - used <= 3 ? C.rust : C.ink, minWidth: 70, textAlign: 'right' }}>{limit - used}<span style={{ fontSize: 13, color: C.ink3 }}> left</span></span>
    </span>
  </div>;
}

function Result({ found, show, f, at, stats }: { found: string[]; show: boolean; f: number; at: number; stats: string }) {
  const o = show ? k(f, [at, at + 14], [0, 1]) : 0;
  const got = new Set(found);
  return <div style={{ marginTop: 6, opacity: o }}>
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
      {RIGHT.map(n => <span key={n} style={{ padding: '6px 12px', borderRadius: 8, fontFamily: F.sans, fontSize: 17, color: got.has(n) ? C.ink : C.ink3,
        border: `1px solid ${got.has(n) ? 'rgba(95,191,136,.6)' : 'rgba(216,108,69,.45)'}`, background: got.has(n) ? 'rgba(95,191,136,.10)' : 'transparent' }}>{got.has(n) ? '✓' : '✕'} {n}</span>)}
    </div>
    <p style={{ margin: '12px 0 0', fontFamily: F.mono, fontSize: 16, color: C.ink3 }}>Found {RIGHT.filter(n => got.has(n)).length} of {RIGHT.length} · {stats}</p>
  </div>;
}

/** Correct answers across the three tasks: 0/3 -> 3/3. */
function Correct({ f }: { f: number }) {
  const o = k(f, [B.correct - 4, B.correct + 14], [0, 1]) * (1 - k(f, [B.metrics - 10, B.metrics + 8], [0, 1]));
  const flip = k(f, [cue('a4.correct') + 30, cue('a4.correct') + 50], [0, 1], camera);
  return <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', opacity: o }}>
    <p style={{ ...label, color: C.ink2 }}>Correct answers · all {P.tasks.length} customer tasks · checked against the college’s records</p>
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 60, marginTop: 20 }}>
      <span style={{ fontFamily: F.serif, fontSize: 260, color: C.rust, letterSpacing: '-.03em', opacity: 1 - 0.55 * flip }}>{BEF.correct}/{P.tasks.length}</span>
      <span style={{ fontFamily: F.serif, fontSize: 120, color: C.ink3, opacity: flip }}>→</span>
      <span style={{ fontFamily: F.serif, fontSize: 260, color: C.pass, letterSpacing: '-.03em', opacity: flip, transform: `scale(${0.9 + 0.1 * flip})`, display: 'inline-block' }}>{AFT.correct}/{P.tasks.length}</span>
    </div>
    <div style={{ display: 'flex', gap: 34, marginTop: 10 }}>
      {BEF.tasks.map((t, i) => { const ok = AFT.tasks[i].correct, s = k(f, [cue('a4.correct') + 40 + i * 8, cue('a4.correct') + 52 + i * 8], [0, 1]);
        return <span key={t.n} style={{ fontFamily: F.mono, fontSize: 20, color: C.ink3 }}>Task {t.n} <span style={{ color: C.rust }}>✕</span>{' '}
          <span style={{ color: ok ? C.pass : C.rust, opacity: s }}>→ {ok ? '✓' : '✕'}</span></span>; })}
    </div>
  </AbsoluteFill>;
}

/** The three reductions, one after another; bars are to scale. */
function Metrics({ f }: { f: number }) {
  const o = k(f, [B.metrics - 10, B.metrics + 10], [0, 1]) * (1 - k(f, [B.works - 10, B.works + 8], [0, 1]));
  const rows = [
    { pct: RED.requests, what: 'fewer model requests', b: BEF.requests, a: AFT.requests, fmt: (n: number) => `${n}` },
    { pct: RED.time, what: 'less agent time', b: BEF.seconds, a: AFT.seconds, fmt: (n: number) => `${Math.round(n)} s` },
    { pct: RED.cost, what: 'lower model cost', b: BEF.cost_usd, a: AFT.cost_usd, fmt: (n: number) => `US$${n.toFixed(2)}` },
  ];
  const t0 = cue('a4.metrics');
  return <AbsoluteFill style={{ opacity: o, justifyContent: 'center', paddingLeft: 160 }}>
    <p style={{ ...label }}>All {P.tasks.length} tasks · Before → After · the same evaluation</p>
    {rows.map((r, i) => { const at = t0 + i * 46, s = k(f, [at, at + 16], [0, 1]), grow = k(f, [at + 6, at + 30], [0, 1], camera);
      return <div key={r.what} style={{ display: 'flex', alignItems: 'center', gap: 50, marginTop: 34, opacity: s, transform: `translateY(${16 * (1 - s)}px)` }}>
        <span style={{ fontFamily: F.serif, fontSize: 130, color: C.ink, width: 360, letterSpacing: '-.03em', lineHeight: 1 }}>{r.pct}%</span>
        <div style={{ width: 1100 }}>
          <p style={{ margin: 0, fontFamily: F.serif, fontSize: 40, color: C.ink2 }}>{r.what}</p>
          <div style={{ marginTop: 14, display: 'grid', gridTemplateColumns: '90px 1fr 140px', rowGap: 8, alignItems: 'center', fontFamily: F.mono, fontSize: 16, color: C.ink3 }}>
            <span>Before</span><span style={{ height: 12, borderRadius: 3, background: C.rust, width: '100%' }} /><span style={{ textAlign: 'right' }}>{r.fmt(r.b)}</span>
            <span>After</span><span style={{ height: 12, borderRadius: 3, background: C.pass, width: `${100 * (1 - (1 - r.a / r.b) * grow)}%` }} /><span style={{ textAlign: 'right', color: C.ink }}>{r.fmt(r.a)}</span>
          </div>
        </div>
      </div>; })}
  </AbsoluteFill>;
}

/** The product's Live report for this run: the Before and After summary. */
function Live({ f }: { f: number }) {
  const o = k(f, [B.works - 10, B.works + 16], [0, 1]) * (1 - k(f, [ACT4.frames - 14, ACT4.frames], [0, 1]));
  const W = 1300, S = W / 1440;
  const push = k(f, [B.works, ACT4.frames], [0, 1], camera);
  return <AbsoluteFill style={{ opacity: o }}>
    <p style={{ position: 'absolute', left: 90, top: 46, ...label, color: C.signal2 }}>The Live report for this evaluation, as the product shows it</p>
    <div style={{ position: 'absolute', left: 310, top: 110, transform: `scale(${1 + 0.08 * push})`, transformOrigin: '50% 75%' }}>
      <BrowserWindow width={W} height={760} site="Agent Readiness" path="/ live report" style={{ position: 'relative' }}>
        <div style={{ position: 'absolute', inset: 0, background: '#F2F0EB' }} />
        <PageImage src={REPORT.image} cssWidth={1440} scale={S} scrollY={150} />
        <div style={{ position: 'absolute', left: 80 * S, top: (598 - 150) * S, width: 1280 * S, height: 205 * S, border: `3px solid ${C.signalStrong}`, borderRadius: 14,
          opacity: k(f, [B.works + 30, B.works + 44], [0, 1]) }} />
      </BrowserWindow>
    </div>
    <p style={{ position: 'absolute', left: 0, right: 0, bottom: 34, textAlign: 'center', margin: 0, fontFamily: F.serif, fontSize: 44, color: C.ink, opacity: k(f, [cue('a4.works') + 10, cue('a4.works') + 30], [0, 1]) }}>
      Same agent. Same tasks. <em>A website that finally works for it.</em></p>
  </AbsoluteFill>;
}
