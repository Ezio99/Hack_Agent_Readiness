import { Pill } from "./ui";
import { attribution, runFlags, secs, usd } from "../lib/metrics";
import type { Run } from "../data/task007";

/** One row per run. Overhead is shown for successful runs only; a failed run shows its verification shortfall instead. */
export function RunTable({ runs, caption }: { runs: Run[]; caption: string }) {
  return (
    <div className="table-wrap" tabIndex={0} role="region" aria-label={caption}>
      <table className="runs">
        <caption>{caption}</caption>
        <thead>
          <tr>
            <th scope="col">Run</th><th scope="col">Arm</th><th scope="col">Independent evaluator</th>
            <th scope="col">Detail pages: observed / required</th><th scope="col">Overhead or shortfall</th>
            <th scope="col">Requests (required · residual · tool)</th><th scope="col">Est. cost</th><th scope="col">Time</th><th scope="col">Evidence flags</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => {
            const att = attribution(r);
            const flags = runFlags(r).filter((f) => f !== "evaluator FAIL");
            return (
              <tr key={r.id} className={r.passed ? undefined : "row-fail"}>
                <th scope="row"><code>{r.id}</code></th>
                <td>{r.arm}</td>
                <td>{r.passed ? <Pill tone="pass">PASS</Pill> : <Pill tone="fail">FAIL</Pill>}</td>
                <td>{r.visits_trace.length} / {r.required_visits}</td>
                <td>
                  {r.passed
                    ? <span>overhead {r.overhead === 0 ? "0" : `+${r.overhead}`}</span>
                    : <span className="shortfall">verification shortfall {r.shortfall?.detail_visit_shortfall} <span className="muted">(not an efficiency gain)</span></span>}
                </td>
                <td>
                  {r.requests}{" "}
                  {r.passed
                    ? <span className="muted">({att.required} · {att.residual} · {att.tool})</span>
                    : <span className="muted">(tool loop {att.tool}; required path <strong>not completed</strong>, so no residual is reported)</span>}
                </td>
                <td>{usd(r.cost)}</td>
                <td>{secs(r.elapsed)}</td>
                <td>{flags.length ? flags.join("; ") : <span className="muted">—</span>}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
