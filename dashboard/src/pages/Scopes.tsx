import { useState } from "react";
import { AttributionBar, AttributionLegend, Callout, PairedBars, Pill } from "../components/ui";
import { RunTable } from "../components/RunTable";
import { allRuns, byArm, byScope, diffBA, meanAttribution, runFlags, scopes, secs, signed, signedUsd, stats, toolLoopCalls, usd } from "../lib/metrics";
import type { Scope } from "../data/task007";

type Sel = "All" | Scope;

export function Scopes({ initial = "All" }: { initial?: Sel }) {
  const [sel, setSel] = useState<Sel>(initial);
  const rs = sel === "All" ? allRuns : byScope(allRuns, sel);
  const A = stats(byArm(rs, "A")), B = stats(byArm(rs, "B"));
  const attA = meanAttribution(byArm(rs, "A")), attB = meanAttribution(byArm(rs, "B"));
  const d = diffBA(rs);
  const attMax = Math.max(attA.total, attB.total);
  const info = sel === "All" ? null : scopes.find((s) => s.scope === sel)!;
  const failed = rs.filter((r) => !r.passed);
  const loops = rs.filter((r) => runFlags(r).some((f) => f.startsWith("agent–tool")));
  const revisited = rs.filter((r) => r.revisits > 0);
  const ovh = (x: ReturnType<typeof stats>) =>
    x.overheadMean === null ? "—" : `${x.overheadMean > 0 ? "+" : ""}${x.overheadMean.toFixed(2)} (${x.overheadRuns} of ${x.successfulRuns} successful runs above 0)`;
  const okMean = (arm: "A" | "B") => {
    const ok = byArm(rs, arm).filter((r) => r.passed);
    return ok.length ? `${(ok.reduce((a, r) => a + r.visits_trace.length, 0) / ok.length).toFixed(2)} (${ok.length} of ${byArm(rs, arm).length} runs)` : "—";
  };
  const cell = (label: string, a: React.ReactNode, b: React.ReactNode) => (
    <tr><th scope="row">{label}</th><td>{a}</td><td>{b}</td></tr>
  );
  return (
    <>
      <h1>Compare by scope</h1>
      <p className="lead">Pick a task scope to see how the two storefront designs compared on the same task, with every contributing run listed.</p>
      <fieldset className="selector">
        <legend>Task scope</legend>
        {(["All", ...scopes.map((s) => s.scope)] as Sel[]).map((s) => (
          <label key={s} className={sel === s ? "chosen" : undefined}>
            <input type="radio" name="scope" value={s} checked={sel === s} onChange={() => setSel(s)} />
            {s === "All" ? "All scopes" : `${s} (rank ${scopes.find((x) => x.scope === s)!.rank})`}
          </label>
        ))}
      </fieldset>

      <section aria-labelledby="task">
        <h2 id="task">{sel === "All" ? "Five scopes, one task shape" : `${sel} scope`}</h2>
        {info ? (
          <p>
            Task: “Find the most expensive <strong>{info.scope}</strong> product that is currently in stock.” The correct answer is the <strong>rank {info.rank}</strong> product when the scope is ordered by price (highest first):
            arm B must open <strong>{info.rank}</strong> detail page{info.rank > 1 ? "s" : ""} to establish it ({info.rank - 1} higher-priced candidate{info.rank > 2 ? "s" : ""} to rule out, then the answer); arm A can read availability on the listing and opens only the answer’s page (<strong>1</strong>).
            {info.rank === 1 && " Rank 1 is the planned control: the most expensive product is already in stock, so both arms need the same single page."}
          </p>
        ) : (
          <p>Kitchen (rank 1, control), Bags (rank 2), and Home, Outdoors and Fern (rank 3). Rank is the number of detail pages arm B must open; arm A always needs one.</p>
        )}
      </section>

      <section aria-labelledby="cmp">
        <h2 id="cmp">Arm A vs arm B</h2>
        <div className="table-wrap" tabIndex={0} role="region" aria-label="Per-arm comparison table">
          <table className="cmp">
            <caption>{sel === "All" ? "All 30 runs" : `${sel}: 6 runs`} — means unless stated. Estimated cost is calculated from tokens, not billed.</caption>
            <thead><tr><th scope="col">Measure</th><th scope="col" className="a">A · availability on listing cards</th><th scope="col" className="b">B · availability on detail pages only</th></tr></thead>
            <tbody>
              {cell("Independent evaluator PASS", `${A.passes} / ${A.n}`, `${B.passes} / ${B.n}`)}
              {cell("Model requests per run", `${A.requests.toFixed(2)} (range ${A.requestsMin}–${A.requestsMax})`, `${B.requests.toFixed(2)} (range ${B.requestsMin}–${B.requestsMax})`)}
              {cell("Estimated cost per run", `${usd(A.cost)} (${usd(A.costMin, 3)}–${usd(A.costMax, 3)})`, `${usd(B.cost)} (${usd(B.costMin, 3)}–${usd(B.costMax, 3)})`)}
              {cell("Elapsed time per run", secs(A.elapsed), secs(B.elapsed))}
              {cell("Detail pages observed / required (mean, all runs)", `${A.visits.toFixed(2)} / ${A.required.toFixed(2)}`, `${B.visits.toFixed(2)} / ${B.required.toFixed(2)}${failed.some((r) => r.arm === "B") ? " — includes failed run" : ""}`)}
              {failed.length ? cell("Detail pages observed (successful runs only)", okMean("A"), okMean("B")) : null}
              {cell("Navigation overhead, successful runs only", ovh(A), ovh(B))}
              {cell("Runs re-opening an already-seen page", `${A.revisitRuns} (${A.extraOpenings} extra openings)`, `${B.revisitRuns} (${B.extraOpenings} extra openings)`)}
              {cell("Runs with an agent–tool loop", A.loopRuns, B.loopRuns)}
              {cell("Runs with a verification shortfall", A.shortfallRuns, B.shortfallRuns)}
            </tbody>
          </table>
        </div>
        <p className="muted">Overhead = observed detail pages − independently derived minimum, reported for <strong>successful runs only</strong>. A failed run is never shown as “fewer pages = more efficient”: it carries a verification shortfall instead.</p>
        {failed.length ? (
          <p className="muted">
            <strong>Reading the “observed” means:</strong> {failed.map((r) => `${r.id} (arm ${r.arm})`).join(", ")} is included in the all-runs mean above although it opened only {failed.map((r) => r.visits_trace.length).join(", ")} of {failed.map((r) => r.required_visits).join(", ")} required pages because it did not finish the verification. That lowers the arm’s mean observed pages; it is <em>incomplete verification, not better efficiency</em>. The successful-runs-only row shows the comparable figure.
          </p>
        ) : null}
        <div className="grid2">
          <PairedBars title="Model requests per run" a={A.requests} b={B.requests} format={(x) => x.toFixed(2)} />
          <PairedBars title="Estimated cost per run (calculated)" a={A.cost} b={B.cost} format={(x) => usd(x)} />
          <PairedBars title="Elapsed time per run" a={A.elapsed} b={B.elapsed} format={secs} />
        </div>
        <p>B − A (mean per run): <strong>{signed(d.requests)} requests</strong>, <strong>{signedUsd(d.cost)} estimated cost</strong>, {signed(d.elapsed, 1)} s.</p>
      </section>

      <section aria-labelledby="why">
        <h2 id="why">Where the requests came from</h2>
        <AttributionLegend />
        <div className="stack">
          <AttributionBar arm="A" att={attA} max={attMax} />
          <AttributionBar arm="B" att={attB} max={attMax} />
        </div>
        <p>
          B − A requests {signed(d.requests)} = <strong>{signed(d.required)} assumed website-required path</strong> {signed(d.residual)} residual agent overhead {signed(d.tool)} agent–tool interface loop.
          The required path is deterministic. The <em>residual</em> is an unclassified remainder (total − required path − loop calls), not a per-request classification; for a run that did not complete the required path (a failed run) it can be negative and should not be read as efficiency.
        </p>
        {sel !== "All" && info && info.rank === 1 && d.requests < 0 ? (
          <Callout title="The control did not behave like a clean null" tone="warn">
            Both arms need one page here, yet arm B used {Math.abs(d.requests).toFixed(1)} fewer requests per run. The difference traces to {loops.length} agent–tool loop{loops.length === 1 ? "" : "s"} ({loops.map((r) => r.id).join(", ")}): {Math.abs(d.residual) < 0.05 ? "the residual was equal across the arms, so the loop accounts for the whole gap" : `the loop accounts for ${signed(d.tool)} of it and other agent behaviour for ${signed(d.residual)}`} — not the storefront design.
          </Callout>
        ) : null}
        {failed.length ? (
          <Callout title={`Independent evaluator FAIL: ${failed.map((r) => r.id).join(", ")}`} tone="bad">
            {failed.map((r) => (
              <p key={r.id}>
                <strong>{r.id}</strong> (arm {r.arm}): required <strong>{r.required_visits}</strong> detail pages, observed <strong>{r.visits_trace.length}</strong> → <strong>verification shortfall {r.shortfall?.detail_visit_shortfall}</strong>; {r.shortfall?.higher_priced_checked} of {r.shortfall?.higher_priced_candidates} higher-priced candidates checked. Answered an out-of-stock product. This is an incorrect, insufficiently verified outcome{toolLoopCalls(r) > 0 ? ` after an agent–tool interface loop (${toolLoopCalls(r)} repeated find_elements calls) used the step budget` : ""} — <em>not</em> an efficient short path.
              </p>
            ))}
          </Callout>
        ) : null}
        {revisited.length ? <p className="muted">Re-opened an already-seen page: {revisited.map((r) => `${r.id}${r.revisits > 1 ? ` ×${r.revisits}` : ""}`).join(", ")}.</p> : null}
      </section>

      <section aria-labelledby="runs">
        <h2 id="runs">Run-level evidence</h2>
        <RunTable runs={rs} caption={`${sel === "All" ? "All runs" : `${sel} runs`}: outcome, navigation and cost per run`} />
        <p className="muted">Legend: <Pill tone="pass">PASS</Pill> / <Pill tone="fail">FAIL</Pill> are the independent evaluator’s verdicts. “Requests (required · agent · tool)” splits each run’s model requests into the assumed website-required path, the residual agent overhead and agent–tool interface loop calls (“not completed” for a failed run). Raw traces are kept locally; see the Recorded replay page for the three runs available locally.</p>
      </section>
    </>
  );
}
