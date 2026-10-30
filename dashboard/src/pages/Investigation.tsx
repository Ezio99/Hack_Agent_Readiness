import { useEffect, useState } from "react";
import { Callout, Kpi, Pill } from "../components/ui";
import { SideBySide, StorefrontBrowser } from "../components/Storefront";
import { EXPLORATORY_VERDICT, MODE_LABEL, compare, parseInvestigation, roles, tally, type EvalResult, type Exploratory, type InvestigationExport, type Mode, type TrialRow } from "../lib/investigation";

const pct = (a: number, b: number) => (b ? `${Math.round((100 * a) / b)}%` : "—");
const num = (x: number | null | undefined, d = 2) => (typeof x === "number" ? x.toFixed(d) : "—");
const short = (id: string) => (id.length > 14 ? `${id.slice(0, 14)}…` : id);

export function ModeBadge({ mode }: { mode: Mode }) {
  return <span className={`mode mode-${mode}`} title={`Evidence mode: ${MODE_LABEL[mode]}`}>{MODE_LABEL[mode]}</span>;
}

const STAGE_TONE = { done: "pass", failed: "fail", awaiting_approval: "warn", running: "warn", pending: "neutral" } as const;

export function Timeline({ d }: { d: InvestigationExport }) {
  return (
    <ol className="timeline" aria-label="Pipeline stages">
      {d.stages.map((s) => (
        <li key={s.name} className={`tl tl-${s.status}${s.skipped ? " tl-skipped" : ""}`}>
          <span className="tl-name">{s.name.replace(/_/g, " ")}</span>
          <Pill tone={STAGE_TONE[s.status] ?? "neutral"}>{s.skipped ? "skipped" : s.status.replace(/_/g, " ")}</Pill>
          {s.skipped && s.reason ? <span className="muted tl-note">{s.reason}</span> : null}
          {s.status === "awaiting_approval" && s.manifest_sha256 ? <span className="muted tl-note">owner approval needed · <code>{short(s.manifest_sha256)}</code></span> : null}
        </li>
      ))}
    </ol>
  );
}

function Cell({ rows }: { rows: TrialRow[] }) {
  if (!rows.length) return <span className="muted">not run</span>;
  return (
    <>
      {rows.map((r) =>
        r.void ? <span key={r.trial_id} title={`${r.run_status}: void, not a website result`}><Pill tone="warn">void</Pill> </span>
          : <span key={r.trial_id} title={`${r.run_status}; ${r.model_requests ?? "?"} requests, ${r.page_views ?? "?"} page views`}><Pill tone={r.passed ? "pass" : "fail"}>{r.passed ? "pass" : "fail"}</Pill> <span className="muted">{r.model_requests ?? "?"} req · {r.page_views ?? "?"} pages</span> </span>)}
    </>
  );
}

export function TaskTable({ d }: { d: InvestigationExport }) {
  const pids = [...new Set(d.tasks.flatMap((t) => Object.keys(t.patched)))];
  const hasControl = d.tasks.some((t) => Object.keys(t.placebo ?? {}).length > 0);
  if (!d.tasks.length) return <p className="muted">No frozen tasks in this export (the task stages had not completed).</p>;
  return (
    <div className="table-wrap">
      <table className="runs">
        <caption className="sr-only">Task outcomes per arm</caption>
        <thead><tr><th scope="col">Task</th><th scope="col">Set</th><th scope="col">{hasControl ? "Historical baseline" : "Baseline"}</th>{hasControl ? <th scope="col">Unmodified repeat (control)</th> : null}{pids.map((p) => <th scope="col" key={p}>Patched <code>{short(p)}</code></th>)}</tr></thead>
        <tbody>
          {d.tasks.map((t) => (
            <tr key={t.task_id} className={t.baseline.some((r) => !r.void && !r.passed) ? "row-fail" : undefined}>
              <th scope="row"><span>{t.question}</span><br /><code>{t.task_id}</code> <span className="muted">{t.kind}</span></th>
              <td>{t.partition}</td>
              <td><Cell rows={t.baseline} />{t.baseline.some((r) => r.attribution && !["success", "infrastructure"].includes(r.attribution)) ? <div className="muted">{t.baseline.map((r) => r.attribution).filter(Boolean).join(", ")}</div> : null}</td>
              {hasControl ? <td><Cell rows={Object.values(t.placebo ?? {}).flat()} /></td> : null}
              {pids.map((p) => <td key={p}><Cell rows={t.patched[p] ?? []} /></td>)}
            </tr>))}
        </tbody>
      </table>
      <p className="muted">Void trials (provider, budget, infrastructure or fidelity guard) are shown but never counted as website results. {d.trials.void} void trial(s) in this run.</p>
    </div>
  );
}

