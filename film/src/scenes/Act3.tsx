import { AbsoluteFill, interpolate, Sequence, useCurrentFrame } from 'remotion';
import FINAL from '../../data/final.json';
import product from '../../data/product.json';
import T from '../../data/transform.json';
import { BrowserWindow } from '../components/BrowserWindow';
import { PageImage } from '../components/Evidence';
import { Sfx } from '../components/Sound';
import { ACT3, cue } from '../narration';
import { C, F, camera, ease } from '../theme/tokens';
import { Captions } from './Opening';

/** Act 3, the transformation (40 s). Bridge: the diagnosis, isolated. Then the three recommendations, the first dominant: a course's real facts
 *  lift off its own Before course page and fly onto its catalogue card, which resolves into the genuine After website (the frozen After
 *  snapshot; every chip lands on the box where the After card actually shows that fact). Then, briefly, the dead end (recorded) and its fix, and
 *  the structured data (verbatim JSON-LD). Ends by setting up the same task on the improved site.
 *  All website images are the frozen Before / After snapshots rendered in the agents' font environment (scripts/capture_transform.py). */
export const ACT3_FRAMES = ACT3.frames;

type Box = { x: number; y: number; width: number; height: number };
const before = T.before, after = T.after;
const FEATURED = 'Mindful meditation';
const facts = before.featured.facts as { label: string; value: string; box: Box }[];
const cardB = before.courses.cards.find(c => c.name === FEATURED)!;
const cardA = after.courses.cards.find(c => c.name === FEATURED)!;
// every chip must land on the After card's row for the same label, with the same value: the After site shows exactly the facts of the course page
const landing = facts.map(fa => { const r = cardA.facts.find(x => x.label === fa.label);
  if (!r || r.value !== fa.value) throw new Error(`After card for ${FEATURED} does not show ${fa.label} = ${fa.value}`); return r; });
if (after.courses.cards.some(c => c.facts.length === 0) || before.courses.cards.some(c => c.facts.length > 0)) throw new Error('catalogue facts changed');
const MATCHES = T.hero_matches;
const DEAD = T.recorded_dead_end;
if (!DEAD.memory.includes('python slug guess failed')) throw new Error('dead-end note changed');
const LD = after.featured.json_ld[0] as Record<string, any>;
const FINDING = FINAL.pages['report-hist-t2'];

const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;
const k = (f: number, i: readonly number[], o: number[], easing = ease) => interpolate(f, i as number[], o, { ...clamp, easing });
const label = { margin: 0, fontFamily: F.mono, fontSize: 14, letterSpacing: '.16em', color: C.ink3, textTransform: 'uppercase' } as const;

// ---- beats (act-local frames), anchored to the narration ----
const B = (() => {
  const three = cue('a3.three'), cards = cue('a3.cards');
  return { three, hero: cards - 30, hiFacts: cards + 4, fly: cards + 70, land: cards + 112, center: cue('a3.same') - 6, scrollAll: cue('a3.same') + 40,
    matches: cue('a3.visible'), dead: cue('a3.deadend') - 14, data: cue('a3.data') - 14, again: cue('a3.again') - 10 };
})();

// ---- the hero composition: two windows, course page (left) and catalogue (right) ----
const WW = 820, S = WW / 1265, WH = 640, CH = 46;
const LX = 80, RX = 1020, WY = 210;
const SL = 1.25, scrollL = 520, scrollXL = 40;              // the course page, pushed in on "Course details" (CSS px)
const top = 150;                                             // where the featured card's top sits inside the right window (CSS px)
const scrollB = cardB.box.y - top, scrollA = cardA.box.y - top;

