import { useEffect, useState } from 'react';
import { SiteFooter, SiteHeader } from '../Shell';
import { api, fmtUsd, words, type EvaluationSummary, type Finding, type Generation, type Overview, type Suite } from '../../lib/lifecycleApi';
import { CARD_FACTS, FEATURED, IMPROVEMENTS, JOURNEY, LIVE, PAGE_AUDIT, VERSIONS, fewerPct, journeyOf, showcaseFrame, trialOf } from '../showcase';
import { Failed, Loading, useLoad, VariantName } from './parts';
import './lifecycle.css';

/** `#/lifecycle[/<step>]` (and `#/demo`): the featured website's journey through the product, as one page: website -> generated tasks -> owner
 *  review -> live evaluation -> recommendations -> the improved website -> re-evaluation -> comparison. Recorded artefacts come from the API (the
 *  generation, the frozen suite, the evaluations and their reports) or, for the recorded live run, from showcase.ts. Nothing is simulated; a live
 *  run is started only from the workspace. */
export function Lifecycle({ step, suite }: { step?: string; suite?: string }) {
  const ov = useLoad(() => api.overview(), 'overview');
  const current = step ?? 'website';
  useEffect(() => {                      // deep link: scroll now, and again once the sections above have loaded their data and images
    if (!step) return;
    const go = () => document.getElementById(`lc-${step}`)?.scrollIntoView?.({ block: 'start' });
    go(); const t = [setTimeout(go, 400), setTimeout(go, 1200)];
    return () => t.forEach(clearTimeout);
  }, [step]);
  return <div className="ar lc">
    <a className="ar-skip" href="#lc-main" onClick={e => { e.preventDefault(); document.getElementById('lc-main')?.focus(); }}>Skip to content</a>
    <SiteHeader active="lifecycle" />
    <main id="lc-main" tabIndex={-1} className="wrap lc-wrap">
      <header className="lc-intro">
        <p className="eyebrow">The {FEATURED.short} journey</p>
        <h1 className="lc-title">From a website to one <em>agents can use.</em></h1>
        <p className="lede">{FEATURED.name} runs evening and weekend short courses. Follow its website through Agent Readiness: customer tasks generated from
          its own catalogue, approved by the owner, run by real Muse Spark browser agents, turned into recommendations, applied to the site, and run again.</p>
      </header>
      <nav className="lc-stepper" aria-label="Journey steps"><ol>{JOURNEY.map(s =>
        <li key={s.id}><a href={`#/lifecycle/${s.id}`} aria-current={current === s.id ? 'step' : undefined}>
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
    <h3>Three versions of the website</h3>
    <ul className="lc-versions">{(['original', 'modified', 'improved'] as const).map(v => <li key={v}>
      <figure><img src={showcaseFrame(`site-${v}-courses`)} alt={`The ${VERSIONS[v].label} course catalogue.`} loading="lazy" /></figure>
      <VariantName v={v} /><p>{VERSIONS[v].blurb}</p></li>)}</ul>
  </>;
}

// --------------------------------------------------------------------------------------------------------------- 02 tasks
const ADMISSION: Record<string, string> = { natural: 'Accepted', rejected: 'Rejected', rubric: 'Needs a person to grade' };

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
  const [filter, setFilter] = useState('natural');
  const final = g.post_fix_reevaluation?.admissions ?? g.admissions;
  const props = g.proposals.filter(p => filter === 'all' || p.admission === filter);
  return <div className="lc-gen">
    <dl className="lc-kpis">
      <div><dt>Questions proposed</dt><dd>{g.proposals.length}</dd><small>{g.rounds.filter(r => r.sent).length} rounds · {String(g.generator.model)}</small></div>
      <div><dt>Accepted</dt><dd>{final.natural ?? 0}</dd><small>answerable from the catalogue, in the customer’s words{g.post_fix_reevaluation ? ` (${g.admissions.natural ?? 0} as first checked; ${final.natural ?? 0} after a fix to the checker, re-checked at no cost)` : ''}</small></div>
      <div><dt>Model cost</dt><dd>{fmtUsd(g.cost.calculated_usd, 3)}</dd><small>{g.cost.requests} model requests</small></div>
    </dl>
    <div className="lc-seg" role="group" aria-label="Filter proposed questions">{['natural', 'rubric', 'rejected', 'all'].filter(k => k === 'all' || g.admissions[k]).map(k =>
      <button key={k} type="button" aria-pressed={filter === k} onClick={() => setFilter(k)}>{k === 'all' ? `All ${g.proposals.length}` : `${ADMISSION[k] ?? words(k)} ${g.admissions[k]}`}</button>)}</div>
    <ul className="lc-proposals">{props.map(p => <li key={p.id} className={p.admission}>
      <div className="lc-prop-head"><span className={`tag ${p.admission === 'natural' ? 'tag-pass' : p.admission === 'rejected' ? 'tag-fail' : 'tag-neutral'}`}>{ADMISSION[p.admission] ?? words(p.admission)}</span>
        <small>{words(p.capability)}{p.persona ? ` · ${words(p.persona)}` : ''}</small></div>
      <q>{p.customer_wording ?? `[${p.withheld}]`}</q>
      {p.rejection_reasons.length > 0 && <p className="lc-reject">{p.rejection_reasons.join('; ')}</p>}
    </li>)}</ul>
  </div>;
}

// --------------------------------------------------------------------------------------------------------------- 03 review
function ReviewStep({ selected }: { selected?: string }) {
  const suites = useLoad(() => api.suites(), 'suites');
  const mine = (suites.data ?? []).filter(s => s.site === FEATURED.site && !s.synthetic);
  const id = selected ?? mine.find(s => s.state === 'frozen' && s.name === 'larkspur-core' && s.version === 2)?.sha256 ?? mine.find(s => s.state === 'frozen')?.sha256;
  const s = useLoad(() => id ? api.suite(id) : Promise.resolve(null), `suite-${id}`);
  const judge = mine.find(x => `${x.name}@v${x.version}` === FEATURED.judgeSuite);
  return <>
    <p className="lede sm">The owner reads the accepted questions and approves an exact, frozen set. A frozen set never changes: re-evaluating the website later
      uses the very same questions, so the comparison is fair. Approval happens at the owner’s terminal, never on the web.</p>
    {suites.error && <Failed error={suites.error} what="Task sets" />}
    {s.data && <SuiteView s={s.data} />}
    {judge && s.data && <p className="lc-note">Live runs started by judges use <strong>{FEATURED.judgeSuite}</strong>: {(() => {
      const ids = [...s.data.tasks].map(t => t.task_id).sort();
      const n = FEATURED.judgeTasks.map(id => ids.indexOf(id) + 1).filter(x => x > 0);
      return `task${n.length === 1 ? '' : 's'} ${n.length > 1 ? `${n.slice(0, -1).join(', ')} and ${n.at(-1)}` : n.join('')}`;
    })()} of this set ({judge.state}).</p>}
  </>;
}

function SuiteView({ s }: { s: Suite }) {
  const appr = s.approvals.find(a => a.decision === 'approved');
  return <div className="lc-suite">
    <p className="lc-suite-state"><span className={`tag ${s.state === 'frozen' ? 'tag-signal' : 'tag-neutral'}`}>{s.state === 'frozen' ? 'Approved and frozen' : words(s.state)}</span>
      <strong>{s.suite_name} v{s.version}</strong> · {s.counts.tasks} tasks{appr ? ` · approved by the ${appr.role} on ${new Date(appr.decided_at).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })}` : ''}</p>
    <ol className="lc-review-tasks">{[...s.tasks].sort((a, b) => a.task_id.localeCompare(b.task_id)).map((t, i) => <li key={t.task_id}>
      <span className="lc-tn">Task {i + 1}</span><q>{t.customer_wording}</q>
      <small>{words(t.capability)}{t.persona ? ` · ${words(t.persona)}` : ''} · up to {t.limits.max_model_requests} model requests</small>
    </li>)}</ol>
  </div>;
}

// --------------------------------------------------------------------------------------------------------------- 04 evaluate
function EvaluateStep() {
  const o = LIVE.totals.original, m = LIVE.totals.modified;
  const a = journeyOf('original', 1), b = journeyOf('modified', 1);
  const shot = (j: typeof a, n: number) => j.steps.find(x => x.step === n);
  return <>
    <p className="lede sm">Each task goes to a fresh Muse Spark browser agent on each version of the site, in a browser that can reach nothing but the frozen copy.
      Every page, screenshot, action and the agent’s own notes are recorded, and the answer is graded against the course records.</p>
    <dl className="lc-kpis">
      <div><dt>Agents</dt><dd>{LIVE.trials.length}</dd><small>{LIVE.tasks.length} tasks × Original and Modified · {FEATURED.liveDate}</small></div>
      <div><dt>Model requests</dt><dd>{o.requests} <span className="lc-arrow">→</span> {m.requests}</dd><small>Original → Modified · {fewerPct(o.requests, m.requests)}% fewer</small></div>
      <div><dt>Correct answers</dt><dd>{LIVE.correct.original} <span className="lc-arrow">→</span> {LIVE.correct.modified}</dd><small>of {LIVE.tasks.length} tasks</small></div>
      <div><dt>Model cost</dt><dd>{fmtUsd(LIVE.cost_usd, 2)}</dd><small>{LIVE.agent.model} · all {LIVE.trials.length} agents</small></div>
    </dl>
    <div className="lc-sbs">
      {[['original', a, 13], ['modified', b, 2]].map(([v, j, n]) => { const jj = j as typeof a; const st = shot(jj, n as number) ?? jj.steps[jj.steps.length - 1]; const tr = trialOf(v as string, 1)!;
        return <figure key={v as string} className={`lc-side ${v === 'original' ? 'o' : 'm'}`}>
          <figcaption><VariantName v={v as string} /> · task 1 · {tr.requests} requests · {Math.round(tr.seconds)} s</figcaption>
          <img src={showcaseFrame(st.frame)} alt={`Recorded screenshot: ${v} site, step ${st.step}, ${st.path}.`} loading="lazy" />
          <blockquote>“{jj.steps[jj.steps.length - 1].memory}”</blockquote>
        </figure>; })}
    </div>
    <p className="lc-cta-row"><a className="btn btn-signal" href={`#/reports/${LIVE.id}/tasks/1`}>Replay task 1 side by side <span className="arr" aria-hidden="true">→</span></a>
      <a className="btn btn-ghost" href={`#/reports/${LIVE.id}`}>Open the live report</a></p>
  </>;
}

// --------------------------------------------------------------------------------------------------------------- 05 recommendations
/** Which Improved change answers a recommendation (by the finding's subject). */
function appliedBy(f: Finding): string | null {
  const t = `${f.title} ${f.recommendation}`.toLowerCase();
  if (/structured data|json-ld/.test(t)) return 'structured';
  if (/dead end|failing link/.test(t)) return 'dead-ends';
  if (/listing|card/.test(t)) return 'facts';
  if (/budget|loop|revisit|unnecessary navigation/.test(t)) return 'compare';
  return null;
}

function RecommendationsStep() {
  const ev = useLoad(() => api.evaluation(LIVE.id), LIVE.id);
  const d = ev.data ? Object.values(ev.data.diagnostics)[0] : null;
  const fs = d?.findings ?? [];
  const causes = fs.filter(f => f.basis === 'hypothesis' && f.severity !== 'info');
  const structural = fs.filter(f => f.basis === 'observed' && f.layer === 'structural' && f.variant === 'original');
  const behaviour = new Map<string, number>();
  fs.filter(f => f.basis === 'observed' && f.layer === 'behavioral' && f.variant === 'original' && !f.title.startsWith('v1 format')).forEach(f => {
    const k = f.title.replace(/ on task \d+.*$/, ''); behaviour.set(k, (behaviour.get(k) ?? 0) + 1); });
  const recs = [...new Map([...causes, ...structural].map(f => [f.recommendation, f])).values()];
  return <>
    <p className="lede sm">The report reads what the agents did and what the pages contain, and turns it into specific changes. Each recommendation cites its
      evidence: the steps where an agent ran out of requests, the page that returned a 404, the fact that sat one click too deep.</p>
    {ev.loading && <Loading what="the live report" />}
    {ev.error && <Failed error={ev.error} what="The live report" />}
    {d && <div className="lc-recs">
      <div><h3>What the agents ran into <small>(Original site)</small></h3>
        <ul className="lc-counts">{[...behaviour.entries()].map(([k, n]) => <li key={k}><span>{k[0].toUpperCase() + k.slice(1)}</span><b>{n} task{n === 1 ? '' : 's'}</b></li>)}</ul></div>
      <div><h3>Recommendations</h3>
        <ul className="lc-rec-list">{recs.map(f => { const a = appliedBy(f); const imp = IMPROVEMENTS.find(x => x.id === a);
          return <li key={f.id + f.recommendation}><p>{f.recommendation}</p>
            <small>{f.basis === 'hypothesis' ? `Likely cause of the extra navigation on task ${f.tasks.join(', ')}` : f.title}</small>
            {imp && <a className="tag tag-pass" href="#/lifecycle/improve">✓ Applied: {imp.title}</a>}</li>; })}</ul></div>
    </div>}
    <p className="lc-cta-row"><a className="btn btn-ghost" href={`#/reports/${LIVE.id}#diagnostics`}>Every finding, with its evidence</a></p>
  </>;
}

// --------------------------------------------------------------------------------------------------------------- 06 improve
function ImproveStep() {
  return <>
    <p className="lede sm">The Modified site was a first, single fix: fee, duration, level and seats on the cards. The Improved site applies every recommendation.
      The course records are unchanged, so every frozen task keeps exactly the same correct answer.</p>
    <div className="lc-before-after">
      <figure className="lc-side o"><figcaption><VariantName v="original" /> · /courses</figcaption><img src={showcaseFrame('site-original-courses')} alt="Original catalogue: name, subject and summary only." loading="lazy" /></figure>
      <figure className="lc-side i"><figcaption><VariantName v="improved" /> · /courses</figcaption><img src={showcaseFrame('site-improved-courses')} alt="Improved catalogue: a filter form and every fact on each card." loading="lazy" /></figure>
    </div>
    <div className="lc-table-wrap"><table className="lc-table lc-facts-grid"><caption>What each version shows on its course cards</caption>
      <thead><tr><th scope="col">Fact</th>{(['original', 'modified', 'improved'] as const).map(v => <th scope="col" key={v}><VariantName v={v} /></th>)}</tr></thead>
      <tbody>{CARD_FACTS.map(f => <tr key={f.fact}><th scope="row">{f.fact}</th>{[f.original, f.modified, f.improved].map((x, i) => <td key={i} className={x ? 'yes' : 'no'}>{x ? '✓ on the card' : 'course page only'}</td>)}</tr>)}</tbody></table></div>
    <dl className="lc-kpis">{(['original', 'modified', 'improved'] as const).map(v => <div key={v}><dt>Page audit · {VERSIONS[v].label}</dt><dd>{PAGE_AUDIT[v].length}</dd>
      <small>{PAGE_AUDIT[v].length ? `problems in the pages themselves (${PAGE_AUDIT[v].length === 1 ? 'one' : 'e.g.'} ${PAGE_AUDIT[v][0]})` : 'nothing left for the page audit to flag'}</small></div>)}</dl>
    <ol className="lc-improvements">{IMPROVEMENTS.map((x, i) => <li key={x.id} id={`improve-${x.id}`}>
      <div className="lc-imp-text">
        <span className="lc-tn">Change {i + 1}</span><h3>{x.title}</h3>
        <dl><div><dt>What agents hit</dt><dd>{x.problem}</dd></div><div><dt>Recommendation</dt><dd>{x.recommendation}</dd></div><div><dt>On the Improved site</dt><dd>{x.change} <code>{x.tryPath}</code></dd></div></dl>
      </div>
      {x.preview && <figure><img src={showcaseFrame(x.preview)} alt={`Improved site: ${x.title}.`} loading="lazy" /></figure>}
    </li>)}</ol>
  </>;
}

// --------------------------------------------------------------------------------------------------------------- 07 re-evaluate
function ReevaluateStep({ ov }: { ov: Overview | null }) {
  const ev = ov?.evaluation?.evaluation ?? null;
  const ready = !!ev && ev.launches.left > 0 && ev.mode === 'paid';
  return <>
    <p className="lede sm">The same frozen tasks run again on Original and Improved, with fresh agents, the same model and the same limits. The product re-checks
      every task on the new site first: a task whose correct answer changed would be set aside, with the reason.</p>
    <div className="lc-launch">
      <div>
        <h3>{ready ? 'Ready for a live run' : 'Live runs'}</h3>
        {ev ? <p>{ev.variants.map(v => <VariantName key={v} v={v} />)} · {ev.suite} · {ev.options[0]?.trials ?? '–'} browser agents per run ·{' '}
          <strong>{ev.launches.left} of {ev.launches.max} live run{ev.launches.max === 1 ? '' : 's'} left</strong></p>
          : <p>No live run is open right now. The owner opens a set number of runs; completed evaluations stay available to everyone.</p>}
        <p className="muted">Start it in the workspace with your access code, watch every agent work live, and the report appears when they finish (about 4–6 minutes).</p>
      </div>
      <a className="btn btn-signal" href="#/run">{ready ? 'Run Original vs Improved' : 'Open the workspace'} <span className="arr" aria-hidden="true">→</span></a>
    </div>
  </>;
}

// --------------------------------------------------------------------------------------------------------------- 08 compare
const versionsOf = (e: EvaluationSummary) => e.variants ?? [];

function CompareStep() {
  const evs = useLoad(() => api.evaluations(), 'evaluations');
  const list = (evs.data ?? []).filter(e => (e.site_id ?? e.site) === FEATURED.site && e.state === 'completed' && e.mode === 'paid');
  const day = (s?: string | null) => s ? new Date(s).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Australia/Sydney' }) : '';
  const improved = list.filter(e => versionsOf(e).includes('improved'));
  return <>
    <p className="lede sm">Every completed live evaluation of {FEATURED.short}, side by side. Each opens its full report with every agent’s trace.</p>
    {evs.error && <Failed error={evs.error} what="Evaluations" />}
    {evs.data && <div className="lc-table-wrap"><table className="lc-table lc-compare"><caption>Live evaluations of {FEATURED.name}</caption>
      <thead><tr><th scope="col">Evaluation</th><th scope="col">Versions</th><th scope="col">Correct answers</th><th scope="col">Model requests</th><th scope="col"><span className="sr-only">Report</span></th></tr></thead>
      <tbody>{list.map(e => { const vs = versionsOf(e); return <tr key={e.id}>
        <th scope="row">{e.source === 'dataset' ? 'First evaluation' : 'Live evaluation'} · {day(e.started_at)}<small>{e.suite} · {e.tasks} tasks · {e.trials} agents</small></th>
        <td>{vs.map(v => <VariantName key={v} v={v} />)}</td>
        <td>{vs.map(v => <span key={v} className="lc-inline">{e.success?.[v]?.v2_passed ?? '–'}/{e.success?.[v]?.trials ?? '–'}</span>)}</td>
        <td>{vs.map(v => <span key={v} className="lc-inline">{e.requests?.[v] ?? '–'}</span>)}</td>
        <td><a className="btn btn-sm btn-ghost" href={`#/reports/${e.id}`}>Report →</a></td></tr>; })}</tbody></table></div>}
    {evs.data && !improved.length && <p className="lc-note"><strong>The Improved site has not had a live run yet.</strong> Start the first one in the <a className="link" href="#/run">workspace</a>; it appears here when the agents finish.</p>}
  </>;
}