export function Findings({ d }: { d: InvestigationExport }) {
  const obs = new Map(d.observations.map((o) => [o.id, o]));
  const novel = d.hypotheses.filter((h) => h.tier === "novel");
  const other = d.hypotheses.filter((h) => h.tier === "verifiable" && !h.promoted);
  return (
    <>
      <h3>Verified findings</h3>
      {d.findings.length === 0 ? <p className="muted">No verified findings. A hypothesis is promoted to a finding only after deterministic verification and independent trial support.</p> : (
        <ul className="findings">
          {d.findings.map((f) => (
            <li key={f.id} className="finding conf-observed">
              <span className="pill pill-pass">Verified finding</span> <ModeBadge mode={f.provenance.mode} /> <span className="muted">attribution: {f.attribution}{f.structural_proof ? " · structural proof" : ""}</span>
              <h4>{f.statement}</h4>
              <p className="muted">Evidence</p>
              <ul>
                {f.observation_ids.map((id) => <li key={id}><code>{short(id)}</code> {obs.get(id)?.summary}</li>)}
                {f.unresolved_observation_ids.map((id) => <li key={id} className="shortfall">Unresolved observation <code>{short(id)}</code></li>)}
                {f.support.map((s) => <li key={s.ref}>{s.resolved ? "Supporting trial" : <span className="shortfall">Unresolved trial reference</span>} <code>{s.ref}</code></li>)}
              </ul>
            </li>))}
        </ul>)}
      <details open><summary><strong>Hypotheses that are not findings</strong> (full records)</summary>
      <ul className="findings">
        {novel.map((h) => (
          <li key={h.id} className="finding conf-hypothesis">
            <span className="pill pill-warn">{h.provenance.source.startsWith("owner:") ? "Owner-authored hypothesis" : "Novel hypothesis"} — UNVERIFIED</span> <ModeBadge mode={h.provenance.mode} />
            <h4>{h.statement}</h4>
            <p className="muted">Prediction to test: {h.prediction}</p>
          </li>))}
        {other.map((h) => (
          <li key={h.id} className="finding conf-inferred">
            <span className={`pill pill-${h.status === "refuted" ? "fail" : "neutral"}`}>Hypothesis — {h.status}</span> <ModeBadge mode={h.provenance.mode} />
            <h4>{h.statement}</h4>
            {h.verification ? <p className="muted">Checked by {h.verification.verifier}: {h.verification.result}</p> : null}
          </li>))}
        {novel.length + other.length === 0 ? <li className="muted">None recorded.</li> : null}
      </ul>
      </details>
    </>
  );
}

function Bar({ label, cls, value, text }: { label: string; cls: "A" | "B"; value: number; text: string }) {
  return (
    <div className="bar-row">
      <span className="bar-label">{label}</span>
      <span className="bar-track" aria-hidden="true"><span className={`bar bar-${cls}`} style={{ width: `${Math.max(2, value * 100)}%` }} /></span>
      <span className="bar-value">{text}</span>
    </div>
  );
}

