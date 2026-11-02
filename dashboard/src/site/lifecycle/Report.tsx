import { useState } from 'react';
import { SiteFooter, SiteHeader } from '../Shell';
import { api, fmtSec, fmtUsd, variantClass, words, type Evaluation, type Finding, type Trial } from '../../lib/lifecycleApi';
import { Failed, GradeTag, Hash, Loading, ModeBadge, PairBars, Section, useLoad, VariantName } from './parts';
import { TraceCompare } from './Trace';
import './lifecycle.css';

/** `#/reports/<id>` and `#/reports/<id>/tasks/<n>`: one readiness report for any evaluation (the preloaded M7 dataset and evaluations launched in the
 *  product share this page, because the server projects both into the same document). */
export function ReportPage({ id, task }: { id: string; task?: number }) {
  const ev = useLoad(() => api.evaluation(id), id);
  return <div className="ar lc">
    <a className="ar-skip" href="#lc-main" onClick={e => { e.preventDefault(); document.getElementById('lc-main')?.focus(); }}>Skip to content</a>
    <SiteHeader active="lifecycle" cta={false} />
    <main id="lc-main" tabIndex={-1} className="wrap lc-wrap">
      <nav className="lc-crumbs" aria-label="Breadcrumb"><a href="#/lifecycle">Lifecycle</a><span aria-hidden="true">/</span><a href="#/lifecycle/report">Reports</a>
        {task != null && <><span aria-hidden="true">/</span><a href={`#/reports/${id}`}>{ev.data?.title ?? id}</a></>}</nav>
      {ev.loading && <Loading what="the evaluation" />}
      {ev.error && <Failed error={ev.error} what="This evaluation" />}
      {ev.data && (task != null ? <TraceCompare ev={ev.data} n={task} /> : <Report ev={ev.data} />)}
    </main>
    <SiteFooter />
  </div>;
}

const variantsOf = (ev: Evaluation) => ev.manifest.variants.map(v => v.name);
const trialsFor = (ev: Evaluation, n: number) => ev.trials.filter(t => t.task === n);

