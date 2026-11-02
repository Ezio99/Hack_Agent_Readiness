import { useEffect, useState } from 'react';
import { SiteFooter, SiteHeader } from '../Shell';
import { api, fmtUsd, short, words, type EvaluationSummary, type Generation, type Overview, type Site, type Suite } from '../../lib/lifecycleApi';
import { Disabled, Failed, Hash, Loading, ModeBadge, useLoad, VariantName } from './parts';
import './lifecycle.css';

const STEPS = [
  { id: 'website', n: '01', label: 'Website', blurb: 'Business context and customer personas' },
  { id: 'tasks', n: '02', label: 'Tasks', blurb: 'AI generation and independent validation' },
  { id: 'review', n: '03', label: 'Review', blurb: 'Human approval of a frozen suite' },
  { id: 'evaluate', n: '04', label: 'Evaluate', blurb: 'Real browser agent, jailed' },
  { id: 'report', n: '05', label: 'Report', blurb: 'Six dimensions with evidence' },
  { id: 'reevaluate', n: '06', label: 'Re-evaluate', blurb: 'Same frozen suite, new website' },
] as const;

/** `#/lifecycle[/<step>]`: the evaluation lifecycle as one workflow. Every step reads the server; actions that are not safely available are shown
 *  disabled with the server's reason, never simulated. */
export function Lifecycle({ step, suite }: { step?: string; suite?: string }) {
  const ov = useLoad(() => api.overview(), 'overview');
  const sites = useLoad(() => api.sites(), 'sites');
  const [siteId, setSiteId] = useState('larkspur');
  const current = step ?? 'website';
  useEffect(() => { if (step) document.getElementById('lc-panel')?.scrollIntoView?.({ block: 'start' }); }, [step]);
  const site = sites.data?.find(s => s.id === siteId) ?? null;
  return <div className="ar lc">
    <a className="ar-skip" href="#lc-main" onClick={e => { e.preventDefault(); document.getElementById('lc-main')?.focus(); }}>Skip to content</a>
    <SiteHeader active="lifecycle" cta={false} />
    <main id="lc-main" tabIndex={-1} className="wrap lc-wrap">
      <header className="lc-intro">
        <p className="eyebrow">Evaluation lifecycle</p>
        <h1 className="lc-title">From a website to <em>verified</em> agent readiness.</h1>
        <p className="lede">Describe the business and its customers, let AI propose tasks that a validator checks against the site's own records, approve and
          freeze a suite, run a real browser agent against it, read the evidence, then re-evaluate the same frozen suite after you change the website.</p>
      </header>
      <nav className="lc-stepper" aria-label="Lifecycle steps"><ol>{STEPS.map(s => { const info = ov.data?.steps.find(x => x.id === s.id);
        return <li key={s.id}><a href={`#/lifecycle/${s.id}`} aria-current={current === s.id ? 'step' : undefined}>
          <span className="lc-step-n">{s.n}</span><strong>{s.label}</strong><small>{s.blurb}</small>
          {info && info.action_available === false && <span className="lc-step-state">view only</span>}</a></li>; })}</ol></nav>
      {ov.error && <Failed error={ov.error} what="The lifecycle service" />}
      <div id="lc-panel" className="lc-panel">
        {current === 'website' && <WebsitePanel sites={sites.data} error={sites.error} siteId={siteId} setSiteId={setSiteId} ov={ov.data} />}
        {current === 'tasks' && <TasksPanel site={site} />}
        {current === 'review' && <ReviewPanel site={site} selected={suite} ov={ov.data} />}
        {current === 'evaluate' && <EvaluatePanel ov={ov.data} />}
        {current === 'report' && <ReportsPanel />}
        {current === 'reevaluate' && <ReevaluatePanel ov={ov.data} />}
      </div>
      <nav className="lc-next" aria-label="Next step">{(() => { const i = STEPS.findIndex(s => s.id === current); const nx = STEPS[i + 1];
        return nx ? <a className="btn btn-ghost" href={`#/lifecycle/${nx.id}`}>Next: {nx.label} <span className="arr" aria-hidden="true">→</span></a> : null; })()}</nav>
    </main>
    <SiteFooter />
  </div>;
}