function ResultCard({ d, r }: { d: InvestigationExport; r: EvalResult }) {
  const c = compare(d.tasks, r.proposal_id);
  const b = c.baseline, p = c.patched;
  const tone = r.verdict === "improvement" ? "good" : r.verdict === "regression" ? "bad" : "info";
  return (
    <section className="card" aria-label={`Baseline versus patched for ${r.proposal_id}`}>
      <h4>Patch <code>{short(r.proposal_id)}</code>{d.synthetic ? <> <span className="mode mode-scripted">ILLUSTRATIVE — synthetic numbers</span></> : null} <Pill tone={r.verdict === "improvement" ? "pass" : r.verdict === "regression" ? "fail" : "neutral"}>{r.verdict}</Pill>{" "}
        {r.measured ? <span className="mode mode-live">MEASURED (live)</span> : <span className="mode mode-unmeasured">NOT MEASURED — {r.effect_mode ? MODE_LABEL[r.effect_mode].toLowerCase() : "no"} evidence, a pipeline check only</span>}</h4>
      <figure className="paired" role="group" aria-label={`Evidence-backed pass rate: baseline ${pct(b.passed, b.usable)}, patched ${pct(p.passed, p.usable)}`}>
        <figcaption>Evidence-backed pass rate on {c.tasks} usable task{c.tasks === 1 ? "" : "s"} (descriptive)</figcaption>
        <Bar label="Baseline" cls="B" value={b.usable ? b.passed / b.usable : 0} text={`${b.passed}/${b.usable}`} />
        <Bar label="Patched" cls="A" value={p.usable ? p.passed / p.usable : 0} text={`${p.passed}/${p.usable}`} />
      </figure>
      <p className="muted">Mean model requests per trial: baseline {num(b.requests, 1)} → patched {num(p.requests, 1)}. {c.skipped ? `${c.skipped} task(s) lack a usable trial in one arm and are not compared.` : ""}</p>
      <dl className="facts">
        <dt>Pre-registered rule</dt><dd>{r.rule_preregistered_at_freeze ? "fixed before any trial ran" : "not recorded as pre-registered"}</dd>
        <dt>Pairs · pass Δ · request Δ</dt><dd>{r.pairs ?? "—"} · {num(r.pass_delta)} · {num(r.request_change)} (p = {num(r.p_pass)} / {num(r.p_requests)})</dd>
        <dt>Holdout consistent</dt><dd>{r.holdout_consistent == null ? "—" : r.holdout_consistent ? "yes" : "no"}{r.by_partition ? <span className="muted"> — pass change: {Object.entries(r.by_partition).map(([k, v]) => `${k} ${v.pass_delta == null ? "—" : (v.pass_delta > 0 ? "+" : "") + v.pass_delta.toFixed(2)} (${v.pairs} pairs)`).join(" · ")}. “No” means the two partitions’ pass changes have different signs; it does not by itself mean the holdout got worse, and it only withdraws an <em>improvement</em> verdict when the holdout pass rate fell.</span> : null}</dd>
        <dt>Reason</dt><dd>{r.reason ?? "—"}</dd>
        {r.excluded.length ? <><dt>Excluded</dt><dd>{r.excluded.map((e) => `${e.task_id}: ${e.reason}`).join("; ")}</dd></> : null}
      </dl>
      <Callout title="How to read this" tone={tone === "bad" ? "warn" : "info"}>
        <p>{r.measured ? "A measured effect is for these frozen tasks, this agent profile and this patched mirror only; it does not prove why the change worked." : "This effect was not measured with live trials. It shows the pipeline works end to end; it is not evidence about agent behaviour."}</p>
      </Callout>
    </section>
  );
}

const ARM_BAR = { baseline: { label: "Historical baseline", cls: "H" }, placebo: { label: "Unmodified repeat", cls: "C" }, patched: { label: "Patched", cls: "A" } } as const;

/** Model requests per task in the three arms, with the role each task plays in the pre-registered design. Descriptive; the verdicts are computed by the rules, not by this chart. */
export function ThreeArmChart({ d, x }: { d: InvestigationExport; x: Exploratory }) {
  const q = new Map(d.tasks.map((t) => [t.task_id, t.question]));
  const all = roles(x).flatMap(({ task_id }) => (["baseline", "placebo", "patched"] as const).map((a) => x.tasks[a][task_id]?.requests ?? 0));
  const top = Math.max(1, ...all);
  return (
    <div className="threearm" role="group" aria-label="Model requests per task in each arm">
      <ul className="legend" aria-label="Legend">{Object.values(ARM_BAR).map((a) => <li key={a.cls}><span className={`swatch bar-${a.cls}`} aria-hidden="true" />{a.label}</li>)}</ul>
      {roles(x).map(({ task_id, role }) => (
        <section key={task_id} className="card" aria-label={`${role}: ${task_id}`}>
          <h4><Pill tone={role === "Affected" ? "pass" : "neutral"}>{role}</Pill> <span>{q.get(task_id) ?? task_id}</span></h4>
          {(["baseline", "placebo", "patched"] as const).map((a) => {
            const r = x.tasks[a][task_id];
            if (!r) return a === "placebo" ? null : <div key={a} className="bar-row"><span className="bar-label">{ARM_BAR[a].label}</span><span /><span className="bar-value muted">no trial</span></div>;
            return <div key={a} className="bar-row"><span className="bar-label">{ARM_BAR[a].label}</span><span className="bar-track" aria-hidden="true"><span className={`bar bar-${ARM_BAR[a].cls}`} style={{ width: `${Math.max(2, (100 * r.requests) / top)}%` }} /></span>
              <span className="bar-value">{r.requests} req · {r.pass ? "pass" : "fail"}</span></div>;
          })}
        </section>))}
    </div>
  );
}

