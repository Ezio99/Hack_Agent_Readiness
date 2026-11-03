# Independent A$20 evaluation budget and actual-cost accounting: review and implementation plan (NOT implemented)

**Date:** 2026-11-03 (Sydney). **Branch:** `final-showcase` (production `dde7e22`, image `d40199ef…`). **Cost:** US$0. Read-only review; nothing deployed, migrated, settled or launched.
**Owner requirements (2026-11-03):** a new, independent **A$20** budget for further evaluations and development, starting at A$20 available; historical costs and reservations never reduce it; only spending explicitly assigned to it counts; tracked apart from the A$50 programme; no transfer or double count; 1.50 AUD/USD. Actual settled cost is expenditure, a reservation is a temporary safety commitment. Existing judge launches are **not** assumed to belong to the new budget.

## 1. Review of the current implementation

| # | Requirement | Today (`dde7e22`) | Gap |
|---|---|---|---|
| 1 | Verified, fully settled runs contribute only their actual cost | Yes for the hosted ceiling: `settlements` (write-once) replaces a job's reservation by its ledger-verified cost; automatic for jobs admitted by `dde7e22`, owner CLI for historical ones | None for the ceiling. There is no budget to apply it to (gap 5) |
| 2 | Unused reservation released after reconciliation | Yes (`released = reserved − settled`, derived; `jobs.reserved` never rewritten) | None |
| 3 | Active/uncertain jobs keep conservative reservations | Yes: running, interrupted and failed jobs with unsettled requests keep their full reservation; owner recovery commits unsettled requests at their bound, never at zero | None |
| 4 | No double counting | Programme view matches a hosted job to the programme ledger by **substring** of the job id in the entries' JSON (`programme_view`) | **Fragile.** A label mentioning a job id would hide a real cost, and nothing prevents one job appearing in two ledgers. Needs a structured `hosted_job` field and a disjointness check |
| 5 | Budget enforces actual + outstanding of its own jobs | One global hosted ceiling over **all** jobs (`committed = settled + outstanding`) | **No budget concept.** Jobs carry no budget, and armings carry no budget |
| 6 | Historical spend/holds never reduce the new budget | The ceiling's available amount (US$10.588) is reduced by historical holds (e529 US$7.436, Ironbark US$3.300) | **A new-budget launch would compete with historical holds** under the shared ceiling |
| 7 | Hosted ceiling ≠ expenditure ≠ budget | Workspace panel says "Actual model spend US$0.63 … of the US$21.96 hosted budget" (hosted-only figures, ceiling called a budget); the programme view uses the ceiling's available amount as exposure | **Wording and model conflate them.** US$0.63 is hosted settled cost, not programme spend (US$19.42) |
| 8 | Ironbark reconciliation without guessing | Refused (`exceeds_reservation`): each repetition ledger also contains the source run's entries | **Provable now (see §6):** the forks are byte-exact prefixes of a pinned source ledger |
| – | Off-host paid work (local research CLIs) | Per-experiment caps and ledgers; no programme- or budget-level atomic check | The new budget must cover it explicitly (§3.4) |

Rules 1–3 are already right for hosted jobs. The work is to add budgets as a separate dimension, fix the wording and the programme-ledger matching, and add a fork-prefix verification rule.

## 2. Representation and isolation of the A$20 budget

**Authoritative store:** new additive tables in the hosted admission database. The job's reservation, its budget assignment and the budget check happen in **one** `BEGIN IMMEDIATE` transaction, so concurrent launches can never exceed either limit.

```sql
budgets(id TEXT PRIMARY KEY,                -- e.g. 'ar-a20-2026-11'
        limit_micro_aud INTEGER NOT NULL,   -- 20_000_000
        rate_num INTEGER NOT NULL, rate_den INTEGER NOT NULL,   -- AUD per USD as 3/2 (=1.50): integer arithmetic, no floats
        opened_at REAL, opened_by TEXT, attestation TEXT)        -- write-once, owner TTY only
budget_jobs(job_id TEXT PRIMARY KEY REFERENCES jobs(id), budget_id TEXT NOT NULL, at REAL)   -- written with the reservation
budget_external(ref TEXT PRIMARY KEY, budget_id, max_microusd, ledger_sha256 UNIQUE, settled_microusd NULL, ...)  -- off-host work (§3.4)
```

- **A$ amounts:** each job's USD amount is converted with a ceiling division, `ceil(µUSD × 3 / 2)` µAUD. A$ figures are rounded up, never down.
- **Budget figures:**
  - spent = Σ settled cost of its settled jobs and external charges;
  - outstanding = Σ full reservation of its unsettled jobs and open external allocations;
  - **available = A$20 − spent − outstanding.**
- **Isolation:**
  - A job belongs to **at most one** budget (primary key).
  - Jobs with no `budget_jobs` row are **legacy**, meaning the A$50 programme. That covers all four existing jobs and every launch of `larkspur-judge-1`.
  - A budget's figures are computed only from its own rows, so historical spend and holds cannot reach it.
  - There are no transfer operations.
