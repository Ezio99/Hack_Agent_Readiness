import { useEffect, useRef, useState } from 'react';
import { SiteFooter, SiteHeader } from '../Shell';
import { api, fmtUsd, inPublicScope, words, type EvaluationSummary, type Finding, type Generation, type Overview, type Suite } from '../../lib/lifecycleApi';
import { AFTER, AFTER_CHANGES, AFTER_V, BEFORE, BEFORE_V, FEATURED, FEATURED_TASK, JOURNEY, fewerPct, journeyOf, showcaseFrame, trialOf } from '../showcase';
import { Failed, Loading, plain, useLoad, VariantName } from './parts';
import './lifecycle.css';

/** `#/lifecycle[/<step>]` (and `#/demo`): Larkspur Community College's journey through the product, as one page: website -> generated tasks ->
 *  owner review -> live evaluation (Before) -> recommendations -> the improved website (After) -> re-evaluation -> comparison. Recorded artefacts
 *  come from the API (the generation, the frozen suite, the Before and After reports) or from showcase.ts. Nothing is simulated; a live run is
 *  started only from the workspace. The chapter bar follows the reader's scroll position (scroll spy) and chapter links scroll below the sticky
 *  header and bar. */

const SITE_HEADER_PX = 64;
/** Height that sticky chrome covers at the top of the viewport: the site header, plus the chapter bar when it is sticky (desktop). */
function stickyOffset(): number {
  const nav = document.querySelector<HTMLElement>('.lc-stepper');
  const head = document.querySelector<HTMLElement>('.site-head');
  const h = head ? head.getBoundingClientRect().height : SITE_HEADER_PX;
  return h + (nav && getComputedStyle(nav).position === 'sticky' ? nav.getBoundingClientRect().height : 0);
}
export function scrollToStep(id: string, smooth: boolean) {
  const el = document.getElementById(`lc-${id}`);
  if (!el) return;
  window.scrollTo({ top: Math.max(0, el.getBoundingClientRect().top + window.scrollY - stickyOffset() - 12), behavior: smooth ? 'smooth' : 'auto' });
}
/** The chapter in view: the last section whose top has passed the line just below the sticky chrome (the last one at the end of the page). */
export function activeStep(): string {
  const line = stickyOffset() + 24;
  let cur: string = JOURNEY[0].id;
  for (const s of JOURNEY) { const el = document.getElementById(`lc-${s.id}`); if (el && el.getBoundingClientRect().top <= line) cur = s.id; }
  if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2) cur = JOURNEY[JOURNEY.length - 1].id;
  return cur;
}
export function Lifecycle({ step, suite }: { step?: string; suite?: string }) {
  const ov = useLoad(() => api.overview(), 'overview');
  const [active, setActive] = useState<string>(step ?? 'website');
  const lock = useRef(0);                // while a chapter click scrolls the page, the spy keeps the clicked chapter
  useEffect(() => {                      // scroll spy: one passive listener, at most one update per frame
    let queued = false;
    const update = () => { queued = false; if (Date.now() < lock.current) return; setActive(a => { const n = activeStep(); return n === a ? a : n; }); };
    const on = () => { if (!queued) { queued = true; requestAnimationFrame(update); } };
    window.addEventListener('scroll', on, { passive: true }); window.addEventListener('resize', on, { passive: true });
    update();
    return () => { window.removeEventListener('scroll', on); window.removeEventListener('resize', on); };
  }, []);
  useEffect(() => {                      // deep link or chapter click: scroll now, and again once the sections above have loaded (unless the reader scrolls)
    if (!step) return;
    setActive(step); lock.current = Date.now() + 1500;
    let user = false;
    const stop = () => { user = true; lock.current = 0; };
    const go = () => { if (!user) scrollToStep(step, false); };
    go(); const t = [setTimeout(go, 400), setTimeout(go, 1200)];
    window.addEventListener('wheel', stop, { passive: true }); window.addEventListener('touchmove', stop, { passive: true }); window.addEventListener('keydown', stop);
    return () => { t.forEach(clearTimeout); window.removeEventListener('wheel', stop); window.removeEventListener('touchmove', stop); window.removeEventListener('keydown', stop); };
  }, [step]);
  const choose = (id: string) => (e: React.MouseEvent) => {            // the same chapter again: no hash change, so scroll here
    if (window.location.hash === `#/lifecycle/${id}`) { e.preventDefault(); setActive(id); lock.current = Date.now() + 1200; scrollToStep(id, !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches); }
  };
  return <div className="ar lc">
    <a className="ar-skip" href="#lc-main" onClick={e => { e.preventDefault(); document.getElementById('lc-main')?.focus(); }}>Skip to content</a>
    <SiteHeader active="lifecycle" />
    <main id="lc-main" tabIndex={-1} className="wrap lc-wrap">
      <header className="lc-intro">
        <p className="eyebrow">The {FEATURED.short} journey</p>
        <h1 className="lc-title">From a website to one <em>agents can use.</em></h1>
        <p className="lede">{FEATURED.name} runs evening and weekend short courses. Follow its website through Agent Readiness: customer tasks generated from
          its own catalogue, fixed before any run, run by real Muse Spark browser agents, turned into recommendations, applied to the site, and run again.</p>
        <p className="lc-note">Every step below uses the college’s real evaluation: its redesigned website (Before), the changes Agent Readiness recommended, and the
          improved website (After), each evaluated live with the same questions on 4 Nov 2026.</p>
      </header>
      <nav className="lc-stepper" aria-label="Journey steps"><ol>{JOURNEY.map(s =>
        <li key={s.id}><a href={`#/lifecycle/${s.id}`} onClick={choose(s.id)} aria-current={active === s.id ? 'step' : undefined}>
          <span className="lc-step-n">{s.n}</span><strong>{s.label}</strong><small>{s.blurb}</small></a></li>)}</ol></nav>
      <div className="lc-journey">
        <Step id="website"><WebsiteStep /></Step>
        <Step id="tasks"><TasksStep /></Step>
        <Step id="review"><ReviewStep selected={suite} /></Step>
        <Step id="evaluate"><EvaluateStep /></Step>
        <Step id="recommendations"><RecommendationsStep /></Step>
        <Step id="improve"><ImproveStep /></Step>
        <Step id="reevaluate"><ReevaluateStep ov={ov.data} /></Step>
        <Step id="compare"><CompareStep /></Step>
      </div>
    </main>
    <SiteFooter />
  </div>;
}