export function Report({ ev }: { ev: Evaluation }) {
  const vs = variantsOf(ev);
  const diag = Object.values(ev.diagnostics)[0];
  return <article className="lc-report">
    <header className="lc-report-head">
      <p className="eyebrow">Readiness report · {ev.site.label}</p>
      <h1 className="lc-title">{ev.title}</h1>
      <div className="lc-badges"><ModeBadge mode={ev.mode} />{ev.exploratory && <span className="lc-mode neutral">Exploratory · no claim</span>}
        {ev.source?.kind === 'dataset' && <span className="lc-mode neutral">Preloaded from sanitized dataset v{ev.source.version}</span>}
        {ev.source?.kind === 'launched' && <span className="lc-mode neutral">Launched in the product</span>}</div>
      {ev.notice && <p className="lc-notice" role="note">{ev.notice}</p>}
      {ev.caveat && <p className="lc-caveat" role="note"><strong>Read this first.</strong> {ev.caveat} Official grades are grader v1 as recorded; grader v2 is a labelled post-hoc rescore; rules marked prospective are shown, never applied.</p>}
      <dl className="lc-facts">
        <div><dt>Frozen suite</dt><dd>{ev.suite.name} v{ev.suite.version} · <Hash sha={ev.frozen_suite.sha256} /></dd></div>
        <div><dt>Approval</dt><dd>{ev.approval.decision} by the {ev.approval.role}{ev.approval.synthetic ? ' (SYNTHETIC fixture)' : ''}, {new Date(ev.approval.decided_at).toUTCString().slice(5, 22)} UTC · <Hash sha={ev.approval.sha256} /></dd></div>
        <div><dt>Manifest</dt><dd><Hash sha={ev.manifest.sha256} /> · {ev.manifest.repetitions} repetition · seed {ev.manifest.seed} · plan {ev.manifest.plan}</dd></div>
        <div><dt>Agent</dt><dd>{ev.mode === 'paid' ? 'Real model' : ev.execution_provider} · {ev.agent.model}, reasoning {ev.agent.reasoning_effort ?? '–'}, {ev.agent.max_completion_tokens} completion tokens · profile {ev.agent.profile}{ev.mode !== 'paid' ? ' (declared by the manifest; not called)' : ''}</dd></div>
        <div><dt>Website variants</dt><dd>{ev.manifest.variants.map(v => <span key={v.name} className="lc-inline"><VariantName v={v.name} /> <Hash sha={v.snapshot_sha256} /></span>)}</dd></div>
        <div><dt>Spend</dt><dd>{ev.mode === 'paid' ? <>{fmtUsd(ev.cost.settled_spend?.settled_usd ?? ev.cost.total_usd, 6)} calculated{ev.cost.settled_spend ? ` · ${ev.cost.settled_spend.settled_requests} requests settled, ${ev.cost.settled_spend.unsettled_requests} unsettled` : ''} · cap {fmtUsd(ev.manifest.budget.hard_cap_usd, 2)} · not a bill</> : 'US$0 · no model was called'}</dd></div>
      </dl>
    </header>

    <Glance ev={ev} vs={vs} />
    <TaskMatrix ev={ev} vs={vs} />

    <Section id="dim-success" n="Dimension 1" title="Task success" basis={ev.dimensions.task_success.basis}><Success ev={ev} vs={vs} /></Section>
    <Section id="dim-nav" n="Dimension 2" title="Navigation efficiency" basis={ev.dimensions.navigation_efficiency.basis}><Navigation ev={ev} vs={vs} /></Section>
    <Section id="dim-evidence" n="Dimension 3" title="Evidence quality" basis={ev.dimensions.evidence_quality.basis}><Evidence ev={ev} vs={vs} /></Section>
    <Section id="dim-access" n="Dimension 4" title="Information accessibility" basis={ev.dimensions.information_accessibility.basis}><Access ev={ev} vs={vs} /></Section>
    <Section id="dim-reliability" n="Dimension 5" title="Agent reliability" basis={ev.dimensions.agent_reliability.basis}><Reliability ev={ev} vs={vs} /></Section>
    <Section id="dim-coverage" n="Dimension 6" title="Coverage" basis={ev.dimensions.coverage.basis}><Coverage ev={ev} /></Section>
    <Section id="diagnostics" n="Diagnostics" title="What the evidence shows, and what it only suggests"
             basis="Observed facts are measured page properties or recorded agent behaviour. Hypotheses link a page property to behaviour on tasks that depend on it; they stay hypotheses unless a pre-registered comparison establishes them.">
      {diag ? <DiagnosticsView d={diag} /> : <p className="muted">No diagnostics.</p>}
    </Section>
    <Provenance ev={ev} />
  </article>;
}

function Glance({ ev, vs }: { ev: Evaluation; vs: string[] }) {
  const ts = ev.dimensions.task_success.variants, nav = ev.dimensions.navigation_efficiency.variants;
  return <section className="lc-glance" aria-label="At a glance">
    {vs.map(v => <article key={v} className={`lc-glance-card ${variantClass(v)}`}>
      <h3><VariantName v={v} /></h3>
      <dl>
        <div><dt>Passed · official v1</dt><dd className="big">{ts[v].v1_passed}/{ts[v].trials}</dd></div>
        <div><dt>Passed · v2 post-hoc</dt><dd className="big">{ts[v].v2_passed}/{ts[v].trials}</dd></div>
        <div><dt>Model requests</dt><dd>{nav[v].model_requests_total ?? '–'}</dd></div>
        <div><dt>Agent time</dt><dd>{fmtSec(nav[v].elapsed_seconds_total)}</dd></div>
        {ev.mode === 'paid' && <div><dt>Calculated cost</dt><dd>{fmtUsd(nav[v].cost_usd_total)}</dd></div>}
      </dl>
    </article>)}
    <p className="lc-glance-note">Counts of completed trials; there is no composite readiness score, because no scoring method has been validated. {ev.exploratory ? 'Exploratory: the differences describe these runs only.' : ''}</p>
  </section>;
}

function cover(t?: Trial) {
  const c = t?.answer_coverage;
  if (!c) return null;
  return c.expected_items > 1 ? `named ${c.named_expected} of ${c.expected_items}${c.named_other ? ` + ${c.named_other} other` : ''}` : c.named_other ? `correct + ${c.named_other} other named` : c.named_expected ? 'names the expected item' : 'expected item not named';
}

