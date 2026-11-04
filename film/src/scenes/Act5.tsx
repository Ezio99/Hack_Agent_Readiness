import { AbsoluteFill, interpolate, Sequence, useCurrentFrame } from 'remotion';
import P from '../../data/paired.json';
import { BrowserWindow } from '../components/BrowserWindow';
import { PageImage } from '../components/Evidence';
import { Mark } from '../components/Mark';
import { Sfx } from '../components/Sound';
import { ACT5, cue } from '../narration';
import { C, F, camera, ease } from '../theme/tokens';
import { Captions } from './Opening';

/** Act 5, the product and the vision (25 s). Today: the real product (the Workspace and the Live report, captured read-only). Tomorrow: a
 *  CONCEPT of a discovery layer that agents consult, drawn in a visibly different style (dashed outlines, a permanent "Concept · not built"
 *  label, fictional .example sites, illustrative values) so it can never be mistaken for shipped functionality. Then the mark and tagline. */
export const ACT5_FRAMES = ACT5.frames;

const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;
const k = (f: number, i: readonly number[], o: number[], easing = ease) => interpolate(f, i as number[], o, { ...clamp, easing });
const label = { margin: 0, fontFamily: F.mono, fontSize: 14, letterSpacing: '.16em', color: C.ink3, textTransform: 'uppercase' } as const;
const B = { concept: cue('a5.tomorrow') - 20, which: cue('a5.which'), brand: cue('a5.brand') - 30 };

export function Act5({ captions = false }: { captions?: boolean }) {
  const f = useCurrentFrame();
  return <AbsoluteFill style={{ background: C.bg, overflow: 'hidden' }}>
    <AbsoluteFill style={{ background: 'radial-gradient(ellipse 60% 55% at 50% 50%, rgba(237,234,227,.05), rgba(0,0,0,0) 70%)' }} />
    {f < B.concept + 30 && <Today f={f} />}
    {f >= B.concept - 10 && f < B.brand + 30 && <Concept f={f} />}
    {f >= B.brand && <End f={f} />}
    <Sequence from={cue('a5.brand') - 6} durationInFrames={80}><Sfx name="chime" volume={0.35} /></Sequence>
    {captions && <Captions act={ACT5} f={f} />}
  </AbsoluteFill>;
}

/** Today: the working product. */
function Today({ f }: { f: number }) {
  const o = k(f, [0, 20], [0, 1]) * (1 - k(f, [B.concept, B.concept + 24], [0, 1]));
  const drift = k(f, [0, B.concept + 24], [0, 1], camera);
  const ws = P.product.workspace, rep = P.product.live, WS = 1000 / 1440 * 1.12;
  return <AbsoluteFill style={{ opacity: o }}>
    <p style={{ position: 'absolute', left: 90, top: 46, ...label, color: C.signal2 }}>Today · the working product</p>
    <div style={{ position: 'absolute', left: 90 - 30 * drift, top: 120, transform: `scale(${1 - 0.03 * drift})`, transformOrigin: 'top left' }}>
      <BrowserWindow width={1000} height={600} site="Agent Readiness" path="/ workspace" style={{ position: 'relative' }}>
        <div style={{ position: 'absolute', inset: 0, background: '#F2F0EB' }} />
        <PageImage src={ws.image} cssWidth={1440} scale={WS} scrollY={60} scrollX={50} />
        {(ws as { redact?: { x: number; y: number; width: number; height: number }[] }).redact?.map((r, i) =>
          <div key={i} style={{ position: 'absolute', left: (r.x - 50 - 3) * WS, top: (r.y - 60 - 2) * WS, width: (r.width + 6) * WS, height: (r.height + 4) * WS, background: '#F2F0EB' }} />)}
      </BrowserWindow>
      <p style={{ margin: '14px 0 0', fontFamily: F.serif, fontSize: 30, color: C.ink }}>Workspace <span style={{ color: C.ink3 }}>· run real agents on a website</span></p>
    </div>
    <div style={{ position: 'absolute', left: 860 + 30 * drift, top: 330, transform: `scale(${1 + 0.03 * drift})`, transformOrigin: 'top left', opacity: k(f, [24, 44], [0, 1]) }}>
      <BrowserWindow width={980} height={560} site="Agent Readiness" path="/ live report" style={{ position: 'relative' }}>
        <div style={{ position: 'absolute', inset: 0, background: '#F2F0EB' }} />
        <PageImage src={rep.image} cssWidth={1440} scale={980 / 1440 * 1.1} scrollY={430} scrollX={60} />
      </BrowserWindow>
      <p style={{ margin: '14px 0 0', fontFamily: F.serif, fontSize: 30, color: C.ink }}>Live report <span style={{ color: C.ink3 }}>· evidence, diagnosis, verification</span></p>
    </div>
  </AbsoluteFill>;
}