function Step({ id, children }: { id: (typeof JOURNEY)[number]['id']; children: React.ReactNode }) {
  const s = JOURNEY.find(x => x.id === id)!;
  const i = JOURNEY.findIndex(x => x.id === id);
  const next = JOURNEY[i + 1];
  return <section id={`lc-${id}`} className="lc-jstep" aria-labelledby={`lc-${id}-h`}>
    <header className="lc-jstep-head"><span className="lc-jstep-big" aria-hidden="true">{s.n}</span>
      <div><p className="eyebrow">Step {s.n} · {s.label}</p><h2 id={`lc-${id}-h`} className="lc-h2">{s.blurb}</h2></div></header>
    {children}
    {next && <p className="lc-jstep-next"><a className="link" href={`#/lifecycle/${next.id}`}>Next: {next.label} →</a></p>}
  </section>;
}

// --------------------------------------------------------------------------------------------------------------- 01 website
function WebsiteStep() {
  const site = useLoad(() => api.site(FEATURED.site), `site-${FEATURED.site}`);
  const ctx = site.data?.context;
  return <>
    <p className="lede sm">The product works on a frozen copy of the website and a short description of the business: who the customers are and what they come
      to do. The answers to every task come from the college’s own course records, which the agents never see.</p>
    {site.error && <Failed error={site.error} what="The website profile" />}
    {ctx && <div className="lc-context">
      <p className="lc-business">{ctx.business}</p>
      <div className="lc-two">
        <div><h3>Customers</h3><ul className="lc-personas">{ctx.personas.map(p => <li key={p.id}><strong>{p.name}</strong><p>{p.needs}</p></li>)}</ul></div>
        <div><h3>What they come to do</h3><ul className="lc-list">{ctx.journeys.map(j => <li key={j.id}>{j.name}{j.attributes.length ? <small> · {j.attributes.join(', ')}</small> : null}</li>)}</ul></div>
      </div>
    </div>}
    <h3>Two versions of the website</h3>
    <ul className="lc-versions two">{([[BEFORE_V, 'The college’s freshly redesigned website. Each course card shows a name, a subject and a summary; the fee, class day, level and seats left are on the course’s own page.'],
      [AFTER_V, 'The same design and pages, with the three changes Agent Readiness recommended: every fact on every card, no dead end, structured course data.']] as const).map(([v, blurb]) => <li key={v}>
      <figure><img src={showcaseFrame(`site-${v}-courses`)} alt={`The ${v === BEFORE_V ? 'Before' : 'After'} course catalogue.`} loading="lazy" /></figure>
      <VariantName v={v} /><p>{blurb}</p></li>)}</ul>
  </>;
}