function TaskMatrix({ ev, vs }: { ev: Evaluation; vs: string[] }) {
  return <Section id="tasks" n="Tasks" title="Every frozen task, on every website variant"
                  basis="The customer's own wording, executed unchanged (natural condition). Each cell is one recorded browser-agent trial; open a task to compare the traces side by side.">
    <div className="lc-table-wrap"><table className="lc-matrix">
      <thead><tr><th scope="col">Task</th>{vs.map(v => <th scope="col" key={v}><VariantName v={v} /></th>)}<th scope="col"><span className="sr-only">Compare</span></th></tr></thead>
      <tbody>{ev.tasks.filter(t => t.executed).map(t => { const ts = trialsFor(ev, t.n); return <tr key={t.n}>
        <th scope="row"><span className="lc-tn">Task {t.n}</span><q>{t.customer_wording}</q><small>{words(t.capability)} · {t.kind}{t.persona ? ` · ${words(t.persona)}` : ''}</small></th>
        {vs.map(v => { const tr = ts.find(x => x.variant === v); return <td key={v} className={`lc-cell ${variantClass(v)}`}>{tr ? <>
          <div className="lc-grades"><GradeTag g={tr.grades.v1} which="v1" /><GradeTag g={tr.grades.v2} which="v2" />{tr.grades.v2_1_contrast && <GradeTag g={tr.grades.v2_1_contrast} which="v2.1" />}</div>
          <small>{[cover(tr), `${tr.metrics.model_requests ?? '–'} requests`, fmtSec(tr.metrics.elapsed_seconds), tr.reliability.dead_end ? 'dead end' : null, tr.reliability.empty_answer ? 'empty answer' : null].filter(Boolean).join(' · ')}</small>
        </> : <small>not run</small>}</td>; })}
        <td><a className="btn btn-sm btn-ghost" href={`#/reports/${ev.id}/tasks/${t.n}`} aria-label={`Compare traces for task ${t.n}`}>Compare traces <span className="arr" aria-hidden="true">→</span></a></td>
      </tr>; })}</tbody>
    </table></div>
  </Section>;
}

function Success({ ev, vs }: { ev: Evaluation; vs: string[] }) {
  const ts = ev.dimensions.task_success.variants;
  const an = Object.values(ev.analysis)[0];
  return <>
    <div className="lc-table-wrap"><table className="lc-table"><thead><tr><th scope="col">Grader</th>{vs.map(v => <th scope="col" key={v}><VariantName v={v} /></th>)}</tr></thead><tbody>
      <tr><th scope="row">Official grader v1 · passed (evidence-supported)</th>{vs.map(v => <td key={v}>{ts[v].v1_passed}/{ts[v].trials} ({ts[v].v1_evidence_backed})</td>)}</tr>
      <tr><th scope="row">Grader v2, post-hoc rescore · passed (evidence-supported)</th>{vs.map(v => <td key={v}>{ts[v].v2_passed}/{ts[v].trials} ({ts[v].v2_evidence_backed})</td>)}</tr>
      <tr><th scope="row">v2.1 contrast review rule · prospective, not applied</th>{vs.map(v => <td key={v}>{ts[v].v2_1_contrast_review_passes} answer(s) a reviewer would accept</td>)}</tr>
    </tbody></table></div>
    {an && <div className="lc-analysis"><p><strong>{an.label}.</strong> {an.outcome}. Exact sign-flip test over {an.official_v1.pairs} task pairs: official v1 mean difference {an.official_v1.mean_difference ?? '–'} (p = {an.official_v1.p_value ?? '–'}); post-hoc v2 mean difference {an.post_hoc_v2.mean_difference ?? '–'} (p = {an.post_hoc_v2.p_value ?? '–'}).</p>
      <p className="muted">Per task (Modified − Original), v1 / v2: {an.official_v1.per_task.map((x, i) => <span key={x.task} className="lc-inline">task {x.task}: {x.difference > 0 ? '+' : ''}{x.difference} / {(an.post_hoc_v2.per_task[i]?.difference ?? 0) > 0 ? '+' : ''}{an.post_hoc_v2.per_task[i]?.difference ?? '–'}</span>)}</p></div>}
    <p className="lc-note">Why two graders: v1 accepts only the bare expected names (a correct answer with its fee and seats attached fails); v2 accepts consistent supporting detail and rejects hedges and contradictions. v1 stays the grade of record.</p>
  </>;
}

