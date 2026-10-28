import { Callout, Kpi, PairedBars, AttributionBar, AttributionLegend, ARM_LABEL } from "../components/ui";
import { allRuns, attribution, byArm, diffBA, failedRuns, meanAttribution, protocol, secs, signed, signedUsd, stats, usd } from "../lib/metrics";
import { provenance } from "../data/task007";

export function Overview({ go }: { go: (p: "scopes" | "evidence") => void }) {
  const A = stats(byArm(allRuns, "A")), B = stats(byArm(allRuns, "B"));
  const total = stats(allRuns);
  const diff = diffBA(allRuns);
  const attA = meanAttribution(byArm(allRuns, "A")), attB = meanAttribution(byArm(allRuns, "B"));
  const proto = protocol(allRuns);
  const attMax = Math.max(attA.total, attB.total);
  return (
    <>
      <section aria-labelledby="hero">
        <h1 id="hero">Two sites show the same products. One makes the AI agent work harder.</h1>
        <p className="lead">
          Agent Readiness shows a website developer <strong>what a Meta Muse Spark–powered shopping agent did</strong>, <strong>why it cost more effort on one design</strong> and{" "}
          <strong>what to change</strong>. The numbers below come from a controlled experiment (Task 007): {total.n} recorded runs on one synthetic 20-product storefront.
        </p>
        <Callout title="Recorded experiment data — not a live demo" tone="info">
          Every figure is read from the committed, reconciled Task 007 per-run data (<code>{provenance.dataPath}</code>). Nothing here is live inference or simulated.
          Costs are <strong>calculated estimates</strong> from provider-reported token counts at published prices (US${provenance.pricePerMInputUsd}/M input, US${provenance.pricePerMOutputUsd}/M output), not bills.
        </Callout>
      </section>

      <section aria-labelledby="headline">
        <h2 id="headline">Headline results</h2>
        <div className="kpis">
          <Kpi label="Runs" value={total.n} note="5 task scopes × 2 arms × 3 runs" />
          <Kpi label="Independent evaluator PASS" value={`${total.passes} / ${total.n}`} tone="good" note={`Arm A ${A.passes}/${A.n} · Arm B ${B.passes}/${B.n}. An agent saying "done" is not the same as a correct answer.`} />
          <Kpi label="Model requests per run" value={<><span className="a">{A.requests.toFixed(2)}</span> vs <span className="b">{B.requests.toFixed(2)}</span></>} note="Arm A vs Arm B (mean)" />
          <Kpi label="Estimated cost per run" value={<><span className="a">{usd(A.cost)}</span> vs <span className="b">{usd(B.cost)}</span></>} note="calculated estimate, Arm A vs Arm B" />
          <Kpi label="Time per run" value={<><span className="a">{secs(A.elapsed)}</span> vs <span className="b">{secs(B.elapsed)}</span></>} note="Arm A vs Arm B (mean elapsed)" />
        </div>
        <div className="grid2">
          <PairedBars title="Model requests per run (mean)" a={A.requests} b={B.requests} format={(x) => x.toFixed(2)} />
          <PairedBars title="Estimated cost per run (mean, calculated)" a={A.cost} b={B.cost} format={(x) => usd(x)} />
          <PairedBars title="Elapsed time per run (mean)" a={A.elapsed} b={B.elapsed} format={secs} />
        </div>
        <p className="muted">
          Difference (B − A, mean per run): {signed(diff.requests)} requests, {signedUsd(diff.cost, 4)} estimated cost, {signed(diff.elapsed, 1)} s. Spread is large: arm A cost ranged from {usd(A.costMin)} to {usd(A.costMax)} per run,
          arm B from {usd(B.costMin)} to {usd(B.costMax)} (see the <button className="linklike" onClick={() => go("scopes")}>scope comparison</button>).
        </p>
      </section>

      <section aria-labelledby="what">
        <h2 id="what">What was tested</h2>
        <div className="grid2">
          <div className="card arm-a"><h3>{ARM_LABEL.A}</h3><p>Each product card on the listing page shows “In stock” or “Out of stock”. The agent can read availability without opening a product.</p></div>
          <div className="card arm-b"><h3>{ARM_LABEL.B}</h3><p>The listing shows name, brand, category and price only. Availability and the product ID are on each product’s detail page.</p></div>
        </div>
        <p>
          Everything else is identical: inventory, prices, product IDs, task wording, the independent evaluator and the agent configuration. The task is
          “Find the most expensive <em>scope</em> product that is currently in stock” — the answer needs the product ID, which is only on the detail page, so both arms must open the answer’s page; arm B must additionally open every higher-priced candidate to learn that it is out of stock.
        </p>
      </section>

      <section aria-labelledby="why">
        <h2 id="why">Why did arm B cost more? Separating three sources</h2>
        <AttributionLegend />
        <div className="stack">
          <AttributionBar arm="A" att={attA} max={attMax} />
          <AttributionBar arm="B" att={attB} max={attMax} />
        </div>
        <table className="mini">
          <caption>Mean model requests per run by source</caption>
          <thead><tr><th scope="col">Arm</th><th scope="col">Assumed website-required path</th><th scope="col">Residual agent overhead</th><th scope="col">Agent–tool interface loop</th><th scope="col">Total</th></tr></thead>
          <tbody>
            <tr><th scope="row">A</th><td>{attA.required.toFixed(2)}</td><td>{attA.residual.toFixed(2)}</td><td>{attA.tool.toFixed(2)}</td><td>{attA.total.toFixed(2)}</td></tr>
            <tr><th scope="row">B</th><td>{attB.required.toFixed(2)}</td><td>{attB.residual.toFixed(2)}</td><td>{attB.tool.toFixed(2)}</td><td>{attB.total.toFixed(2)}</td></tr>
            <tr><th scope="row">B − A</th><td><strong>{signed(diff.required)}</strong></td><td>{signed(diff.residual)}</td><td>{signed(diff.tool)}</td><td>{signed(diff.requests)}</td></tr>
          </tbody>
        </table>
        <Callout title="How this accounting works" tone="info">
          <p>
            Requests are <strong>not classified one by one</strong>. For each run: <em>required path</em> is assumed from the task (A 2; B 2 × rank), <em>loop calls</em> are the repeated <code>find_elements</code> calls in the three loop runs, and the <strong>residual</strong> is total requests minus those two. The residual is therefore an unclassified remainder, not a measured “agent fault”.
            For the failed run 27 the required path was <em>not completed</em> (it opened 1 of 3 required pages), so its “required” share is an assumed path and its residual is negative ({attribution(failedRuns()[0]).residual}); excluding failed runs, arm B’s mean residual is {meanAttribution(byArm(allRuns, "B").filter((r) => r.passed)).residual.toFixed(2)} (all runs: {attB.residual.toFixed(2)}).
          </p>
        </Callout>
        <ul>
          <li><strong>Assumed website-required path</strong> is deterministic: a click and a back-step per higher-priced candidate, then the answer (arm A: 2 requests; arm B: 2 × rank). It is the part a page design causes.</li>
          <li><strong>Residual agent overhead</strong> is what remains: total requests − required path − loop calls. It bundles every other agent behaviour (re-opening a page it had already seen, “be thorough” detours, applying filters, backtracking); it occurs in both arms and is as large as the website effect in some cells.</li>
          <li><strong>Agent–tool interface</strong> is {allRuns.filter((r) => r.find_elements.length >= 3).length} runs where repeated <code>find_elements</code> calls returned links to the harness but the model-visible history kept only a count line. That is an agent/tool defect, <em>not</em> a storefront defect.</li>
        </ul>
      </section>

      <section aria-labelledby="rec">
        <h2 id="rec">Evidence-backed recommendation</h2>
        <Callout title="Show stock status on listing cards for stock-sensitive tasks" tone="good">
          <p>
            When shoppers (or agents) must pick the best <em>in-stock</em> item, surfacing availability on the listing removes the detail-page checks that arm B needs: in this storefront that deterministic cost was <strong>{signed(diff.required, 1)} requests per run</strong> on average (growing with how many higher-priced items are out of stock), with similar accuracy (A 15/15, B 14/15 — the one failure was an agent–tool interface loop, see Evidence).
          </p>
          <p className="muted">
            Limits of this evidence: one synthetic 20-product storefront, one model and agent framework, three repetitions per cell, near-ceiling success, exploratory statistics. This does not show how real websites behave and is not a readiness score.
          </p>
        </Callout>
        <p><button className="primary" onClick={() => go("scopes")}>Compare by scope →</button> <button onClick={() => go("evidence")}>See the evidence and method →</button></p>
      </section>

      <section aria-labelledby="muse">
        <h2 id="muse">Where Meta Muse Spark fits</h2>
        <p>
          The measurement instrument is a browser agent driven by <strong>Meta Muse Spark</strong> (<code>{provenance.model}</code>, profile <code>{provenance.profile}</code>): every navigation decision in these runs is a Muse Spark response —
          <strong> {proto.total} model responses across {total.n} runs</strong>. Reading what it actually did is the diagnostic.
        </p>
        <div className="kpis">
          <Kpi label="Raw-valid responses" value={`${proto.rawValid} / ${proto.total}`} note="strict JSON, accepted as returned" />
          <Kpi label="Compatibility-recovered" value={`${proto.recovered} / ${proto.total}`} note={`prose sentence before the JSON action; ${proto.firstStepsRecovered}/${proto.firstSteps} first steps`} />
          <Kpi label="Rejected" value={`${proto.rejected} / ${proto.total}`} note="no response was unusable" />
        </div>
        <p className="muted">Protocol compliance describes the model’s output format, not whether the answer was right; correctness is decided only by the independent evaluator. Without the compatibility step a strict-format agent would have failed at its first action.</p>
      </section>

      <section aria-labelledby="limits">
        <h2 id="limits">What this dashboard does not claim</h2>
        <ul>
          <li>No universal “agent readiness” score and no claim about real websites, other models, other agent frameworks or human shoppers.</li>
          <li>Exploratory results: three runs per arm per scope; differences are descriptive, not confirmatory tests.</li>
          <li>No live agent run is performed here; trace replay is planned for a later stage and will be labelled <em>Recorded experiment replay</em>.</li>
        </ul>
      </section>
    </>
  );
}
