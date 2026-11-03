import { useEffect, useState } from 'react';
import { api, fmtSec, fmtUsd, VARIANT_LABEL, variantClass, words, type Evaluation, type Step, type Timeline, type Trial } from '../../lib/lifecycleApi';
import { Failed, GradeTag, Loading, useLoad, VariantName } from './parts';
import { FindingCard } from './Report';

/** Original and Modified traces of one frozen task, side by side: real recorded screenshots, the navigation path, requests, time and cost, the
 *  outcome under official v1 and post-hoc v2 (and any prospective rule, labelled), evidence counts and the diagnostics that cite this task. */
export function TraceCompare({ ev, n }: { ev: Evaluation; n: number }) {
  const task = ev.tasks.find(t => t.n === n);
  const vs = ev.manifest.variants.map(v => v.name);
  const trials = vs.map(v => ev.trials.find(t => t.task === n && t.variant === v)).filter((t): t is Trial => !!t);
  const access = ev.dimensions.information_accessibility.tasks.find(t => t.task === n);
  const findings = Object.values(ev.diagnostics).flatMap(d => d.findings ?? []).filter(f => f.tasks.includes(n));
  const executed = ev.tasks.filter(t => t.executed).map(t => t.n);
  if (!task) return <p className="lc-error">This evaluation has no task {n}.</p>;
  return <article className="lc-trace">
    <header className="lc-trace-head">
      <p className="eyebrow">Task {n} · {words(task.capability)} · {task.kind}{task.persona ? ` · persona: ${words(task.persona)}` : ''}</p>
      <h1 className="lc-title sm"><q>{task.customer_wording}</q></h1>
      <p className="lc-note">The customer's own wording, executed unchanged on both website variants by the same agent, under the same frozen manifest.
        {ev.mode !== 'paid' && ' Rehearsal: the replies come from a scripted stand-in, not a model.'}</p>
      {access && <p className="lc-places">Facts this question depends on: {access.facts.map(f => <span key={f} className="lc-inline"><b>{f}</b> — {vs.map(v => <span key={v} className={`lc-place ${access.placement[v]?.[f] === 'listing cards' ? 'ok' : 'deep'}`}>{VARIANT_LABEL(v)}: {access.placement[v]?.[f]}</span>)}</span>)}</p>}
      <nav className="lc-task-nav" aria-label="Other tasks">{executed.map(x => <a key={x} href={`#/reports/${ev.id}/tasks/${x}`} aria-current={x === n ? 'page' : undefined}>Task {x}</a>)}</nav>
    </header>
    <div className="lc-sides">{trials.map(t => <Side key={t.id} ev={ev} t={t} />)}</div>
    {findings.length > 0 && <section className="lc-section" aria-labelledby="tf-h"><header className="lc-section-head"><h2 id="tf-h">Diagnostics that cite task {n}</h2>
      <p className="lc-basis">Observed facts and hypotheses are labelled separately; a hypothesis is a suspected contributor, not an established cause.</p></header>
      <ul className="lc-findings two">{findings.map(f => <FindingCard key={f.id + f.variant} f={f} />)}</ul></section>}
  </article>;
}

function answerText(t: Trial): string {
  if (t.answer_withheld) return t.answer_withheld;
  if (t.answer == null) return 'no answer';
  const text = Array.isArray(t.answer) ? (t.answer.length ? t.answer.join('; ') : '(empty list)') : t.answer;
  return t.answer_normalized ? `${text} (${t.answer_normalized.note})` : text;
}