// --------------------------------------------------------------------------------------------------------------- 02 tasks

function TasksStep() {
  const gens = useLoad(() => api.generations(), 'generations');
  const id = (gens.data ?? []).find(g => g.site === FEATURED.site)?.id ?? null;
  const g = useLoad(() => id ? api.generation(id) : Promise.resolve(null), `gen-${id}`);
  return <>
    <p className="lede sm">Muse Spark proposes the questions customers would ask, in their own words. An independent checker (no model involved) keeps a question
      only if the catalogue really answers it, the answer is unique and can be graded, and the wording states everything the agent needs.</p>
    {gens.error && <Failed error={gens.error} what="Task generation" />}
    {g.data && <GenerationView g={g.data} />}
  </>;
}

function GenerationView({ g }: { g: Generation }) {
  const final = g.post_fix_reevaluation?.admissions ?? g.admissions;
  return <div className="lc-gen">
    <dl className="lc-kpis">
      <div><dt>Questions proposed</dt><dd>{g.proposals.length}</dd><small>by {String(g.generator.model)}</small></div>
      <div><dt>Accepted</dt><dd>{final.natural ?? 0}</dd><small>answerable from the catalogue, in the customer’s words</small></div>
      <div><dt>Not used</dt><dd>{(final.rejected ?? 0) + (final.rubric ?? 0)}</dd><small>{final.rejected ?? 0} not answerable exactly · {final.rubric ?? 0} would need a person to grade</small></div>
      <div><dt>Model cost</dt><dd>{fmtUsd(g.cost.calculated_usd, 3)}</dd><small>{g.cost.requests} model requests</small></div>
    </dl>
    <details className="lc-gen-list"><summary>The {g.proposals.length} proposed questions</summary>
      <ul className="lc-proposals">{g.proposals.map(p => <li key={p.id}><q>{p.customer_wording ?? `[${p.withheld}]`}</q></li>)}</ul></details>
  </div>;
}

// --------------------------------------------------------------------------------------------------------------- 03 review
function ReviewStep({ selected }: { selected?: string }) {
  const suites = useLoad(() => api.suites(), 'suites');
  const mine = (suites.data ?? []).filter(s => s.site === FEATURED.site && !s.synthetic);
  const id = selected ?? mine.find(s => `${s.name}@v${s.version}` === FEATURED.judgeSuite && s.state === 'frozen')?.sha256 ?? mine.find(s => s.state === 'frozen')?.sha256;
  const s = useLoad(() => id ? api.suite(id) : Promise.resolve(null), `suite-${id}`);
  const judge = mine.find(x => `${x.name}@v${x.version}` === FEATURED.judgeSuite);
  return <>
    <p className="lede sm">The accepted questions are reviewed and fixed as an exact set before any evaluation. The set never changes, so every version of the
      website is tested on the very same questions and the comparison is fair.</p>
    {suites.error && <Failed error={suites.error} what="Task sets" />}
    {s.data && <SuiteView s={s.data} />}
    {judge && s.data && <p className="lc-note">Both the Before and the After evaluation, and every live run started in the workspace, use exactly these questions.</p>}
  </>;
}

