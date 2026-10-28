import { useEffect, useState } from "react";
import { Callout, Pill } from "../components/ui";
import { REPLAY_LABEL, cumulative, describeAction, hasVisibilityGap, loadReplays, visibilityLoop, type Manifest, type Replay } from "../lib/replay";
import { usd } from "../lib/metrics";

type Loaded = { manifest: Manifest; replays: Replay[] } | "missing" | "loading";

export function ReplayPage() {
  const [data, setData] = useState<Loaded>("loading");
  useEffect(() => { loadReplays().then((d) => setData(d ?? "missing")).catch(() => setData("missing")); }, []);
  return (
    <>
      <h1>Recorded replay</h1>
      <p className="replay-banner" role="note"><strong>{REPLAY_LABEL}.</strong> Each step below is a real step from a Task 007 run, replayed from a sanitized local export. Nothing is simulated and no model is called.</p>
      {data === "loading" && <p>Loading recorded data…</p>}
      {data === "missing" && <Missing />}
      {typeof data === "object" && <ReplayViewer replays={data.replays} manifest={data.manifest} />}
    </>
  );
}

export function Missing() {
  return (
    <Callout title="Replay data is not included in this build" tone="warn">
      <p>
        The sanitized trace export is <strong>development-only</strong>: it is generated locally from the preserved raw run artifacts and is not committed or published until the exact files and fields are approved.
        Nothing is faked in its place.
      </p>
      <p>To view it locally (requires the local <code>runs/pilot-task007/</code> artifacts):</p>
      <pre className="code">python3 dashboard/scripts/export_replay.py --audit{"\n"}cd dashboard && npm run dev</pre>
    </Callout>
  );
}

