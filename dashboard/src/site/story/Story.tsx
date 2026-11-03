import { useEffect, useRef, useState } from 'react';
import { SiteFooter, SiteHeader } from '../Shell';
import { Track, easeInOut, easeOut, seg } from '../demo/engine';
import { reducedMotion } from '../router';
import { LIVE, POLISHED_V1, POLISHED_V2, showcaseFrame, type LiveRecord, type LiveStep } from '../showcase';
import './story.css';

/** The cinematic Larkspur showcase: Polished v1 → live agent evaluation → discovered friction → recommendation → Polished v2 → re-evaluation →
 *  measured result. Every number, frame and quote comes from the two recorded live evaluations (showcase/larkspur.json, exported from the
 *  product's own reports). It calls no API. The outcome is told as measured: v2 did not beat v1. */

const V1 = POLISHED_V1, V2 = POLISHED_V2;
const t1 = V1.totals.polished, t2 = V2.totals.polished2;
const trial = (r: LiveRecord, v: string, n: number) => r.trials.find(t => t.variant === v && t.task === n)!;
const steps = (r: LiveRecord, key: string) => r.journeys[key].steps;
const s1 = steps(V1, 'polished-2'), s2 = steps(V2, 'polished2-2');
const usd = (n: number) => `US$${n.toFixed(2)}`;
const date = new Date(V1.started_at).toLocaleDateString('en-AU', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Australia/Sydney' });
const O = LIVE.totals.original, I = LIVE.totals.improved;

const ACT: Record<string, string> = {
  '/': 'Home page', '/courses/compare': 'Comparison table', '/courses?level=Beginner&campus=&day=Weekend': 'Filtered results',
};
const where = (p: string | null) => (p && ACT[p]) ?? p ?? '';

function useReduce() {
  const [r, setR] = useState(reducedMotion());
  useEffect(() => {
    const m = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    if (!m) return;
    const on = () => setR(m.matches); m.addEventListener?.('change', on); return () => m.removeEventListener?.('change', on);
  }, []);
  return r;
}

/** Fade-and-rise on entering the viewport (static content; presentational only). */
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
  return <Track id="st-hero" vh={240} reduce={reduce} label="Polished Larkspur" className="st-hero"
    vars={p => ({ a: 1 - easeOut(seg(p, .05, .32)), z: easeInOut(seg(p, .0, .7)), c: easeOut(seg(p, .55, .85)) })}>
    <div className="st-hero-copy">
      <p className="st-kicker">Agent Readiness · Larkspur Community College</p>
      <h1 className="st-mega">Built for people.<br /><span>Tested by agents.</span></h1>
    </div>
    <div className="st-hero-device"><Browser src={showcaseFrame('site-polished-home')} url="/" alt="Polished v1: the redesigned Larkspur Community College home page (frozen snapshot)." /></div>
    <p className="st-hero-cap">We redesigned a college website for people. Then live AI agents tried to use it.</p>
  </Track>;
}

function Redesign({ reduce }: { reduce: boolean }) {
  const shots = [['site-polished-home', '/', 'Home: a course finder, subjects and campuses'], ['site-polished-courses', '/courses', 'Catalogue: filters beside cards that label every fact'],
    ['site-polished-courses-wheel-thrown-pottery', '/courses/wheel-thrown-pottery', 'Course page: key facts and how to enrol']] as const;
  const [i, setI] = useState(0);
  return <Track id="st-v1" vh={300} reduce={reduce} label="Polished v1" className="st-v1"
    vars={p => ({ a: easeOut(seg(p, 0, .15)) })} onProgress={p => setI(Math.min(2, Math.floor(seg(p, .1, .9) * 3)))}>
    <div className="st-wrap st-split">
      <div className="st-copy">
        <p className="st-kicker">Chapter 1 · Polished v1</p>
        <h2 className="st-h2">A website people would <em>enjoy using.</em></h2>
        <p className="st-body">A new identity, original illustrations, a course finder, filter panels, labelled facts on every card and a layout that works on a phone. Every
          agent-friendly feature from the earlier rounds stayed: the filter, browse pages, a comparison table and structured data.</p>
        <ol className="st-chips">{shots.map(([, , l], k) => <li key={l} className={(reduce || k === i) ? 'on' : ''}>{l}</li>)}</ol>
      </div>
      <div className="st-stack">{shots.map(([f, u, l], k) => <Browser key={f} className={(reduce || k === i) ? 'on' : ''} src={showcaseFrame(f)} url={u} alt={`Polished v1 · ${l}`} />)}</div>
    </div>
  </Track>;
}