function SuiteView({ s }: { s: Suite }) {
  const appr = s.approvals.find(a => a.decision === 'approved');
  return <div className="lc-suite">
    <p className="lc-suite-state"><span className={`tag ${s.state === 'frozen' ? 'tag-signal' : 'tag-neutral'}`}>{s.state === 'frozen' ? 'Fixed for every evaluation' : words(s.state)}</span>
      <strong>{s.counts.tasks} customer tasks</strong>{appr ? ` · fixed on ${new Date(appr.decided_at).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })}` : ''}</p>
    <ol className="lc-review-tasks">{[...s.tasks].sort((a, b) => a.task_id.localeCompare(b.task_id)).map((t, i) => <li key={t.task_id}>
      <span className="lc-tn">Task {i + 1}</span><q>{t.customer_wording}</q>
      <small>up to {t.limits.max_model_requests} model requests per agent</small>
    </li>)}</ol>
  </div>;
}

// --------------------------------------------------------------------------------------------------------------- 04 evaluate
const T = FEATURED_TASK;                                                             // the weekend-courses question
const bt = (n: number) => trialOf(BEFORE_V, n, BEFORE)!, at = (n: number) => trialOf(AFTER_V, n, AFTER)!;
const B = BEFORE.totals[BEFORE_V], A = AFTER.totals[AFTER_V];

function EvaluateStep() {
  const j = journeyOf(BEFORE_V, T, BEFORE), last = j.steps[j.steps.length - 1], mid = j.steps.find(x => x.step === 2) ?? j.steps[0];
  const dead = journeyOf(BEFORE_V, 1, BEFORE).steps.find(x => x.step === 9);
  return <>
    <p className="lede sm">Each task goes to a fresh Muse Spark browser agent, in a browser that can reach nothing but the frozen copy of the website. Every page,
      screenshot, action and the agent’s own notes are recorded, and the answer is graded against the course records. This is the Before website.</p>
    <dl className="lc-kpis">
      <div><dt>Agents</dt><dd>{BEFORE.trials.length}</dd><small>{BEFORE.tasks.length} tasks · Before · 4 Nov 2026</small></div>
      <div><dt>Correct answers</dt><dd>{BEFORE.correct[BEFORE_V]}/{BEFORE.tasks.length}</dd><small>checked against the course records</small></div>
      <div><dt>Model requests</dt><dd>{B.requests}</dd><small>{BEFORE.trials.map(t => t.requests).join(' · ')} per task (limit {bt(1).limit})</small></div>
      <div><dt>Model cost</dt><dd>{fmtUsd(B.cost_usd, 2)}</dd><small>{BEFORE.agent.model} · {B.seconds} s of browsing</small></div>
    </dl>
    <div className="lc-sbs">
      <figure className="lc-side o"><figcaption><VariantName v={BEFORE_V} /> · task {T} · step {mid.step}: the catalogue</figcaption>
        <img src={showcaseFrame(mid.frame)} alt="Recorded screenshot: the Before catalogue, course cards with a name and summary only." loading="lazy" />
        <blockquote>“{mid.memory}”</blockquote></figure>
      <figure className="lc-side o"><figcaption><VariantName v={BEFORE_V} /> · task {T} · step {last.step}: the answer · {bt(T).requests} requests</figcaption>
        <img src={showcaseFrame(last.frame)} alt={`Recorded screenshot: the Before site, step ${last.step}.`} loading="lazy" />
        <blockquote>“{last.memory}”</blockquote></figure>
    </div>
    {dead && <p className="lc-note">Task 1: the agent guessed <code>{dead.path}</code> from the course name and got “not found” (step {dead.step}).</p>}
    <p className="lc-cta-row"><a className="btn btn-signal" href={`#/reports/${BEFORE.id}/tasks/${T}`}>Replay task {T} step by step <span className="arr" aria-hidden="true">→</span></a>
      <a className="btn btn-ghost" href={`#/reports/${BEFORE.id}`}>Open the Before report</a></p>
  </>;
}

