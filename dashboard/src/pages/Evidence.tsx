import { Callout, Pill } from "../components/ui";
import { allRuns, attribution, byArm, diffBA, failedRuns, protocol, stats, sum, toolLoopCalls, usd } from "../lib/metrics";
import { provenance } from "../data/task007";

export function Evidence() {
  const total = stats(allRuns);
  const proto = protocol(allRuns);
  const run27 = failedRuns()[0];
  const loopRuns = allRuns.filter((r) => toolLoopCalls(r) > 0);
  const loopCalls = sum(loopRuns.map(toolLoopCalls));
  const overheadRuns = allRuns.filter((r) => (r.overhead ?? 0) > 0);
  const A = stats(byArm(allRuns, "A")), B = stats(byArm(allRuns, "B"));
  const att27 = attribution(run27);
  return (
    <>
      <h1>Evidence and method</h1>
      <p className="lead">What the findings rest on, how each number was derived, and what the experiment cannot tell you.</p>

      <section aria-labelledby="findings">
        <h2 id="findings">Findings and their evidence</h2>
        <ol className="findings">
          <li><strong>Correctness is near ceiling.</strong> {total.passes} of {total.n} runs passed the independent evaluator (A {A.passes}/{A.n}, B {B.passes}/{B.n}); every pass had the answered product’s page observed and the higher-priced candidates ruled out. The benchmark therefore discriminates by effort, not accuracy.</li>
          <li><strong>Hiding availability on detail pages costs deterministic extra navigation.</strong> Arm B must open every higher-priced candidate; the cost grows with how many are out of stock (rank). Arm B’s extra website-required requests per run: {diffBA(allRuns).required.toFixed(1)} on average over scopes, with identical accuracy except the single tool-loop failure.</li>
          <li><strong>The agent adds its own overhead (reported separately).</strong> {overheadRuns.length} successful runs re-opened a page they had already seen (A {overheadRuns.filter((r) => r.arm === "A").length}, B {overheadRuns.filter((r) => r.arm === "B").length}); all of the positive overhead is re-opening the same page, never opening a wrong product.</li>
          <li><strong>One tool-interface defect, not a site defect.</strong> {loopRuns.length} runs ({loopRuns.map((r) => r.id).join(", ")}) repeated <code>find_elements</code> {loopCalls} times in total.</li>
          <li><strong>The Muse Spark agent needed protocol compatibility handling.</strong> {proto.rawValid} raw-valid, {proto.recovered} compatibility-recovered, {proto.rejected} rejected responses of {proto.total}; correctness is judged separately.</li>
        </ol>
      </section>

      <section aria-labelledby="run27">
        <h2 id="run27">Case study: run {run27.id} (independent evaluator FAIL)</h2>
        <Callout title="An incorrect, insufficiently verified outcome — not an efficient short path" tone="bad">
          <dl className="facts">
            <dt>Independent evaluator</dt><dd><Pill tone="fail">FAIL</Pill> answered {run27.answer.product_id} (${(run27.answer.price_cents / 100).toFixed(2)}, available: {String(run27.answer.available)}); the target was {run27.expected}.</dd>
            <dt>Required vs observed pages</dt><dd>required <strong>{run27.required_visits}</strong>, observed <strong>{run27.visits_trace.length}</strong> → verification shortfall <strong>{run27.shortfall?.detail_visit_shortfall}</strong> ({run27.shortfall?.higher_priced_checked} of {run27.shortfall?.higher_priced_candidates} higher-priced candidates checked). No overhead value is reported for a failed run.</dd>
            <dt>Mechanism</dt><dd>{toolLoopCalls(run27)} consecutive <code>find_elements</code> calls (steps {run27.find_elements[0].step}–{run27.find_elements[run27.find_elements.length - 1].step}). The tool returned the product links to the harness, but in all {run27.find_elements.length} calls the model-visible history kept only the line <code>Found 11 elements matching "a".</code> — the agent kept retrying until the 12-step budget was nearly gone.</dd>
            <dt>Attribution</dt><dd><strong>Agent–tool interface</strong> ({att27.tool} of {run27.requests} requests), not the storefront. Arm B’s assumed required path is {att27.required} requests; the run did not complete it (the loop used the step budget), so its residual ({att27.residual}) is not meaningful.</dd>
            <dt>Guard / harness</dt><dd>The final-step state was reached (request {run27.requests} of 12) and accepted as designed; the harness status reads “completed” only because the agent called <code>done</code>. Only the independent evaluator establishes failure.</dd>
          </dl>
        </Callout>
        <p className="muted">A step-by-step <em>Recorded experiment replay</em> of this run is on the Recorded replay page when the locally generated, sanitized export is present (development-only data; not published); nothing is simulated.</p>
      </section>

      <section aria-labelledby="method">
        <h2 id="method">Method in brief</h2>
        <ul>
          <li><strong>Fixture:</strong> a synthetic 20-product storefront; no checkout, accounts or real data.</li>
          <li><strong>Reference agent:</strong> Browser Use driving Meta Muse Spark (<code>{provenance.model}</code>), profile <code>{provenance.profile}</code>, {provenance.limits}.</li>
          <li><strong>Independent evaluator:</strong> grades the final answer against inventory truth, separate from what the agent claims.</li>
          <li><strong>Oracle:</strong> derives the minimum detail pages any correct agent needs (arm A 1; arm B = rank) from inventory truth alone. <em>Overhead</em> = observed − minimum, for successful runs only; failed runs report a <em>verification shortfall</em> instead.</li>
          <li><strong>Request accounting (an assumption, not a per-request classification):</strong> assumed required path (A 2 requests; B 2×rank) + loop calls (≥3 consecutive identical <code>find_elements</code> calls) + <strong>residual agent overhead</strong> = total requests. The residual bundles every other agent behaviour and is negative for run 27, whose required path was not completed.</li>
          <li><strong>Schedule:</strong> 30 runs, counterbalanced ABBAAB/BAABBA blocks per scope, executed once each from commit <code>{provenance.executionCommit}</code>; schedule SHA-256 <code>{provenance.scheduleSha256.slice(0, 12)}…</code>.</li>
        </ul>
      </section>

      <section aria-labelledby="gloss">
        <h2 id="gloss">Definitions</h2>
        <dl className="facts">
          <dt>Estimated (calculated) cost</dt><dd>Provider-reported prompt and completion tokens × published prices (US${provenance.pricePerMInputUsd}/M input, US${provenance.pricePerMOutputUsd}/M output). The provider reported no cost; this is not a bill. Total for all {total.n} runs: {usd(total.totalCost)}.</dd>
          <dt>Raw-valid / recovered / rejected</dt><dd>Whether the model’s reply was strict JSON as returned, JSON after stripping a single-line prose prefix (a documented compatibility parser), or unusable. This is output format, not answer correctness.</dd>
          <dt>Rank</dt><dd>Position of the correct answer when the scope is ordered by price, highest first; the number of detail pages arm B must open.</dd>
          <dt>Verification shortfall</dt><dd>Required detail pages − observed pages, only for failed runs; shows incomplete checking and is never an efficiency measure.</dd>
        </dl>
      </section>

      <section aria-labelledby="limits">
        <h2 id="limits">Limitations</h2>
        <ul>
          <li>One synthetic 20-product storefront, one model, one agent framework, one prompt; three runs per arm per scope; unseeded sampling; one pass of the schedule.</li>
          <li>Near-ceiling accuracy; statistics are descriptive. The negative control (Kitchen) did not behave as a clean null because of an agent–tool loop in one arm-A run.</li>
          <li>Arm A’s listing is slightly larger (extra availability lines), so the A/B contrast is an end-to-end bundle.</li>
          <li>Nothing here supports a claim about real e-commerce sites, other models, human users or a composite “agent readiness” score.</li>
        </ul>
      </section>

      <section aria-labelledby="prov">
        <h2 id="prov">Provenance and data</h2>
        <p>
          Data: <code>{provenance.dataPath}</code> (30 reconciled runs). Narrative and reproducibility scripts: <code>{provenance.reportPath}</code> and <code>collaboration/reports/007-pilot-data/</code>.
          Raw browser traces and screenshots are preserved locally, outside Git. This dashboard is a standalone static app: no backend, no API key, no live model calls.
        </p>
      </section>
    </>
  );
}
