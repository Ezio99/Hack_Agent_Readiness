import { useEffect, useRef, useState } from 'react';
import { SiteFooter, SiteHeader } from '../Shell';
import { Track, easeInOut, easeOut, seg } from '../demo/engine';
import { reducedMotion } from '../router';
import { AFTER, AFTER_V, BEFORE, BEFORE_V, LIVE, TRIAL_A, TRIAL_B, showcaseFrame, type LiveRecord, type LiveStep } from '../showcase';
import './story.css';

/** The cinematic showcase: a website that looks great to people → AI agents struggle → Agent Readiness finds why → the website is improved → agents
 *  are evaluated again → measured results. "Before" and "After" are the two live evaluations of 4 Nov 2026 (each version alone, same frozen tasks,
 *  same agent). Every number, frame and quote comes from those recorded runs (showcase/larkspur.json, exported from the product's own reports);
 *  the page calls no API. Earlier experiments appear only as clearly labelled history. */

const B = BEFORE.totals[BEFORE_V], A = AFTER.totals[AFTER_V];
const trial = (r: LiveRecord, v: string, n: number) => r.trials.find(t => t.variant === v && t.task === n)!;
const steps = (r: LiveRecord, key: string) => r.journeys[key].steps;
const sB = steps(BEFORE, `${BEFORE_V}-2`), sA = steps(AFTER, `${AFTER_V}-2`);
const usd = (n: number) => `US$${n.toFixed(2)}`;
const fewer = (a: number, b: number) => Math.round(100 * (a - b) / a);
const date = new Date(BEFORE.started_at).toLocaleDateString('en-AU', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Australia/Sydney' });
const deadEnd = trial(BEFORE, BEFORE_V, 1);
const opened = (r: LiveRecord, v: string) => r.trials.filter(t => t.variant === v).reduce((n, t) => n + (t.path ?? []).filter(p => /^\/courses\/[^/?]+$/.test(p)).length, 0);

const where = (p: string | null) => p === '/' ? 'Home page' : p === '/courses' ? 'All courses' : p?.startsWith('/courses/') ? `Course page · ${p.slice(9)}` : p ?? '';

function useReduce() {
  const [r, setR] = useState(reducedMotion());
  useEffect(() => {
    const m = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    if (!m) return;
    const on = () => setR(m.matches); m.addEventListener?.('change', on); return () => m.removeEventListener?.('change', on);
  }, []);
  return r;
}

function useReveal(root: React.RefObject<HTMLElement | null>) {
  useEffect(() => {
    const el = root.current;
    if (!el || typeof IntersectionObserver === 'undefined') { el?.querySelectorAll('[data-reveal]').forEach(n => n.classList.add('in')); return; }
    const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } }), { rootMargin: '0px 0px -10% 0px' });
    el.querySelectorAll('[data-reveal]').forEach(n => io.observe(n));
    return () => io.disconnect();
  }, [root]);
}

function Browser({ src, url, alt, className = '' }: { src?: string; url: string; alt: string; className?: string }) {
  return <div className={`st-browser ${className}`}>
    <div className="st-bar"><span className="st-dots"><i /><i /><i /></span><span className="st-url">larkspur-college{url}</span></div>
    <div className="st-shot">{src ? <img src={src} alt={alt} /> : null}</div>
  </div>;
}

function Hero({ reduce }: { reduce: boolean }) {
  return <Track id="st-hero" vh={240} reduce={reduce} label="Larkspur Community College" className="st-hero"
    vars={p => ({ a: 1 - easeOut(seg(p, .05, .32)), z: easeInOut(seg(p, .0, .7)), c: easeOut(seg(p, .55, .85)) })}>
    <div className="st-hero-copy">
      <p className="st-kicker">Agent Readiness · Larkspur Community College</p>
      <h1 className="st-mega">Looks great to people.<br /><span>Can agents use it?</span></h1>
    </div>
    <div className="st-hero-device"><Browser src={showcaseFrame(`site-${BEFORE_V}-home`)} url="/" alt="The Larkspur Community College home page, redesigned for people (the Before website)." /></div>
    <p className="st-hero-cap">A college website, freshly redesigned for people. Then live AI agents tried to use it.</p>
  </Track>;
}

