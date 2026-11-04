import { useState } from 'react';
import { SiteFooter, SiteHeader } from '../Shell';
import { PUBLIC_SCOPE, VARIANT_LABEL, api, displayTitle, inPublicScope, latestPaired, fmtSec, fmtUsd, variantClass, type Evaluation, type Finding, type Trial } from '../../lib/lifecycleApi';
import { Failed, GradeTag, Hash, Loading, ModeBadge, PairBars, plain, Section, useLoad, VariantName } from './parts';
import { TraceCompare } from './Trace';
import { AFTER, AFTER_V, BEFORE, BEFORE_V } from '../showcase';
import './lifecycle.css';

/** `#/reports/<id>` and `#/reports/<id>/tasks/<n>`: one readiness report for any evaluation (the recorded first evaluation and evaluations launched in
 *  the product share this page, because the server projects both into the same document). The grades shown are the recorded ones: "correct" is the
 *  recorded grade that accepts a right answer with consistent extra detail (grader v2), and "exact match" is the official grader (v1). */
/** The public experience is the final Larkspur experiment only (Before and After, and later runs of those versions). Any other evaluation is an
 *  archived record: it stays reachable by its exact URL for audit, behind a notice, and is never linked from the public pages. */
export const isPublicEvaluation = (ev: Evaluation) => !PUBLIC_SCOPE.versions || (ev.site.id === 'larkspur' && inPublicScope(ev.manifest.variants.map(v => v.name)));

/** `#/reports/latest` (the "Live report" link): the newest genuine paired Before vs After evaluation, the same run the Workspace opens by default.
 *  Before one exists, it shows the two separate live runs of 4 Nov 2026 as what they are: two runs, never presented as one paired execution. */
export function LatestReportPage() {
  const evs = useLoad(() => api.evaluations(), 'evaluations');
  const pick = evs.data ? latestPaired(evs.data) : null;
  if (pick) return <ReportPage id={pick.id} />;
  const card = (r: typeof BEFORE, v: string, label: string) => { const t = r.totals[v];
    return <a className={`lc-side ${label === 'Before' ? 'o' : 'i'} lc-latest-card`} href={`#/reports/${r.id}`}>
      <span className="eyebrow">{label} · run {r.id.slice(5, 13)}</span>
      <strong>{r.correct[v]}/{r.tasks.length} correct</strong><span>{t.requests} model requests · {t.seconds} s · US${t.cost_usd.toFixed(2)}</span>
      <span className="link">Open the {label} report →</span></a>; };
  return <div className="ar lc">
    <SiteHeader active="report" cta={false} />
    <main id="lc-main" tabIndex={-1} className="wrap lc-wrap">
      {evs.loading && <Loading what="the latest evaluation" />}
      {evs.error && <Failed error={evs.error} what="The evaluations" />}
      {evs.data && <section className="lc-latest" aria-labelledby="lc-latest-h">
        <p className="eyebrow">Live report · Larkspur Community College</p>
        <h1 id="lc-latest-h" className="lc-title">Before and After: two separate live runs</h1>
        <p className="lede sm">No side-by-side evaluation of both versions has been run yet. The current evidence is two separate live evaluations of 4 Nov 2026, one per
          version, with the same three frozen tasks, agent and limits. Each has its own report and agent traces. Run both versions together in the <a className="link" href="#/run">Workspace</a>;
          its report will appear here.</p>
        <div className="lc-sbs">{card(BEFORE, BEFORE_V, 'Before')}{card(AFTER, AFTER_V, 'After')}</div>
      </section>}
    </main>
    <SiteFooter />
  </div>;
}