export function Act3({ captions = false }: { captions?: boolean }) {
  const f = useCurrentFrame();
  return <AbsoluteFill style={{ background: C.bg, overflow: 'hidden' }}>
    <AbsoluteFill style={{ background: 'radial-gradient(ellipse 60% 55% at 50% 50%, rgba(237,234,227,.05), rgba(0,0,0,0) 70%)' }} />
    {f < B.hero + 30 && <Bridge f={f} />}
    {f >= B.hero && f < B.dead + 20 && <Hero f={f} />}
    {f >= B.dead - 10 && f < B.data + 20 && <DeadEnd f={f} />}
    {f >= B.data - 10 && f < B.again + 20 && <Data f={f} />}
    {f >= B.again - 10 && <Again f={f} />}
    {facts.map((_, i) => <Sequence key={i} from={B.land + i * 5} durationInFrames={12}><Sfx name="tick" volume={0.22} /></Sequence>)}
    <Sequence from={B.scrollAll + 10} durationInFrames={70}><Sfx name="chime" volume={0.28} /></Sequence>
    {captions && <Captions act={ACT3} f={f} />}
  </AbsoluteFill>;
}

/** The bridge from Act 2: the report's finding recedes; the diagnosis, isolated; then the three recommendations, the first dominant. */
function Bridge({ f }: { f: number }) {
  const out = k(f, [B.hero - 10, B.hero + 20], [0, 1]);
  const toList = k(f, [B.three - 10, B.three + 20], [0, 1], camera);
  const recs = ['Put the facts on the catalogue cards', 'Fix the dead end', 'Describe each course in structured data'];
  return <AbsoluteFill style={{ opacity: 1 - out }}>
    {/* the finding card, as the report showed it, receding */}
    <div style={{ position: 'absolute', left: 420, top: 160, width: 1080, height: 300, overflow: 'hidden', borderRadius: 14, opacity: 0.5 * (1 - k(f, [0, 40], [0, 1])),
      filter: `blur(${k(f, [0, 40], [0, 8])}px)` }}>
      <PageImage src={FINDING.image} cssWidth={1440} scale={1.4} scrollY={FINDING.boxes.finding_class_day.y - 30} />
    </div>
    <div style={{ position: 'absolute', left: 150, top: 300 - 150 * toList, width: 1620, opacity: k(f, [10, 34], [0, 1]) }}>
      <p style={{ ...label, color: C.signal2 }}>Agent Readiness · the diagnosis</p>
      <p style={{ margin: '22px 0 0', fontFamily: F.serif, fontSize: 104 - 36 * toList, lineHeight: 1.05, letterSpacing: '-.02em', color: C.ink2 }}>The facts agents need</p>
      <p style={{ margin: 0, fontFamily: F.serif, fontSize: 104 - 36 * toList, lineHeight: 1.05, letterSpacing: '-.02em', color: C.ink }}>are <em>missing from the catalogue.</em></p>
    </div>
    <div style={{ position: 'absolute', left: 150, top: 470, width: 1620 }}>
      {recs.map((r, i) => { const o = k(f, [B.three + 16 + i * 12, B.three + 34 + i * 12], [0, 1]);
        return <div key={r} style={{ display: 'flex', alignItems: 'baseline', gap: 28, marginTop: i ? 18 : 0, opacity: o * (i === 0 ? 1 : 0.55), transform: `translateY(${14 * (1 - o)}px)` }}>
          <span style={{ fontFamily: F.mono, fontSize: i === 0 ? 30 : 22, color: i === 0 ? C.signal2 : C.ink3 }}>0{i + 1}</span>
          <span style={{ fontFamily: F.serif, fontSize: i === 0 ? 64 : 40, color: i === 0 ? C.ink : C.ink2 }}>{r}</span>
        </div>; })}
    </div>
  </AbsoluteFill>;
}