function Website({ reduce }: { reduce: boolean }) {
  const shots = [[`site-${BEFORE_V}-home`, '/', 'Home: a clear welcome and subject areas'], [`site-${BEFORE_V}-courses`, '/courses', 'All courses: an illustrated card for every course'],
    [`site-${BEFORE_V}-courses-wheel-thrown-pottery`, '/courses/wheel-thrown-pottery', 'Course page: fee, day, level, seats and more']] as const;
  const [i, setI] = useState(0);
  return <Track id="st-site" vh={300} reduce={reduce} label="The website" className="st-v1"
    vars={p => ({ a: easeOut(seg(p, 0, .15)) })} onProgress={p => setI(Math.min(2, Math.floor(seg(p, .1, .9) * 3)))}>
    <div className="st-wrap st-split">
      <div className="st-copy">
        <p className="st-kicker">Chapter 1 · The website</p>
        <h2 className="st-h2">A website people would <em>enjoy using.</em></h2>
        <p className="st-body">Larkspur Community College runs evening and weekend courses. Its redesigned site has a new identity, illustrations and a layout that works on a phone.
          Like many catalogues, each course card shows a name and a short summary; the fee, class day, level and seats left are on the course’s own page.</p>
        <ol className="st-chips">{shots.map(([, , l], k) => <li key={l} className={(reduce || k === i) ? 'on' : ''}>{l}</li>)}</ol>
      </div>
      <div className="st-stack">{shots.map(([f, u, l], k) => <Browser key={f} className={(reduce || k === i) ? 'on' : ''} src={showcaseFrame(f)} url={u} alt={`Before · ${l}`} />)}</div>
    </div>
  </Track>;
}

function Tasks() {
  return <section className="st-section st-tasks" aria-label="The live evaluation">
    <div className="st-wrap">
      <p className="st-kicker" data-reveal>Chapter 2 · Agents try it</p>
      <h2 className="st-h2" data-reveal>Three real customer questions. <em>Three fresh agents.</em></h2>
      <ol className="st-qs">{BEFORE.tasks.map(t => <li key={t.n} data-reveal><span>Task {t.n}</span><q>{t.wording}</q></li>)}</ol>
      <p className="st-fine" data-reveal>Meta {BEFORE.agent.model} driving a browser in an isolated sandbox that can reach only a frozen copy of the website · every answer checked
        against the college’s own records · evaluated live, {date}.</p>
    </div>
  </section>;
}

function Numbers({ r, v, label }: { r: LiveRecord; v: string; label: string }) {
  const t = r.totals[v];
  return <dl className="st-numbers" aria-label={label}>
    <div data-reveal><dt>Correct answers</dt><dd>{r.correct[v]}<small>/{r.tasks.length}</small></dd></div>
    <div data-reveal><dt>Model requests</dt><dd>{t.requests}</dd></div>
    <div data-reveal><dt>Agent time</dt><dd>{t.seconds}<small> s</small></dd></div>
    <div data-reveal><dt>Actual cost</dt><dd><small>US$</small>{t.cost_usd.toFixed(2)}</dd></div>
  </dl>;
}

function BeforeResult() {
  return <section className="st-section st-result" aria-label="Before: measured">
    <div className="st-wrap">
      <p className="st-kicker" data-reveal>Before · measured</p>
      <h2 className="st-h2 center" data-reveal>{BEFORE.correct[BEFORE_V] === 0 ? <>Not one right answer. <em>Every agent ran out of road.</em></> : <>The agents struggled.</>}</h2>
      <Numbers r={BEFORE} v={BEFORE_V} label="Before: live evaluation" />
      <p className="st-body center" data-reveal>The agents opened {opened(BEFORE, BEFORE_V)} course pages one at a time, came back to the catalogue each time, and answered from what they had
        managed to check. One guessed a course address and hit a dead end.</p>
    </div>
  </section>;
}