// --------------------------------------------------------------------------------------------------------------- 1 website
function WebsitePanel({ sites, error, siteId, setSiteId, ov }: { sites: Site[] | null; error: string | null; siteId: string; setSiteId: (s: string) => void; ov: Overview | null }) {
  if (error) return <Failed error={error} what="Website contexts" />;
  if (!sites) return <Loading what="website contexts" />;
  const s = sites.find(x => x.id === siteId) ?? sites[0];
  return <section aria-labelledby="w-h">
    <h2 id="w-h" className="lc-h2">1 · Website onboarding</h2>
    <div className="lc-sites" role="radiogroup" aria-label="Website">{sites.map(x => <button key={x.id} type="button" role="radio" aria-checked={x.id === s.id} onClick={() => setSiteId(x.id)}>
      <strong>{x.label}</strong><small>{x.domain} · {x.variants.length} variants · oracle from the site's own records</small></button>)}</div>
    {ov && !ov.onboarding.available && <Disabled title="Add a website from a URL — not available" detail={ov.onboarding.detail} />}
    {s.context ? <div className="lc-context">
      <p className="lc-label" role="note">{s.context.label}</p>
      <p className="lc-business">{s.context.business}</p>
      <div className="lc-two">
        <div><h3>Business goals</h3><ul className="lc-list">{s.context.goals.map(g => <li key={g}>{g}</li>)}</ul></div>
        <div><h3>Customer journeys <small>(weights are illustrative priorities)</small></h3><ul className="lc-journeys">{s.context.journeys.map(j => <li key={j.id}>
          <span>{j.name}<small>{j.attributes.join(', ') || 'policy pages'}</small></span><span className="lc-weight" aria-label={`weight ${j.weight}`}><i style={{ width: `${j.weight * 100 / 0.3}%` }} />{j.weight.toFixed(2)}</span></li>)}</ul></div>
      </div>
      <h3>Customer personas</h3>
      <ul className="lc-personas">{s.context.personas.map(p => <li key={p.id}><strong>{p.name}</strong><p>{p.needs}</p><small>{p.constraints}</small></li>)}</ul>
    </div> : <p className="muted">No business context has been onboarded for this website.</p>}
    <h3>Website variants <small>(frozen, content-hashed snapshots; nothing is crawled on request)</small></h3>
    <ul className="lc-variants">{s.variants.map(v => <li key={v.name}><VariantName v={v.name} /><p>{v.description}</p>{v.snapshot_sha256 && <Hash sha={v.snapshot_sha256} label="snapshot" />}</li>)}</ul>
    {s.note && <p className="lc-note">{s.note} <a className="link" href="#/run">Open the workspace</a>.</p>}
  </section>;
}

// --------------------------------------------------------------------------------------------------------------- 2 tasks
function TasksPanel({ site }: { site: Site | null }) {
  const gens = useLoad(() => api.generations(), 'generations');
  const list = (gens.data ?? []).filter(g => !site || g.site === site.id);
  const [sel, setSel] = useState<string | null>(null);
  const id = sel ?? list[0]?.id ?? null;
  const g = useLoad(() => id ? api.generation(id) : Promise.resolve(null), `gen-${id}`);
  return <section aria-labelledby="t-h">
    <h2 id="t-h" className="lc-h2">2 · AI-assisted task generation and validation</h2>
    <p className="lede sm">A model proposes customer tasks in the customer's own words. An independent validator, with no model involved, checks every proposal against the site's
      source records: it must be grounded, answerable, unique, gradable on both website variants, and its wording must state every value it needs. It never sees agent results.</p>
    <Disabled title="Generate new tasks — needs owner authorisation" detail="A generation round is a paid model call. It is not launchable from the web in this release; recorded generation runs are shown below." />
    {gens.error && <Failed error={gens.error} what="Generation runs" />}
    {gens.data && !list.length && <p className="muted">No generation runs are recorded for {site?.label ?? 'this website'}.</p>}
    {list.length > 1 && <div className="lc-seg">{list.map(x => <button key={x.id} type="button" aria-pressed={x.id === id} onClick={() => setSel(x.id)}>{x.id}</button>)}</div>}
    {g.data && <GenerationView g={g.data} />}
  </section>;
}

function GenerationView({ g }: { g: Generation }) {
  const [filter, setFilter] = useState('all');
  const props = g.proposals.filter(p => filter === 'all' || p.admission === filter);
  return <div className="lc-gen">
    <dl className="lc-facts">
      <div><dt>Run</dt><dd><code>{g.id}</code> · {new Date(g.created_at).toUTCString().slice(5, 22)} UTC · <ModeBadge mode={g.mode} /></dd></div>
      <div><dt>Generator</dt><dd>{String(g.generator.model)} · reasoning {String(g.generator.reasoning_effort)} · prompt {String(g.generator.prompt_version)} · {String(g.generator.proposals_per_round)} per round, ≤ {String(g.generator.max_rounds)} rounds</dd></div>
      <div><dt>Stopped</dt><dd>{words(g.stop_reason)} after {g.rounds.filter(r => r.sent).length} rounds · {g.cost.requests} requests · {fmtUsd(g.cost.calculated_usd, 6)} calculated (cap {fmtUsd(g.limits.cap_usd, 2)})</dd></div>
      <div><dt>Outcome</dt><dd>{Object.entries(g.admissions).map(([k, n]) => `${n} ${words(k)}`).join(' · ')}{g.post_fix_reevaluation && <> — after a lexicon fix, re-evaluated offline at zero cost: {Object.entries(g.post_fix_reevaluation.admissions).map(([k, n]) => `${n} ${words(k)}`).join(' · ')}</>}</dd></div>
    </dl>
    <div className="lc-table-wrap"><table className="lc-table"><thead><tr><th scope="col">Round</th><th scope="col">Proposals</th><th scope="col">Admitted</th><th scope="col">Tokens (prompt / completion)</th><th scope="col">Latency</th><th scope="col">Cost</th><th scope="col">Gaps after</th></tr></thead>
      <tbody>{g.rounds.map(r => <tr key={r.round}><th scope="row">{r.round}</th><td>{r.candidates}</td><td>{Object.entries(r.admissions ?? {}).map(([k, n]) => `${n} ${words(k)}`).join(', ')}</td>
        <td>{r.prompt_tokens} / {r.completion_tokens}</td><td>{r.latency_seconds} s</td><td>{fmtUsd(r.cost_usd, 6)}</td><td>{r.gaps_after?.length ? r.gaps_after.join('; ') : r.targets_met ? 'targets met' : '–'}</td></tr>)}</tbody></table></div>
    {g.feedback.map(f => <p key={f.for_round} className="lc-note"><b>Feedback to round {f.for_round}</b> (no answers, by construction): gaps {f.coverage_gaps.join('; ') || 'none'}; missing capabilities {f.missing_capabilities.join(', ') || 'none'}; {f.avoid_signatures} signatures to avoid.</p>)}
    <div className="lc-seg" role="group" aria-label="Filter proposals">{['all', ...Object.keys(g.admissions)].map(k => <button key={k} type="button" aria-pressed={filter === k} onClick={() => setFilter(k)}>{k === 'all' ? `All ${g.proposals.length}` : `${words(k)} ${g.admissions[k]}`}</button>)}</div>
    <ul className="lc-proposals">{props.map(p => <li key={p.id} className={p.admission}>
      <div className="lc-prop-head"><span className={`tag ${p.admission === 'natural' ? 'tag-pass' : p.admission === 'rejected' ? 'tag-fail' : 'tag-neutral'}`}>{words(p.admission)}</span>
        <small>round {p.round} · {words(p.capability)} · {p.kind}{p.persona ? ` · ${words(p.persona)}` : ''}{p.journey ? ` · ${words(p.journey)}` : ''}</small></div>
      <q>{p.customer_wording ?? `[${p.withheld}]`}</q>
      {p.rejection_reasons.length > 0 && <p className="lc-reject">{p.rejection_reasons.join('; ')}</p>}
      {p.nl_traces.length > 0 && <details><summary>How the wording was traced to the specification</summary><ul>{p.nl_traces.map((t, i) => <li key={i}>{t.component}: {t.decision} <small>({t.status})</small></li>)}</ul></details>}
    </li>)}</ul>
    {g.gap_report && <p className="lc-note"><b>Gap report.</b> {g.gap_report.note}. Missing capabilities: {g.gap_report.missing_capabilities.join(', ') || 'none'}. Thresholds lowered: {g.gap_report.thresholds_lowered ? 'yes' : 'no'}.</p>}
    <p className="lc-note">This run produced suite proposal <Hash sha={g.suite_sha256} /> ({g.suite_name}); see <a className="link" href="#/lifecycle/review">Review</a> for what was approved and frozen.</p>
  </div>;
}

// --------------------------------------------------------------------------------------------------------------- 3 review
const STATE_TAG: Record<string, string> = { frozen: 'tag-signal', approved: 'tag-pass', rejected: 'tag-fail', proposed: 'tag-neutral' };

function ReviewPanel({ site, selected, ov }: { site: Site | null; selected?: string; ov: Overview | null }) {
  const suites = useLoad(() => api.suites(), 'suites');
  const list = (suites.data ?? []).filter(s => !site || s.site === site.id);
  const id = selected ?? list.find(s => s.state === 'frozen' && !s.synthetic)?.sha256 ?? list[0]?.sha256;
  const s = useLoad(() => id ? api.suite(id) : Promise.resolve(null), `suite-${id}`);
  return <section aria-labelledby="r-h">
    <h2 id="r-h" className="lc-h2">3 · Human review, approval and freezing</h2>
    {suites.error && <Failed error={suites.error} what="Suites" />}
    <ul className="lc-suites">{list.map(x => <li key={x.sha256}><a href={`#/lifecycle/suites/${x.sha256}`} aria-current={x.sha256 === id ? 'true' : undefined}>
      <span className={`tag ${STATE_TAG[x.state]}`}>{x.state}</span><strong>{x.name} v{x.version}</strong><small>{x.tasks} tasks · {x.refs.join(', ') || 'no ref'} · prepared by {x.created_by}{x.synthetic ? ' · SYNTHETIC fixture' : ''}</small>
      <code>{short(x.sha256)}…</code></a></li>)}</ul>
    {s.data && <SuiteView s={s.data} ov={ov} />}
    {s.error && <Failed error={s.error} what="This suite" />}
  </section>;
}

function SuiteView({ s, ov }: { s: Suite; ov: Overview | null }) {
  return <div className="lc-suite">
    <div className="lc-suite-hash"><span className="eyebrow">Exact suite hash · approval applies to this value only</span><code>{s.sha256}</code></div>
    <dl className="lc-facts">
      <div><dt>State</dt><dd><span className={`tag ${STATE_TAG[s.state]}`}>{s.state}</span> {s.refs.length > 0 && <>as <code>{s.refs.join(', ')}</code></>}</dd></div>
      <div><dt>Approvals</dt><dd>{s.approvals.length ? s.approvals.map(a => <span key={a.sha256} className="lc-inline">{a.decision} by the {a.role}, {new Date(a.decided_at).toUTCString().slice(5, 22)} UTC{a.synthetic ? ' (SYNTHETIC)' : ''} · <Hash sha={a.sha256} /></span>) : 'none yet'}</dd></div>
      <div><dt>Frozen</dt><dd>{s.frozen.length ? s.frozen.map(f => <span key={f.sha256} className="lc-inline">{new Date(f.frozen_at).toUTCString().slice(5, 22)} UTC · <Hash sha={f.sha256} /></span>) : 'not frozen'}</dd></div>
      <div><dt>Prepared</dt><dd>by {s.created_by}, {s.created_at} · selection {s.selection_rule} · inputs: {s.inputs.map(i => i.kind).join(', ')}</dd></div>
      <div><dt>Contents</dt><dd>{s.counts.tasks} tasks · {Object.entries(s.counts.by_category).map(([k, n]) => `${n} ${words(k)}`).join(', ')}</dd></div>
    </dl>
    <ol className="lc-review-tasks">{s.tasks.map(t => <li key={t.task_id}>
      <q>{t.customer_wording}</q>
      <small>{words(t.category)} · {t.condition ?? 'not executed'} · {words(t.capability)}{t.persona ? ` · ${words(t.persona)}` : ''}{t.journey ? ` · ${words(t.journey)}` : ''} · limit {t.limits.max_model_requests} requests</small>
      {t.executed_wording && t.executed_wording !== t.customer_wording && <p>Executed as: <q>{t.executed_wording}</q></p>}
      {t.assumptions.length > 0 && <p className="lc-assume">Assumptions: {t.assumptions.join('; ')}</p>}
      {t.interpretation_decisions.length > 0 && <details><summary>Interpretation decisions</summary><ul>{t.interpretation_decisions.map(d => <li key={d}>{d}</li>)}</ul></details>}
    </li>)}</ol>
    {s.gaps.length > 0 && <p className="lc-gaps"><strong>Coverage gaps disclosed for review:</strong> {s.gaps.join('; ')}.</p>}
    <div className="lc-approve">
      <h3>Owner checklist</h3><ul className="lc-list">{s.checklist.map(c => <li key={c}>{c}</li>)}</ul>
      <p className="lc-attest"><span className="eyebrow">Attestation the owner types</span><code>{s.attestation.approve}</code></p>
      <button type="button" className="btn" disabled aria-describedby="approve-why">Approve and freeze this exact hash</button>
      <Disabled title="Web approval is disabled" detail={(ov?.approval ?? s.web_decision).detail}>
        <p id="approve-why">At an owner terminal: <code>{s.owner_terminal_command}</code>, then <code>… approval freeze &lt;STORE&gt; {short(s.sha256)}… &lt;APPROVAL&gt;</code>. Any edit creates a new version that needs a new approval.</p>
      </Disabled>
    </div>
  </div>;
}

// --------------------------------------------------------------------------------------------------------------- 4 evaluate
const ARM_STEPS = [
  'ssh <vm> && cd ~/agent-readiness/deploy',
  'docker compose exec app python -m agent_readiness.lifecycle.arming prepare --arming larkspur-live-1 --mode paid --frozen larkspur-core@v2 --variants original modified --repetitions 1 --launches 1',
  'docker compose exec -it app python -m agent_readiness.lifecycle.arming arm      …the same arguments…   (the owner types the attestation shown)',
];

/** The armed evaluation (server-side selection) and the one launch path: the evaluation workspace. */
function ArmedEvaluation({ ov, reevaluate = false }: { ov: Overview | null; reevaluate?: boolean }) {
  const cfg = ov?.evaluation;
  const ev = cfg?.evaluation;
  return <div className="lc-launch">
    <h3>{reevaluate ? 'Re-evaluate' : 'Launch'} from the evaluation workspace</h3>
    {ev ? <dl className="lc-facts">
      <div><dt>Armed</dt><dd><code>{ev.arming_id}</code> · <ModeBadge mode={ev.mode} /> · armed {ev.armed_at}</dd></div>
      <div><dt>Frozen suite</dt><dd>{ev.suite} · <Hash sha={ev.frozen_suite_sha256} /></dd></div>
      <div><dt>Website</dt><dd>{ev.site}: {ev.variants.map(v => <VariantName key={v} v={v} />)}</dd></div>
      <div><dt>Model</dt><dd>{ev.agent.model} · reasoning {ev.agent.reasoning_effort} · {ev.agent.max_completion_tokens} completion tokens · profile {ev.agent.profile}</dd></div>
      <div><dt>Launches</dt><dd>{ev.launches.left} of {ev.launches.max} left · {ev.options.map(o => <span key={o.repetitions} className="lc-inline">{o.repetitions} repetition(s): {o.trials} trials, reserves {fmtUsd(o.reservation_usd, 3)}{o.fits_hosted_ceiling === false ? ' (does not fit the hosted budget)' : ''}</span>)}</dd></div>
    </dl> : <Disabled title="No evaluation is armed on this server" detail={cfg ? `Reason: ${words(cfg.reason ?? 'not armed')}. The owner arms a frozen suite at the server terminal.` : 'This server does not run evaluations (view-only).'} />}
    <a className="btn btn-signal" href="#/run">Open the evaluation workspace <span className="arr" aria-hidden="true">→</span></a>
    <details className="lc-ssh"><summary>How the owner arms an evaluation (over SSH)</summary>
      <ol>{ARM_STEPS.map(c => <li key={c}><code>{c}</code></li>)}</ol>
      <p>The owner reads exactly what would run — the frozen suite, the website snapshots, the manifest per repetition count, the model, the reservation per launch and
        the hosted budget left — and types the attestation shown. {reevaluate ? 'A re-evaluation arms the same frozen suite with other registered website variants; the server prepares a regression manifest that differs only in its variants. ' : ''}
        The operator token can launch an armed evaluation but can never arm one; each launch runs once and is never retried.</p></details>
  </div>;
}

function EvaluatePanel({ ov }: { ov: Overview | null }) {
  return <section aria-labelledby="e-h">
    <h2 id="e-h" className="lc-h2">4 · Browser-agent evaluation of the approved suite</h2>
    <p className="lede sm">Only a frozen, owner-approved suite can be evaluated. The owner arms it at the server terminal; the operator launches it in the evaluation workspace,
      as before. The browser runs in a network jail that can reach only the frozen website copy, and every model request is reserved against a durable ledger before it is sent.</p>
    <ArmedEvaluation ov={ov} />
    <RecordedList title="Evaluations" />
  </section>;
}

// --------------------------------------------------------------------------------------------------------------- 5 report, 6 re-evaluate
function RecordedList({ title, filter }: { title: string; filter?: (e: EvaluationSummary) => boolean }) {
  const evs = useLoad(() => api.evaluations(), 'evaluations');
  const list = (evs.data ?? []).filter(e => !filter || filter(e));
  return <div className="lc-recorded"><h3>{title}</h3>
    {evs.error && <Failed error={evs.error} what="Evaluations" />}
    {evs.data && !list.length && <p className="muted">None yet.</p>}
    <ul className="lc-evals">{list.map(e => <li key={e.id}><a href={e.state === 'completed' ? `#/reports/${e.id}` : `#/run/${e.id}`}>
      <div className="lc-eval-top"><ModeBadge mode={e.mode} /><span className="tag tag-neutral">{words(e.state)}</span>{e.source === 'dataset' && <span className="tag tag-neutral">dataset v{e.dataset_version}</span>}</div>
      <strong>{e.title ?? e.id}</strong>
      <small>{[e.site, e.suite, e.variants?.join(' vs '), e.tasks != null ? `${e.tasks} tasks, ${e.trials} trials` : null].filter(Boolean).join(' · ')}</small>
      {e.success && <span className="lc-eval-nums">{Object.entries(e.success).map(([v, s]) => <span key={v}><VariantName v={v} /> v1 {s.v1_passed}/{s.trials} · v2 {s.v2_passed}/{s.trials} · {e.requests?.[v] ?? '–'} requests</span>)}</span>}
    </a></li>)}</ul></div>;
}

function ReportsPanel() {
  return <section aria-labelledby="rp-h">
    <h2 id="rp-h" className="lc-h2">5 · Multidimensional readiness reports</h2>
    <p className="lede sm">Each report shows six dimensions — task success, navigation efficiency, evidence quality, information accessibility, agent reliability and coverage —
      as measured quantities with their basis. No composite score is computed, because no scoring method has been validated.</p>
    <RecordedList title="Reports" />
  </section>;
}

function ReevaluatePanel({ ov }: { ov: Overview | null }) {
  return <section aria-labelledby="re-h">
    <h2 id="re-h" className="lc-h2">6 · Re-evaluation against the same frozen suite</h2>
    <p className="lede sm">After a website change, the same frozen suite runs again. The server creates a regression manifest that may differ from the original only in its website
      variants — same tasks, agent, plan, seed and limits — and re-checks every task on the new snapshot: a task whose answer changed is invalidated for that variant, with the reason.</p>
    <ArmedEvaluation ov={ov} reevaluate />
    <RecordedList title="Evaluations of frozen suites" />
  </section>;
}
