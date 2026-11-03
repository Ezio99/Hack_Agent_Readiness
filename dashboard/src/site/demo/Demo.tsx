import { useEffect, useMemo, useRef, useState } from 'react';
import { Brand, SiteFooter } from '../Shell';
import { useReducedMotion } from '../router';
import { evidence, frame, headline, isItemPage, ITEMS, recordedOn, replication, row, shortId, trial } from '../evidence';
import { LatestLive } from '../LatestLive';
import { easeInOut, easeOut, register, seg, Track } from './engine';
import { Journey, type Notes } from './Journey';
import './demo.css';

/** The recorded evaluation, told as a scroll-driven story. Every screenshot, action, quote and number is
 *  taken from eval-9aaac35c (live, Meta Muse Spark 1.3). Lines marked "Note" are editorial. */

const CHAPTERS = [
  { id: 'intro', label: 'A working website' },
  { id: 'task', label: 'The task' },
  { id: 'original', label: 'Original run' },
  { id: 'friction', label: 'The friction' },
  { id: 'change', label: 'The change' },
  { id: 'modified', label: 'Modified run' },
  { id: 'outcome', label: 'The result' },
  { id: 'method', label: 'How it’s measured' },
  { id: 'run', label: 'Run your own' },
] as const;

const O = trial('original', 1), M = trial('modified', 1);
const T1 = evidence.tasks[0];

const ORIGINAL_NOTES: Notes = {
  2: 'The listing shows names and daily prices. No deposits.',
  3: 'With no deposit on the cards, the agent bets that pricier machines carry bigger deposits.',
  5: 'The deposit is on the item page. That is one machine of sixteen.',
  6: 'Back on the listing, it has to collect the links again.',
  12: `${O.steps.filter(s => isItemPage(s.path)).length} of ${ITEMS} item pages opened. With the step limit close, it answers with what it has.`,
};
const MODIFIED_NOTES: Notes = {
  1: 'On the Modified site the cards carry deposits, so the agent reads some before it leaves the homepage.',
  3: 'One text search on the listing returns all sixteen deposits.',
  [M.steps.length]: 'No item page opened. The answer is checked against all sixteen cards.',
};

function Intro({ reduce }: { reduce: boolean }) {
  const shot = frame(O.steps[0].frame);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (reduce) return;
    const fit = () => {
      const f = box.current, track = document.getElementById('intro');
      if (!f || !track) return;
      const s0 = Math.max(window.innerWidth / f.offsetWidth, window.innerHeight / (f.offsetHeight - 34)) * 1.02;
      track.style.setProperty('--s0', s0.toFixed(3));
    };
    fit();
    return register(fit);
  }, [reduce]);
  return <Track id="intro" vh={320} reduce={reduce} label="A working website" className="intro"
    vars={p => ({ t1: 1 - seg(p, .1, .26), b: easeInOut(seg(p, .14, .62)), c: easeOut(seg(p, .64, .9)) })}>
    <div className="intro-frame" ref={box}>
      <div className="frame">
        <div className="frame-bar"><span className="frame-dots"><i /><i /><i /></span><span className="frame-url">ironbark-hire/</span></div>
        <div className="frame-shot"><img src={shot} alt="Recorded screenshot of the Ironbark Hire Co. homepage, as the agent first saw it." /></div>
      </div>
      <div className="intro-shade" aria-hidden="true" />
    </div>
    <div className="intro-t1">
      <p className="eyebrow">A recorded evaluation · {recordedOn}</p>
      <h1 className="display">This website works.</h1>
      <p className="intro-sub">Ironbark Hire Co. rents out sixteen machines in five categories. Prices, deposits and hire terms are all published.</p>
      <p className="intro-cue" aria-hidden="true">Scroll</p>
    </div>
    <div className="intro-t2"><p className="display">For a person, every answer is a click or two away.</p></div>
  </Track>;
}

function Question({ reduce }: { reduce: boolean }) {
  const words = 'But can an AI agent actually finish a task here?'.split(' ');
  return <Track id="question" vh={220} reduce={reduce} label="The question" className="question" vars={p => ({ cap: seg(p, .78, .92) })}>
    <div className="wrap">
      <h2 className="display q-words">{words.map((w, i) => <span key={i} style={{ ['--s' as string]: (i / words.length) * .62 + .08 }}>{w} </span>)}</h2>
      <p className="q-cap">We asked one. What follows is a recording of what it saw, what it did and what it wrote down.</p>
    </div>
  </Track>;
}