export function ReportPage({ id, task }: { id: string; task?: number }) {
  const ev = useLoad(() => api.evaluation(id), id);
  const [audit, setAudit] = useState(false);
  return <div className="ar lc">
    <a className="ar-skip" href="#lc-main" onClick={e => { e.preventDefault(); document.getElementById('lc-main')?.focus(); }}>Skip to content</a>
    <SiteHeader active="report" cta={false} />
    <main id="lc-main" tabIndex={-1} className="wrap lc-wrap">
      <nav className="lc-crumbs" aria-label="Breadcrumb"><a href="#/lifecycle">Journey</a><span aria-hidden="true">/</span><a href="#/lifecycle/compare">Before and after</a>
        {task != null && <><span aria-hidden="true">/</span><a href={`#/reports/${id}`}>{ev.data ? displayTitle(ev.data) : id}</a></>}</nav>
      {ev.loading && <Loading what="the evaluation" />}
      {ev.error && <Failed error={ev.error} what="This evaluation" />}
      {ev.data && !isPublicEvaluation(ev.data) && !audit && <div className="lc-archived" role="note">
        <p className="eyebrow">Not part of this experiment</p>
        <h1 className="lc-title sm">This evaluation is not part of the current Larkspur Community College experiment.</h1>
        <p className="lede sm">The public reports are the <a className="link" href={`#/reports/${BEFORE.id}`}>Before</a> and <a className="link" href={`#/reports/${AFTER.id}`}>After</a> evaluations.
          Earlier records are kept unchanged for audit.</p>
        <p><button type="button" className="btn btn-ghost btn-sm" onClick={() => setAudit(true)}>Show the archived record (audit)</button></p></div>}
      {ev.data && (isPublicEvaluation(ev.data) || audit) && <>
        {!isPublicEvaluation(ev.data) && <p className="lc-notice" role="note">Archived record, shown for audit: not part of the current experiment.</p>}
        {task != null ? <TraceCompare ev={ev.data} n={task} /> : <Report ev={ev.data} />}</>}
    </main>
    <SiteFooter />
  </div>;
}