/** Tomorrow: a concept. An agent with a task asks which websites it can actually use. Everything here is illustrative. */
const SITES = [
  { site: 'larkspur.example', supports: 'yes', access: 'yes', reliable: 'yes', effort: '~3 steps', best: true },
  { site: 'northgate.example', supports: 'yes', access: 'partly', reliable: 'yes', effort: '13+ steps', best: false },
  { site: 'harbour.example', supports: 'yes', access: 'yes', reliable: 'no', effort: '—', best: false },
  { site: 'riverbend.example', supports: 'no', access: '—', reliable: '—', effort: '—', best: false },
];
const COLS: [keyof typeof SITES[0], string][] = [['supports', 'Supports the task'], ['access', 'Usable by agents'], ['reliable', 'Reliable'], ['effort', 'Effort to succeed']];
function Concept({ f }: { f: number }) {
  const o = k(f, [B.concept - 10, B.concept + 20], [0, 1]) * (1 - k(f, [B.brand, B.brand + 24], [0, 1]));
  const colAt = (i: number) => B.which + [0, 40, 80, 130][i];
  const pick = k(f, [B.which + 160, B.which + 184], [0, 1]);
  const mark = (v: string) => v === 'yes' ? <span style={{ color: C.pass }}>✓</span> : v === 'no' ? <span style={{ color: C.rust }}>✕</span> : v === 'partly' ? <span style={{ color: '#E0B54F' }}>~</span> : <span>{v}</span>;
  return <AbsoluteFill style={{ opacity: o }}>
    {/* the concept frame: dashed, labelled for its whole duration */}
    <div style={{ position: 'absolute', left: 70, top: 70, right: 70, bottom: 70, border: `2px dashed rgba(154,164,255,.45)`, borderRadius: 26 }} />
    <div style={{ position: 'absolute', left: 110, top: 52, padding: '6px 16px', borderRadius: 999, background: C.bg, border: `1px solid rgba(154,164,255,.6)`,
      fontFamily: F.mono, fontSize: 15, letterSpacing: '.16em', color: C.signal2 }}>CONCEPT · TOMORROW · NOT YET BUILT</div>
    <p style={{ position: 'absolute', right: 110, top: 60, margin: 0, fontFamily: F.mono, fontSize: 13, letterSpacing: '.12em', color: C.ink3 }}>ILLUSTRATIVE SITES AND VALUES</p>
    {/* the agent's question */}
    <div style={{ position: 'absolute', left: 150, top: 170, width: 520, padding: '26px 28px', borderRadius: 18, border: `1.5px dashed ${C.rule}`, background: 'rgba(237,234,227,.03)',
      opacity: k(f, [B.concept + 10, B.concept + 30], [0, 1]) }}>
      <p style={{ ...label, color: C.signal2 }}>An AI agent, with a task</p>
      <p style={{ margin: '14px 0 0', fontFamily: F.serif, fontSize: 38, lineHeight: 1.18, color: C.ink }}>“Find a beginner course that meets on weekends.”</p>
      <p style={{ margin: '18px 0 0', fontFamily: F.mono, fontSize: 16, color: C.ink3 }}>asks: which websites can I actually use?</p>
    </div>
    {/* the discovery layer's answer */}
    <div style={{ position: 'absolute', left: 740, top: 170, width: 1040, opacity: k(f, [B.concept + 30, B.concept + 50], [0, 1]) }}>
      <p style={{ ...label, color: C.signal2 }}>Agent Readiness · discovery layer (concept)</p>
      <div style={{ marginTop: 18, display: 'grid', gridTemplateColumns: '300px repeat(4, 1fr)', rowGap: 0, fontFamily: F.sans, fontSize: 24 }}>
        <span />{COLS.map(([, h], i) => <span key={h} style={{ ...label, fontSize: 12, padding: '0 0 12px', opacity: k(f, [colAt(i), colAt(i) + 12], [0, 1]) }}>{h}</span>)}
        {SITES.map((s, r) => { const best = s.best && pick > 0;
          return [<span key={s.site} style={{ padding: '18px 0', borderTop: `1px dashed ${C.rule}`, fontFamily: F.mono, fontSize: 22, color: best ? C.ink : C.ink2,
              opacity: k(f, [B.concept + 40 + r * 8, B.concept + 54 + r * 8], [0, 1]) }}>{best && <span style={{ color: C.pass }}>→ </span>}{s.site}</span>,
            ...COLS.map(([c], i) => <span key={s.site + c} style={{ padding: '18px 0', borderTop: `1px dashed ${C.rule}`, color: C.ink2, fontSize: 26,
              opacity: k(f, [colAt(i) + r * 5, colAt(i) + r * 5 + 12], [0, 1]) * (s.best ? 1 : 1 - 0.45 * pick) }}>{mark(String(s[c]))}</span>)]; })}
      </div>
      <div style={{ marginTop: 26, padding: '16px 22px', borderRadius: 14, border: `1.5px dashed rgba(95,191,136,.6)`, display: 'inline-block', opacity: pick }}>
        <span style={{ fontFamily: F.serif, fontSize: 30, color: C.ink }}>The agent goes where it can succeed: <span style={{ color: C.pass }}>larkspur.example</span></span>
      </div>
    </div>
    <p style={{ position: 'absolute', left: 150, bottom: 120, margin: 0, fontFamily: F.serif, fontSize: 34, color: C.ink2, opacity: k(f, [B.concept + 60, B.concept + 80], [0, 1]) }}>
      Not just which sites are relevant: which ones an agent can <em style={{ color: C.ink }}>actually use.</em></p>
  </AbsoluteFill>;
}

/** The close: the real mark, the name, the tagline. */
function End({ f }: { f: number }) {
  const o = k(f, [B.brand, B.brand + 20], [0, 1]) * (1 - k(f, [ACT5.frames - 24, ACT5.frames - 1], [0, 1]));   // the hold, then a gentle fade out
  const tag = k(f, [cue('a5.tagline'), cue('a5.tagline') + 30], [0, 1]);
  return <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', opacity: o }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 34, transform: `translateY(${-40 * tag}px)` }}>
      <Mark size={112} start={B.brand + 6} />
      <span style={{ fontFamily: F.sans, fontWeight: 500, fontSize: 84, letterSpacing: '-.02em', color: C.ink, opacity: k(f, [B.brand + 30, B.brand + 52], [0, 1]) }}>Agent Readiness</span>
    </div>
    <p style={{ position: 'absolute', top: 600, margin: 0, fontFamily: F.serif, fontStyle: 'italic', fontSize: 52, color: C.ink2, opacity: tag,
      transform: `translateY(${14 * (1 - tag)}px)` }}>Building the discovery layer for the agentic web.</p>
  </AbsoluteFill>;
}
