import { useEffect, useRef } from 'react';
import { SiteFooter, SiteHeader } from './Shell';
import { AFTER, AFTER_CHANGES, AFTER_V, BEFORE, BEFORE_V, FEATURED, FEATURED_TASK, JOURNEY, LIVE, fewerPct, journeyOf, showcaseFrame, trialOf, type LiveStep } from './showcase';
import { LatestLive } from './LatestLive';
import './home.css';

/** The product homepage. It tells the featured story with the recorded evidence of the two live evaluations of 4 Nov 2026: "Before" (the college's
 *  redesigned website) and "After" (the same design with Agent Readiness's recommendations applied), each evaluated alone with the same frozen tasks
 *  and agent (showcase.ts). The 3 Nov Original vs Improved run appears only as labelled history. It calls no API. */

const T = FEATURED_TASK;                                     // the weekend-courses question
const lost = journeyOf(BEFORE_V, T, BEFORE);
const found = journeyOf(AFTER_V, T, AFTER);
const lastLost = lost.steps[lost.steps.length - 1];
const midLost = lost.steps.find(s => s.step === 9) ?? lastLost;
const t1o = trialOf(BEFORE_V, T, BEFORE)!, t1m = trialOf(AFTER_V, T, AFTER)!;
const O = BEFORE.totals[BEFORE_V], M = AFTER.totals[AFTER_V];
const C0 = BEFORE.correct[BEFORE_V], C1 = AFTER.correct[AFTER_V], N = BEFORE.tasks.length;
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
    <p className="eyebrow">Muse Spark · Before · step {lastLost.step} of {lost.steps.length}</p>
    <blockquote>“{lastLost.memory}”</blockquote>
    <StepTicks steps={lost.steps} label="Before: catalogue, course pages and answer" />
    <p className="plate-legend"><span><i className="t-list" />Catalogue</span><span><i className="t-item" />Course page</span><span><i className="t-done" />Answer</span></p>
    <div className="plate-verdicts">
      <div><span className="tag tag-fail">✕ {lostCount} of {answerCount} courses found</span><small><span className="swatch o" aria-hidden="true" />Before · {t1o.requests} requests · {Math.round(t1o.seconds)} s</small></div>
      <div><span className="tag tag-pass">✓ All {answerCount} courses found</span><small><span className="swatch i" aria-hidden="true" />After · {t1m.requests} requests · {Math.round(t1m.seconds)} s</small></div>
    </div>
  </aside>;
}

function HeroFigure() {
  return <figure className="hero-fig">
    <div className="frame">
      <div className="frame-bar"><span className="frame-dots"><i /><i /><i /></span><span className="frame-url">{FEATURED.host}{lastLost.path}</span><span className="hero-fig-arm">Before · step {lastLost.step}</span></div>
      <div className="frame-shot"><img src={showcaseFrame(lastLost.frame)} alt="Recorded screenshot: the redesigned Larkspur course catalogue (Before), where cards show a name and a summary but no level or class day." fetchPriority="high" /></div>
    </div>
    <figcaption className="figcap"><b>Fig. 1</b><span>Live evaluation, 4 Nov 2026. Task: “{BEFORE.tasks[T - 1].wording}” The redesigned catalogue keeps every class day and level one click deep, so the agent opened course pages one at a time and answered after {t1o.requests} requests with {lostCount} of the {answerCount} courses. After the change, the agent read all {answerCount} from the course cards in {t1m.requests}. Screenshot and memory are unedited.</span></figcaption>
  </figure>;
}