- **Write-once and auditable:** opening the budget is an owner terminal action (`python -m agent_readiness.hosted.budget open --id ar-a20-2026-11 --limit-aud 20 --rate 1.50`, typed confirmation). The rate is fixed when the budget is opened. Any later rate change needs a new owner-approved budget, so earlier figures are never re-valued.
- **Read-only statement:** `budget status --id …` and a JSON export (`collaboration/budget/budget-ar-a20-2026-11.json`, generated, never hand-edited) list every assigned job and external charge with its reservation, settlement and ledger sha256.

## 3. Assigning runs to a budget

1. **Through the owner's arming, never by default.** A new arming schema `hosted-arming-v2` adds a required `budget` field. Existing `hosted-arming-v1` records stay parseable and byte-identical; they mean legacy. Adding an optional field to v1 is avoided because that would change existing records' hashes. `arming prepare/arm --budget ar-a20-2026-11` prints the budget figures, and the owner's typed attestation names the budget.
2. **Admission (atomic).** In one transaction, `reserve_amount(job, client, µUSD, budget=…)` checks:
   - the single slot and the rate limit (unchanged);
   - the budget: spent + outstanding + this reservation ≤ limit;
   - the ceiling scope (§5).

   It then inserts the `jobs`, `auto_settle` and `budget_jobs` rows together. If any check fails, nothing is written.
3. **Settlement** is unchanged. When the job ends with a fully settled ledger, its `settlements` row moves the job from "outstanding" to "spent" at its actual cost, in its budget and in the ceiling at once. Failed or interrupted jobs with unsettled requests keep their full reservation in the budget until the owner's recovery commits them at their bound.
4. **Off-host work (development, task generation, research runs).** The owner records an **external allocation** in the budget first (`budget allocate --ref … --max-usd …`, terminal). The local run is configured with an experiment cap ≤ the allocation. Afterwards `budget settle-external --ref … --ledger <path>` verifies the local ledger like a hosted one and records the actual cost. The ledger sha256 is unique, so one ledger cannot be charged twice. An allocation that is never settled stays outstanding at its maximum. Off-host spending therefore counts in the budget, and its worst case is held before any request is sent.

## 4. Actual cost vs reservation tracking

Already separate, and kept that way:
- **Reservations:** `jobs.reserved`, never rewritten.
- **Actual costs:** `settlements`, write-once, ledger-verified.
- **Assignment:** `budget_jobs`.
- **Budget figures:** derived only, never stored.

**Programme ledger (A$50, file):**
- It records only actual verified costs, never reservations.
- New hosted entries carry a structured `hosted_job` field.
- `programme_view` matches on that field, plus explicit ids for the two existing Ironbark entries and `hosted-stageb-live-1`, instead of a substring match.
- A test fails if any job is in both the programme ledger and a budget, or appears twice.
- Jobs assigned to the A$20 budget are never appended to the A$50 ledger.

## 5. Does the hosted admission ceiling need restructuring?

Yes, in scope, not in value. Today one ceiling (US$21.956) covers every job, so historical holds (US$10.736 still outstanding) limit what a new-budget launch could use. That contradicts requirement 6.

- **Option A (recommended): scope the ceiling to legacy jobs.**
  - `policy.ceiling` keeps its value and meaning for jobs without a budget.
  - New-budget jobs are bounded by their budget only.
  - Total hosted exposure is legacy ceiling + Σ budget limits, both fixed by the owner.
  - **Rollback-safe:** an older image counts budget jobs against the legacy ceiling too, which is more conservative.
  - No ceiling value changes.
- **Option B: keep one host-wide cap and check both.** Simpler semantics, but a new-budget launch needs ceiling room. At US$10.588 available, the 2 remaining legacy launches and new-budget launches compete. To isolate the budget fully, the ceiling would have to rise by US$13.333 (a ceiling change).

The dashboard copy is fixed in either case:
- **Budget panel:**
  - "Hosted admission ceiling (a safety cap, not a budget)" with its own reserved and available figures;
  - "Evaluation budget A$20: spent, held, available, launches it covers";
  - the programme figures separately.
- **History Cost column:** per-job actual cost and the budget it was charged to.
- **Owner reporting:** the A$50 programme, using actual costs plus authorised exposure.

## 6. Historical jobs and existing judge launches

**Legacy (A$50 programme), not the new budget:**
- the four existing jobs;
- `larkspur-judge-1` and its 2 remaining launches;
- any further launch under a v1 arming.

**Ironbark: verified without guessing (read-only, production files):**
- The source run's ledger is `live-2d58a80e14/spend/ledger.jsonl`: sha256 `90bbc68f6b30…`, 126 lines, 63/63 settled, US$0.864825. It is mounted read-only in the production container and recorded once in the programme ledger as `ironbark-source`.
- For both Ironbark repetition ledgers, the first 126 lines hash to exactly `90bbc68f…`, so they are byte-exact forks.
- Their own increments are:

| Job | Own increment | Matches programme ledger entry |
|---|---|---|
| `eval-9aaac35c` | 76/76 settled, US$1.090968 | `hosted-live-1` |
| `eval-aa23e330` | 78/78 settled, US$1.126097 | `hosted-live-2` |

