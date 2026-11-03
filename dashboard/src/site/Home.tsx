import { useEffect, useRef } from 'react';
import { SiteFooter, SiteHeader } from './Shell';
import { CARD_FACTS, FEATURED, FEATURED_TASK, FIRST_LIVE, IMPROVEMENTS, JOURNEY, LIVE, PAGE_AUDIT, fewerPct, journeyOf, showcaseFrame, trialOf, type LiveStep } from './showcase';
import { LatestLive } from './LatestLive';
import './home.css';

/** The product homepage. It tells the featured Larkspur story end to end with the recorded evidence of the paid live evaluation (showcase.ts);
 *  it calls no API, so it renders even when the evaluation service is unavailable. */

const T = FEATURED_TASK;                                     // the class-day question: Original vs Improved, live
const lost = journeyOf('original', T);
const found = journeyOf('improved', T);
const lastLost = lost.steps[lost.steps.length - 1];
const midLost = lost.steps.find(s => s.step === 9) ?? lastLost;
const t1o = trialOf('original', T)!, t1m = trialOf('improved', T)!;
const O = LIVE.totals.original, M = LIVE.totals.improved;
const F = FIRST_LIVE.totals;
const isCourse = (p: string | null) => !!p && /^\/courses\/(?!compare$)[^/?]+$/.test(p);
const answerCount = Array.isArray(found.answer) ? found.answer.length : 1;
const lostCount = Array.isArray(lost.answer) ? lost.answer.length : 1;
const usd = (n: number) => `$${n.toFixed(2)}`;
const cents = (n: number) => `${Math.round(n * 100)}¢`;
const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`;

/** Fades sections in as they enter the viewport. Purely presentational; content is in the DOM from the start. */
function useReveal(root: React.RefObject<HTMLElement | null>) {
  useEffect(() => {
    const el = root.current;
    if (!el || typeof IntersectionObserver === 'undefined') { el?.querySelectorAll('[data-reveal]').forEach(n => n.classList.add('in')); return; }
    const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } }), { rootMargin: '0px 0px -8% 0px' });
    el.querySelectorAll('[data-reveal]').forEach(n => io.observe(n));
    return () => io.disconnect();
  }, [root]);
}

function StepTicks({ steps, label }: { steps: LiveStep[]; label: string }) {
  return <ol className="ticks" aria-label={label}>{steps.map((s, i) => <li key={s.step} className={isCourse(s.path) ? 'item' : i === steps.length - 1 ? 'done' : ''} title={`Step ${s.step}: ${s.path}`} />)}</ol>;
}

function HeroNote() {
  return <aside className="plate-note" aria-label="Recorded agent memory">
    <p className="eyebrow">Muse Spark · Original site · step {lastLost.step} of {lost.steps.length}</p>
    <blockquote>“{lastLost.memory}”</blockquote>
    <StepTicks steps={lost.steps} label="Original journey: catalogue, course pages and answer" />
    <p className="plate-legend"><span><i className="t-list" />Catalogue</span><span><i className="t-item" />Course page</span><span><i className="t-done" />Answer</span></p>
    <div className="plate-verdicts">
      <div><span className="tag tag-fail">✕ {lostCount} of {answerCount} courses found</span><small><span className="swatch o" aria-hidden="true" />Original · {t1o.requests} requests · {Math.round(t1o.seconds)} s</small></div>
      <div><span className="tag tag-pass">✓ All {answerCount} courses found</span><small><span className="swatch i" aria-hidden="true" />Improved · {t1m.requests} requests · {Math.round(t1m.seconds)} s</small></div>
    </div>
  </aside>;
}

function HeroFigure() {
  return <figure className="hero-fig">
    <div className="frame">
      <div className="frame-bar"><span className="frame-dots"><i /><i /><i /></span><span className="frame-url">{FEATURED.host}{lastLost.path}</span><span className="hero-fig-arm">Original · step {lastLost.step}</span></div>
      <div className="frame-shot"><img src={showcaseFrame(lastLost.frame)} alt="Recorded screenshot: the Original Larkspur course catalogue, where cards show a name and a summary but no level or class day." fetchPriority="high" /></div>
    </div>
    <figcaption className="figcap"><b>Fig. 1</b><span>Live evaluation, {FEATURED.liveDate}. Task: “{LIVE.tasks[T - 1].wording}” The Original catalogue hides every class day one click deep, so the agent opened course pages one at a time and stopped at {t1o.requests} requests with {lostCount} of the {answerCount} courses. On the Improved site the agent opened the comparison table and found all {answerCount} in {t1m.requests}. Screenshot and memory are unedited.</span></figcaption>
  </figure>;
}

function TaskBars() {
  const max = Math.max(...LIVE.trials.map(t => t.requests));
  return <figure className="task-bars" aria-label="Model requests per task, Original and Improved">
    <p className="tb-legend"><span><i className="o" />Original</span><span><i className="i" />Improved</span><span className="tb-limit">limit {t1o.limit} per task</span></p>
    <ol>{LIVE.tasks.map(t => { const o = trialOf('original', t.n), m = trialOf('improved', t.n);
      return <li key={t.n}><span className="tb-q"><b>Task {t.n}</b> {t.wording}</span>
        <span className="tb-rows">{[['o', o], ['i', m]].map(([c, x]) => { const tr = x as typeof o; return <span key={c as string} className="tb-row">
          <span className={`tb-bar ${c}`} style={{ width: `${100 * (tr?.requests ?? 0) / max}%` }} /><span className="tb-v">{tr?.requests ?? '–'}</span></span>; })}</span></li>; })}</ol>
  </figure>;
}

export function Home({ section }: { section?: string }) {
  const root = useRef<HTMLDivElement>(null);
  useReveal(root);
  useEffect(() => {
    if (!section) return;
    const el = document.getElementById(section);
    el?.scrollIntoView({ behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
  }, [section]);
  return <div className="ar home" ref={root}>
    <a className="ar-skip" href="#main" onClick={e => { e.preventDefault(); document.getElementById('main')?.focus(); }}>Skip to content</a>
    <SiteHeader active="home" />
    <main id="main" tabIndex={-1}>
      <section className="hero wrap">
        <p className="eyebrow hero-eyebrow" data-reveal>Usability testing for AI agents</p>
        <h1 className="display hero-title" data-reveal>See your website <em>the way an agent does.</em></h1>
        <div className="hero-grid">
          <div className="hero-side">
            <p className="lede" data-reveal>Agent Readiness sends real Meta Muse Spark browser agents to do your customers’ tasks on your website, checks every answer against your own data, and tells you what to change. Then it runs the same tasks on your improved site and shows the difference.</p>
            <div className="hero-cta" data-reveal>
              <a className="btn btn-signal" href="#/run">Run a live evaluation <span className="arr" aria-hidden="true">→</span></a>
              <a className="btn btn-ghost" href="#/lifecycle">Walk through the {FEATURED.short} journey</a>
            </div>
            <LatestLive className="hero-latest" />
            <div className="hero-note" data-reveal><HeroNote /></div>
          </div>
          <div className="hero-visual" data-reveal><HeroFigure /></div>
        </div>
      </section>

      <section id="problem" className="problem wrap" aria-labelledby="problem-h">
        <div className="sec-head" data-reveal><p className="eyebrow"><b>01</b> — The agentic web</p>
          <h2 id="problem-h" className="h2">A page that’s easy for people can be <em>expensive</em> for agents.</h2></div>
        <div className="problem-cols" data-reveal>
          <p>A person scans the course catalogue, opens a course or two and books. An agent does the same work one model request at a time: read, decide, navigate. On {FEATURED.name}’s original catalogue every fee, class day and seat count sat one click deep, on fourteen separate pages. The agent’s budget ran out before the work did.</p>
          <p>Analytics won’t show you this. The pages load, nothing throws an error, and the agent leaves with a partial answer — or a guess. Agent Readiness shows what analytics can’t: whether the answer was right, which pages the agent saw, where it got stuck, and what it cost.</p>
        </div>
        <figure className="quote" data-reveal>
          <blockquote>“{midLost.memory}”</blockquote>
          <figcaption className="figcap"><b>Muse Spark, working memory</b><span>Original site · the weekend-courses task · step {midLost.step} of {lost.steps.length}, after checking 3 of 14 course pages. It stopped four steps later with {lostCount} of the {answerCount} courses.</span></figcaption>
        </figure>
      </section>

      <section id="how" className="how" aria-labelledby="how-h">
        <div className="wrap">
          <div className="sec-head" data-reveal><p className="eyebrow"><b>02</b> — How it works</p>
            <h2 id="how-h" className="h2">Evaluate, improve, <em>evaluate again.</em></h2>
            <p className="lede">Eight steps, shown here with the real {FEATURED.short} evaluation. Every step opens in the journey.</p></div>
          <ol className="how-list how-journey">
            {JOURNEY.map(s => <li key={s.id} data-reveal>
              <span className="how-n">{s.n}</span>
              <h3><a className="link" href={`#/lifecycle/${s.id}`}>{s.label}</a></h3><p>{s.blurb}.</p>
              <p className="how-spec mono">{({
                website: `${FEATURED.name} · 14 courses · 2 campuses`,
                tasks: '24 customer questions proposed by Muse Spark · each checked against the course records',
                review: `${LIVE.tasks.length} tasks approved and frozen by the owner`,
                evaluate: `${FIRST_LIVE.trials.length} live browser agents · isolated Chromium · ${t1o.limit} requests per task`,
                recommendations: 'campus, class day, fee, duration, seats on the cards · fix dead ends · structured data',
                improve: `${IMPROVEMENTS.length} changes on the Improved site`,
                reevaluate: 'the same frozen tasks · Original vs Improved · judges can start it',
                compare: `live: correct ${LIVE.correct.original}/${LIVE.tasks.length} → ${LIVE.correct.improved}/${LIVE.tasks.length} · ${O.requests} → ${M.requests} requests`,
              } as Record<string, string>)[s.id]}</p>
            </li>)}
          </ol>
        </div>
      </section>

      <section id="evidence" className="evidence" aria-labelledby="evidence-h">
        <div className="wrap">
          <div className="sec-head" data-reveal><p className="eyebrow"><b>03</b> — Results</p>
            <h2 id="evidence-h" className="h2">Every recommendation applied. <em>Measured live.</em></h2>
            <p className="lede">The same {LIVE.tasks.length} customer tasks on the Original and the Improved site: fee and seats, weekend class day, fee and duration. Same model, fresh agents, {FEATURED.liveDate}.</p></div>
          <dl className="numbers" data-reveal>
            <div><dt>Correct answers</dt><dd><span className="n-o">{LIVE.correct.original}/{LIVE.tasks.length}</span><span className="n-arrow" aria-hidden="true">→</span><span className="n-i">{LIVE.correct.improved}/{LIVE.tasks.length}</span></dd><p>Checked against the course records</p></div>
            <div><dt>Model requests, all tasks</dt><dd><span className="n-o">{O.requests}</span><span className="n-arrow" aria-hidden="true">→</span><span className="n-i">{M.requests}</span></dd><p>{fewerPct(O.requests, M.requests)}% fewer on Improved</p></div>
            <div><dt>Agent time, all tasks</dt><dd><span className="n-o">{mmss(O.seconds)}</span><span className="n-arrow" aria-hidden="true">→</span><span className="n-i">{mmss(M.seconds)}</span></dd><p>Minutes of browsing: {O.seconds} s → {M.seconds} s</p></div>
            <div><dt>Model cost</dt><dd><span className="n-o">{cents(O.cost_usd)}</span><span className="n-arrow" aria-hidden="true">→</span><span className="n-i">{cents(M.cost_usd)}</span></dd><p>US cents ({usd(O.cost_usd)} → {usd(M.cost_usd)}), calculated from the provider’s token counts</p></div>
          </dl>
          <div data-reveal><TaskBars /></div>
          <p className="honest" data-reveal>Every Improved agent went from the home page straight to the new comparison table and answered from it, in 2 requests. Every Original agent opened course pages one at a time and stopped at 13 of 14 requests with a partial answer.</p>
          <p className="honest" data-reveal>The first live evaluation tested only the first fix (fee, duration, level and seats on the cards) on six tasks: requests fell {F.original.requests} → {F.modified.requests}, but the class-day and campus questions stayed hard. That is what the report recommended fixing next. <a className="link" href={`#/reports/${FIRST_LIVE.id}`}>The first live evaluation</a></p>
          <a className="btn" href={`#/reports/${LIVE.id}`} data-reveal>Open the live report <span className="arr" aria-hidden="true">→</span></a>
        </div>
      </section>

      <section id="learn" className="learn wrap" aria-labelledby="learn-h">
        <div className="learn-copy" data-reveal>
          <p className="eyebrow"><b>04</b> — The improved website</p>
          <h2 id="learn-h" className="h2">Every recommendation, <em>applied.</em></h2>
          <p className="lede">The Improved {FEATURED.short} site puts all seven deciding facts on every card and fixes every dead end the agents hit. Run it live: the same frozen tasks, Original vs Improved.</p>
          <p className="audit-line"><span className="mono">Page audit</span> problems the report finds in the pages themselves: <b className="n-o">{PAGE_AUDIT.original.length}</b> Original → <b>{PAGE_AUDIT.modified.length}</b> Modified → <b className="n-i">{PAGE_AUDIT.improved.length}</b> Improved</p>
          <div className="hero-cta"><a className="btn btn-signal" href="#/run">Run Original vs Improved <span className="arr" aria-hidden="true">→</span></a><a className="btn btn-ghost" href="#/lifecycle/improve">See every change</a></div>
          <table className="facts-table"><caption className="sr-only">Facts shown on the course cards of each version</caption>
            <thead><tr><th scope="col">On the course cards</th><th scope="col">Original</th><th scope="col">Modified</th><th scope="col">Improved</th></tr></thead>
            <tbody>{CARD_FACTS.map(f => <tr key={f.fact}><th scope="row">{f.fact}</th>{([f.original, f.modified, f.improved]).map((x, i) => <td key={i} className={x ? 'yes' : 'no'}>{x ? '✓' : '–'}</td>)}</tr>)}</tbody></table>
        </div>
        <article className="sheet" data-reveal aria-label="Changes on the Improved site">
          <header><span className="mono">Improved site · {IMPROVEMENTS.length} changes</span><span className="mono muted">from the report’s recommendations</span></header>
          <figure className="improve-shot"><img src={showcaseFrame('site-improved-courses')} alt="The Improved Larkspur catalogue: a filter form above course cards that each state fee, duration, level, class day, campus, seats left and materials." loading="lazy" /></figure>
          <ul className="findings">{IMPROVEMENTS.map((x, i) => <li key={x.id}>
            <span className="sev sev-low">{String(i + 1).padStart(2, '0')}</span>
            <div><h3>{x.title}</h3><p>{x.change}</p></div></li>)}</ul>
        </article>
      </section>

      <section id="trust" className="trust wrap" aria-labelledby="trust-h">
        <div className="sec-head" data-reveal><p className="eyebrow"><b>05</b> — Built to be trusted</p>
          <h2 id="trust-h" className="h2">Real agents, <em>contained.</em></h2></div>
        <ul className="trust-grid">
          <li data-reveal><h3>Isolated browsers</h3><p>Each Chromium runs in its own network namespace that can reach only a frozen copy of the website. No internet, no DNS, no local services. Model credentials never enter the browser.</p></li>
          <li data-reveal><h3>Hard spend limits</h3><p>Every model request is reserved against a per-run cap before it is sent, inside a fixed service budget. One evaluation runs at a time, and each live run is authorised in advance by the owner.</p></li>
          <li data-reveal><h3>Independent grading</h3><p>Answers are checked against the site’s own records, which the agent never sees. The agent’s opinion of its own answer is ignored.</p></li>
          <li data-reveal><h3>Inspectable runs</h3><p>Every run keeps its screenshots, actions and the model’s stated goals at a permanent address, next to its grade, timing and cost.</p></li>
        </ul>
      </section>

      <section className="cta ar-night" aria-labelledby="cta-h">
        <div className="wrap">
          <p className="eyebrow">Evaluation workspace</p>
          <h2 id="cta-h" className="display cta-title">Run it live.</h2>
          <p className="lede">Enter your access code in the workspace to send fresh Muse Spark agents through the {FEATURED.short} tasks on the Original and the Improved site. Watch each agent work, screenshot by screenshot, and read the report when they finish.</p>
          <div className="hero-cta"><a className="btn btn-signal" href="#/run">Open the workspace <span className="arr" aria-hidden="true">→</span></a><a className="btn btn-ghost" href="#/lifecycle">Walk through the journey first</a></div>
          <p className="cta-note mono">Starting a live evaluation needs an access code. Completed evaluations are open to everyone.</p>
        </div>
      </section>
    </main>
    <SiteFooter />
  </div>;
}