function Navigation({ ev, vs }: { ev: Evaluation; vs: string[] }) {
  const nav = ev.dimensions.navigation_efficiency.variants;
  const rows = ev.tasks.filter(t => t.executed).map(t => ({ key: String(t.n), label: `Task ${t.n}`, values: Object.fromEntries(vs.map(v => [v, trialsFor(ev, t.n).find(x => x.variant === v)?.metrics.model_requests ?? null])) }));
  const time = ev.tasks.filter(t => t.executed).map(t => ({ key: String(t.n), label: `Task ${t.n}`, values: Object.fromEntries(vs.map(v => [v, trialsFor(ev, t.n).find(x => x.variant === v)?.metrics.elapsed_seconds ?? null])) }));
  return <>
    <div className="lc-table-wrap"><table className="lc-table"><thead><tr><th scope="col">Per trial</th>{vs.map(v => <th scope="col" key={v}><VariantName v={v} /></th>)}</tr></thead><tbody>
      {([['Model requests, mean (total)', (v: string) => `${nav[v].model_requests_mean ?? '–'} (${nav[v].model_requests_total ?? '–'})`], ['Agent steps, mean', (v: string) => nav[v].steps_mean ?? '–'],
         ['Page views, mean', (v: string) => nav[v].page_views_mean ?? '–'], ['Time, mean (total)', (v: string) => `${fmtSec(nav[v].elapsed_seconds_mean)} (${fmtSec(nav[v].elapsed_seconds_total)})`],
         ['Revisits, total', (v: string) => nav[v].revisits_total ?? '–'], ['Item pages opened, mean', (v: string) => nav[v].item_pages_opened_mean ?? '–']] as const)
        .map(([k, f]) => <tr key={k}><th scope="row">{k}</th>{vs.map(v => <td key={v}>{f(v)}</td>)}</tr>)}
    </tbody></table></div>
    <div className="lc-two"><PairBars rows={rows} variants={vs} unit="req" label="Model requests per task" /><PairBars rows={time} variants={vs} unit="s" label="Agent time per task (seconds)" /></div>
  </>;
}

function Evidence({ ev, vs }: { ev: Evaluation; vs: string[] }) {
  const e = ev.dimensions.evidence_quality;
  const r2 = vs.flatMap(v => e.variants[v].ranked_subset_rule_2.map(x => ({ ...x, v })));
  return <>
    <div className="lc-table-wrap"><table className="lc-table"><thead><tr><th scope="col">Recorded evidence rule</th>{vs.map(v => <th scope="col" key={v}><VariantName v={v} /></th>)}</tr></thead><tbody>
      <tr><th scope="row">Trials whose answer pages were shown to the agent</th>{vs.map(v => <td key={v}>{e.variants[v].evidence_satisfied}/{e.variants[v].trials}</td>)}</tr>
      <tr><th scope="row">Correct under v2 but answer pages not shown</th>{vs.map(v => <td key={v}>{e.variants[v].correct_but_unsupported_v2}</td>)}</tr>
      <tr><th scope="row">Required pages not shown (total)</th>{vs.map(v => <td key={v}>{e.variants[v].missing_pages_total}</td>)}</tr>
    </tbody></table></div>
    {r2.length > 0 && <div className="lc-prospective"><p><strong>Prospective rule <code>{e.prospective_rule.id}</code>.</strong> {e.prospective_rule.status}. For a ranking within a filter, every filtered candidate's decisive facts must have been shown, not only the winner's.</p>
      <ul>{r2.map(x => <li key={`${x.v}-${x.task}`}><VariantName v={x.v} /> task {x.task}: {x.shown_pages} of {x.required_pages} required pages shown · {x.satisfied ? <span className="tag tag-pass">✓ comparison evidenced</span> : <span className="tag tag-fail">✕ comparison not evidenced</span>}</li>)}</ul></div>}
  </>;
}