function Side({ ev, t }: { ev: Evaluation; t: Trial }) {
  const tl = useLoad(() => api.timeline(ev.id, t.id), `${ev.id}/${t.id}`);
  const c = t.answer_coverage, m = t.metrics;
  return <section className={`lc-side ${variantClass(t.variant)}`} aria-label={`${VARIANT_LABEL(t.variant)} trace`}>
    <header><h2><VariantName v={t.variant} /></h2>
      <div className="lc-grades"><GradeTag g={t.grades.v1} which="v1" /><GradeTag g={t.grades.v2} which="v2" />{t.grades.v2_1_contrast && <GradeTag g={t.grades.v2_1_contrast} which="v2.1" />}</div></header>
    <dl className="lc-side-stats">
      <div><dt>Answer</dt><dd>{c && c.expected_items > 1 ? `${c.named_expected} of ${c.expected_items} expected items` : c ? (c.named_expected ? 'expected item named' : 'expected item not named') : '–'}{c?.named_other ? ` · ${c.named_other} other named` : ''}</dd></div>
      <div><dt>Requests</dt><dd>{m.model_requests ?? '–'}{m.request_limit ? ` of ${m.request_limit}` : ''}</dd></div>
      <div><dt>Time</dt><dd>{fmtSec(m.elapsed_seconds)}</dd></div>
      <div><dt>{ev.mode === 'paid' ? 'Cost (calculated)' : 'Cost'}</dt><dd>{ev.mode === 'paid' ? fmtUsd(m.cost_usd) : 'US$0'}</dd></div>
      <div><dt>Pages</dt><dd>{t.navigation.distinct_pages} distinct · {t.navigation.revisits} revisits</dd></div>
      <div><dt>Evidence</dt><dd>{t.evidence.satisfied ? 'answer pages shown' : `${t.evidence.missing_pages} required page(s) not shown`}</dd></div>
    </dl>
    <blockquote className="lc-answer"><span className="eyebrow">{t.answer_withheld ? 'Answer' : "Agent's answer, as recorded"}</span><p>{answerText(t)}</p></blockquote>
    {t.grades.v2_1_contrast && <p className="lc-prospective-note">Prospective review rule v2.1: {t.grades.v2_1_contrast.reasons.join(', ')} — {t.grades.v2_1_contrast.status}.</p>}
    {t.evidence.ranked_subset_rule_2.applies && <p className="lc-prospective-note">Prospective evidence rule 2: {t.evidence.ranked_subset_rule_2.shown_pages} of {t.evidence.ranked_subset_rule_2.required_pages} candidate pages shown ({t.evidence.ranked_subset_rule_2.satisfied ? 'comparison evidenced' : 'comparison not evidenced'}).</p>}
    {(t.reliability.http_errors.length > 0 || t.reliability.near_request_limit || t.reliability.partial_answer || t.reliability.empty_answer) &&
      <ul className="lc-flags">{t.reliability.http_errors.map((e, i) => <li key={i}>Dead end: <code>{e.path}</code> returned {e.status}{t.reliability.recovered ? ' (recovered)' : ''}</li>)}
        {t.reliability.near_request_limit && <li>Used {m.model_requests} of {m.request_limit} requests (at or near the limit)</li>}
        {t.reliability.partial_answer && <li>Partial answer</li>}{t.reliability.empty_answer && <li>Empty answer</li>}</ul>}
    <p className="lc-path" aria-label="Navigation path"><span className="eyebrow">Path</span> {t.navigation.visits.map((p, i) => <span key={i}><code>{p}</code>{i < t.navigation.visits.length - 1 ? ' → ' : ''}</span>)}</p>
    {tl.loading && <Loading what="the trace" />}
    {tl.error && <Failed error={tl.error} what="The trace" />}
    {tl.data && <Player ev={ev} trial={t} tl={tl.data} />}
  </section>;
}

function Player({ ev, trial, tl }: { ev: Evaluation; trial: Trial; tl: Timeline }) {
  const steps = tl.steps;
  const [i, setI] = useState(0);
  useEffect(() => { setI(0); }, [tl.id]);
  if (!steps.length) return <p className="muted">No recorded steps.</p>;
  const s: Step = steps[Math.min(i, steps.length - 1)];
  const shot = s.screenshot ?? tl.screenshots[Math.min(i, tl.screenshots.length - 1)];
  return <div className="lc-player">
    <div className="frame">
      <div className="frame-bar"><span className="frame-dots"><i /><i /><i /></span><span className="frame-url">{s.path ?? ''}</span></div>
      <div className="frame-shot lc-shot">{shot ? <img src={api.shot(ev.id, trial.id, shot)} alt={`${VARIANT_LABEL(trial.variant)} task ${trial.task}, step ${s.step}: ${s.path ?? 'page'}`} loading="lazy" /> : <span className="muted">no screenshot</span>}</div>
    </div>
    <div className="lc-stepbar">
      <button type="button" className="btn btn-sm btn-ghost" onClick={() => setI(x => Math.max(0, x - 1))} disabled={i === 0} aria-label="Previous step">←</button>
      <input type="range" min={0} max={steps.length - 1} value={i} onChange={e => setI(Number(e.target.value))} aria-label={`Step, ${VARIANT_LABEL(trial.variant)}`} />
      <button type="button" className="btn btn-sm btn-ghost" onClick={() => setI(x => Math.min(steps.length - 1, x + 1))} disabled={i >= steps.length - 1} aria-label="Next step">→</button>
      <span className="mono">step {s.step} / {steps.length}</span>
    </div>
    <div className="lc-step">
      <p className="lc-actions">{s.actions.map((a, k) => <span key={k} className={`lc-act${a.name === 'Answer' ? ' done' : ''}`}><b>{a.name}</b>{a.target ? ` ${a.target}` : ''}</span>)}{s.error && <span className="lc-act err">error: {s.error}</span>}</p>
      {s.memory && <p><span className="eyebrow">Agent memory</span> {s.memory}</p>}
      {s.goal && <p><span className="eyebrow">Next goal</span> {s.goal}</p>}
    </div>
    <ol className="lc-steps" aria-label="All steps">{steps.map((x, k) => <li key={k}><button type="button" aria-current={k === i ? 'step' : undefined} onClick={() => setI(k)}>
      <span className="mono">{x.step}</span> {x.actions.map(a => a.name).join(', ')} <small>{x.path}</small></button></li>)}</ol>
  </div>;
}