- Neither increment has open requests, any request settled above its own reservation, or an id shared with the source run, and each is ≤ the job's US$1.650 reservation.

**Proposed rule `fork-prefix-1`.** A ledger whose first N lines are byte-identical to a pinned, separately recorded source ledger is assessed on its remaining lines only, so the job is settled at its own increment.
- It applies only to the pinned source sha256.
- It refuses if the prefix differs by a single byte.
- Ledgers and job records are not modified.

Settling both Ironbark jobs (owner terminal, separate approval) would commit US$2.217065 and release US$1.082935 of the legacy ceiling. The programme ledger already holds both amounts, so nothing is added there.

**`eval-e529`:** eligible (US$1.546226, already in the programme ledger). Settling it releases US$5.889774 of legacy ceiling. With Option A that only matters for legacy launches, and §7 shows the effect on the A$50 hard bound.

## 7. Resulting capacity (USD × 1.50 = A$)

**New A$20 budget** (after it is opened):
- spent A$0, outstanding A$0, **available A$20.00 (US$13.333)**.
- One launch of the current three-task option reserves US$3.740 = A$5.61, so it covers **3 launches** (A$16.83 held, A$3.17 free).
- At the observed actual cost (US$0.631751 = A$0.95 per launch), about 21 completed launches would fit, but admission always holds the full reservation until each run settles.

**A$50 programme (legacy):**
- Actual expenditure US$19.418057 = **A$29.13**. That is the US$18.786306 in the ledger plus `eval-c04fdb10` US$0.631751, which is verified but still awaits your approval to append.
- Outstanding exposure, depending on the bound used:

| Bound | Exposure | Total |
|---|---|---|
| Authorised (arming: 2 × US$3.740) | US$7.480 | US$26.898057 = **A$40.35** |
| Hard (all available legacy ceiling, today) | US$10.588 | **A$45.01** |
| Hard, after settling Ironbark too | US$11.671 | A$46.63 |
| Hard, after settling e529 as well | US$17.561 | A$55.47, over the limit: only with a lower ceiling (§2 of hosted-settlement.md) |

**Hosted admission ceiling:** US$21.956 (a safety cap, not expenditure): reserved US$14.476, settled US$0.631751, outstanding US$10.736, available US$10.588249.

## 8. Implementation, migration, testing, rollback

**Implementation (one release):**
- `hosted/budget.py` (tables, figures, owner CLI: open/status/allocate/settle-external, all typed confirmations at a terminal);
- `Admission.reserve_amount(..., budget=None)` with the scoped ceiling (Option A) or both checks (Option B);
- `hosted-arming-v2` with `budget`;
- `settlement.py`: `fork-prefix-1` (pinned source sha256) and the structured programme matching;
- API `spending`: separate `ceiling`, `budgets[]` and (owner reporting) programme blocks;
- workspace panel and history copy;
- the `programme-ledger.json` structured `hosted_job` field on **new** entries. Existing entries are unchanged; the matching table for them lives in code.

**Tests (zero cost):**
- isolation (historical jobs and holds never change budget figures);
- exact limit (+1 µAUD refused) with integer AUD conversion;
- 8 concurrent launches across legacy and budget scopes on separate connections, with neither limit exceeded;
- a failed or interrupted budget job keeps its reservation;
- settlement moves outstanding to spent in the budget and the ceiling together;
- disjointness (a job in two budgets, or in the A$50 ledger and a budget, fails);
- external allocations (duplicate ledger refused; unsettled allocation held at its maximum);
- `hosted-arming-v1` records byte-identical and legacy;
- the fork-prefix rule on the real production copies (1.090968 / 1.126097; a one-byte change refuses);
- the rollback image (`dde7e22`) on a database with budget rows (it ignores them and counts budget jobs against its ceiling);
- the judge browser end-to-end on a budget arming, and the no-network paid-path rehearsal;
- dashboard vitest and build; critical and dev suites.

**Migration (each step needs your approval):**
1. Deploy. The image adds three empty tables; nothing is assigned or changed.
2. Open the budget at your terminal (`budget open`, typed).
3. A new arming with `--budget ar-a20-2026-11`, only when you want new launches.
4. Optionally, the Ironbark settlements (fork-prefix) at your terminal.

The ceiling value, the existing armings, the jobs, ledgers and settlements are untouched.

**Rollback:** `rollback-dde7e22` (the current image).
- It ignores the budget tables and counts any budget job against the legacy ceiling (more conservative).
- Budget rows are additive and are not deleted.
- If ever required, restore the admission database from the backup taken before step 2.

## 9. Decisions needed from the owner
1. Ceiling scope: **Option A** (recommended: ceiling applies to legacy jobs only) or Option B (one host-wide cap; a ceiling change would be needed for full isolation).
2. The budget id (`ar-a20-2026-11` proposed) and whether off-host development spending also goes through external allocations (recommended: yes).
3. Whether to append `eval-c04fdb10` to the A$50 programme ledger (structured `hosted_job` field).
4. Whether to settle the two Ironbark jobs under `fork-prefix-1` (no change to the programme ledger; releases US$1.082935 of legacy ceiling).