function Access({ ev, vs }: { ev: Evaluation; vs: string[] }) {
  const a = ev.dimensions.information_accessibility;
  const facts = [...new Set(vs.flatMap(v => Object.keys(a.facts[v] ?? {})))].sort();
  return <>
    <div className="lc-table-wrap"><table className="lc-table"><thead><tr><th scope="col">Fact</th>{vs.map(v => <th scope="col" key={v}><VariantName v={v} /> · on listing cards</th>)}</tr></thead><tbody>
      {facts.map(f => <tr key={f}><th scope="row">{f}</th>{vs.map(v => { const x = a.facts[v]?.[f]; return <td key={v}>{x ? <><b>{x.on_listing_cards}/{x.items}</b> cards · {x.on_item_pages}/{x.items} item pages</> : '–'}</td>; })}</tr>)}
    </tbody></table></div>
    <div className="lc-table-wrap"><table className="lc-table"><thead><tr><th scope="col">Task needs</th>{vs.map(v => <th scope="col" key={v}><VariantName v={v} /></th>)}</tr></thead><tbody>
      {a.tasks.map(t => <tr key={t.task}><th scope="row">Task {t.task}: {t.facts.join(', ')}</th>{vs.map(v => <td key={v}>{t.facts.map(f => <span key={f} className={`lc-place ${t.placement[v]?.[f] === 'listing cards' ? 'ok' : 'deep'}`}>{f}: {t.placement[v]?.[f]}</span>)}
        {t.min_link_steps?.[v] != null && <small> · answer ≥ {t.min_link_steps[v]} link step(s) from the start page</small>}</td>)}</tr>)}
    </tbody></table></div>
  </>;
}

function Reliability({ ev, vs }: { ev: Evaluation; vs: string[] }) {
  const r = ev.dimensions.agent_reliability.variants;
  const rows: [string, (v: string) => number | null][] = [['Dead ends (HTTP errors, failed actions)', v => r[v].dead_ends], ['…recovered, still answered', v => r[v].recovered_after_dead_end],
    ['Partial answers (some expected items missing)', v => r[v].partial_answers], ['Empty answers', v => r[v].empty_answers], ['At or within one request of the limit', v => r[v].near_request_limit],
    ['Stopped by a limit', v => r[v].limit_stops], ['Void trials', v => r[v].void], ['Model replies recovered by the protocol parser', v => r[v].protocol_recoveries]];
  return <div className="lc-table-wrap"><table className="lc-table"><thead><tr><th scope="col">Trials</th>{vs.map(v => <th scope="col" key={v}><VariantName v={v} /></th>)}</tr></thead>
    <tbody>{rows.map(([k, f]) => <tr key={k}><th scope="row">{k}</th>{vs.map(v => <td key={v}>{f(v) ?? '–'}</td>)}</tr>)}</tbody></table></div>;
}

function Coverage({ ev }: { ev: Evaluation }) {
  const c = ev.dimensions.coverage;
  const personaName = (id: string) => c.context?.personas.find(p => p.id === id)?.name ?? words(id);
  const journeyName = (id: string) => c.context?.journeys.find(j => j.id === id)?.name ?? words(id);
  return <>
    {c.context && <p className="lc-note">{c.context.label}</p>}
    <div className="lc-three">
      <div><h3>Personas</h3><ul className="lc-counts">{Object.entries(c.personas ?? {}).map(([k, n]) => <li key={k}><span>{personaName(k)}</span><b>{n}</b></li>)}</ul></div>
      <div><h3>Journeys</h3><ul className="lc-counts">{Object.entries(c.journeys ?? {}).map(([k, n]) => <li key={k} className={n ? '' : 'gap'}><span>{journeyName(k)}</span><b>{n}</b></li>)}</ul></div>
      <div><h3>Capabilities</h3><ul className="lc-counts">{Object.entries(c.capabilities ?? {}).map(([k, n]) => <li key={k} className={n ? '' : 'gap'}><span>{words(k)}</span><b>{n}</b></li>)}</ul></div>
    </div>
    {c.status && <ul className="lc-targets">{Object.entries(c.status).map(([k, s]) => <li key={k} className={s.met ? 'met' : 'unmet'}><span aria-hidden="true">{s.met ? '✓' : '!'}</span> {words(k)}: target {s.target} — {s.met ? 'met' : 'not met'}</li>)}</ul>}
    {c.gaps.length > 0 && <p className="lc-gaps"><strong>Gaps, as frozen (targets were never lowered):</strong> {c.gaps.join('; ')}.</p>}
  </>;
}

