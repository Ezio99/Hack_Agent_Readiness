import { useState } from 'react';
import { SiteFooter, SiteHeader } from '../Shell';
import { api, displayTitle, fmtSec, fmtUsd, variantClass, words, type Evaluation, type Finding, type Trial } from '../../lib/lifecycleApi';
import { Failed, GradeTag, Hash, Loading, ModeBadge, PairBars, plain, Section, useLoad, VariantName } from './parts';
import { TraceCompare } from './Trace';
import './lifecycle.css';

/** `#/reports/<id>` and `#/reports/<id>/tasks/<n>`: one readiness report for any evaluation (the recorded first evaluation and evaluations launched in
 *  the product share this page, because the server projects both into the same document). The grades shown are the recorded ones: "correct" is the
 *  recorded grade that accepts a right answer with consistent extra detail (grader v2), and "exact match" is the official grader (v1). */
export function ReportPage({ id, task }: { id: string; task?: number }) {
  const ev = useLoad(() => api.evaluation(id), id);
  return <div className="ar lc">
    <a className="ar-skip" href="#lc-main" onClick={e => { e.preventDefault(); document.getElementById('lc-main')?.focus(); }}>Skip to content</a>
    <SiteHeader active="report" cta={false} />
    <main id="lc-main" tabIndex={-1} className="wrap lc-wrap">
      <nav className="lc-crumbs" aria-label="Breadcrumb"><a href="#/lifecycle">Journey</a><span aria-hidden="true">/</span><a href="#/lifecycle/compare">Evaluations</a>
        {task != null && <><span aria-hidden="true">/</span><a href={`#/reports/${id}`}>{ev.data ? displayTitle(ev.data) : id}</a></>}</nav>
      {ev.loading && <Loading what="the evaluation" />}
      {ev.error && <Failed error={ev.error} what="This evaluation" />}
      {ev.data && (task != null ? <TraceCompare ev={ev.data} n={task} /> : <Report ev={ev.data} />)}
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
        <div><dt>Task set</dt><dd>{ev.suite.name} v{ev.suite.version} · approved by the {ev.approval.role}{ev.approval.synthetic ? ' (test fixture)' : ''}</dd></div>
        <div><dt>Model cost</dt><dd>{ev.mode === 'paid' ? <>{fmtUsd(ev.cost.settled_spend?.settled_usd ?? ev.cost.total_usd, 4)} for all agents · calculated from the provider’s token counts</> : 'US$0 · no model was called'}</dd></div>
      </dl>
    </header>

    <Glance ev={ev} vs={vs} />
    <TaskMatrix ev={ev} vs={vs} />

    <Section id="diagnostics" n="Recommendations" title="What slowed the agents down, and what to change"
             basis="Observations are measured page properties and recorded agent behaviour, each with its evidence. Likely causes link a missing fact to the extra navigation on the tasks that needed it.">
      {diag ? <DiagnosticsView d={diag} /> : <p className="muted">No recommendations for this evaluation.</p>}
    </Section>
    <Section id="dim-success" n="Dimension 1" title="Task success" basis="Every answer is checked against the site’s own records, which the agent never sees. Correct: the answer is right (consistent extra detail allowed). Exact match: the answer matches the expected answer exactly (the official grader).">
      <Success ev={ev} vs={vs} /></Section>
    <Section id="dim-nav" n="Dimension 2" title="Navigation efficiency" basis={ev.dimensions.navigation_efficiency.basis}><Navigation ev={ev} vs={vs} /></Section>
    <Section id="dim-evidence" n="Dimension 3" title="Evidence" basis="Whether the agent was actually shown the pages that hold the answer, rather than guessing."><Evidence ev={ev} vs={vs} /></Section>
    <Section id="dim-access" n="Dimension 4" title="Information accessibility" basis={ev.dimensions.information_accessibility.basis}><Access ev={ev} vs={vs} /></Section>
    <Section id="dim-reliability" n="Dimension 5" title="Agent reliability" basis={ev.dimensions.agent_reliability.basis}><Reliability ev={ev} vs={vs} /></Section>
    <Section id="dim-coverage" n="Dimension 6" title="Coverage" basis="Which customers and journeys the task set covers. The customer profiles are illustrative, written for this fictional college."><Coverage ev={ev} /></Section>
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
        <th scope="row"><span className="lc-tn">Task {t.n}</span><q>{t.customer_wording}</q><small>{words(t.capability)}{t.persona ? ` · ${words(t.persona)}` : ''}</small></th>
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
      <tr><th scope="row">Exact match (official grader)</th>{vs.map(v => <td key={v}>{ts[v].v1_passed}/{ts[v].trials}</td>)}</tr>
    </tbody></table></div>
    <p className="lc-note">An answer such as “Beginners yoga – $150, 12 seats left” is correct but not an exact match: the official grader accepts only the bare course names.</p>
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
    <tr><th scope="row">Correct without having seen the pages the answer needs (recorded rule)</th>{vs.map(v => <td key={v}>{e.variants[v].correct_but_unsupported_v2}</td>)}</tr>
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

function Coverage({ ev }: { ev: Evaluation }) {
  const c = ev.dimensions.coverage;
  const personaName = (id: string) => c.context?.personas.find(p => p.id === id)?.name ?? words(id);
  const journeyName = (id: string) => c.context?.journeys.find(j => j.id === id)?.name ?? words(id);
  return <>
    <div className="lc-three">
      <div><h3>Customers</h3><ul className="lc-counts">{Object.entries(c.personas ?? {}).map(([k, n]) => <li key={k}><span>{personaName(k)}</span><b>{n}</b></li>)}</ul></div>
      <div><h3>Journeys</h3><ul className="lc-counts">{Object.entries(c.journeys ?? {}).map(([k, n]) => <li key={k} className={n ? '' : 'gap'}><span>{journeyName(k)}</span><b>{n}</b></li>)}</ul></div>
      <div><h3>Kinds of question</h3><ul className="lc-counts">{Object.entries(c.capabilities ?? {}).map(([k, n]) => <li key={k} className={n ? '' : 'gap'}><span>{words(k)}</span><b>{n}</b></li>)}</ul></div>
    </div>
    {c.gaps.length > 0 && <p className="lc-gaps"><strong>Not covered by this task set:</strong> {c.gaps.join('; ')}.</p>}
  </>;
}

export function FindingCard({ f }: { f: Finding }) {
  return <li className={`lc-finding ${f.basis}`}>
    <div className="lc-finding-head"><span className={`lc-sev ${f.severity}`}>{f.severity}</span>{f.variant && <VariantName v={f.variant} />}{f.tasks.length > 0 && <span className="muted">task {f.tasks.join(', ')}</span>}</div>
    <p className="lc-finding-t">{plain(f.title)}</p>
    <p className="lc-finding-i">{plain(f.impact)}</p>
    <p className="lc-finding-r"><b>Recommendation.</b> {plain(f.recommendation)}</p>
    <details><summary>Evidence ({f.evidence.length})</summary>
      <ul className="lc-ev">{f.evidence.map((e, i) => <li key={i}><code>{e.type}</code> {plain(e.ref)}{e.detail ? ` — ${plain(e.detail)}` : ''}</li>)}</ul>
      <p className="muted"><b>How to check the fix.</b> {plain(f.verify)}</p></details>
  </li>;
}

function DiagnosticsView({ d }: { d: NonNullable<Evaluation['diagnostics'][string]> }) {
  const [layer, setLayer] = useState<'all' | 'structural' | 'behavioral'>('all');
  if (!d.available) return <p className="muted">Recommendations unavailable: {d.reason}</p>;
  const fs = (d.findings ?? []).filter(f => !f.title.startsWith('v1 format'));   // grading-format notes, not website findings
  const obs = fs.filter(f => f.basis === 'observed' && (layer === 'all' || f.layer === layer));
  const hyp = fs.filter(f => f.basis === 'hypothesis');
  return <>
    <p className="lc-note">{obs.length} observations, {hyp.length} likely causes
      {Object.entries(d.structural_changes ?? {}).map(([k, c]) => <span key={k}> · the {words(k)} version fixed {c.resolved} of the page problems found on the first version{c.introduced ? ` and introduced ${c.introduced}` : ''}</span>)}.</p>
    <div className="lc-diag">
      <div><h3>Likely causes and what to change</h3><ul className="lc-findings">{hyp.map(f => <FindingCard key={f.id + f.variant} f={f} />)}</ul></div>
      <div><h3>Observations</h3>
        <div className="lc-seg" role="group" aria-label="Filter observations">{(['all', 'structural', 'behavioral'] as const).map(x => <button key={x} type="button" aria-pressed={layer === x} onClick={() => setLayer(x)}>{x === 'all' ? 'All' : x === 'structural' ? 'Page structure' : 'Agent behaviour'}</button>)}</div>
        <ul className="lc-findings">{obs.map(f => <FindingCard key={f.id + f.variant} f={f} />)}</ul></div>
    </div>
  </>;
}

function Provenance({ ev }: { ev: Evaluation }) {
  const ex = Object.values(ev.execution)[0];
  return <Section id="provenance" n="Provenance" title="Where these numbers come from">
    <ul className="lc-prov">
      {ev.source?.kind === 'dataset' && <li>Recorded evaluation <code>{ev.source.id}</code> (built {ev.source.built_at}): {ev.source.description}</li>}
      <li>Execution: {ex?.executed}/{ex?.planned ?? '–'} agent runs finished{ex?.stopped ? `, stopped: ${ex.stopped}` : ''}; browser isolation self-test {ex?.jail_selftest_ok ? 'passed' : 'not recorded'}{ev.mode === 'paid' ? `; spending authorised in advance ${ex?.authorization_verified ? 'for exactly this task set and configuration' : '(not recorded)'}` : ''}.</li>
      <li>Agent: {ev.agent.model}, reasoning {ev.agent.reasoning_effort ?? '–'}, {ev.agent.max_completion_tokens} completion tokens, profile {ev.agent.profile}; manifest <Hash sha={ev.manifest.sha256} /> · {ev.manifest.repetitions} repetition · seed {ev.manifest.seed}.</li>
      <li>Task set: {ev.suite.name} v{ev.suite.version}, frozen <Hash sha={ev.frozen_suite.sha256} />, approved {new Date(ev.approval.decided_at).toUTCString().slice(5, 22)} UTC <Hash sha={ev.approval.sha256} />.</li>
      <li>Website versions: {ev.manifest.variants.map(v => <span key={v.name} className="lc-inline"><VariantName v={v.name} /> <Hash sha={v.snapshot_sha256} /></span>)}</li>
      <li>Privacy: expected answers and grading criteria stay on the server; this page shows the agents’ own answers and counts.</li>
    </ul>
  </Section>;
}