/** The centrepiece: real facts leave the course page and land on the card; the catalogue resolves into the After website. */
function Hero({ f }: { f: number }) {
  const inn = k(f, [B.hero, B.hero + 26], [0, 1], camera);
  const resolve = k(f, [B.land - 4, B.land + 26], [0, 1]);
  const leftOut = k(f, [B.center, B.center + 30], [0, 1], camera);
  const grow = k(f, [B.center + 6, B.center + 46], [0, 1], camera);
  const exit = k(f, [B.dead - 14, B.dead + 6], [0, 1]);
  // the right window: from its slot to the centre, larger; then the camera scrolls the After catalogue (top to the last row)
  const scrollRight0 = interpolate(f, [B.center, B.center + 46, B.center + 60, B.matches - 24], [scrollA, 300, 300, 1000], { ...clamp, easing: camera });
  const rScale = 1 + 0.18 * grow, rX = RX + (960 - WW * 1.18 / 2 - RX) * grow, rY = WY + (92 - WY) * grow;
  // the four matching cards: pull back until all four are on screen at once
  const mCards = MATCHES.map(n => after.courses.cards.find(x => x.name === n)!);
  const mTop = Math.min(...mCards.map(c => c.box.y)) - 16, mBot = Math.max(...mCards.map(c => c.box.y + c.box.height)) + 16;
  const pull = k(f, [B.matches - 24, B.matches + 12], [0, 1], camera);
  const sR = S + (Math.min(S, WH / (mBot - mTop)) - S) * pull;
  const scrollRight = scrollRight0 + (mTop - scrollRight0) * pull;
  const toScreenL = (b: Box) => ({ x: LX + (b.x - scrollXL) * SL, y: WY + CH + (b.y - scrollL) * SL });
  const toScreenR = (b: Box) => ({ x: RX + b.x * S, y: WY + CH + (b.y - scrollA) * S });
  const hiRow = (i: number) => k(f, [B.hiFacts + i * 7, B.hiFacts + i * 7 + 10], [0, 1]);
  const pageCard = (box: Box, scroll: number, color: string, o: number, sc: number) => o > 0 &&
    <div style={{ position: 'absolute', left: (box.x - 8) * sc, top: (box.y - 8 - scroll) * sc, width: (box.width + 16) * sc, height: (box.height + 16) * sc,
      border: `3px solid ${color}`, borderRadius: 14, opacity: o }} />;
  const factsOnCards = resolve >= 1 ? (grow > 0.5 ? 14 : 1) : 0;

  return <AbsoluteFill style={{ opacity: inn * (1 - exit) }}>
    {/* labels */}
    <div style={{ position: 'absolute', left: LX, top: WY - 58, width: WW, opacity: 1 - leftOut }}>
      <p style={label}>Original website · the course page</p>
      <p style={{ margin: '6px 0 0', fontFamily: F.sans, fontSize: 20, color: C.ink2 }}>{FEATURED}: one of the courses the agent never reached</p>
    </div>
    <div style={{ position: 'absolute', left: RX, top: WY - 58, width: WW, opacity: 1 - grow }}>
      <p style={label}>{resolve < 0.5 ? 'Original website' : <span style={{ color: C.pass }}>Agent-ready website</span>} · the catalogue</p>
      <p style={{ margin: '6px 0 0', fontFamily: F.sans, fontSize: 20, color: C.ink2 }}>Facts on catalogue cards: <b style={{ color: resolve < 0.5 ? C.rust : C.pass }}>{factsOnCards} of 14</b></p>
    </div>

    {/* left: the Before course page, its facts highlighted one by one */}
    <div style={{ position: 'absolute', left: 0, top: 0, opacity: 1 - leftOut, transform: `translateX(${-120 * leftOut}px)` }}>
      <BrowserWindow width={WW} height={WH} path={before.featured.path} style={{ left: LX, top: WY }}>
        <PageImage src={before.featured.image} cssWidth={1265} scale={SL} scrollY={scrollL} scrollX={scrollXL} />
        {facts.map((fa, i) => { const o = hiRow(i) * (1 - 0.6 * k(f, [B.fly + i * 6, B.fly + i * 6 + 10], [0, 1]));
          return o > 0 && <div key={fa.label} style={{ position: 'absolute', left: (fa.box.x - 8 - scrollXL) * SL, top: (fa.box.y - 4 - scrollL) * SL, width: (fa.box.width + 16) * SL,
            height: (fa.box.height + 8) * SL, background: 'rgba(43,59,230,.10)', borderLeft: `3px solid ${C.signalStrong}`, opacity: o }} />; })}
      </BrowserWindow>
    </div>

    {/* right: the catalogue, Before -> After (the genuine After snapshot) */}
    <div style={{ position: 'absolute', left: rX, top: rY, transform: `scale(${rScale})`, transformOrigin: '0 0' }}>
      <BrowserWindow width={WW} height={WH} path="/courses" style={{ position: 'relative' }}
        badge={resolve > 0.5 ? <span style={{ fontFamily: F.mono, fontSize: 13, letterSpacing: '.12em', color: C.pass }}>AGENT-READY WEBSITE</span> : <span style={{ fontFamily: F.mono, fontSize: 13, letterSpacing: '.12em', color: C.ink3 }}>ORIGINAL WEBSITE</span>}>
        <PageImage src={before.courses.image} cssWidth={1265} scale={S} scrollY={scrollB} opacity={1 - resolve} />
        <PageImage src={after.courses.image} cssWidth={1265} scale={sR} scrollY={scrollRight} opacity={resolve} />
        {pageCard(cardB.box, scrollB, C.signal, k(f, [B.hiFacts + 30, B.hiFacts + 44], [0, 1]) * (1 - resolve), S)}
        {pageCard(cardA.box, scrollRight, C.pass, resolve * (1 - k(f, [B.center, B.center + 20], [0, 1])), sR)}
        {mCards.map(c => <div key={c.name}>{pageCard(c.box, scrollRight, C.signal2, k(f, [B.matches, B.matches + 16], [0, 1]), sR)}</div>)}
        {/* the four courses the hero task asks for: their Level and Class day rows, now on the cards */}
        {MATCHES.map(name => { const c = after.courses.cards.find(x => x.name === name)!; const o = k(f, [B.matches, B.matches + 16], [0, 1]);
          return o > 0 && c.facts.filter(r => r.label === 'Level' || r.label === 'Class day').map(r =>
            <div key={name + r.label} style={{ position: 'absolute', left: (r.box.x - 6) * sR, top: (r.box.y - 4 - scrollRight) * sR, width: (r.box.width + 12) * sR,
              height: (r.box.height + 8) * sR, border: `2.5px solid ${C.signalStrong}`, borderRadius: 6, background: 'rgba(43,59,230,.07)', opacity: o }} />); })}
      </BrowserWindow>
    </div>

    {/* the flying facts: from each row of the course page to the same row on the After card */}
    {facts.map((fa, i) => {
      const t0 = B.fly + i * 5, t1 = B.land + i * 5;
      const p = k(f, [t0, t1], [0, 1], camera), gone = k(f, [t1 + 2, t1 + 14], [0, 1]);
      if (f < t0 - 1 || gone >= 1) return null;
      const a = toScreenL(fa.box), b = toScreenR(landing[i].box);
      const x = a.x + (b.x - a.x) * p, y = a.y + (b.y - a.y) * p - 120 * Math.sin(Math.PI * p);
      const w = fa.box.width * SL + (landing[i].box.width * S - fa.box.width * SL) * p;
      return <div key={fa.label} style={{ position: 'absolute', left: x, top: y, width: w, padding: '5px 9px', borderRadius: 7, background: '#fff',
        boxShadow: `0 10px 30px rgba(0,0,0,.45), 0 0 0 2px ${C.signalStrong}`, opacity: (f < t0 ? 0 : 1) * (1 - gone), fontFamily: F.sans, color: '#1d1a2e',
        transform: `scale(${1 + 0.12 * Math.sin(Math.PI * p)})`, transformOrigin: '0 50%', display: 'flex', gap: 8, alignItems: 'baseline', whiteSpace: 'nowrap', zIndex: 20 }}>
        <span style={{ fontSize: 10.5, letterSpacing: '.08em', textTransform: 'uppercase', color: '#6b6577', fontWeight: 700 }}>{fa.label}</span>
        <span style={{ fontSize: 14, fontWeight: 700 }}>{fa.value}</span>
      </div>; })}

    {/* the payoff line, once the whole catalogue is on screen */}
    <div style={{ position: 'absolute', left: 90, bottom: 26, opacity: k(f, [B.scrollAll - 20, B.scrollAll], [0, 1]) * (1 - k(f, [B.matches - 10, B.matches + 6], [0, 1])) }}>
      <p style={{ ...label, color: C.pass }}>Agent-ready website · facts on catalogue cards: 14 of 14</p>
      <p style={{ margin: '8px 0 0', fontFamily: F.serif, fontSize: 40, color: C.ink }}>Same design. Same pages. The facts, where agents look.</p>
    </div>
    <div style={{ position: 'absolute', left: 90, bottom: 26, opacity: k(f, [B.matches + 4, B.matches + 20], [0, 1]) }}>
      <p style={{ ...label, color: C.signal2 }}>The hero task, answerable from the catalogue</p>
      <p style={{ margin: '8px 0 0', fontFamily: F.serif, fontSize: 40, color: C.ink }}>All 4 beginner weekend courses: level and day on the card.</p>
    </div>
  </AbsoluteFill>;
}

