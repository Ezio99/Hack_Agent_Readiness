import { useEffect, useRef } from 'react';
import { SiteFooter, SiteHeader } from './Shell';
import { evidence, frame, headline, recordedOn, shortId, trial, row, isItemPage, ITEMS } from './evidence';
import './home.css';

const original = trial('original', 1);

const guess = original.steps[2];                       // "Likely highest deposit correlates with highest value machine"
const lastOriginal = original.steps[original.steps.length - 1];
const itemsOpened = original.steps.filter(s => isItemPage(s.path)).length;

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

function StepTicks({ steps, label }: { steps: typeof original.steps; label: string }) {
  return <ol className="ticks" aria-label={label}>{steps.map(s => <li key={s.step} className={isItemPage(s.path) ? 'item' : s.done ? 'done' : ''} title={`Step ${s.step}: ${s.path}`} />)}</ol>;
}

function HeroPlate() {
  return <figure className="plate" data-reveal>
    <div className="plate-stage">
      <div className="plate-front frame">
        <div className="frame-bar"><span className="frame-dots"><i /><i /><i /></span><span className="frame-url">ironbark-hire{guess.path} · Original</span></div>
        <div className="frame-shot"><img src={frame(guess.frame)} alt="Recorded screenshot: the Original Ironbark listing page, where cards show prices but no refundable deposit." /></div>
      </div>
      <aside className="plate-note" aria-label="Recorded agent memory">
        <p className="eyebrow">Muse Spark · Original · step {guess.step} of {original.steps.length}</p>
        <blockquote>“{guess.memory}”</blockquote>
        <StepTicks steps={original.steps} label="Original journey: listing, item pages and answer" />
        <p className="plate-legend"><span><i className="t-list" />Listing</span><span><i className="t-item" />Item page</span><span><i className="t-done" />Answer</span></p>
        <div className="plate-verdicts">
          <div><span className="tag tag-fail">✕ Not passed</span><small>Original · {row('Original', 1).requests} requests</small></div>
          <div><span className="tag tag-pass">✓ Evidence-supported</span><small>Modified · {row('Modified', 1).requests} requests</small></div>
        </div>
      </aside>
    </div>
    <figcaption className="figcap"><b>Fig. 1</b><span>Recorded evaluation {shortId}, {recordedOn}. Task: “{original.question}” The Original listing hides deposits one click deep; the agent guessed which of {ITEMS} machines to open. Screenshots and memory are unedited.</span></figcaption>
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
  const f = evidence.insights.findings.filter(x => x.severity !== 'info');
  const st = evidence.insights.stats;
  return <div className="ar home" ref={root}>
    <a className="ar-skip" href="#main" onClick={e => { e.preventDefault(); document.getElementById('main')?.focus(); }}>Skip to content</a>
    <SiteHeader active="home" />
    <main id="main" tabIndex={-1}>
      <section className="hero wrap">
        <p className="eyebrow hero-eyebrow" data-reveal>Usability testing for AI agents</p>
        <h1 className="display hero-title" data-reveal>See your website <em>the way an agent does.</em></h1>
        <div className="hero-sub" data-reveal>
          <p className="lede">Agent Readiness sends real Meta Muse Spark browser agents to complete tasks on your site, grades every answer against ground truth the agent never sees, and shows exactly where navigation breaks down. Then it measures whether your fix works.</p>
          <div className="hero-cta">
            <a className="btn btn-signal" href="#/run">Run an evaluation <span className="arr" aria-hidden="true">→</span></a>
            <a className="btn btn-ghost" href="#/demo">Watch the recorded demo</a>
          </div>
        </div>
        <HeroPlate />
      </section>

      <section id="problem" className="problem wrap" aria-labelledby="problem-h">
        <div className="sec-head" data-reveal><p className="eyebrow"><b>01</b> — The agentic web</p>
          <h2 id="problem-h" className="h2">A page that’s easy for people can be <em>expensive</em> for agents.</h2></div>
        <div className="problem-cols" data-reveal>
          <p>A person scans a listing, opens one product, glances at the deposit and moves on. An agent does the same work one model request at a time: read, decide, navigate. It works inside a fixed budget of steps. When the fact it needs sits one click deep on sixteen separate pages, the budget runs out before the work does.</p>
          <p>Analytics won’t show you this failure. The page loads, nothing throws an error, and the agent leaves with an answer. Agent Readiness measures what analytics can’t: whether the answer was right, which pages the agent actually saw, and how many steps it took to get there.</p>
        </div>
        <figure className="quote" data-reveal>
          <blockquote>“{lastOriginal.memory}”</blockquote>
          <figcaption className="figcap"><b>Muse Spark, working memory</b><span>Original site · task 1 · step {lastOriginal.step} of {original.steps.length}, after opening {itemsOpened} of {ITEMS} item pages. The independent grader did not pass the answer.</span></figcaption>
        </figure>
      </section>

      <section id="how" className="how" aria-labelledby="how-h">
        <div className="wrap">
          <div className="sec-head" data-reveal><p className="eyebrow"><b>02</b> — How it works</p>
            <h2 id="how-h" className="h2">A controlled experiment, <em>not a lint score.</em></h2></div>
          <ol className="how-list">
            {[
              ['Frame the tasks', 'Write the questions a customer’s agent would be sent to answer. Each task is frozen with ground truth stored apart from anything the agent can see.', `${evidence.tasks.length} frozen tasks · start at the homepage · ${evidence.tasks[0].limits.max_steps}-step limit · ${evidence.tasks[0].limits.timeout_seconds} s timeout`],
              ['Run paired agents', 'Each repetition sends fresh browser agents through every task on the Original site and on a Modified version, in counterbalanced order. A new agent for every run, and no retries.', `Meta Muse Spark 1.3 · Browser Use · isolated Chromium · 8 runs per repetition`],
              ['Grade independently', 'A separate grader checks every answer against ground truth. An evidence-supported pass also requires that the agent actually viewed the pages holding the answer. The agent’s own claims are ignored.', 'strict pass · evidence-supported pass · self-assessment ignored'],
              ['Diagnose and compare', 'Every step is recorded: page, screenshot, action and the model’s stated goal. The steps become friction findings, and the two versions are compared with a rule fixed before the run.', `${evidence.frozen_rule.id} · α ${evidence.frozen_rule.alpha.toFixed(2)} · exploratory listing rule`],
            ].map(([t, d, spec], i) => <li key={t} data-reveal>
              <span className="how-n">{String(i + 1).padStart(2, '0')}</span>
              <h3>{t}</h3><p>{d}</p><p className="how-spec mono">{spec}</p>
            </li>)}
          </ol>
        </div>
      </section>

      <section id="learn" className="learn wrap" aria-labelledby="learn-h">
        <div className="learn-copy" data-reveal>
          <p className="eyebrow"><b>03</b> — What you learn</p>
          <h2 id="learn-h" className="h2">Findings drawn from what agents <em>did,</em> not what they said.</h2>
          <p className="lede">Deterministic rules read the telemetry of every finished run: which pages the agents opened, how often they doubled back, where they searched. Each finding cites its measurement. Suggestions stay labelled as proposals until an evaluation tests them.</p>
          <a className="link" href={`#/run/${evidence.source.job}`}>Open this evaluation in the workspace →</a>
        </div>
        <article className="sheet" data-reveal aria-label="Excerpt from the insights of evaluation eval-9aaac35c">
          <header><span className="mono">Insights · {shortId}</span><span className="mono muted">{evidence.insights.runs.Original} Original + {evidence.insights.runs.Modified} Modified runs</span></header>
          <ul className="findings">{f.map(x => <li key={x.id}>
            <span className={`sev sev-${x.severity}`}>{x.severity}</span>
            <div><h3>{x.title}</h3><p>{x.observed}</p></div></li>)}</ul>
          <div className="sheet-sugg">
            <p className="eyebrow">Suggested changes</p>
            <ul>{evidence.insights.suggestions.map(s => <li key={s.for}><span className={`tag ${s.status === 'not measured' ? 'tag-neutral' : 'tag-signal'}`}>{s.status === 'not measured' ? 'Not measured' : 'Tested as Modified'}</span><span>{s.text}</span></li>)}</ul>
          </div>
        </article>
      </section>

      <section id="evidence" className="evidence" aria-labelledby="evidence-h">
        <div className="wrap">
          <div className="sec-head" data-reveal><p className="eyebrow"><b>04</b> — Evidence</p>
            <h2 id="evidence-h" className="h2">One change to the listing cards. <em>Measured.</em></h2>
            <p className="lede">The Modified site copied three fields (refundable deposit, minimum hire, delivery and collection) from each product page onto its listing card. Same tasks, same model, fresh agents.</p></div>
          <dl className="numbers" data-reveal>
            <div><dt>Tasks passed, evidence-supported</dt><dd><span className="n-o">{headline.passes.original}/{headline.passes.of}</span><span className="n-arrow" aria-hidden="true">→</span><span className="n-m">{headline.passes.modified}/{headline.passes.of}</span></dd><p>Original → Modified</p></div>
            <div><dt>Model requests, all four tasks</dt><dd><span className="n-o">{headline.requests.original}</span><span className="n-arrow" aria-hidden="true">→</span><span className="n-m">{headline.requests.modified}</span></dd><p>{headline.requests.fewerPct}% fewer on Modified</p></div>
            <div><dt>Mean time per task</dt><dd><span className="n-o">{headline.seconds.original}s</span><span className="n-arrow" aria-hidden="true">→</span><span className="n-m">{headline.seconds.modified}s</span></dd><p>Wall-clock, per agent run</p></div>
            <div><dt>Item pages opened per task</dt><dd><span className="n-o">{st.Original.detail_views.toFixed(1)}</span><span className="n-arrow" aria-hidden="true">→</span><span className="n-m">{st.Modified.detail_views.toFixed(1)}</span></dd><p>Mean over four runs each</p></div>
          </dl>
          <p className="honest" data-reveal>One repetition of four paired tasks, recorded {recordedOn}. Every pair moved the same way, which gives p = {evidence.frozen_rule.p_pass}. That is the strongest result four pairs can produce, and it is still above the pre-registered α of {evidence.frozen_rule.alpha.toFixed(2)}. So the frozen rule reads <strong>{evidence.frozen_rule.verdict}</strong> and the exploratory listing rule reads <strong>consistent with the hypothesis</strong>. More repetitions resolve it, which is why the workspace runs 1, 3 or 5.</p>
          <a className="btn" href="#/demo" data-reveal>See how it happened, step by step <span className="arr" aria-hidden="true">→</span></a>
        </div>
      </section>

      <section id="trust" className="trust wrap" aria-labelledby="trust-h">
        <div className="sec-head" data-reveal><p className="eyebrow"><b>05</b> — Built to be trusted</p>
          <h2 id="trust-h" className="h2">Real agents, <em>contained.</em></h2></div>
        <ul className="trust-grid">
          <li data-reveal><h3>Isolated browsers</h3><p>Each Chromium runs in its own network namespace that can reach only a frozen snapshot of the site. It has no internet, no DNS and no access to local services. Model credentials never enter the browser.</p></li>
          <li data-reveal><h3>Hard spend limits</h3><p>Every model request is reserved against a cap before it is sent: US$0.80 per site version per repetition, inside a fixed service ceiling. Starts are admitted one at a time on the server.</p></li>
          <li data-reveal><h3>Separated evidence</h3><p>Observations, agent execution, proposed changes and measured effects are kept apart. A suggestion is never presented as a result until an evaluation has tested it.</p></li>
          <li data-reveal><h3>Inspectable runs</h3><p>Every run keeps its screenshots, actions and the model’s stated goals at a permanent URL, alongside per-task grades and the comparison verdicts.</p></li>
        </ul>
      </section>

      <section className="cta ar-night" aria-labelledby="cta-h">
        <div className="wrap">
          <p className="eyebrow">Evaluation workspace</p>
          <h2 id="cta-h" className="display cta-title">Run a fresh evaluation.</h2>
          <p className="lede">Choose 1, 3 or 5 paired repetitions. Watch each agent work live, screenshot by screenshot, and get graded results and friction findings when the runs finish.</p>
          <div className="hero-cta"><a className="btn btn-signal" href="#/run">Open the workspace <span className="arr" aria-hidden="true">→</span></a><a className="btn btn-ghost" href="#/demo">Watch the demo first</a></div>
          <p className="cta-note mono">New evaluations currently start by operator invitation. Completed evaluations are open to everyone.</p>
        </div>
      </section>
    </main>
    <SiteFooter />
  </div>;
}