export function FindingCard({ f }: { f: Finding }) {
  return <li className={`lc-finding ${f.basis}`}>
    <div className="lc-finding-head"><span className={`lc-sev ${f.severity}`}>{f.severity}</span><span className="lc-status">{words(f.status)}</span>{f.variant && <VariantName v={f.variant} />}{f.tasks.length > 0 && <span className="muted">task {f.tasks.join(', ')}</span>}</div>
    <p className="lc-finding-t">{f.title}</p>
    <p className="lc-finding-i">{f.impact}</p>
    {(f.detail as { status_basis?: string }).status_basis && <p className="lc-finding-b"><b>Status basis.</b> {(f.detail as { status_basis?: string }).status_basis}</p>}
    <details><summary>Evidence ({f.evidence.length}) and recommendation</summary>
      <ul className="lc-ev">{f.evidence.map((e, i) => <li key={i}><code>{e.type}</code> {e.ref}{e.detail ? ` — ${e.detail}` : ''}</li>)}</ul>
      <p><b>Recommendation.</b> {f.recommendation}</p><p className="muted"><b>How to verify.</b> {f.verify}</p></details>
  </li>;
}

function DiagnosticsView({ d }: { d: NonNullable<Evaluation['diagnostics'][string]> }) {
  const [layer, setLayer] = useState<'all' | 'structural' | 'behavioral'>('all');
  if (!d.available) return <p className="muted">Diagnostics unavailable: {d.reason}</p>;
  const obs = (d.findings ?? []).filter(f => f.basis === 'observed' && (layer === 'all' || f.layer === layer));
  const hyp = (d.findings ?? []).filter(f => f.basis === 'hypothesis');
  return <>
    <p className="lc-note">{d.summary?.observed} observed facts, {d.summary?.hypotheses} hypotheses · behaviour origin: {d.evidence_origin === 'real_model' ? 'real model' : 'scripted stand-in (cannot support a hypothesis about agents)'} · rules {Object.values(d.rules ?? {}).join(', ')}
      {Object.entries(d.structural_changes ?? {}).map(([k, c]) => <span key={k}> · the {k} variant resolved {c.resolved} structural finding(s)</span>)}</p>
    <div className="lc-diag">
      <div><h3>Hypotheses <small>(suspected contributors; untested unless stated)</small></h3><ul className="lc-findings">{hyp.map(f => <FindingCard key={f.id + f.variant} f={f} />)}</ul></div>
      <div><h3>Observed facts</h3>
        <div className="lc-seg" role="group" aria-label="Filter observed facts">{(['all', 'structural', 'behavioral'] as const).map(x => <button key={x} type="button" aria-pressed={layer === x} onClick={() => setLayer(x)}>{x === 'all' ? 'All' : x === 'structural' ? 'Page structure' : 'Agent behaviour'}</button>)}</div>
        <ul className="lc-findings">{obs.map(f => <FindingCard key={f.id + f.variant} f={f} />)}</ul></div>
    </div>
  </>;
}

function Provenance({ ev }: { ev: Evaluation }) {
  const ex = Object.values(ev.execution)[0];
  return <Section id="provenance" n="Provenance" title="Where these numbers come from">
    <ul className="lc-prov">
      {ev.source?.kind === 'dataset' && <li>Preloaded from dataset <code>{ev.source.id}</code> v{ev.source.version} (built {ev.source.built_at}): {ev.source.description} Runs: {ev.source.runs?.join(', ')}.</li>}
      <li>Execution: {ex?.executed}/{ex?.planned ?? '–'} trials, {ex?.stopped ? `stopped: ${ex.stopped}` : 'no halt'}; browser jail self-test {ex?.jail_selftest_ok ? 'passed' : 'not recorded'}{ev.mode === 'paid' ? `; paid authorisation ${ex?.authorization_verified ? 'verified against the exact frozen suite and manifest' : 'not recorded'}` : ''}.</li>
      <li>Graders: {ev.graders.official}; {ev.graders.post_hoc}; prospective: {ev.graders.prospective.map(p => p.id).join(', ')} (never applied).</li>
      <li>Privacy: expected answers, criteria and required evidence pages stay on the server; this page shows the agent's own answers and counts derived from the oracle.</li>
      <li>Suite hash <Hash sha={ev.suite.sha256} /> · prepared by {ev.suite.created_by}.</li>
    </ul>
  </Section>;
}