/** Fix 2, briefly: the recorded dead end (Before, task 1) and the same address on After. */
function DeadEnd({ f }: { f: number }) {
  const o = k(f, [B.dead - 10, B.dead + 14], [0, 1]) * (1 - k(f, [B.data - 14, B.data + 4], [0, 1]));
  const W2 = 760, S2 = W2 / 1265, H2 = Math.round(960 * S2 * 0.78);
  return <AbsoluteFill style={{ opacity: o }}>
    <p style={{ position: 'absolute', left: 120, top: 70, ...label, color: C.signal2 }}>02 · Fix the dead end</p>
    {[{ x: 120, title: 'Original website · recorded (diagnostic run)', sub: `Task ${DEAD.task}, step ${DEAD.step}: the agent guessed this address. Its note: “python slug guess failed”`, img: DEAD.image, css: 1280,
        path: DEAD.path, color: C.rust, badge: 'RECORDED' },
      { x: 1040, title: 'Agent-ready website', sub: `The same address now opens the course page (${after.dead_end.final_path})`, img: after.dead_end.image, css: 1265,
        path: after.dead_end.requested, color: C.pass, badge: 'AGENT-READY' }].map(p =>
      <div key={p.title}>
        <div style={{ position: 'absolute', left: p.x, top: 130, width: W2 }}>
          <p style={{ ...label, color: p.color }}>{p.title}</p>
          <p style={{ margin: '6px 0 0', fontFamily: F.sans, fontSize: 19, color: C.ink2, lineHeight: 1.35 }}>{p.sub}</p>
        </div>
        <BrowserWindow width={W2} height={H2} path={p.path} site="" style={{ left: p.x, top: 240 }}
          badge={<span style={{ fontFamily: F.mono, fontSize: 12, letterSpacing: '.12em', color: p.color }}>{p.badge}</span>}>
          <PageImage src={p.img} cssWidth={p.css} scale={S2} />
        </BrowserWindow>
      </div>)}
    <p style={{ position: 'absolute', left: 880, width: 160, top: 240 + (46 + H2) / 2 - 30, margin: 0, textAlign: 'center', fontFamily: F.mono, fontSize: 44, color: C.ink3 }}>→</p>
  </AbsoluteFill>;
}