function TaskScene({ reduce }: { reduce: boolean }) {
  const spec = [
    ['Agent', 'Meta Muse Spark 1.3, driving a real Chromium browser'],
    ['Start', 'The homepage, in a fresh browser'],
    ['Limits', `${T1.limits.max_steps} steps · ${T1.limits.timeout_seconds} seconds · no retries`],
    ['Grading', 'Independent: checked against ground truth the agent never sees'],
  ];
  return <Track id="task" vh={200} reduce={reduce} label="The task" className="task"
    vars={p => ({ a: easeOut(seg(p, .02, .3)), ...Object.fromEntries(spec.map((_, i) => [`s${i}`, easeOut(seg(p, .28 + i * .1, .42 + i * .1))])), z: easeOut(seg(p, .7, .86)) })}>
    <div className="wrap task-grid">
      <div className="task-q">
        <p className="eyebrow">Task 1 of {evidence.tasks.length} · frozen before the run</p>
        <h2 className="display">{T1.question}</h2>
      </div>
      <dl className="task-spec">{spec.map(([k, v], i) => <div key={k} style={{ ['--k' as string]: `var(--s${i})` }}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
      <p className="task-z">To answer, it has to compare the refundable deposit of all {ITEMS} machines.</p>
    </div>
  </Track>;
}

const LANES = [{ key: 'home', label: 'Homepage', y: 50 }, { key: 'list', label: 'Listing  /hire', y: 140 }, { key: 'item', label: 'Item pages', y: 230 }];
const laneOf = (path: string | null) => path === '/' ? 50 : isItemPage(path) ? 230 : 140;
const X0 = 150, X1 = 960;
const xOf = (step: number) => X0 + (step - 1) * (X1 - X0) / (T1.limits.max_steps - 1);
const pathFor = (t: typeof O) => t.steps.map((s, i) => `${i ? 'L' : 'M'}${xOf(s.step).toFixed(1)},${laneOf(s.path)}`).join(' ');

function Friction({ reduce }: { reduce: boolean }) {
  const items = O.steps.filter(s => isItemPage(s.path));
  const returns = O.steps.filter((s, i) => i > 0 && isItemPage(O.steps[i - 1].path) && s.path === '/hire').length;
  const collects = O.steps.filter(s => s.actions.some(a => a.name === 'Find elements')).length;
  const finding = evidence.insights.findings.find(f => f.id === 'detail-dependency');
  const loops = evidence.insights.findings.find(f => f.id === 'navigation-loops');
  const name = (p: string | null) => (p ?? '').replace('/hire/', '').split('-').filter(w => !/\d/.test(w) && w !== 'electric').join(' ');
  return <Track id="friction" vh={300} reduce={reduce} label="Where it broke down" className="friction"
    vars={p => ({ h: easeOut(seg(p, 0, .14)), d1: seg(p, .1, .42), k: easeOut(seg(p, .4, .52)), d2: seg(p, .52, .7), f: easeOut(seg(p, .72, .86)) })}>
    <div className="wrap fr-grid">
      <div className="fr-copy">
        <p className="eyebrow">Where it broke down</p>
        <h2 className="h2">The deposit lived one click deep, <em>on sixteen separate pages.</em></h2>
        <p className="fr-body">On the Original site every comparison was a round trip: listing, item page, then back to the listing to find the next link. The step limit arrived long before the sixteenth page.</p>
      </div>
      <figure className="fr-fig">
        <svg viewBox="0 0 1000 290" role="img" aria-label={`Pages visited per step. Original: ${O.steps.map(s => s.path).join(', ')}. Modified: ${M.steps.map(s => s.path).join(', ')}.`}>
          {LANES.map(l => <g key={l.key}><line x1={X0 - 12} x2={X1 + 14} y1={l.y} y2={l.y} className="fr-lane" /><text x={0} y={l.y + 4} className="fr-lane-label">{l.label}</text></g>)}
          <line x1={xOf(T1.limits.max_steps)} x2={xOf(T1.limits.max_steps)} y1={24} y2={262} className="fr-limit" />
          <text x={xOf(T1.limits.max_steps)} y={16} className="fr-axis" textAnchor="middle">limit · {T1.limits.max_steps}</text>
          {[1, 4, 8, 12].map(s => <text key={s} x={xOf(s)} y={284} className="fr-axis" textAnchor="middle">step {s}</text>)}
          <path d={pathFor(O)} pathLength={1} className="fr-line o" />
          {O.steps.map((s, i) => <circle key={s.step} cx={xOf(s.step)} cy={laneOf(s.path)} r={s.done ? 7 : 4.5} className={`fr-pt o${s.done ? ' done' : ''}`} style={{ ['--t' as string]: i / (O.steps.length - 1) }} />)}
          {items.map(s => <text key={s.step} x={xOf(s.step)} y={laneOf(s.path) + 26} className="fr-item-label" textAnchor="middle">{name(s.path)}</text>)}
          <path d={pathFor(M)} pathLength={1} className="fr-line m" />
          {M.steps.map((s, i) => <circle key={s.step} cx={xOf(s.step)} cy={laneOf(s.path) - 0} r={s.done ? 7 : 4.5} className={`fr-pt m${s.done ? ' done' : ''}`} style={{ ['--t' as string]: i / (M.steps.length - 1) }} />)}
        </svg>
        <figcaption className="fr-legend"><span><i className="o" />Original · task 1 · {O.steps.length} steps · not passed</span><span><i className="m" />Modified · task 1 · {M.steps.length} steps · passed</span></figcaption>
      </figure>
      <dl className="fr-stats">
        <div><dt>Item pages opened</dt><dd>{items.length}<small> of {ITEMS}</small></dd></div>
        <div><dt>Returns to the listing</dt><dd>{returns}</dd></div>
        <div><dt>Link lists re-collected</dt><dd>{collects}</dd></div>
      </dl>
      <div className="fr-all">
        <p className="eyebrow">Across all four tasks, measured by the insight rules</p>
        <ul>{[finding, loops].filter(Boolean).map(f => <li key={f!.id}><strong>{f!.title}</strong><span>{f!.observed}</span></li>)}</ul>
      </div>
    </div>
  </Track>;
}

/** A responsive crop of a recorded screenshot (coordinates in the 1280×960 capture). */
function Crop({ k, x, y, w, h, alt }: { k: string | null; x: number; y: number; w: number; h: number; alt: string }) {
  const W = 1280, H = 960;
  return <div className="crop" style={{ aspectRatio: `${w} / ${h}` }}>
    <img src={frame(k)} alt={alt} loading="lazy" style={{ width: `${100 * W / w}%`, left: `${-100 * x / w}%`, top: `${-100 * y / h}%`, height: `${100 * H / h}%` }} />
  </div>;
}

/* The hedge-trimmer card appears in both recordings: Original task 1 step 3 and Modified task 2 step 3.
   Crops are in capture pixels (1280×960) and aligned on the card's category tags. */
const CARD = { x: 450, w: 365 };
const FIELDS = [
  { label: 'Refundable deposit', y: 50 },        // row centres, % of the close-up crop height
  { label: 'Minimum hire', y: 68.75 },
  { label: 'Delivery and collection', y: 87.5 },
];

function Change({ reduce }: { reduce: boolean }) {
  const before = O.steps[2], after = trial('modified', 2).steps[2];
  return <Track id="change" vh={380} reduce={reduce} label="The change" className="change"
    vars={p => ({ a: easeOut(seg(p, 0, .08)), z: easeOut(seg(p, .06, .16)), l1: easeOut(seg(p, .18, .26)), l2: easeOut(seg(p, .26, .34)), l3: easeOut(seg(p, .34, .42)),
      x: easeInOut(seg(p, .48, .64)), h: easeOut(seg(p, .64, .74)), f: easeOut(seg(p, .76, .88)) })}>
    <div className="wrap ch-grid">
      <div className="ch-copy">
        <p className="eyebrow">The change</p>
        <h2 className="h2">Put the facts <em>where agents look.</em></h2>
        <p>The Modified site copies three fields from every product page onto its listing card: refundable deposit, minimum hire, and delivery and collection. Nothing else changes.</p>
        <p className="ch-fine">An owner-selected change, tested here as an experiment. It was not proposed by an automatic finding.</p>
      </div>
      <div className="ch-stage">
        <figure className="ch-close" aria-label="Close-up of the three fields on a Modified listing card">
          <div className="ch-close-shot">
            <Crop k={after.frame} x={CARD.x} y={182} w={250} h={128} alt="Recorded close-up of a Modified listing card: from $35 per day, Refundable deposit: $100, Minimum hire: 1 day, Delivery and collection: Optional." />
            <ol className="ch-labels">{FIELDS.map((f, i) => <li key={f.label} style={{ top: `${f.y}%`, ['--k' as string]: `var(--l${i + 1})` }}><i aria-hidden="true" /><span>{f.label}</span></li>)}</ol>
          </div>
          <figcaption className="figcap"><b>Close-up</b><span>Modified site · recorded screenshot · the cordless hedge trimmer card</span></figcaption>
        </figure>
        <div className="ch-compare">
          <figure className="ch-card ch-before">
            <figcaption><span className="swatch o" aria-hidden="true" />Original card</figcaption>
            <Crop k={before.frame} x={CARD.x} y={362} w={CARD.w} h={210} alt="Recorded crop of the Original hedge trimmer listing card: category, name, description, power, weight and daily price only." />
            <p className="ch-absent">Deposit, minimum hire and delivery: on the product page only</p>
          </figure>
          <figure className="ch-card ch-after">
            <figcaption><span className="swatch m" aria-hidden="true" />Modified card</figcaption>
            <div className="ch-after-shot">
              <Crop k={after.frame} x={CARD.x} y={28} w={CARD.w} h={280} alt="Recorded crop of the same card on the Modified site, now also listing refundable deposit, minimum hire and delivery and collection." />
              <span className="ch-mark" aria-hidden="true" />
            </div>
            <p className="ch-plus">+ 3 lines per card</p>
          </figure>
          <p className="ch-source figcap"><b>Recorded</b><span>Original: task 1, step 3 · Modified: task 2, step 3 · same evaluation, unedited pixels</span></p>
        </div>
      </div>
    </div>
  </Track>;
}

function Outcome({ reduce }: { reduce: boolean }) {
  const max = T1.limits.max_steps;
  const fr = evidence.frozen_rule;
  return <Track id="outcome" vh={260} reduce={reduce} label="The result" className="outcome"
    vars={p => ({ a: easeOut(seg(p, 0, .16)), n0: easeOut(seg(p, .1, .24)), n1: easeOut(seg(p, .18, .32)), n2: easeOut(seg(p, .26, .4)), g: easeInOut(seg(p, .38, .62)), z: easeOut(seg(p, .64, .8)) })}>
    <div className="wrap oc-grid">
      <header className="oc-head">
        <p className="eyebrow">The result · all four tasks · one repetition</p>
        <h2 className="h2">Four for four, <em>in about half the requests.</em></h2>
      </header>
      <dl className="oc-numbers">
        <div style={{ ['--k' as string]: 'var(--n0)' }}><dt>Tasks passed (official grader v1)</dt><dd><span className="o">{headline.passes.original}/{headline.passes.of}</span><i aria-hidden="true">→</i><span className="m">{headline.passes.modified}/{headline.passes.of}</span></dd></div>
        <div style={{ ['--k' as string]: 'var(--n1)' }}><dt>Model requests</dt><dd><span className="o">{headline.requests.original}</span><i aria-hidden="true">→</i><span className="m">{headline.requests.modified}</span></dd><p>{headline.requests.fewerPct}% fewer</p></div>
        <div style={{ ['--k' as string]: 'var(--n2)' }}><dt>Mean time per task</dt><dd><span className="o">{headline.seconds.original}s</span><i aria-hidden="true">→</i><span className="m">{headline.seconds.modified}s</span></dd></div>
      </dl>
      <figure className="oc-chart">
        <figcaption><span>Model requests per task</span><span className="oc-legend"><span><i className="o" />Original</span><span><i className="m" />Modified</span></span></figcaption>
        <ul>{evidence.tasks.map(t => <li key={t.task}>
          <p className="oc-q"><span className="mono">Task {t.task}</span>{t.question}</p>
          {(['Original', 'Modified'] as const).map(arm => { const r = row(arm, t.task), pass = r.outcome === 'evidence_supported_pass';
            return <div key={arm} className={`oc-bar ${arm === 'Original' ? 'o' : 'm'}`} title={`${arm}: ${r.requests} requests, ${pass ? 'evidence-supported pass' : 'not passed'}`}>
              <span className="oc-track"><i style={{ width: `${100 * r.requests / max}%` }} /></span>
              <span className="oc-val">{r.requests}</span>
              <span className={`tag ${pass ? 'tag-pass' : 'tag-fail'}`}>{pass ? '✓ pass' : '✕ not passed'}</span>
            </div>; })}
        </li>)}</ul>
      </figure>
      <p className="oc-honest">Every pair moved the same way, giving p = {fr.p_pass}: the strongest result four pairs can produce, and still above the pre-registered α of {fr.alpha.toFixed(2)}. The frozen rule reads <strong>{fr.verdict}</strong>; the exploratory listing rule reads <strong>consistent with the hypothesis</strong>. More repetitions settle it. Replicated later the same day by a second live run of the same four tasks ({replication.second.job}): {replication.second.official.original}/{replication.of} → {replication.second.official.modified}/{replication.of} under the official grader v1 ({replication.second.postHoc.original}/{replication.of} → {replication.second.postHoc.modified}/{replication.of} under the labelled post-hoc grader v2), {replication.second.requests.original} → {replication.second.requests.modified} model requests. The headline figures are the first run's ({replication.first.job}).</p>
      <LatestLive className="oc-latest" />
    </div>
  </Track>;
}

function Method() {
  const sugg = evidence.insights.suggestions;
  return <section id="method" className="method" aria-labelledby="method-h">
    <div className="wrap">
      <p className="eyebrow">How Agent Readiness measures</p>
      <h2 id="method-h" className="h2">Usability, <em>measured from the outside.</em></h2>
      <ol className="me-steps">
        <li><span>01</span><h3>Frozen tasks</h3><p>Questions with ground truth stored apart from anything the agent can see. The same tasks run on both versions of the site.</p></li>
        <li><span>02</span><h3>Paired, fresh agents</h3><p>Every repetition runs each task once on Original and once on Modified, in counterbalanced order, in isolated browsers that reach only a snapshot of the site.</p></li>
        <li><span>03</span><h3>Independent grading</h3><p>A pass needs the right answer. An evidence-supported pass also needs proof that the agent viewed the pages holding it. What the agent says about itself is ignored.</p></li>
        <li><span>04</span><h3>Findings, then proposals</h3><p>Rules over the recorded steps produce friction findings. Suggested fixes stay labelled as proposals until an evaluation tests one.</p></li>
      </ol>
      <div className="me-sugg">
        <p className="eyebrow">Suggestions generated for this evaluation</p>
        <ul>{sugg.map(s => <li key={s.for}><span className={`tag ${s.status === 'not measured' ? 'tag-neutral' : 'tag-signal'}`}>{s.status === 'not measured' ? 'Not measured' : 'Tested as Modified'}</span>{s.text}</li>)}</ul>
      </div>
      <p className="me-link"><a className="link" href={`#/run/${evidence.source.job}`}>Inspect every run of {shortId} in the workspace →</a></p>
    </div>
  </section>;
}

function Finale() {
  return <section id="run" className="finale" aria-labelledby="finale-h">
    <div className="wrap">
      <h2 id="finale-h" className="display">Now run it yourself.</h2>
      <p className="lede">Choose 1, 3 or 5 paired repetitions and watch fresh agents work live. Four pairs can never clear the pre-registered threshold; twelve or twenty can.</p>
      <div className="fin-cta"><a className="btn btn-signal" href="#/run">Run an evaluation <span className="arr" aria-hidden="true">→</span></a><a className="btn btn-ghost" href="#/">Back to the product</a></div>
      <p className="fin-src mono">Source: evaluation {evidence.source.job} · repetition {evidence.source.repetition} · {evidence.source.model} · evidence origin: real model · recorded {recordedOn}</p>
    </div>
  </section>;
}

function Rail({ active, jump }: { active: string; jump: (id: string) => void }) {
  const at = CHAPTERS.findIndex(c => c.id === active);
  return <nav className="rail" aria-label="Demo chapters">
    <ol>{CHAPTERS.map((c, i) => <li key={c.id} className={i < at ? 'done' : i === at ? 'active' : undefined}><a href={`#/demo/${c.id}`} aria-current={active === c.id ? 'true' : undefined} onClick={e => { e.preventDefault(); jump(c.id); }}>
      <span className="rail-n">{String(i + 1).padStart(2, '0')}</span><span className="rail-label">{c.label}</span></a></li>)}</ol>
  </nav>;
}

export function Demo({ scene }: { scene?: string }) {
  const reduce = useReducedMotion();
  const [active, setActive] = useState<string>(scene && CHAPTERS.some(c => c.id === scene) ? scene : 'intro');
  const bar = useRef<HTMLDivElement>(null);
  const chapterBar = useRef<HTMLSpanElement>(null);
  const ids = useMemo(() => CHAPTERS.map(c => c.id), []);

  // Chapter tracking + reading progress, on the shared scroll loop.
  useEffect(() => register(() => {
    const doc = document.documentElement;
    const p = doc.scrollHeight > innerHeight ? scrollY / (doc.scrollHeight - innerHeight) : 0;
    bar.current?.style.setProperty('transform', `scaleX(${Math.min(1, Math.max(0, p))})`);
    let current: string = ids[0];
    for (const id of ids) { const el = document.getElementById(id); if (el && el.getBoundingClientRect().top <= innerHeight * .45) current = id; }
    // Progress within the current chapter (tracks: scroll progress; flow sections: how far they have passed).
    const el = document.getElementById(current);
    if (el && chapterBar.current) {
      const r = el.getBoundingClientRect();
      const span = el.classList.contains('track') ? r.height - innerHeight : r.height;
      const cp = span > 0 ? Math.min(1, Math.max(0, -r.top / span)) : 1;
      chapterBar.current.style.transform = `scaleX(${cp.toFixed(3)})`;
    }
    setActive(a => {
      if (a !== current) history.replaceState(null, '', `#/demo${current === 'intro' ? '' : `/${current}`}`);
      return current;
    });
  }), [ids]);

  const jump = (id: string, smooth = !reduce) => {
    const el = document.getElementById(id);
    if (!el) return;
    // Land a little inside each track so its scene has settled.
    const into = el.classList.contains('track') && id !== 'intro' ? Math.min(innerHeight * .9, (el.offsetHeight - innerHeight) * .12) : 0;
    window.scrollTo({ top: el.getBoundingClientRect().top + scrollY + into, behavior: smooth ? 'smooth' : 'auto' });
    const focusTarget = el.querySelector<HTMLElement>('h1, h2');
    if (focusTarget) { focusTarget.setAttribute('tabindex', '-1'); focusTarget.focus({ preventScroll: true }); }
  };
  useEffect(() => { if (scene && scene !== 'intro') requestAnimationFrame(() => jump(scene, false)); }, []);   // deep link

  return <div className="ar ar-night demo">
    <a className="ar-skip" href="#/demo/outcome" onClick={e => { e.preventDefault(); jump('outcome'); }}>Skip to the result</a>
    <div className="demo-progress" aria-hidden="true"><div ref={bar} /></div>
    <header className="demo-head">
      <div className="wrap">
        <div className="demo-head-l"><Brand /><span className="demo-head-tag mono">Earlier case study · Ironbark Hire · {shortId}</span></div>
        <p className="demo-chapter"><span className="mono">{String(CHAPTERS.findIndex(c => c.id === active) + 1).padStart(2, '0')}<small> / {String(CHAPTERS.length).padStart(2, '0')}</small></span><strong>{CHAPTERS.find(c => c.id === active)?.label}</strong><i aria-hidden="true"><span ref={chapterBar} /></i></p>
        <div className="demo-head-r"><a className="btn btn-sm btn-ghost" href="#/">Exit</a><a className="btn btn-sm btn-signal" href="#/lifecycle">The Larkspur journey</a></div></div>
    </header>
    <Rail active={active} jump={id => jump(id)} />
    <main id="demo-main">
      <Intro reduce={reduce} />
      <Question reduce={reduce} />
      <TaskScene reduce={reduce} />
      <Journey id="original" trial={O} notes={ORIGINAL_NOTES} reduce={reduce} kicker="The Original site · task 1" title="Sixteen machines. One deposit at a time." />
      <Friction reduce={reduce} />
      <Change reduce={reduce} />
      <Journey id="modified" trial={M} notes={MODIFIED_NOTES} reduce={reduce} kicker="The Modified site · task 1 · a fresh agent" title="Same question. A different listing." />
      <Outcome reduce={reduce} />
      <Method />
      <Finale />
    </main>
    <SiteFooter />
  </div>;
}