const variantsOf = (ev: Evaluation) => ev.manifest.variants.map(v => v.name);
const trialsFor = (ev: Evaluation, n: number) => ev.trials.filter(t => t.task === n);
const when = (s: string | null) => s ? new Date(s).toLocaleString('en-AU', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Australia/Sydney' }) + ' AEDT' : null;
/** "correct" = the recorded grade that accepts consistent extra detail (v2) when the run has one; otherwise the official grade. */
const correct = (t: Trial) => (t.grades.v2 ?? t.grades.v1).passed;

export function Report({ ev }: { ev: Evaluation }) {
  const vs = variantsOf(ev);
  const diag = Object.values(ev.diagnostics)[0];
  const ex = Object.values(ev.execution);
  const planned = ex.reduce((a, x) => a + (x.planned ?? 0), 0);
  const done = ev.trials.filter(t => t.status === 'completed').length;
  return <article className="lc-report">
    <header className="lc-report-head">
      <p className="eyebrow">Readiness report · {ev.site.label}</p>
      <h1 className="lc-title">{displayTitle(ev)}</h1>
      <div className="lc-badges"><ModeBadge mode={ev.mode} />
        {ev.source?.kind === 'dataset' && <span className="lc-mode neutral">First evaluation · recorded</span>}
        {ev.source?.kind === 'launched' && <span className="lc-mode neutral">{ev.mode === 'paid' ? 'Live run in this product' : 'Run in this product'}{ev.started_at ? ` · ${when(ev.started_at)}` : ''}</span>}</div>
      {ev.mode !== 'paid' && ev.notice && <p className="lc-notice" role="note">{ev.notice}</p>}
      <dl className="lc-facts">
        <div><dt>Agent runs</dt><dd><strong>{done}/{planned || ev.trials.length} finished</strong>{ex.some(x => x.stopped) ? ' · the run stopped early' : ''} · {ev.tasks.filter(t => t.executed).length} tasks on {vs.length === 1 ? 'one version of the site, evaluated on its own' : `${vs.length} versions of the site`}</dd></div>
        <div><dt>Website versions</dt><dd>{vs.map(v => <span key={v} className="lc-inline"><VariantName v={v} /></span>)}</dd></div>
        <div><dt>Agent</dt><dd>{ev.mode === 'paid' ? `${ev.agent.model}, reasoning ${ev.agent.reasoning_effort ?? '–'}` : `${ev.execution_provider} (the declared model ${ev.agent.model} was not called)`} · Browser Use in an isolated Chromium</dd></div>
        <div><dt>Tasks</dt><dd>{ev.tasks.filter(t => t.executed).length} customer tasks{vs.length > 1 ? ', the same for both versions' : ''}{ev.approval.synthetic ? ' (test fixture)' : ''}</dd></div>
        <div><dt>Model cost</dt><dd>{ev.mode === 'paid' ? <>{fmtUsd(ev.cost.settled_spend?.settled_usd ?? ev.cost.total_usd, 4)} for all agents · calculated from the provider’s token counts</> : 'US$0 · no model was called'}</dd></div>
      </dl>
    </header>

    <Glance ev={ev} vs={vs} />
    <TaskMatrix ev={ev} vs={vs} />

    <Section id="diagnostics" n="Recommendations" title="What slowed the agents down, and what to change"
             basis="Observations are measured page properties and recorded agent behaviour, each with its evidence. Likely causes link a missing fact to the extra navigation on the tasks that needed it.">
      {diag ? <DiagnosticsView d={diag} ev={ev} /> : <p className="muted">No recommendations for this evaluation.</p>}
    </Section>
    <Section id="dim-success" n="Dimension 1" title="Task success" basis="Every answer is checked against the college’s own records, which the agent never sees. Correct: the answer names the right courses (extra detail allowed). Exact match: nothing but the course names.">
      <Success ev={ev} vs={vs} /></Section>
    <Section id="dim-nav" n="Dimension 2" title="Navigation efficiency" basis="What each agent spent: model requests (one per decision the agent makes), steps, pages viewed and time. A revisit is a return to a page already seen."><Navigation ev={ev} vs={vs} /></Section>
    <Section id="dim-evidence" n="Dimension 3" title="Evidence" basis="Whether the agent was actually shown the pages that hold the answer, rather than guessing."><Evidence ev={ev} vs={vs} /></Section>
    <Section id="dim-access" n="Dimension 4" title="Information accessibility" basis="Where each fact appears on the website: on the course cards, or only on each course’s own page; and, per task, how far the facts it needs are from the home page."><Access ev={ev} vs={vs} /></Section>
    <Section id="dim-reliability" n="Dimension 5" title="Agent reliability" basis="Failures and limits, per agent: dead ends, partial or empty answers, and runs that reached the request limit."><Reliability ev={ev} vs={vs} /></Section>
    <Provenance ev={ev} />
  </article>;
}

function Glance({ ev, vs }: { ev: Evaluation; vs: string[] }) {
  const ts = ev.dimensions.task_success.variants, nav = ev.dimensions.navigation_efficiency.variants;
  const n = (v: string) => ev.trials.filter(t => t.variant === v && t.status === 'completed' && correct(t)).length;
  return <section className="lc-glance" aria-label="At a glance">
    {vs.map(v => <article key={v} className={`lc-glance-card ${variantClass(v)}`}>
      <h3><VariantName v={v} /></h3>
      <dl>
        <div><dt>Correct answers</dt><dd className="big">{n(v)}/{ts[v].trials}</dd></div>
        <div><dt>Exact match</dt><dd className="big">{ts[v].v1_passed}/{ts[v].trials}</dd></div>
        <div><dt>Model requests</dt><dd>{nav[v].model_requests_total ?? '–'}</dd></div>
        <div><dt>Agent time</dt><dd>{fmtSec(nav[v].elapsed_seconds_total)}</dd></div>
        {ev.mode === 'paid' && <div><dt>Model cost</dt><dd>{fmtUsd(nav[v].cost_usd_total)}</dd></div>}
      </dl>
    </article>)}
  </section>;
}

function cover(t?: Trial) {
  const c = t?.answer_coverage;
  if (!c) return null;
  return c.expected_items > 1 ? `named ${c.named_expected} of ${c.expected_items}${c.named_other ? ` + ${c.named_other} other` : ''}` : c.named_other ? `correct + ${c.named_other} other named` : c.named_expected ? 'names the expected item' : 'expected item not named';
}

function TaskMatrix({ ev, vs }: { ev: Evaluation; vs: string[] }) {
  return <Section id="tasks" n="Tasks" title="Every task, on every version of the site"
                  basis="The customer’s own words, given to the agent unchanged. Each cell is one recorded browser agent; open a task to replay both side by side.">
    <div className="lc-table-wrap"><table className="lc-matrix">
      <thead><tr><th scope="col">Task</th>{vs.map(v => <th scope="col" key={v}><VariantName v={v} /></th>)}<th scope="col"><span className="sr-only">Replay</span></th></tr></thead>
      <tbody>{ev.tasks.filter(t => t.executed).map(t => { const ts = trialsFor(ev, t.n); return <tr key={t.n}>
        <th scope="row"><span className="lc-tn">Task {t.n}</span><q>{t.customer_wording}</q></th>
        {vs.map(v => { const tr = ts.find(x => x.variant === v); return <td key={v} className={`lc-cell ${variantClass(v)}`}>{tr ? <>
          <div className="lc-grades"><GradeTag g={tr.grades.v2 ?? tr.grades.v1} which="v2" /><GradeTag g={tr.grades.v1} which="v1" /></div>
          <small>{[cover(tr), `${tr.metrics.model_requests ?? '–'} requests`, fmtSec(tr.metrics.elapsed_seconds), tr.reliability.dead_end ? 'hit a dead end' : null, tr.reliability.empty_answer ? 'no answer' : null].filter(Boolean).join(' · ')}</small>
        </> : <small>not run</small>}</td>; })}
        <td><a className="btn btn-sm btn-ghost" href={`#/reports/${ev.id}/tasks/${t.n}`} aria-label={`Replay task ${t.n} side by side`}>Replay <span className="arr" aria-hidden="true">→</span></a></td>
      </tr>; })}</tbody>
    </table></div>
  </Section>;
}

function Success({ ev, vs }: { ev: Evaluation; vs: string[] }) {
  const ts = ev.dimensions.task_success.variants;
  const n = (v: string) => ev.trials.filter(t => t.variant === v && t.status === 'completed' && correct(t)).length;
  return <>
    <div className="lc-table-wrap"><table className="lc-table"><thead><tr><th scope="col">Tasks</th>{vs.map(v => <th scope="col" key={v}><VariantName v={v} /></th>)}</tr></thead><tbody>
      <tr><th scope="row">Correct answers</th>{vs.map(v => <td key={v}><strong>{n(v)}/{ts[v].trials}</strong></td>)}</tr>
      <tr><th scope="row">Exact match</th>{vs.map(v => <td key={v}>{ts[v].v1_passed}/{ts[v].trials}</td>)}</tr>
    </tbody></table></div>
    <p className="lc-note">An answer such as “Beginners yoga – $150, 12 seats left” is correct but not an exact match, which needs the course names alone.</p>
  </>;
}

function Navigation({ ev, vs }: { ev: Evaluation; vs: string[] }) {
  const nav = ev.dimensions.navigation_efficiency.variants;
  const rows = ev.tasks.filter(t => t.executed).map(t => ({ key: String(t.n), label: `Task ${t.n}`, values: Object.fromEntries(vs.map(v => [v, trialsFor(ev, t.n).find(x => x.variant === v)?.metrics.model_requests ?? null])) }));
  const time = ev.tasks.filter(t => t.executed).map(t => ({ key: String(t.n), label: `Task ${t.n}`, values: Object.fromEntries(vs.map(v => [v, trialsFor(ev, t.n).find(x => x.variant === v)?.metrics.elapsed_seconds ?? null])) }));
  return <>
    <div className="lc-table-wrap"><table className="lc-table"><thead><tr><th scope="col">Per agent</th>{vs.map(v => <th scope="col" key={v}><VariantName v={v} /></th>)}</tr></thead><tbody>
      {([['Model requests, mean (total)', (v: string) => `${nav[v].model_requests_mean ?? '–'} (${nav[v].model_requests_total ?? '–'})`], ['Agent steps, mean', (v: string) => nav[v].steps_mean ?? '–'],
         ['Page views, mean', (v: string) => nav[v].page_views_mean ?? '–'], ['Time, mean (total)', (v: string) => `${fmtSec(nav[v].elapsed_seconds_mean)} (${fmtSec(nav[v].elapsed_seconds_total)})`],
         ['Revisits, total', (v: string) => nav[v].revisits_total ?? '–'], ['Course pages opened, mean', (v: string) => nav[v].item_pages_opened_mean ?? '–']] as const)
        .map(([k, f]) => <tr key={k}><th scope="row">{k}</th>{vs.map(v => <td key={v}>{f(v)}</td>)}</tr>)}
    </tbody></table></div>
    <div className="lc-two"><PairBars rows={rows} variants={vs} unit="req" label="Model requests per task" /><PairBars rows={time} variants={vs} unit="s" label="Agent time per task (seconds)" /></div>
  </>;
}

function Evidence({ ev, vs }: { ev: Evaluation; vs: string[] }) {
  const e = ev.dimensions.evidence_quality;
  return <div className="lc-table-wrap"><table className="lc-table"><thead><tr><th scope="col">Agents</th>{vs.map(v => <th scope="col" key={v}><VariantName v={v} /></th>)}</tr></thead><tbody>
    <tr><th scope="row">Shown the pages that hold the answer</th>{vs.map(v => <td key={v}>{e.variants[v].evidence_satisfied}/{e.variants[v].trials}</td>)}</tr>
    {vs.some(v => e.variants[v].evidence_satisfied_or_equivalent !== undefined) && <tr><th scope="row">…or an equivalent page that states every deciding fact for every course (e.g. a comparison table)</th>
      {vs.map(v => <td key={v}><strong>{e.variants[v].evidence_satisfied_or_equivalent ?? e.variants[v].evidence_satisfied}/{e.variants[v].trials}</strong></td>)}</tr>}
    <tr><th scope="row">Correct without being shown the answer pages</th>{vs.map(v => <td key={v}>{e.variants[v].correct_but_unsupported_v2}</td>)}</tr>
    <tr><th scope="row">Answer pages not shown (total)</th>{vs.map(v => <td key={v}>{e.variants[v].missing_pages_total}</td>)}</tr>
  </tbody></table></div>;
}

function Access({ ev, vs }: { ev: Evaluation; vs: string[] }) {
  const a = ev.dimensions.information_accessibility;
  const facts = [...new Set(vs.flatMap(v => Object.keys(a.facts[v] ?? {})))].sort();
  return <>
    <div className="lc-table-wrap"><table className="lc-table"><thead><tr><th scope="col">Fact</th>{vs.map(v => <th scope="col" key={v}><VariantName v={v} /> · on the cards</th>)}</tr></thead><tbody>
      {facts.map(f => <tr key={f}><th scope="row">{f}</th>{vs.map(v => { const x = a.facts[v]?.[f]; return <td key={v}>{x ? <><b>{x.on_listing_cards}/{x.items}</b> cards · {x.on_item_pages}/{x.items} course pages</> : '–'}</td>; })}</tr>)}
    </tbody></table></div>
    <div className="lc-table-wrap"><table className="lc-table"><thead><tr><th scope="col">Task needs</th>{vs.map(v => <th scope="col" key={v}><VariantName v={v} /></th>)}</tr></thead><tbody>
      {a.tasks.map(t => <tr key={t.task}><th scope="row">Task {t.task}: {t.facts.join(', ')}</th>{vs.map(v => <td key={v}>{t.facts.map(f => <span key={f} className={`lc-place ${t.placement[v]?.[f] === 'listing cards' ? 'ok' : 'deep'}`}>{f}: {t.placement[v]?.[f]}</span>)}
        {t.min_link_steps?.[v] != null && <small> · answer ≥ {t.min_link_steps[v]} click(s) from the home page</small>}</td>)}</tr>)}
    </tbody></table></div>
  </>;
}

function Reliability({ ev, vs }: { ev: Evaluation; vs: string[] }) {
  const r = ev.dimensions.agent_reliability.variants;
  const rows: [string, (v: string) => number | null][] = [['Dead ends (page not found, failed actions)', v => r[v].dead_ends], ['…recovered and still answered', v => r[v].recovered_after_dead_end],
    ['Partial answers (some expected items missing)', v => r[v].partial_answers], ['Empty answers', v => r[v].empty_answers], ['At or within one request of the limit', v => r[v].near_request_limit],
    ['Stopped by a limit', v => r[v].limit_stops], ['Void runs', v => r[v].void]];
  return <div className="lc-table-wrap"><table className="lc-table"><thead><tr><th scope="col">Agents</th>{vs.map(v => <th scope="col" key={v}><VariantName v={v} /></th>)}</tr></thead>
    <tbody>{rows.map(([k, f]) => <tr key={k}><th scope="row">{k}</th>{vs.map(v => <td key={v}>{f(v) ?? '–'}</td>)}</tr>)}</tbody></table></div>;
}

/** One evidence line in plain language: findings by their title, agent runs by version and task, page facts by page (no internal ids or selectors). */
function evidenceLine(e: { type: string | null; ref: string | null; detail: string | null }, ev?: Evaluation): string {
  const ref = plain(e.ref ?? ''), detail = plain(e.detail ?? '').replace(/; stop \w+/, '')
    .replace('graded not passed by the exact-match grader and by the correctness grader', 'not correct')
    .replace(/evidence-supported/g, 'exact match with evidence').replace(/ \(\/[a-z]+\/\{\}\)/g, '');
  if (e.type === 'finding') return detail || ref;
  if (e.type === 'trial') {
    const m = ref.match(/^(.+?)-(gen-[0-9a-f]+-[a-z])-r\d+$/);
    if (m) { const n = ev?.tasks.find(t => t.task_id === m[2])?.n; return `${m[1]} agent${n ? `, task ${n}` : ''}: ${detail}`; }
    const g = ref.match(/^(.+?): \d+ trials?$/);
    return `${g ? g[1] : ref}: ${detail}`;
  }
  if (e.type === 'listing_field') return `${ref.split('#')[1] ?? ref}: ${detail}`;
  if (e.type === 'page') return /</.test(detail) ? ref : `${ref}${detail ? ` (${detail})` : ''}`;
  return detail ? `${ref}: ${detail}` : ref;
}

export function FindingCard({ f, ev }: { f: Finding; ev?: Evaluation }) {
  return <li className={`lc-finding ${f.basis}`}>
    <div className="lc-finding-head"><span className={`lc-sev ${f.severity}`}>{f.severity}</span>{f.variant && <VariantName v={f.variant} />}{f.tasks.length > 0 && <span className="muted">task {f.tasks.join(', ')}</span>}</div>
    <p className="lc-finding-t">{plain(f.title)}</p>
    <p className="lc-finding-i">{plain(f.impact)}</p>
    <p className="lc-finding-r"><b>Recommendation.</b> {plain(f.recommendation)}</p>
    <details><summary>Evidence ({f.evidence.length})</summary>
      <ul className="lc-ev">{f.evidence.map((e, i) => <li key={i}>{evidenceLine(e, ev)}</li>)}</ul>
      <p className="muted"><b>How to check the fix.</b> {plain(f.verify)}</p></details>
  </li>;
}

/** Agent-behaviour observations of the same kind are shown once with every task they occurred on (the recorded findings are per task). */
function groupBehaviour(fs: Finding[]): Finding[] {
  const out: Finding[] = [], byKey = new Map<string, Finding>();
  const rank = (x: string) => ['info', 'low', 'medium', 'high'].indexOf(x);
  for (const f of fs) {
    if (f.layer !== 'behavioral') { out.push(f); continue; }
    const kind = f.title.replace(/ on task \d+.*$/, ''), key = `${f.variant}|${kind}`, g = byKey.get(key);
    if (!g) { const n = { ...f, title: kind[0].toUpperCase() + kind.slice(1), tasks: [...f.tasks], evidence: [...f.evidence] }; byKey.set(key, n); out.push(n); continue; }
    g.tasks = [...new Set([...g.tasks, ...f.tasks])].sort(); g.evidence = [...g.evidence, ...f.evidence];
    if (rank(f.severity) > rank(g.severity)) g.severity = f.severity;
  }
  return out;
}

function DiagnosticsView({ d, ev }: { d: NonNullable<Evaluation['diagnostics'][string]>; ev: Evaluation }) {
  const [layer, setLayer] = useState<'all' | 'structural' | 'behavioral'>('all');
  if (!d.available) return <p className="muted">Recommendations unavailable.</p>;
  const fs = (d.findings ?? []).filter(f => !f.title.startsWith('v1 format'));   // grading-format notes, not website findings
  const obs = groupBehaviour(fs.filter(f => f.basis === 'observed')).filter(f => layer === 'all' || f.layer === layer);
  const hyp = fs.filter(f => f.basis === 'hypothesis' && f.status !== 'unverified');                 // unmeasured risk hints are not shown as causes
  const first = ev.manifest.variants[0]?.name;
  return <>
    <p className="lc-note">{obs.length} observations, {hyp.length} likely causes
      {Object.entries(d.structural_changes ?? {}).map(([k, c]) => <span key={k}> · {VARIANT_LABEL(k)} fixed {c.resolved} of the {c.resolved + c.persisting} page problems found on {first ? VARIANT_LABEL(first) : 'the first version'}{c.introduced ? ` and introduced ${c.introduced}` : ''}</span>)}.</p>
    <div className="lc-diag">
      <div><h3>Likely causes and what to change</h3><ul className="lc-findings">{hyp.map(f => <FindingCard key={f.id + f.variant} f={f} ev={ev} />)}</ul></div>
      <div><h3>Observations</h3>
        <div className="lc-seg" role="group" aria-label="Filter observations">{(['all', 'structural', 'behavioral'] as const).map(x => <button key={x} type="button" aria-pressed={layer === x} onClick={() => setLayer(x)}>{x === 'all' ? 'All' : x === 'structural' ? 'Page structure' : 'Agent behaviour'}</button>)}</div>
        <ul className="lc-findings">{obs.map(f => <FindingCard key={f.id + f.variant} f={f} ev={ev} />)}</ul></div>
    </div>
  </>;
}

function Provenance({ ev }: { ev: Evaluation }) {
  const ex = Object.values(ev.execution)[0];
  return <Section id="provenance" n="Provenance" title="Where these numbers come from">
    <ul className="lc-prov">
      {ev.source?.kind === 'dataset' && <li>Recorded evaluation <code>{ev.source.id}</code> (built {ev.source.built_at}): {ev.source.description}</li>}
      <li>Execution: {ex?.executed}/{ex?.planned ?? '–'} agent runs finished{ex?.stopped ? `, stopped: ${ex.stopped}` : ''}; browser isolation check {ex?.jail_selftest_ok ? 'passed' : 'not recorded'}{ev.mode === 'paid' ? `; spending authorised in advance ${ex?.authorization_verified ? 'for exactly this task set and configuration' : '(not recorded)'}` : ''}.</li>
      <li>Agent: {ev.agent.model}, reasoning {ev.agent.reasoning_effort ?? '–'}: the same agent and limits for every run · one agent per task{ev.manifest.variants.length > 1 ? ' on each version' : ''} · run <code>{ev.id}</code>.</li>
      <li>Tasks: {ev.tasks.filter(t => t.executed).length} customer tasks, fixed before the run <Hash sha={ev.frozen_suite.sha256} />.</li>
      <li>Website versions (frozen copies): {ev.manifest.variants.map(v => <span key={v.name} className="lc-inline"><VariantName v={v.name} /> <Hash sha={v.snapshot_sha256} /></span>)}</li>
      <li>Privacy: expected answers and grading criteria stay on the server; this page shows the agents’ own answers and counts.</li>
    </ul>
  </Section>;
}