/** Fix 3, briefly: the After course page and its structured data, verbatim (an excerpt of the page's own JSON-LD). */
function Data({ f }: { f: number }) {
  const o = k(f, [B.data - 10, B.data + 14], [0, 1]) * (1 - k(f, [B.again - 14, B.again + 4], [0, 1]));
  const W3 = 820, S3 = W3 / 1265;
  const lines: [string, boolean][] = [
    ['{', false], [`  "@type": "${LD['@type']}",`, false], [`  "name": "${LD.name}",`, false], [`  "educationalLevel": "${LD.educationalLevel}",`, true],
    [`  "hasCourseInstance": { "courseSchedule": {`, false], [`      "byDay": "${LD.hasCourseInstance.courseSchedule.byDay}" } },`, true],
    [`  "offers": { "price": ${LD.offers.price}, "priceCurrency": "${LD.offers.priceCurrency}",`, false],
    [`    "inventoryLevel": { "value": ${LD.offers.inventoryLevel.value}, "unitText": "${LD.offers.inventoryLevel.unitText}" } },`, false],
    [`  "timeRequired": "${LD.timeRequired}",  …`, false], ['}', false]];
  return <AbsoluteFill style={{ opacity: o }}>
    <p style={{ position: 'absolute', left: 120, top: 70, ...label, color: C.signal2 }}>03 · Describe each course in structured data</p>
    <BrowserWindow width={W3} height={600} path={after.featured.path} style={{ left: 120, top: 150 }}
      badge={<span style={{ fontFamily: F.mono, fontSize: 12, letterSpacing: '.12em', color: C.pass }}>AGENT-READY WEBSITE</span>}>
      <PageImage src={after.featured.image} cssWidth={1265} scale={S3} />
    </BrowserWindow>
    <div style={{ position: 'absolute', left: 990, top: 150, width: 840, padding: '26px 30px', borderRadius: 16, background: '#141413', border: `1px solid ${C.rule}` }}>
      <p style={{ ...label, fontSize: 12 }}>The page’s own schema.org data (excerpt) · {'<script type="application/ld+json">'}</p>
      <pre style={{ margin: '18px 0 0', fontFamily: F.mono, fontSize: 19, lineHeight: 1.6, color: C.ink2, whiteSpace: 'pre-wrap' }}>
        {lines.map(([t, key], i) => <div key={i} style={{ opacity: k(f, [B.data + 6 + i * 4, B.data + 14 + i * 4], [0, 1]), color: key ? C.signal2 : undefined,
          background: key ? 'rgba(114,128,242,.10)' : undefined }}>{t}</div>)}
      </pre>
    </div>
  </AbsoluteFill>;
}