/** Headline request changes (unmodified repeat → patched) for the affected tasks, and any control whose pass status differs between arms. Derived only from the exported rows. */
export function Headline({ d, x }: { d: InvestigationExport; x: Exploratory }) {
  const q = new Map(d.tasks.map((t) => [t.task_id, t.question]));
  const aff = roles(x).filter((r) => r.role === "Affected");
  const flips = roles(x).filter((r) => r.role !== "Affected").flatMap(({ task_id, role }) => {
    const b = x.tasks.baseline[task_id], c = x.tasks.placebo[task_id], p = x.tasks.patched[task_id];
    if (!p) return [];
    const was = c ?? b;
    return was && was.pass !== p.pass ? [{ task_id, role, was, p, vs: c ? "unmodified repeat" : "historical baseline" }] : [];
  });
  return (
    <>
      <ul className="headline" aria-label="Affected-task request changes">
        {aff.map(({ task_id }) => <li key={task_id} className="card"><span className="big">{x.tasks.placebo[task_id]?.requests ?? "—"} → {x.tasks.patched[task_id]?.requests ?? "—"}</span> model requests<br /><span className="muted">{q.get(task_id) ?? task_id} (unmodified repeat → patched)</span></li>)}
      </ul>
      {flips.map((f) => (
        <Callout key={f.task_id} title="A control task changed outcome" tone="warn">
          <p><strong>{q.get(f.task_id) ?? f.task_id}</strong> ({f.role.toLowerCase()}, <code>{f.task_id}</code>) went from <strong>{f.was.pass ? "pass" : "fail"}</strong> ({f.was.requests} requests, {f.vs}) to <strong>{f.p.pass ? "pass" : "fail"}</strong> ({f.p.requests} requests, patched).
            Its request count moved within the pre-registered tolerance, and the exploratory rules test controls on request counts only, so this does not change the verdict. With one trial per arm it cannot be separated from run-to-run variation, and it is not evidence either way about the change.</p>
        </Callout>))}
    </>
  );
}

export function ExploratoryPanel({ d, x }: { d: InvestigationExport; x: Exploratory }) {
  const v = EXPLORATORY_VERDICT[x.verdict] ?? { label: x.verdict, tone: "info" as const };
  const frozen = d.evaluation.results[0];
  return (
    <>
      <div className="grid2 verdicts">
        <section className="card verdict-frozen" aria-label="Frozen pre-registered verdict">
          <p className="eyebrow">Frozen rule · fixed before any trial</p>
          <h4><code>{d.evaluation.rule?.id ?? "paired-signflip-v1"}</code> <Pill tone={frozen?.verdict === "improvement" ? "pass" : frozen?.verdict === "regression" ? "fail" : "neutral"}>{frozen?.verdict ?? "—"}</Pill></h4>
          <p className="muted">Historical baseline vs patched, {frozen?.pairs ?? "—"} task pairs. Reported unchanged. With only two tasks that can be affected, this rule can at best say “inconclusive”.</p>
          {frozen ? <p className="muted">Pass Δ {num(frozen.pass_delta)} · request Δ {num(frozen.request_change)} (p = {num(frozen.p_requests)})</p> : null}
        </section>
        <section className={`card verdict-exploratory verdict-${v.tone}`} aria-label="Exploratory verdict">
          <p className="eyebrow">Exploratory rules · owner-selected change · not a replacement</p>
          <h4><code>{x.rules_id}</code> <Pill tone={v.tone === "good" ? "pass" : v.tone === "bad" ? "fail" : "warn"}>{v.label}</Pill></h4>
          <p className="muted">Contemporaneous unmodified repeat vs patched is the primary comparison; the historical baseline is secondary.</p>
          {x.reasons.map((r) => <p key={r} className="muted">{r}</p>)}
        </section>
      </div>
      <Headline d={d} x={x} />
      <ThreeArmChart d={d} x={x} />
      <dl className="facts">
        <dt>Noise estimate</dt><dd>{x.noise_estimate_requests ?? "—"} request(s): the largest gap between an unmodified repeat and its historical trial</dd>
        <dt>Controls within tolerance</dt><dd>{x.controls_within_tolerance == null ? "—" : x.controls_within_tolerance ? "yes" : "no — the result is uninterpretable"}</dd>
        <dt>Effect floor</dt><dd>{x.rules ? `patched requests ≤ ${(1 - x.rules.effect_floor) * 100}% of the unmodified repeat, on every affected task` : "rules text unavailable (stored hash does not match this build)"}</dd>
        <dt>Rules hash</dt><dd><code>{short(x.rules_sha256)}</code> {x.rules_match_code ? "· matches the pre-registered rules" : "· does NOT match the code"}</dd>
        {x.missing_or_void.length ? <><dt>Missing or void</dt><dd>{x.missing_or_void.join(", ")}</dd></> : null}
      </dl>
      <Callout title="What this does and does not show" tone="info">
        <p>One trial per task per arm, one site, one model. {x.rules?.claims ?? "Allowed wording: consistent with / not consistent with a reduction in browsing effort for this exploratory change on this site and these tasks."}</p>
        <p>The change was chosen by the site owner after an unpromoted pattern was observed. It is <strong>not</strong> an investigator-verified finding, and the holdout tasks were not blind to the owner.</p>
      </Callout>
    </>
  );
}