// --------------------------------------------------------------------------------------------------------------- 05 recommendations
/** Which After change answers a recommendation (by the finding's subject). */
function appliedBy(f: Finding): string | null {
  const t = `${f.title} ${f.recommendation}`.toLowerCase();
  if (/structured data|json-ld/.test(t)) return 'structured';
  if (/dead end|failing link/.test(t)) return 'dead-end';
  if (/listing|card/.test(t)) return 'facts';
  return null;
}

function RecommendationsStep() {
  const ev = useLoad(() => api.evaluation(BEFORE.id), BEFORE.id);
  const d = ev.data ? Object.values(ev.data.diagnostics)[0] : null;
  const fs = (d?.findings ?? []).filter(f => f.variant === BEFORE_V);
  const causes = fs.filter(f => f.basis === 'hypothesis' && f.severity !== 'info');
  const structural = fs.filter(f => f.basis === 'observed' && f.layer === 'structural');
  const dead = fs.filter(f => f.basis === 'observed' && f.rule === 'dead-end');
  const behaviour = new Map<string, number>();
  fs.filter(f => f.basis === 'observed' && f.layer === 'behavioral' && !f.title.startsWith('v1 format')).forEach(f => {
    const k = f.title.replace(/ on task \d+.*$/, ''); behaviour.set(k, (behaviour.get(k) ?? 0) + 1); });
  const recs = [...new Map([...causes, ...dead, ...structural].map(f => [f.recommendation, f])).values()];
  return <>
    <p className="lede sm">The report reads what the agents did and what the pages contain, and turns it into specific changes. Each recommendation cites its
      evidence: the steps where an agent ran out of requests, the page that returned “not found”, the fact that sat one click too deep.</p>
    {ev.loading && <Loading what="the Before report" />}
    {ev.error && <Failed error={ev.error} what="The Before report" />}
    {d && <div className="lc-recs">
      <div><h3>What the agents ran into <small>(Before)</small></h3>
        <ul className="lc-counts">{[...behaviour.entries()].map(([k, n]) => <li key={k}><span>{k[0].toUpperCase() + k.slice(1)}</span><b>{n} task{n === 1 ? '' : 's'}</b></li>)}</ul></div>
      <div><h3>Recommendations</h3>
        <ul className="lc-rec-list">{recs.map(f => { const a = appliedBy(f); const imp = AFTER_CHANGES.find(x => x.id === a);
          return <li key={f.id + f.recommendation}><p>{f.recommendation}</p>
            <small>{f.basis === 'hypothesis' ? `Likely cause of the extra navigation on task ${f.tasks.join(', ')}` : plain(f.title)}</small>
            {imp && <a className="tag tag-pass" href="#/lifecycle/improve">✓ Applied: {imp.title}</a>}</li>; })}</ul></div>
    </div>}
    <p className="lc-cta-row"><a className="btn btn-ghost" href={`#/reports/${BEFORE.id}#diagnostics`}>Every finding, with its evidence</a></p>
  </>;
}

// --------------------------------------------------------------------------------------------------------------- 06 improve
const FACTS = ['Course fee', 'Duration', 'Level', 'Class day', 'Campus', 'Seats left', 'Materials'];

