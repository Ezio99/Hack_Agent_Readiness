# Which evaluation is canonical for the film? (audit, 2026-11-04; read-only, no paid call)

## The three live evaluations of the final experiment
All three use the same frozen task set (`db2eb1cb…`), the same site snapshots (Before `2ee4a7be…`, After `2a16c38b…`), the same agent (`muse-spark-1.3`, low reasoning effort) and the same limit (14 requests per task).

| | Diagnostic run: Before alone<br>`eval-ea13944e` | After alone<br>`eval-5cf934b3` | **Paired run: Before + After in one job**<br>`eval-1cf64d5e` |
|---|---|---|---|
| When (UTC) | 3 Nov 23:31 | 3 Nov 23:42 | 4 Nov 04:18 |
| Correct (exact match) | Before 0/3 (0/3) | After 3/3 (1/3) | Before 0/3 (0/3) → **After 3/3 (1/3)** |
| Model requests | 36 | 15 | **39 → 10 (−74%)** |
| Agent time | 310.6 s | 121.1 s | **326.1 s → 56.5 s (−83%)** |
| Model cost (settled) | US$0.5215 | US$0.2044 | **US$0.5715 → US$0.1335 (−77%)** |
| Course pages opened | 11 | 0 | 10 → 0 |
| Hero task 2 | Before: 11 of 14 requests, found 2 of 4 | After: 6 requests, 4 of 4 | Before: 13 of 14, found **1 of 4**; After: **3 requests, 18 s, 4 of 4** |
| Dead end (`/courses/introduction-to-python`) | yes (task 1, step 9) | n/a | none |
| Its report produced the recommendations | **yes**; the After site implements them (`modified_polished.py` cites this run) | | no (measured afterwards) |
| Shown publicly | Showcase, Home, submission text (36 → 15) | Showcase | **Live report** (`#/reports/latest`) and Workspace default |

**Trace quality:**
- All three have complete screenshots and notes.
- The paired Before task-2 trace is even stronger: its final note reads "Remaining 10 unchecked due to step budget". Two of its steps record an unrecognised action ("Other action"), which the film would show without an action label.
- The paired report shows Before and After side by side for each task, which suits the Act 4 footage.

## Recommendation: tell the story in the order it happened, with each run labelled
1. **Acts 1–3 stay on the diagnostic run** (`eval-ea13944e`): the agent's failure, the report's diagnosis, the dead end, and the three recommendations. This is the run whose report produced the fixes, so the story is literally true: measure → diagnose → fix.
   - On screen: "Recorded · 4 Nov 2026" (already there).
   - No rework is needed.
2. **Act 4 uses only the paired run** (`eval-1cf64d5e`) for every number and every piece of footage. It is labelled as the re-evaluation: Before and After in one evaluation, at the same time, with the same tasks, agent and limits.
   - **0/3 → 3/3; 74% fewer requests; 83% less time; 77% lower cost.**
   - These match what a judge sees on the public Live report.
   - The After hero trace (4 of 4 in 3 requests) comes from the same run.
3. **Never combine the two** in one number, chart or sequence. Act 2's task-level figures ("11 of 14", "2 of 4") appear only inside the diagnostic run's segment, under its own label.
4. **Retire the 36 → 15 numbers from the film.** The After-alone run (`eval-5cf934b3`) is not needed.

**Why not paired-only?**
- The paired run did not produce the recommendations, and it has no dead end. Rebuilding Acts 1–2 on it would mean taking the dead-end evidence from another run anyway.
- It would also cost about an hour of rework before the deadline.

**Why not the original separate runs?** The public Live report now shows the paired run, so a judge who clicks "Live report" would see different numbers from the film.

## Consequence outside the film (owner decision)
Home, the Showcase, `docs/FINAL_SUBMISSION.md` and the video storyboard still quote 0/3 → 3/3 with **36 → 15 requests, 58% / 61% / 61%** from the separate runs. If the film adopts the paired results, the submission text should quote the paired figures too.
- The Showcase can stay as it is: it is labelled with its own runs. But its headline would differ from the film and the Live report.
- That is a product and documentation change outside this branch, and it needs your approval.