export function Comparison({ d }: { d: InvestigationExport }) {
  const e = d.evaluation;
  if (e.state === "missing") return <Callout title="No evaluation data" tone="warn"><p>{e.reason} Baseline results are shown above; no before/after comparison is available.</p></Callout>;
  if (e.state === "not_evaluated") return <Callout title="Not evaluated" tone="info"><p>{e.reason ?? "No evaluation was run"}. Nothing was retested, so nothing is compared.</p></Callout>;
  return <>{e.exploratory ? <ExploratoryPanel d={d} x={e.exploratory} /> : null}{e.results.map((r) => <ResultCard key={r.proposal_id} d={d} r={r} />)}{e.rule?.causal_scope ? <p className="muted">Scope: {e.rule.causal_scope}</p> : null}</>;
}

export function Proposals({ d, onSeeChange }: { d: InvestigationExport; onSeeChange?: (proposalId: string) => void }) {
  if (!d.proposals.length) return <p className="muted">No proposals.</p>;
  return (
    <ul className="findings">
      {d.proposals.map((p) => (
        <li key={p.id} className={`finding ${p.basis === "verified_finding" ? "conf-observed" : "conf-hypothesis"}`}>
          <span className={`pill ${p.basis === "verified_finding" ? "pill-pass" : "pill-warn"}`}>{p.label}</span>{p.owner_selected ? <> <span className="mode mode-unmeasured">chosen by the site owner · exploratory</span></> : null} <span className="muted">status: {p.status}{p.approved ? " · owner-approved" : ""} · validation: {p.validation}</span>
          <p>{"manual" in p.change ? p.change.manual : `Patch operations: ${p.change.ops.join(", ")}`}</p>
          <p className="muted">Expected: {p.expected_effect}{p.risks.length ? ` · Risks: ${p.risks.join("; ")}` : ""}</p>
          {onSeeChange && d.storefront?.state === "ok" && d.storefront.variants.some((v) => v.proposal_id === p.id) ? <p><button type="button" className="primary" onClick={() => onSeeChange(p.id)}>See the exact website change →</button></p> : null}
        </li>))}
    </ul>
  );
}

export function Spend({ d }: { d: InvestigationExport }) {
  const s = d.spend;
  if (!s || s.state !== "ok") return null;
  const usd = (x: number | null | undefined) => (typeof x === "number" ? `US$${x.toFixed(4)}` : "—");
  return (
    <p className="muted" aria-label="Spend">Calculated model spend (published prices, <strong>not a bill</strong>): {usd(s.committed_usd)} of a {usd(s.ceiling_usd)} ceiling, {usd(s.remaining_usd)} remaining, {s.open_reservations ?? 0} open reservation(s).
      {" "}By arm: {Object.entries(s.by_arm_usd ?? {}).map(([k, v]) => `${k === "other" ? "task generation + investigator" : k} ${usd(v)}`).join(" · ")}.</p>
  );
}