function ImproveStep() {
  return <>
    <p className="lede sm">The After website keeps every page and the whole design, and changes only what the report recommended. The course records are
      unchanged, so every frozen task keeps exactly the same correct answer.</p>
    <div className="lc-before-after">
      <figure className="lc-side o"><figcaption><VariantName v={BEFORE_V} /> · /courses</figcaption><img src={showcaseFrame(`site-${BEFORE_V}-courses`)} alt="Before catalogue: name, subject and summary only." loading="lazy" /></figure>
      <figure className="lc-side i"><figcaption><VariantName v={AFTER_V} /> · /courses</figcaption><img src={showcaseFrame(`site-${AFTER_V}-courses`)} alt="After catalogue: every fact on each card." loading="lazy" /></figure>
    </div>
    <div className="lc-table-wrap"><table className="lc-table lc-facts-grid"><caption>What each version shows on its course cards</caption>
      <thead><tr><th scope="col">Fact</th><th scope="col"><VariantName v={BEFORE_V} /></th><th scope="col"><VariantName v={AFTER_V} /></th></tr></thead>
      <tbody>{FACTS.map(f => <tr key={f}><th scope="row">{f}</th><td className="no">course page only</td><td className="yes">✓ on the card</td></tr>)}</tbody></table></div>
    <ol className="lc-improvements">{AFTER_CHANGES.map((x, i) => <li key={x.id} id={`improve-${x.id}`}>
      <div className="lc-imp-text"><span className="lc-tn">Change {i + 1}</span><h3>{x.title}</h3><p>{x.change}</p></div>
    </li>)}</ol>
  </>;
}

// --------------------------------------------------------------------------------------------------------------- 07 re-evaluate
function ReevaluateStep({ ov }: { ov: Overview | null }) {
  const ev = ov?.evaluation?.evaluation ?? null;
  const ready = !!ev && (ev.launches === null || ev.launches.left > 0) && ev.mode === 'paid';     // launches null: the shared budget's evaluation
  const j = journeyOf(AFTER_V, T, AFTER), st = j.steps.find(x => x.step === 2) ?? j.steps[0];
  return <>
    <p className="lede sm">The same frozen tasks run again on the After website, with fresh agents, the same model and the same limits. The product re-checks
      every task on the new site first: a task whose correct answer changed would be set aside, with the reason.</p>
    <div className="lc-sbs">
      <figure className="lc-side i"><figcaption><VariantName v={AFTER_V} /> · task {T} · step {st.step} · {at(T).requests} requests in total</figcaption>
        <img src={showcaseFrame(st.frame)} alt="Recorded screenshot: the After catalogue, every fact on each card." loading="lazy" />
        <blockquote>“{st.memory}”</blockquote></figure>
      <div className="lc-launch">
        <div>
          <h3>{ready ? 'Run it yourself' : 'Live runs'}</h3>
          {ev ? <p>{ev.variants.map(v => <VariantName key={v} v={v} />)} · {ev.options[0]?.trials ?? '–'} browser agents per run ·{' '}
            <strong>{ev.launches ? `${ev.launches.left} of ${ev.launches.max} live run${ev.launches.max === 1 ? '' : 's'} left` : 'runs while the A$20 evaluation budget lasts'}</strong></p>
            : <p>No live run is open right now. Completed evaluations stay available to everyone.</p>}
          <p className="muted">Start it in the workspace with your access code, watch every agent work live, and read the report when they finish.</p>
        </div>
        <a className="btn btn-signal" href="#/run">{ready ? 'Run it live' : 'Open the workspace'} <span className="arr" aria-hidden="true">→</span></a>
      </div>
    </div>
  </>;
}

// --------------------------------------------------------------------------------------------------------------- 08 compare
const versionsOf = (e: EvaluationSummary) => e.variants ?? [];