function Trace({ id, reduce, kicker, title, list, highlight, version }: { id: string; reduce: boolean; kicker: string; title: React.ReactNode; list: LiveStep[]; highlight: number; version: string }) {
  const [i, setI] = useState(0);
  const shown = list.filter(s => s.frame);
  const cur = reduce ? shown[shown.length - 1] : shown[i];
  return <Track id={id} vh={120 + 55 * shown.length} reduce={reduce} label={kicker} className="st-trace"
    vars={p => ({ a: easeOut(seg(p, 0, .1)) })} onProgress={p => setI(Math.min(shown.length - 1, Math.floor(seg(p, .06, .94) * shown.length)))}>
    <div className="st-wrap st-split wide">
      <div className="st-copy">
        <p className="st-kicker">{kicker}</p>
        <h2 className="st-h2">{title}</h2>
        <ol className="st-steps">{list.map(s => <li key={s.step} className={`${s.step === cur?.step ? 'on' : ''}${s.step === highlight ? ' hot' : ''}`}>
          <span className="st-step-n">Step {s.step}</span><span className="st-step-where">{where(s.path)}</span>
          <blockquote>“{s.memory}”</blockquote></li>)}</ol>
      </div>
      <figure className="st-trace-fig">
        <Browser src={showcaseFrame(cur?.frame)} url={cur?.path ?? '/'} alt={`Recorded screenshot, ${version}, task 2, step ${cur?.step}: what the agent saw.`} />
        <figcaption>Recorded screenshot · {version} · task 2 · step {cur?.step} of {list.length}</figcaption>
      </figure>
    </div>
  </Track>;
}

function Recommendation() {
  return <section className="st-section st-rec" aria-label="What Agent Readiness recommended">
    <div className="st-wrap">
      <p className="st-kicker" data-reveal>Chapter 4 · Agent Readiness finds why</p>
      <h2 className="st-h2" data-reveal>The answers were there. <em>Agents couldn’t see them.</em></h2>
      <div className="st-cards">
        <article data-reveal><h3>Put the facts on the cards</h3><p>Fee, seats left, class day, duration and level were only on course pages, so every comparison cost a page visit per course. State all seven facts on every card.</p></article>
        <article data-reveal><h3>Fix the dead end</h3><p>An agent guessed <code>{(deadEnd.path ?? []).find(p => p.includes('introduction')) ?? '/courses/introduction-to-python'}</code> from the course name and got “not found”. Course addresses that follow the name now lead to the course.</p></article>
        <article data-reveal><h3>Describe each course</h3><p>No course page described itself in a machine-readable way. Each now carries structured course data with the same values the page shows.</p></article>
      </div>
      <p className="st-fine" data-reveal>Nothing else changed: the same pages, the same design, the same facts. No search filters, comparison tables or new pages were added.</p>
    </div>
  </section>;
}

function Change({ reduce }: { reduce: boolean }) {
  return <Track id="st-change" vh={260} reduce={reduce} label="The website, improved" className="st-v2" vars={p => ({ x: easeInOut(seg(p, .2, .75)), a: easeOut(seg(p, 0, .15)) })}>
    <div className="st-wrap">
      <p className="st-kicker">Chapter 5 · The website, improved</p>
      <h2 className="st-h2">Same design. <em>Scroll to see the change.</em></h2>
      <div className="st-compare" aria-label="All courses page, before and after">
        <Browser className="base" src={showcaseFrame(`site-${BEFORE_V}-courses`)} url="/courses" alt="Before: course cards with a name, subject and summary only." />
        <Browser className="top" src={showcaseFrame(`site-${AFTER_V}-courses`)} url="/courses" alt="After: the same cards also state fee, duration, level, class day, campus, seats left and materials." />
        <span className="st-compare-l">Before</span><span className="st-compare-r">After</span>
      </div>
    </div>
  </Track>;
}