const STEPS = [["website", "1 · Website"], ["analysis", "2 · Agent analysis"], ["recommendations", "3 · Recommendations"], ["changes", "4 · Website changes"], ["impact", "5 · Measured impact"]] as const;
const goTo = (id: string) => document.getElementById(`inv-${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" });

function Coverage({ d }: { d: InvestigationExport }) {
  const kinds = [...new Set(d.tasks.map((t) => t.kind))];
  if (!kinds.length) return null;
  return <p className="muted">Task kinds in this set: {kinds.map((k) => k.replace(/_/g, " ")).join(", ")}.{kinds.includes("reach_page") ? "" : " No navigation (reach-page) task is included, so navigation effort is not measured."} Every task is graded independently of the agent’s own claim of success.</p>;
}


/** Baseline model requests per task against the task's request limit: where the agent's effort went. Descriptive only. */
export function EffortBars({ d }: { d: InvestigationExport }) {
  const rows = d.tasks.map((t) => ({ t, r: t.baseline.find((x) => !x.void) })).filter((x) => x.r && typeof x.r.model_requests === "number");
  if (!rows.length) return null;
  const top = Math.max(1, ...rows.map((x) => x.t.limits?.max_model_requests ?? x.r!.model_requests!));
  return (
    <figure className="paired effort" role="group" aria-label="Baseline model requests per task">
      <figcaption>Model requests per task in the baseline run (limit {rows[0].t.limits?.max_model_requests ?? "—"})</figcaption>
      {rows.map(({ t, r }) => (
        <div key={t.task_id} className="bar-row">
          <span className="bar-label">{t.question.length > 44 ? `${t.question.slice(0, 44)}…` : t.question}</span>
          <span className="bar-track" aria-hidden="true"><span className="bar bar-H" style={{ width: `${Math.max(2, (100 * r!.model_requests!) / top)}%` }} /></span>
          <span className="bar-value">{r!.model_requests} req · {r!.passed ? "pass" : "fail"}</span>
        </div>))}
    </figure>
  );
}

/** Who found what: what the investigator actually established, kept apart from what the owner chose to test. Neither is presented as a verified causal finding. */
export function ProvenanceSplit({ d }: { d: InvestigationExport }) {
  const pattern = d.hypotheses.filter((h) => h.tier === "verifiable" && h.status === "supported" && !h.promoted);
  const refuted = d.hypotheses.filter((h) => h.tier === "verifiable" && h.status === "refuted").length;
  const owner = d.hypotheses.filter((h) => h.provenance.source.startsWith("owner"));
  const ownerProps = d.proposals.filter((p) => p.owner_selected);
  return (
    <div className="provsplit">
      <section className="card prov-inv" aria-label="Discovered by the investigator">
        <p className="eyebrow">Discovered by the investigator ({d.investigation.model ?? "model"})</p>
        <h4>{d.findings.length ? `${d.findings.length} verified finding(s)` : "No verified findings"}</h4>
        {pattern.map((h) => <p key={h.id}><Pill tone="neutral">structurally supported · not promoted</Pill> {h.statement}<br /><span className="muted">Deterministic check: {h.verification?.verifier ?? "—"} → {h.verification?.result ?? "—"}. Not promoted to a finding: a pattern in the pages is not proof that it causes agent friction.</span></p>)}
        {!pattern.length && !d.findings.length ? <p className="muted">The investigator did not establish a supported pattern.</p> : null}
        {refuted ? <p className="muted">{refuted} other hypothesis(es) were checked and refuted.</p> : null}
      </section>
      <section className="card prov-owner" aria-label="Chosen by the site owner">
        <p className="eyebrow">Chosen by the site owner</p>
        <h4>{ownerProps.length ? "Exploratory change to test" : "No owner-selected change"}</h4>
        {owner.map((h) => <p key={h.id}><Pill tone="warn">owner hypothesis · UNVERIFIED</Pill> {h.statement}{h.prediction ? <><br /><span className="muted">Prediction: {h.prediction}</span></> : null}</p>)}
        {!owner.length ? <p className="muted">All proposals below derive from verified findings or unverified investigator hypotheses.</p> : null}
      </section>
    </div>
  );
}

/** Step 4: the exact website change for one proposal, with the metrics of the tasks it can affect. */
export function ChangeSection({ d, proposalId }: { d: InvestigationExport; proposalId: string | null }) {
  const sf = d.storefront;
  if (!sf) return <p className="muted">This export contains no storefront pages, so the website change cannot be shown.</p>;
  if (sf.state !== "ok") return <Callout title="Storefront pages not available" tone="info"><p>{sf.reason}</p></Callout>;
  const v = sf.variants.find((x) => x.proposal_id === proposalId) ?? sf.variants[0];
  if (!v) return <p className="muted">No patched version of the site was applied in this run.</p>;
  const x = d.evaluation.exploratory;
  const q = new Map(d.tasks.map((t) => [t.task_id, t.question]));
  const dd = v.diff;
  return (
    <>
      <p className="lead">{dd.elements_added} line(s) of text were added on {dd.pages_changed.length} page ({dd.pages_changed.map((p) => p).join(", ")}); {dd.pages_unchanged} other pages are byte-identical. Added text: {dd.inserted_text_chars} characters ({dd.net_bytes_added} HTML bytes). The change was applied to a local read-only copy, never to a real site.</p>
      <SideBySide original={sf.original.pages} patched={v.pages} changed={dd.pages_changed} highlightText={dd.inserted_text} />
      <Callout title="Which version did the agents see?" tone="info"><p>The original run and the unmodified repeat used the <strong>original</strong> pages; only the patched trials used the patched pages. These are the captured pages exactly as served to the agents, with no presentation theme.</p></Callout>
      {x ? (
        <section aria-label="Tasks this change can affect">
          <h4>Tasks this change can affect</h4>
          <div className="table-wrap"><table className="runs">
            <caption className="sr-only">Affected tasks: baseline, unmodified repeat and patched</caption>
            <thead><tr><th scope="col">Task</th><th scope="col">Historical baseline</th><th scope="col">Unmodified repeat (control)</th><th scope="col">Patched</th></tr></thead>
            <tbody>{roles(x).filter((r) => r.role === "Affected").map(({ task_id }) => (
              <tr key={task_id}><th scope="row">{q.get(task_id) ?? task_id}</th>
                {(["baseline", "placebo", "patched"] as const).map((a) => <td key={a}>{x.tasks[a][task_id] ? `${x.tasks[a][task_id]!.requests} requests · ${x.tasks[a][task_id]!.pass ? "pass" : "fail"}` : "—"}</td>)}</tr>))}</tbody>
          </table></div>
          <p><button type="button" className="primary" onClick={() => goTo("impact")}>See the full measured impact →</button></p>
        </section>) : null}
    </>
  );
}

export function InvestigationView({ d }: { d: InvestigationExport }) {
  const t = d.tasks.flatMap((x) => x.baseline), bt = tally(t);
  const inspect = d.stages.find((s) => s.name === "inspect")?.summary ?? {};
  const owner = d.proposals.some((p) => p.owner_selected);
  const [selected, setSelected] = useState<string | null>(null);
  const seeChange = (pid: string) => { setSelected(pid); setTimeout(() => goTo("changes"), 0); };
  return (
    <div className="investigation">
      {d.synthetic ? <p className="replay-banner" role="note">SYNTHETIC FIXTURE — hand-written test data, not produced by any model, agent or website.</p> : null}
      {d.audience === "public-demo" ? <p className="muted" role="note">Public demo view: internal identifiers are replaced by aliases and per-trial narratives, stage hashes and file paths are removed. Outcomes, request counts, controls and both verdicts are unchanged.</p> : null}
      <div className="modes" role="note" aria-label="Evidence modes">
        {d.modes.map((m) => <ModeBadge key={m} mode={m} />)}
        <span className="muted">{d.notices.join(" ")}</span>
      </div>
      {d.run.investigation_status && !["completed"].includes(d.run.investigation_status) ? <Callout title={d.run.investigation_status === "not_run" ? "No investigator ran" : "The investigation did not complete"} tone="bad"><p>Status: <code>{d.run.investigation_status}</code>. Nothing was concluded about the website; this is <strong>not</strong> a finding that no problem exists.</p></Callout> : null}
      {!d.run.complete ? <Callout title="Incomplete investigation" tone="warn"><p>Not every stage finished{d.run.missing_artifacts.length ? ` (missing: ${d.run.missing_artifacts.join(", ")})` : ""}. Sections below show what exists; nothing is inferred for the rest.</p></Callout> : null}
      <header className="hero">
        <p className="eyebrow">Agent Readiness · one investigation, end to end</p>
        <h2>{d.run.target}</h2>
        <p className="muted">Website → agent analysis → recommendations → website changes → measured impact. Run <code>{d.run.id}</code> · mode {d.run.mode} · outcome: <strong>{d.run.outcome.replace(/_/g, " ")}</strong></p>
      </header>
      <nav className="steprail" aria-label="Report journey"><ol>{STEPS.map(([id, label]) => <li key={id}><button type="button" onClick={() => goTo(id)}>{label}</button></li>)}</ol></nav>

      <section id="inv-website" aria-labelledby="inv-website-h">
        <h3 id="inv-website-h" className="step">1 · The website being evaluated</h3>
        {d.storefront?.state === "ok" ? <>
          <p className="muted">A controlled test site built for this project (not a real business). Browse the pages exactly as captured and given to the agent.</p>
          <StorefrontBrowser pages={d.storefront.original.pages} />
        </> : <Callout title="Site pages not included" tone="info"><p>{d.storefront && "reason" in d.storefront ? d.storefront.reason : "This export contains no captured pages."}</p></Callout>}
        <div className="kpis">
          <Kpi label="Pages inspected" value={typeof inspect.pages === "number" ? inspect.pages : "—"} note={inspect.fidelity ? `inspection fidelity: ${inspect.fidelity}` : undefined} />
          <Kpi label="Frozen tasks" value={d.tasks.length} note={`${d.tasks.filter((x) => x.partition === "holdout").length} held out from the investigator`} />
          <Kpi label="Baseline pass rate" value={pct(bt.passed, bt.usable)} note={`${bt.passed}/${bt.usable} usable trials`} tone={bt.usable && bt.passed < bt.usable ? "bad" : "neutral"} />
          <Kpi label="Void trials" value={d.trials.void} note="excluded, never a website result" tone={d.trials.void ? "b" : "neutral"} />
        </div>
        <Coverage d={d} />
        <details><summary>How the investigation ran (stages)</summary><Timeline d={d} /></details>
      </section>

      <section id="inv-analysis" aria-labelledby="inv-analysis-h">
        <h3 id="inv-analysis-h" className="step">2 · What the agent did on each task</h3>
        <p className="muted">One browsing agent (frozen configuration) attempted every task. Effort is the number of model requests and pages viewed; success needs evidence-backed correctness, graded independently of the agent.</p>
        <EffortBars d={d} />
        <h3>Task outcomes</h3>
        <TaskTable d={d} />
      </section>

      <section id="inv-recommendations" aria-labelledby="inv-recommendations-h">
        <h3 id="inv-recommendations-h" className="step">3 · Findings and recommendations</h3>
        {owner ? <Callout title="Owner-selected experiment" tone="warn"><p>The change tested below was chosen by the site owner. It is labelled <strong>EXPERIMENTAL</strong> and is <strong>not</strong> an investigator-verified finding. Neither the investigator’s pattern nor the owner’s change is presented as a verified cause.</p></Callout> : null}
        <ProvenanceSplit d={d} />
        <Findings d={d} />
        <h3>Proposed changes</h3>
        <Proposals d={d} onSeeChange={seeChange} />
      </section>

      <section id="inv-changes" aria-labelledby="inv-changes-h">
        <h3 id="inv-changes-h" className="step">4 · The website change</h3>
        <ChangeSection d={d} proposalId={selected} />
      </section>

      <section id="inv-impact" aria-labelledby="inv-impact-h">
        <h3 id="inv-impact-h" className="step">5 · Measured impact</h3>
        <h3>Baseline versus patched</h3>
        <Comparison d={d} />
        <Spend d={d} />
        {d.statement ? <p className="muted">{d.statement}</p> : null}
      </section>
    </div>
  );
}

type Source = "public-synthetic" | "expb-synthetic" | "verified-synthetic";
const SOURCES: Record<Source, { label: string; load: () => Promise<unknown> }> = {
  "public-synthetic": { label: "EXP-B synthetic (public view)", load: async () => (await import("../fixtures/investigation-synthetic-expb-public.json")).default },
  "expb-synthetic": { label: "EXP-B synthetic (private view)", load: async () => (await import("../fixtures/investigation-synthetic-expb.json")).default },
  "verified-synthetic": { label: "Verified-finding synthetic", load: async () => (await import("../fixtures/investigation-synthetic.json")).default },
};

export function InvestigationPage() {
  const [data, setData] = useState<InvestigationExport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadId, setLoadId] = useState(0);                                      // a new report must not inherit the previous report's page selection or scroll state
  const load = (text: string) => { const p = parseInvestigation(text); if (p.ok) { setData(p.data); setLoadId((n) => n + 1); setError(null); } else { setData(null); setError(p.error); } };
  const pick = async (k: Source) => load(JSON.stringify(await SOURCES[k].load()));
  useEffect(() => { void pick("public-synthetic"); }, []);
  return (
    <>
      <h2>Agent Readiness investigation</h2>
      <p className="lead">How well can an AI agent use this website, what gets in the way, what could change, and did the change help? One investigation, end to end.</p>
      <div className="loader">
        <label>Demo data <select aria-label="Demo data" defaultValue="public-synthetic" onChange={(e) => void pick(e.target.value as Source)}>{(Object.keys(SOURCES) as Source[]).map((k) => <option key={k} value={k}>{SOURCES[k].label}</option>)}</select></label>
        <label>Open an exported report <input type="file" accept="application/json,.json" onChange={async (e) => { const f = e.target.files?.[0]; if (f) load(await f.text()); }} /></label>
      </div>
      <p className="muted">Files are read in your browser only; nothing is uploaded. Create one with <code>readiness investigate export RUN_DIR --out report.json --public</code>. The example shown first is a labelled synthetic fixture, not an experimental result.</p>
      {error ? <Callout title="Cannot display this file" tone="bad"><p>{error}</p></Callout> : null}
      {data ? <InvestigationView key={loadId} d={data} /> : !error ? <p className="muted">No report loaded.</p> : null}
    </>
  );
}