/** The set-up for Act 4: the same task, the same agent, the same limits; a full budget. */
function Again({ f }: { f: number }) {
  const o = k(f, [B.again - 10, B.again + 16], [0, 1]) * (1 - k(f, [ACT3.frames - 16, ACT3.frames], [0, 1]));
  const fill = k(f, [B.again + 30, B.again + 70], [0, 14], camera);
  return <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', opacity: o }}>
    <div style={{ textAlign: 'center' }}>
      <p style={{ ...label, color: C.pass }}>The Agent-ready website</p>
      <p style={{ margin: '24px 0 0', fontFamily: F.serif, fontSize: 92, letterSpacing: '-.02em', color: C.ink }}>Same task. Same agent. <em>Same limits.</em></p>
      <div style={{ marginTop: 40, display: 'flex', justifyContent: 'center', gap: 8 }}>
        {Array.from({ length: 14 }, (_, i) => <span key={i} style={{ width: 40, height: 16, borderRadius: 3, background: i < fill ? C.signal : 'rgba(237,234,227,.1)' }} />)}
      </div>
      <p style={{ margin: '16px 0 0', fontFamily: F.mono, fontSize: 18, letterSpacing: '.12em', color: C.ink3 }}>14 STEPS</p>
    </div>
  </AbsoluteFill>;
}