export function ReplayViewer({ replays, manifest }: { replays: Replay[]; manifest?: Manifest }) {
  const [idx, setIdx] = useState(replays.length - 1 >= 0 ? replays.length - 1 : 0);
  const [step, setStep] = useState(1);
  const rep = replays[idx];
  const n = rep.steps.length;
  const choose = (i: number) => { setIdx(i); setStep(1); };
  const s = rep.steps[Math.min(step, n) - 1];
  const loop = visibilityLoop(rep.steps);
  const cum = cumulative(rep.steps, s.step);
  const r = rep.run;
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowRight") { setStep((x) => Math.min(n, x + 1)); e.preventDefault(); }
    if (e.key === "ArrowLeft") { setStep((x) => Math.max(1, x - 1)); e.preventDefault(); }
  };
  const inLoop = loop !== null && s.step >= loop.first && s.step <= loop.last;
  return (
    <>
      <fieldset className="selector">
        <legend>Recorded run</legend>
        {replays.map((x, i) => (
          <label key={x.run.id} className={i === idx ? "chosen" : undefined}>
            <input type="radio" name="replay" checked={i === idx} onChange={() => choose(i)} />
            Fern · arm {x.run.arm} · <code>{x.run.id}</code> · {x.run.evaluator.passed ? "PASS" : "FAIL"}
          </label>
        ))}
      </fieldset>

      <section aria-labelledby="runhead" className="card">
        <h2 id="runhead">Run {r.id} — Fern, arm {r.arm} ({r.arm === "A" ? "availability on listing cards" : "availability on detail pages only"})</h2>
        <p>Task: “{r.task}”</p>
        <p>
          Independent evaluator: {r.evaluator.passed ? <Pill tone="pass">PASS</Pill> : <Pill tone="fail">FAIL</Pill>}{" "}
          answered <code>{r.answer_submitted.product_id}</code> (US${(r.answer_submitted.price_cents / 100).toFixed(2)}, available: {String(r.answer_submitted.available)}).{" "}
          Detail pages observed {r.observed_visits} / required {r.required_visits}
          {r.evaluator.passed
            ? <> · navigation overhead {r.overhead === 0 ? "0" : `+${r.overhead}`}</>
            : <> · <strong className="shortfall">verification shortfall {r.verification_shortfall?.detail_visit_shortfall}</strong> ({r.verification_shortfall?.higher_priced_checked} of {r.verification_shortfall?.higher_priced_candidates} higher-priced candidates checked) — incomplete verification, not an efficient short path</>}.
        </p>
        <p className="muted">
          {r.totals.requests} requests · {r.totals.prompt_tokens.toLocaleString()} prompt / {r.totals.completion_tokens.toLocaleString()} completion tokens · {usd(r.totals.estimated_cost_usd)} calculated estimate (not a bill) · {r.totals.elapsed_s} s.
          Request accounting (assumption, not a per-request classification): assumed required path {r.attribution.required_path_requests}, loop calls {r.attribution.tool_loop_requests},{" "}
          {r.attribution.residual_requests === null
            ? <>residual overhead <strong>not reported — not meaningful: the required path was not completed</strong> (a failed run is never read as efficiency).</>
            : <>residual {r.attribution.residual_requests}.</>}
        </p>
      </section>

      <section aria-labelledby="stepper" onKeyDown={onKey}>
        <h2 id="stepper">Step {s.step} of {n}</h2>
        <div className="stepper">
          <button onClick={() => setStep(Math.max(1, s.step - 1))} disabled={s.step === 1} aria-label="Previous step">← Previous</button>
          <input type="range" min={1} max={n} value={s.step} onChange={(e) => setStep(Number(e.target.value))} aria-label={`Step, 1 to ${n}`} aria-valuetext={`Step ${s.step} of ${n}`} />
          <button onClick={() => setStep(Math.min(n, s.step + 1))} disabled={s.step === n} aria-label="Next step">Next →</button>
        </div>
        <ol className="chips" aria-label="Steps">
          {rep.steps.map((x) => (
            <li key={x.step}>
              <button className={`chip${x.step === s.step ? " current" : ""}${hasVisibilityGap(x) ? " gap" : ""}${x.guard.final_step ? " final" : ""}`} onClick={() => setStep(x.step)} aria-current={x.step === s.step ? "step" : undefined} aria-label={`Step ${x.step}: ${x.actions[0]?.name ?? "no action"}${hasVisibilityGap(x) ? ", tool output not visible to the model" : ""}${x.guard.final_step ? ", final step" : ""}`}>{x.step}</button>
            </li>
          ))}
        </ol>
        <p className="muted">Chips: <span className="chip gap static">n</span> = the tool returned product links the model could not see; <span className="chip final static">n</span> = final step (done-only schema). Arrow keys step through the replay.</p>

        <div className="panels">
          <article className="panel" aria-labelledby="saw">
            <h3 id="saw">What the model saw</h3>
            <p className="muted">{s.page} · <code>{s.path}</code>{s.title ? <> · title <code>{s.title}</code></> : null}</p>
            <p><strong>Last result shown in its history:</strong> <code>{s.model_visible_last_result ?? "—"}</code></p>
            <details>
              <summary>Page text as given to the model (DOM view)</summary>
              <pre className="code" tabIndex={0}>{s.model_visible_dom}</pre>
            </details>
          </article>
          <article className="panel" aria-labelledby="did">
            <h3 id="did">What the agent did</h3>
            <ul>{s.actions.map((a, i) => <li key={i}><code>{describeAction(a)}</code></li>)}</ul>
            <p className="muted">
              Response format: {s.protocol === "raw_valid" ? "raw-valid JSON" : "compatibility-recovered (prose prefix removed; text not exported)"} · finish: {s.finish_reason}.
              Guard: schema {s.guard.schema}{s.guard.budget_warning ? " · budget warning shown" : ""}{s.guard.final_step ? " · final step" : ""}.
            </p>
            <p className="muted">Model reasoning, plans and goal text are intentionally not part of this export.</p>
          </article>
          <article className="panel" aria-labelledby="ret">
            <h3 id="ret">What the tool returned</h3>
            {s.tool_results.map((t, i) => (
              <div key={i}>
                <p><code>{t.action ?? "action"}</code>{t.error ? <> · error: <code>{t.error}</code></> : null}</p>
                <pre className="code" tabIndex={0}>{t.result_excerpt}{t.result_truncated ? "\n[excerpt truncated]" : ""}</pre>
              </div>
            ))}
            <p><strong>Shown to the model on its next request:</strong> <code>{s.result_visible_to_model_next_request ?? "— (final step)"}</code></p>
          </article>
        </div>

        {hasVisibilityGap(s) ? (
          <Callout title="Agent–tool interface gap at this step" tone="bad">
            The tool returned product links to the harness, but the model’s next request contained only <code>{s.result_visible_to_model_next_request}</code>. The agent therefore could not use the links and repeated the call.
            This is an <strong>agent–tool interface</strong> problem, not a storefront (website) problem.
          </Callout>
        ) : null}
        {loop && inLoop ? <p className="loopnote">This step is part of a loop: steps {loop.first}–{loop.last} are {loop.length} consecutive <code>{s.actions[0]?.name}</code> calls with the same visibility gap.</p> : null}

        <p className="muted tally">
          Through step {s.step}: {cum.requests} request{cum.requests === 1 ? "" : "s"}, {cum.prompt.toLocaleString()} prompt / {cum.completion.toLocaleString()} completion tokens, {usd(cum.cost)} calculated estimate, {cum.latency.toFixed(1)} s model time.
          This step: {s.usage.prompt_tokens.toLocaleString()} prompt / {s.usage.completion_tokens.toLocaleString()} completion{s.usage.reasoning_tokens !== null ? ` (${s.usage.reasoning_tokens} reasoning)` : ""} tokens, {s.latency_s} s, {usd(s.estimated_cost_usd)}.
        </p>
      </section>

      {loop && !r.evaluator.passed ? (
        <Callout title={`Why run ${r.id} failed`} tone="bad">
          Steps {loop.first}–{loop.last} are {loop.length} identical <code>{rep.steps[loop.first - 1].actions[0]?.name}</code> calls: the tool output reached the harness but not the model’s history, so the loop used the step budget.
          The run ended with {r.verification_shortfall?.higher_priced_checked} of {r.verification_shortfall?.higher_priced_candidates} higher-priced candidates checked and submitted <code>{r.answer_submitted.product_id}</code> (available: {String(r.answer_submitted.available)}).
          The independent evaluator marks this FAIL; the verification shortfall is {r.verification_shortfall?.detail_visit_shortfall}. The cause is the <strong>agent–tool interface</strong>, not the website.
        </Callout>
      ) : null}
      {manifest ? <p className="muted">Development-only export · schema <code>{manifest.schema}</code> · schedule <code>{manifest.schedule_sha256.slice(0, 12)}…</code> · executed from commit <code>{manifest.execution_commit}</code> · not published.</p> : null}
    </>
  );
}