function Tasks() {
  return <section className="st-section st-tasks" aria-label="The live evaluation">
    <div className="st-wrap">
      <p className="st-kicker" data-reveal>Chapter 2 · A live agent evaluation</p>
      <h2 className="st-h2" data-reveal>Three real customer questions. <em>Three fresh agents.</em></h2>
      <ol className="st-qs">{V1.tasks.map(t => <li key={t.n} data-reveal><span>Task {t.n}</span><q>{t.wording}</q></li>)}</ol>
      <p className="st-fine" data-reveal>{V1.agent.model} driving Browser Use in an isolated Chromium that can reach only a frozen copy of the site · frozen task set larkspur-core@v3 ·
        answers checked against the college’s own records · Polished v1 evaluated on its own, {date}.</p>
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

function ResultV1() {
  return <section className="st-section st-result" aria-label="Polished v1 result">
    <div className="st-wrap">
      <p className="st-kicker" data-reveal>Polished v1 · measured</p>
      <h2 className="st-h2 center" data-reveal>Every answer right. <em>Almost frictionless.</em></h2>
      <Numbers r={V1} v="polished" label="Polished v1 live evaluation" />
      <p className="st-body center" data-reveal>Tasks 1 and 3 took two requests each: the agents went straight to the comparison table. Task 2 took {trial(V1, 'polished', 2).requests}.
        That is where we looked.</p>
    </div>
  </section>;
}

/** A recorded trace replayed by scroll: the frame and the agent's own memory change step by step. */
function Trace({ id, reduce, kicker, title, list, highlight, variant }: { id: string; reduce: boolean; kicker: string; title: React.ReactNode; list: LiveStep[]; highlight: number; variant: string }) {
  const [i, setI] = useState(0);
  const shown = list.filter(s => s.frame);
  const cur = reduce ? shown[shown.length - 1] : shown[i];
  return <Track id={id} vh={120 + 70 * shown.length} reduce={reduce} label={kicker} className="st-trace"
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
        <Browser src={showcaseFrame(cur?.frame)} url={cur?.path ?? '/'} alt={`Recorded screenshot, ${variant} task 2 step ${cur?.step}: what the agent saw.`} />
        <figcaption>Recorded screenshot · {variant} · task 2 · step {cur?.step} of {list.length}</figcaption>
      </figure>
    </div>
  </Track>;
}

function Recommendation() {
  return <section className="st-section st-rec" aria-label="Recommendation">
    <div className="st-wrap">
      <p className="st-kicker" data-reveal>Chapter 4 · The recommendation</p>
      <h2 className="st-h2" data-reveal>Say the whole answer <em>before the first card.</em></h2>
      <div className="st-cards">
        <article data-reveal><h3>Name every match</h3><p>Each result line lists every matching course, so the full set is on screen before any card.</p></article>
        <article data-reveal><h3>Make results fit</h3><p>A compact listing header and slimmer card images, so more results fit in the first view. People scan faster too.</p></article>
        <article data-reveal className="muted"><h3>Not changed</h3><p>Two answers missed the exact-match grade because they added fees and seats. The report marks that as a grading-format effect, not a website problem, so the site was left alone.</p></article>
      </div>
    </div>
  </section>;
}

function Change({ reduce }: { reduce: boolean }) {
  return <Track id="st-v2" vh={260} reduce={reduce} label="Polished v2" className="st-v2" vars={p => ({ x: easeInOut(seg(p, .2, .75)), a: easeOut(seg(p, 0, .15)) })}>
    <div className="st-wrap">
      <p className="st-kicker">Chapter 5 · Polished v2</p>
      <h2 className="st-h2">Same results page. <em>Scroll to change it.</em></h2>
      <div className="st-compare" aria-label="The filtered results page on Polished v1 and v2">
        <Browser className="base" src={showcaseFrame('site-polished-courses-filter')} url="/courses?level=Beginner&day=Weekend" alt="Polished v1: filtered results, four cards, the fourth below the fold." />
        <Browser className="top" src={showcaseFrame('site-polished2-courses-filter')} url="/courses?level=Beginner&day=Weekend" alt="Polished v2: the result line names all four courses before the first card." />
        <span className="st-compare-l">v1</span><span className="st-compare-r">v2</span>
      </div>
    </div>
  </Track>;
}

function Verdict() {
  const rows: [string, string, string][] = [
    ['Correct answers', `${V1.correct.polished}/3`, `${V2.correct.polished2}/3`],
    ['Exact match', `${V1.passed.polished}/3`, `${V2.passed.polished2}/3`],
    ['Model requests', `${t1.requests}`, `${t2.requests}`],
    ['Task 2 requests', `${trial(V1, 'polished', 2).requests}`, `${trial(V2, 'polished2', 2).requests}`],
    ['Agent time', `${t1.seconds} s`, `${t2.seconds} s`],
    ['Actual cost', usd(t1.cost_usd), usd(t2.cost_usd)],
  ];
  return <section className="st-section st-verdict" aria-label="Measured result">
    <div className="st-wrap">
      <p className="st-kicker" data-reveal>Chapter 7 · Measured</p>
      <h2 className="st-mega sm" data-reveal>v2 did not beat v1.</h2>
      <p className="st-body center" data-reveal>Both versions answered every question correctly. On task 2 the agent read the new summary, listing all four courses, and then scrolled anyway
        to check their facts. With one agent per task, a one-request difference is within run-to-run variation. Neither version is better on this evidence.</p>
      <table className="st-table" data-reveal><thead><tr><th scope="col">Live evaluation</th><th scope="col">Polished v1</th><th scope="col">Polished v2</th></tr></thead>
        <tbody>{rows.map(([k, a, b]) => <tr key={k}><th scope="row">{k}</th><td>{a}</td><td>{b}</td></tr>)}</tbody></table>
      <div className="st-lesson" data-reveal>
        <p className="st-kicker">What the agents taught us</p>
        <p className="st-quote">Agents verify. Naming the answer is not enough: they want the deciding facts of every match <em>on screen.</em></p>
        <p className="st-body">Next recommendation, not yet built or evaluated: a compact results view that keeps each match’s fee, day and level in view.</p>
      </div>
    </div>
  </section>;
}

function Context() {
  return <section className="st-section st-context" aria-label="Where Larkspur started">
    <div className="st-wrap">
      <p className="st-kicker" data-reveal>Where Larkspur started</p>
      <h2 className="st-h2" data-reveal>Polish kept what readiness <em>had already won.</em></h2>
      <div className="st-arc">
        <div data-reveal><span>Original site</span><b>{LIVE.correct.original}/3</b><small>{O.requests} requests · {O.seconds} s</small></div>
        <div data-reveal><span>Improved for agents</span><b>{LIVE.correct.improved}/3</b><small>{I.requests} requests · {I.seconds} s</small></div>
        <div data-reveal><span>Polished v1</span><b>{V1.correct.polished}/3</b><small>{t1.requests} requests · {t1.seconds} s</small></div>
        <div data-reveal><span>Polished v2</span><b>{V2.correct.polished2}/3</b><small>{t2.requests} requests · {t2.seconds} s</small></div>
      </div>
      <p className="st-fine" data-reveal>The same three frozen tasks and the same model in every live run. Original and Improved come from one paired run on 3 November 2026; Polished v1 and v2 were each evaluated alone on 4 November.</p>
    </div>
  </section>;
}

function Finale() {
  return <section className="st-section st-finale" aria-label="Try it">
    <div className="st-wrap center">
      <h2 className="st-mega sm" data-reveal>Your turn.</h2>
      <p className="st-body center" data-reveal>Run live agents on Polished Larkspur, watch them browse, and read the report.</p>
      <p className="st-actions" data-reveal><a className="st-btn" href="#/run">Open the Workspace →</a>
        <a className="st-btn ghost" href={`#/reports/${V1.id}`}>Polished v1 report</a><a className="st-btn ghost" href={`#/reports/${V2.id}`}>Polished v2 report</a></p>
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
      <Redesign reduce={reduce} />
      <Tasks />
      <ResultV1 />
      <Trace id="st-friction" reduce={reduce} kicker="Chapter 3 · Discovered friction" variant="Polished v1" list={s1} highlight={3}
        title={<>Four courses found. <em>Three on screen.</em></>} />
      <Recommendation />
      <Change reduce={reduce} />
      <Trace id="st-retest" reduce={reduce} kicker="Chapter 6 · Re-evaluation" variant="Polished v2" list={s2} highlight={4}
        title={<>The agent read the answer. <em>Then it checked.</em></>} />
      <Verdict />
      <Context />
      <Finale />
    </main>
    <SiteFooter />
  </div>;
}