function CompareStep() {
  const evs = useLoad(() => api.evaluations(), 'evaluations');
  const list = (evs.data ?? []).filter(e => (e.site_id ?? e.site) === FEATURED.site && e.state === 'completed' && e.mode === 'paid' && versionsOf(e).length > 0
    && inPublicScope(versionsOf(e)));
  const day = (s?: string | null) => s ? new Date(s).toLocaleString('en-AU', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Australia/Sydney' }) : '';
  const side = (r: typeof BEFORE, v: string, cls: string) => { const jj = journeyOf(v, T, r), last = jj.steps[jj.steps.length - 1], tr = trialOf(v, T, r)!;
    return <figure key={v} className={`lc-side ${cls}`}><figcaption><VariantName v={v} /> · {tr.correct ? '✓ correct' : '✕ not correct'} · {tr.requests} requests · {Math.round(tr.seconds)} s</figcaption>
      <img src={showcaseFrame(last.frame)} alt={`Recorded screenshot: ${v === BEFORE_V ? 'Before' : 'After'}, task ${T}, step ${last.step}.`} loading="lazy" />
      <blockquote>“{last.memory}”</blockquote></figure>; };
  return <>
    <div className="lc-featured">
      <p className="eyebrow">Live evaluations · 4 Nov 2026 · Before and After</p>
      <dl className="lc-kpis">
        <div><dt>Correct answers</dt><dd>{BEFORE.correct[BEFORE_V]}/{BEFORE.tasks.length} <span className="lc-arrow">→</span> {AFTER.correct[AFTER_V]}/{AFTER.tasks.length}</dd><small>the same {BEFORE.tasks.length} customer tasks</small></div>
        <div><dt>Model requests</dt><dd>{B.requests} <span className="lc-arrow">→</span> {A.requests}</dd><small>{fewerPct(B.requests, A.requests)}% fewer after the change</small></div>
        <div><dt>Agent time</dt><dd>{B.seconds} s <span className="lc-arrow">→</span> {A.seconds} s</dd><small>all tasks</small></div>
        <div><dt>Model cost (US$)</dt><dd>${B.cost_usd.toFixed(2)} <span className="lc-arrow">→</span> ${A.cost_usd.toFixed(2)}</dd><small>{BEFORE.agent.model}</small></div>
      </dl>
      <p className="lc-note">Task {T}: “{BEFORE.tasks[T - 1].wording}” One agent per question on each version: a measured result for these tasks, not a statistical guarantee.</p>
      <div className="lc-sbs">{side(BEFORE, BEFORE_V, 'o')}{side(AFTER, AFTER_V, 'i')}</div>
      <p className="lc-cta-row"><a className="btn btn-signal" href="#/showcase">Watch before and after <span className="arr" aria-hidden="true">→</span></a>
        <a className="btn btn-ghost" href={`#/reports/${BEFORE.id}`}>Before report</a><a className="btn btn-ghost" href={`#/reports/${AFTER.id}`}>After report</a></p>
    </div>
    <h3>Every live evaluation of these two versions</h3>
    {evs.error && <Failed error={evs.error} what="Evaluations" />}
    {evs.data && <div className="lc-table-wrap"><table className="lc-table lc-compare"><caption>Live evaluations of {FEATURED.name}, Before and After</caption>
      <thead><tr><th scope="col">Evaluation</th><th scope="col">Version</th><th scope="col">Correct answers</th><th scope="col">Model requests</th><th scope="col"><span className="sr-only">Report</span></th></tr></thead>
      <tbody>{list.map(e => { const vs = versionsOf(e); return <tr key={e.id}>
        <th scope="row">Live evaluation · {day(e.started_at)}<small>{e.tasks} tasks · {e.trials} agents</small></th>
        <td>{vs.map(v => <VariantName key={v} v={v} />)}</td>
        <td>{vs.map(v => <span key={v} className="lc-inline">{e.success?.[v]?.v2_passed ?? '–'}/{e.success?.[v]?.trials ?? '–'}</span>)}</td>
        <td>{vs.map(v => <span key={v} className="lc-inline">{e.requests?.[v] ?? '–'}</span>)}</td>
        <td><a className="btn btn-sm btn-ghost" href={`#/reports/${e.id}`}>Report →</a></td></tr>; })}</tbody></table></div>}
  </>;
}