function TaskBars() {
  const max = Math.max(...[...BEFORE.trials, ...AFTER.trials].map(t => t.requests));
  return <figure className="task-bars" aria-label="Model requests per task, before and after">
    <p className="tb-legend"><span><i className="o" />Before</span><span><i className="i" />After</span><span className="tb-limit">limit {t1o.limit} per task</span></p>
    <ol>{BEFORE.tasks.map(t => { const o = trialOf(BEFORE_V, t.n, BEFORE), m = trialOf(AFTER_V, t.n, AFTER);
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
            <LatestLive className="hero-latest" />
            <div className="hero-cta" data-reveal>
              <a className="btn btn-signal" href="#/showcase">Watch before and after <span className="arr" aria-hidden="true">→</span></a>
              <a className="btn btn-ghost" href="#/run">Run a live evaluation</a>
            </div>
            <div className="hero-note" data-reveal><HeroNote /></div>
          </div>
          <div className="hero-visual" data-reveal><HeroFigure /></div>
        </div>
      </section>

      <section className="polished-band ar-night" aria-labelledby="polished-h">
        <div className="wrap polished-grid">
          <div data-reveal>
            <p className="eyebrow">Latest · {FEATURED.name} · live, 4 Nov 2026</p>
            <h2 id="polished-h" className="h2">Looks great to people. <em>Agents couldn’t use it.</em></h2>
            <p>The college’s redesigned website hid every fee, class day and seat count one click deep. Live agents got {BEFORE.correct[BEFORE_V]} of 3 questions right.
              Agent Readiness showed why; the site was changed exactly as recommended, and the same agents were sent back: {AFTER.correct[AFTER_V]} of 3, with {fewerPct(BEFORE.totals[BEFORE_V].requests, AFTER.totals[AFTER_V].requests)}% fewer model requests.</p>
            <p className="polished-cta"><a className="btn btn-signal" href="#/showcase">Watch before and after <span className="arr" aria-hidden="true">→</span></a>
              <a className="btn btn-ghost" href="#/run">Run it live</a></p>
          </div>
          <dl className="polished-nums" data-reveal>
            {([['Before', BEFORE, BEFORE_V], ['After', AFTER, AFTER_V]] as const).map(([l, r, v]) => <a key={v} href={`#/reports/${r.id}`}>
              <dt>{l}</dt><dd><b>{r.correct[v]}/{r.tasks.length}</b> correct · {r.totals[v].requests} requests · {r.totals[v].seconds} s · US${r.totals[v].cost_usd.toFixed(2)}</dd></a>)}
          </dl>
        </div>
      </section>

      <section id="problem" className="problem wrap" aria-labelledby="problem-h">
        <div className="sec-head" data-reveal><p className="eyebrow"><b>01</b> — The agentic web</p>
          <h2 id="problem-h" className="h2">A page that’s easy for people can be <em>expensive</em> for agents.</h2></div>
        <div className="problem-cols" data-reveal>
          <p>A person scans the course catalogue, opens a course or two and books. An agent does the same work one model request at a time: read, decide, navigate. On {FEATURED.name}’s freshly redesigned catalogue every fee, class day and seat count sat one click deep, on fourteen separate pages. The agents’ budgets ran out before the work did.</p>
          <p>Analytics won’t show you this. The pages load, nothing throws an error, and the agent leaves with a partial answer — or a guess. Agent Readiness shows what analytics can’t: whether the answer was right, which pages the agent saw, where it got stuck, and what it cost.</p>
        </div>
        <figure className="quote" data-reveal>
          <blockquote>“{midLost.memory}”</blockquote>
          <figcaption className="figcap"><b>Muse Spark, working memory</b><span>Before · the weekend-courses task · step {midLost.step} of {lost.steps.length}, after checking 3 of 14 course pages. It answered {lost.steps.length - midLost.step} steps later with {lostCount} of the {answerCount} courses.</span></figcaption>
        </figure>
      </section>

      <section id="how" className="how" aria-labelledby="how-h">
        <div className="wrap">
          <div className="sec-head" data-reveal><p className="eyebrow"><b>02</b> — How it works</p>
            <h2 id="how-h" className="h2">Evaluate, improve, <em>evaluate again.</em></h2>
            <p className="lede">Eight steps, shown here with the real {FEATURED.short} evaluations. The journey walks through each step with the college’s first experiment.</p></div>
          <ol className="how-list how-journey">
            {JOURNEY.map(s => <li key={s.id} data-reveal>
              <span className="how-n">{s.n}</span>
              <h3><a className="link" href={`#/lifecycle/${s.id}`}>{s.label}</a></h3><p>{s.blurb}.</p>
              <p className="how-spec mono">{({
                website: `${FEATURED.name} · 14 courses · 2 campuses`,
                tasks: '24 customer questions proposed by Muse Spark · each checked against the course records',
                review: `${N} tasks approved and frozen by the owner`,
                evaluate: `${BEFORE.trials.length} live browser agents · isolated Chromium · ${t1o.limit} requests per task`,
                recommendations: 'every fact on the course cards · fix the dead end · structured course data',
                improve: `${AFTER_CHANGES.length} changes · same design, same pages`,
                reevaluate: 'the same frozen tasks on the improved website · judges can run it',
                compare: `live: correct ${C0}/${N} → ${C1}/${N} · ${O.requests} → ${M.requests} requests`,
              } as Record<string, string>)[s.id]}</p>
            </li>)}
          </ol>
        </div>
      </section>

      <section id="evidence" className="evidence" aria-labelledby="evidence-h">
        <div className="wrap">
          <div className="sec-head" data-reveal><p className="eyebrow"><b>03</b> — Results</p>
            <h2 id="evidence-h" className="h2">The recommendations applied. <em>Measured live.</em></h2>
            <p className="lede">The same {N} customer tasks before and after the change: fee and seats, weekend class day, fee and duration. Same model, fresh agents, each version evaluated on its own, 4 Nov 2026.</p></div>
          <dl className="numbers" data-reveal>
            <div><dt>Correct answers</dt><dd><span className="n-o">{C0}/{N}</span><span className="n-arrow" aria-hidden="true">→</span><span className="n-i">{C1}/{N}</span></dd><p>Checked against the course records</p></div>
            <div><dt>Model requests, all tasks</dt><dd><span className="n-o">{O.requests}</span><span className="n-arrow" aria-hidden="true">→</span><span className="n-i">{M.requests}</span></dd><p>{fewerPct(O.requests, M.requests)}% fewer after the change</p></div>
            <div><dt>Agent time, all tasks</dt><dd><span className="n-o">{mmss(O.seconds)}</span><span className="n-arrow" aria-hidden="true">→</span><span className="n-i">{mmss(M.seconds)}</span></dd><p>Minutes of browsing: {O.seconds} s → {M.seconds} s</p></div>
            <div><dt>Model cost</dt><dd><span className="n-o">{cents(O.cost_usd)}</span><span className="n-arrow" aria-hidden="true">→</span><span className="n-i">{cents(M.cost_usd)}</span></dd><p>US cents ({usd(O.cost_usd)} → {usd(M.cost_usd)}), calculated from the provider’s token counts</p></div>
          </dl>
          <div data-reveal><TaskBars /></div>
          <p className="honest" data-reveal>After the change every agent read the fourteen course cards on one page and answered without opening a single course page, in {AFTER.trials.map(t => t.requests).sort((a, b) => a - b).join(', ')} requests. Before it, every agent opened course pages one at a time; one guessed a course address and hit a dead end, and none answered correctly. One agent per question on each version: a measured result for these tasks, not a statistical guarantee.</p>
          <p className="honest" data-reveal>Earlier experiment (3 Nov), on the plain original site against a version with every recommendation: correct {LIVE.correct.original}/3 → {LIVE.correct.improved}/3, {LIVE.totals.original.requests} → {LIVE.totals.improved.requests} requests. <a className="link" href={`#/reports/${LIVE.id}`}>That report</a></p>
          <div className="hero-cta" data-reveal><a className="btn" href={`#/reports/${BEFORE.id}`}>Before: the report <span className="arr" aria-hidden="true">→</span></a><a className="btn" href={`#/reports/${AFTER.id}`}>After: the report <span className="arr" aria-hidden="true">→</span></a></div>
        </div>
      </section>

      <section id="learn" className="learn wrap" aria-labelledby="learn-h">
        <div className="learn-copy" data-reveal>
          <p className="eyebrow"><b>04</b> — The improved website</p>
          <h2 id="learn-h" className="h2">Same design. <em>Readable by agents.</em></h2>
          <p className="lede">The improved {FEATURED.short} site keeps every page and the whole design. It changes only what the report recommended: every course card states all seven deciding facts, the dead end leads to the course, and each course describes itself in structured data.</p>
          <div className="hero-cta"><a className="btn btn-signal" href="#/run">Run it live <span className="arr" aria-hidden="true">→</span></a><a className="btn btn-ghost" href="#/showcase">Watch before and after</a></div>
          <table className="facts-table"><caption className="sr-only">Facts shown on the course cards, before and after</caption>
            <thead><tr><th scope="col">On the course cards</th><th scope="col">Before</th><th scope="col">After</th></tr></thead>
            <tbody>{['Course fee', 'Duration', 'Level', 'Class day', 'Campus', 'Seats left', 'Materials'].map(f => <tr key={f}><th scope="row">{f}</th><td className="no">–</td><td className="yes">✓</td></tr>)}</tbody></table>
        </div>
        <article className="sheet" data-reveal aria-label="Changes on the improved website">
          <header><span className="mono">After · {AFTER_CHANGES.length} changes</span><span className="mono muted">from the report’s recommendations</span></header>
          <figure className="improve-shot"><img src={showcaseFrame(`site-${AFTER_V}-courses`)} alt="The improved Larkspur catalogue: course cards that each state fee, duration, level, class day, campus, seats left and materials." loading="lazy" /></figure>
          <ul className="findings">{AFTER_CHANGES.map((x, i) => <li key={x.id}>
            <span className="sev sev-low">{String(i + 1).padStart(2, '0')}</span>
            <div><h3>{x.title}</h3><p>{x.change}</p></div></li>)}</ul>
        </article>
      </section>

      <section id="trust" className="trust wrap" aria-labelledby="trust-h">
        <div className="sec-head" data-reveal><p className="eyebrow"><b>05</b> — Built to be trusted</p>
          <h2 id="trust-h" className="h2">Real agents, <em>contained.</em></h2></div>
        <ul className="trust-grid">
          <li data-reveal><h3>Isolated browsers</h3><p>Each Chromium runs in its own network namespace that can reach only a frozen copy of the website. No internet, no DNS, no local services. Model credentials never enter the browser.</p></li>
          <li data-reveal><h3>Hard spend limits</h3><p>Every model request is reserved against a per-run cap before it is sent, inside a fixed evaluation budget, and each run is settled at its actual cost from the run’s own ledger. One evaluation runs at a time.</p></li>
          <li data-reveal><h3>Independent grading</h3><p>Answers are checked against the site’s own records, which the agent never sees. The agent’s opinion of its own answer is ignored.</p></li>
          <li data-reveal><h3>Inspectable runs</h3><p>Every run keeps its screenshots, actions and the model’s stated goals at a permanent address, next to its grade, timing and cost.</p></li>
        </ul>
      </section>

      <section className="cta ar-night" aria-labelledby="cta-h">
        <div className="wrap">
          <p className="eyebrow">Evaluation workspace</p>
          <h2 id="cta-h" className="display cta-title">Run it live.</h2>
          <p className="lede">Enter your access code in the workspace to send fresh Muse Spark agents through the {FEATURED.short} tasks on the improved website. Watch each agent work, screenshot by screenshot, and read the report when they finish.</p>
          <div className="hero-cta"><a className="btn btn-signal" href="#/run">Open the workspace <span className="arr" aria-hidden="true">→</span></a><a className="btn btn-ghost" href="#/lifecycle">Walk through the journey first</a></div>
          <p className="cta-note mono">Starting a live evaluation needs an access code. Completed evaluations are open to everyone.</p>
        </div>
      </section>
    </main>
    <SiteFooter />
  </div>;
}