function Verdict() {
  const rows: [string, string, string][] = [
    ['Correct answers', `${BEFORE.correct[BEFORE_V]}/3`, `${AFTER.correct[AFTER_V]}/3`],
    ['Exact match', `${BEFORE.passed[BEFORE_V]}/3`, `${AFTER.passed[AFTER_V]}/3`],
    ['Model requests', `${B.requests}`, `${A.requests}`],
    ['Course pages opened', `${opened(BEFORE, BEFORE_V)}`, `${opened(AFTER, AFTER_V)}`],
    ['Agent time', `${B.seconds} s`, `${A.seconds} s`],
    ['Actual cost', usd(B.cost_usd), usd(A.cost_usd)],
  ];
  return <section className="st-section st-verdict" aria-label="Measured result">
    <div className="st-wrap">
      <p className="st-kicker" data-reveal>Chapter 7 · Measured</p>
      <h2 className="st-mega sm" data-reveal>{BEFORE.correct[BEFORE_V]}/3 → {AFTER.correct[AFTER_V]}/3</h2>
      <p className="st-body center" data-reveal>The same three questions, the same agent, the same rules. After the change, agents answered from the catalogue alone with {fewer(B.requests, A.requests)}% fewer
        model requests, in {fewer(B.seconds, A.seconds)}% less time, at {fewer(B.cost_usd, A.cost_usd)}% lower cost.</p>
      <table className="st-table" data-reveal><thead><tr><th scope="col">Live evaluation</th><th scope="col">Before</th><th scope="col">After</th></tr></thead>
        <tbody>{rows.map(([k, a, b]) => <tr key={k}><th scope="row">{k}</th><td>{a}</td><td>{b}</td></tr>)}</tbody></table>
      <p className="st-fine center" data-reveal>Correct: the answer names exactly the right courses (extra detail such as fees is allowed). Exact match: nothing but the course names. One agent per
        question on each version: a measured result for these tasks, not a statistical guarantee.</p>
    </div>
  </section>;
}

function History() {
  return <section className="st-section st-context" aria-label="Earlier experiments">
    <div className="st-wrap">
      <p className="st-kicker" data-reveal>Earlier experiments · kept as history</p>
      <h2 className="st-h2" data-reveal>How we got here.</h2>
      <div className="st-arc two">
        <a data-reveal href={`#/reports/${LIVE.id}`}><span>3 Nov · first experiment</span><b>{LIVE.correct.original}/3 → {LIVE.correct.improved}/3</b>
          <small>The plain original site against a version with every recommendation · {LIVE.totals.original.requests} → {LIVE.totals.improved.requests} requests</small></a>
        <a data-reveal href={`#/reports/${TRIAL_A.id}`}><span>4 Nov · earlier redesign trials A and B</span><b>Superseded</b>
          <small>A redesign built on the already-improved site, so its agents started with every improvement. Reports kept: <u>trial A</u> · trial B ({TRIAL_B.id.slice(5, 13)})</small></a>
      </div>
    </div>
  </section>;
}

function Finale() {
  return <section className="st-section st-finale" aria-label="Try it">
    <div className="st-wrap center">
      <h2 className="st-mega sm" data-reveal>Your turn.</h2>
      <p className="st-body center" data-reveal>Run live agents on the improved Larkspur Community College website, watch them browse, and read the report.</p>
      <p className="st-actions" data-reveal><a className="st-btn" href="#/run">Open the Workspace →</a>
        <a className="st-btn ghost" href={`#/reports/${BEFORE.id}`}>Before: the report</a><a className="st-btn ghost" href={`#/reports/${AFTER.id}`}>After: the report</a></p>
    </div>
  </section>;
}

export function Story() {
  const reduce = useReduce();
  const root = useRef<HTMLDivElement>(null);
  useReveal(root);
  return <div className="ar ar-night story" ref={root}>
    <SiteHeader active="showcase" cta={false} />
    <main id="main">
      <Hero reduce={reduce} />
      <Website reduce={reduce} />
      <Tasks />
      <BeforeResult />
      <Trace id="st-friction" reduce={reduce} kicker="Chapter 3 · Where the agents struggled" version="Before" list={sB} highlight={sB[sB.length - 1].step}
        title={<>One course page <em>at a time.</em></>} />
      <Recommendation />
      <Change reduce={reduce} />
      <Trace id="st-retest" reduce={reduce} kicker="Chapter 6 · Agents, again" version="After" list={sA} highlight={sA[sA.length - 1].step}
        title={<>Every answer <em>on one page.</em></>} />
      <Verdict />
      <History />
      <Finale />
    </main>
    <SiteFooter />
  </div>;
}
