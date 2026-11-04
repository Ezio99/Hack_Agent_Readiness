# Final submission checklist (prepared 2026-11-04 ~12:00 AEDT)

**Legend:** ✅ PASS (checked today) · ❌ FAIL / missing · 👤 OWNER must do · ❓ unconfirmed assumption

## 1. Official requirements
Sources:
- Meta event page: https://dev.meta.ai/events/global-hackathon
- Organizer page: https://cerebralvalley.ai/e/meta-ai-developer-hackathon

Both re-read 2026-11-04.

| Item | Status | Detail |
|---|---|---|
| Deadline | ✅ confirmed | "Nov 4: Project submissions due by 9:00 PM ET" = **Thu 5 Nov 13:00 AEDT** (EST, UTC−5). A third-party listing says 6:30 AM IST (= 12:00 AEDT). **Submit by 12:00 AEDT to be safe.** |
| Judging | ✅ confirmed | Nov 4–8; winners Nov 9 |
| Tracks | ✅ confirmed | Indie ("creativity, technical ambition, and whether it works") or Startup ("technical execution and whether it holds up in production"). 👤 Choose one |
| Themes | ✅ confirmed | "Build for Your World" or "Push the Frontier". Suggested: Push the Frontier (software agents). 👤 Choose |
| Meta models | ✅ confirmed (encouraged, not mandatory) | Muse Spark via the Meta Model API is used for every agent decision (`muse-spark-1.3`) |
| Eligibility | ✅ confirmed text | Excluded: Meta / Cerebral Valley employees, contractors and interns; government-affiliated people; sanctioned regions. 👤 Confirm each team member is eligible |
| Official Rules | ❓ not public | "Official Rules … must be accepted by the selected participants." 👤 Read them in the participant portal, especially original-work and reuse rules |
| Submission platform and fields | ❓ not public | 👤 Open the participant submission form and match its fields to `FINAL_SUBMISSION.md` |
| Video length, format and hosting | ❓ not public | We assume ~3 minutes, public or unlisted (owner's earlier reference). 👤 Confirm on the form |
| Demo URL, repo, team size, judging weights | ❓ not public | Earlier internal weights (Impact 30 / Meta tooling 25 / Demo 25 / Technical 20) are unverified. 👤 Confirm |

## 2. Deliverables
| Item | Status | Detail |
|---|---|---|
| Live product | ✅ | https://209-38-84-72.sslip.io (deployed `1b48dee`): healthy, worker idle, A$18.57 of A$20 budget left |
| Showcase | ✅ | `#/showcase`: Before → After from the recorded evidence |
| Judge path: code → Run → progress → report | ✅ | Run disabled without a code; invalid code → 403; recorded runs open for everyone. Full judge flow passed in a real browser (local zero-cost rehearsal) |
| Video | ❌ 👤 | Not recorded. Storyboard: [FINAL_VIDEO_SCRIPT.md](FINAL_VIDEO_SCRIPT.md) |
| Description text | ✅ draft | [FINAL_SUBMISSION.md](FINAL_SUBMISSION.md). 👤 Adapt it to the form's fields and limits |
| Repository link | ✅ public | https://github.com/Ezio99/Hack_Agent_Readiness. The work is on branch `final-showcase`; `main` does not contain it. 👤 Link the branch or commit, or approve a merge |
| Access code for judges | 👤 | The judge code is on the VM (`deploy/secrets/judge_token`). 👤 Decide how judges receive it (form field or private note); never post it publicly |
| Licence | ❓ | The repository has no licence file. 👤 Decide if the form requires one |
| Team and AI-assistance disclosure | 👤 | Roster and roles; disclose AI coding assistants if asked |

## 3. Evidence audit (claims vs records)
| Check | Status |
|---|---|
| Before and After totals, per-task requests, correct/exact counts, settled costs (showcase data vs `/api/lifecycle/evaluations`) | ✅ 0 mismatches |
| Derived figures: 58 % fewer requests, 61 % less time, 61 % lower cost, US$0.73 total | ✅ recomputed |
| Quoted agent memories (showcase, Home, video) match the recorded steps | ✅ |
| Earlier experiments (3 Nov Original vs Improved: 0/3 → 3/3, 39 → 6) labelled as history | ✅ |
| Budget A$1.433917 spent, 4 runs, all settled | ✅ |
| One over-strong sentence ("came back to the catalogue each time") | ✅ fixed locally → "kept going back to the catalogue" (one agent went course to course) |

## 4. Reliability (production, read-only, fresh browser sessions)
| Check | Status |
|---|---|
| 22 public routes × desktop 1440 and mobile 390: no errors, no writes, no horizontal overflow, no internal names | ✅ |
| Trace replay: step buttons and arrows change the recorded screenshot; images load (Before and After) | ✅ |
| Workspace job page: agent-run cells open the viewer with a real screenshot; Run disabled without a code | ✅ |
| Browser end-to-end suites (judge experience, showcase) | ✅ 2/2 |

## 5. Judge-simulation fixes: DEPLOYED `02ed375` (owner-approved, 2026-11-04 00:44 UTC; verified)
| Fix | Why |
|---|---|
| Home: the result card (0/3 → 3/3) and "Watch before and after" moved above the fold | A first-time visitor saw the purpose but not the measured impact in the first desktop screen |
| Workspace history: "Passed" column renamed "Exact match" | It showed 33 % for After next to 3/3 correct, which looked contradictory |
| Journey: one line saying it follows the 3 Nov first experiment, with a link to the showcase | Avoids mixing it up with Before/After |
| Grammar fix in the Workspace worker status; one Showcase sentence softened | Accuracy and polish |

✅ **Deployed and verified:**
- The 0/3 → 3/3 card sits in the desktop first viewport (y = 694–890 px of 900).
- The Workspace history column reads "Exact match"; grid cells show "Correct" alongside "Exact match: yes/no".
- 22 routes × desktop and mobile: 0 failures.
- Evidence identical (3 184 files); budget unchanged.

The application is frozen.

## 6. Owner actions, in order
1. 👤 Open the participant portal: read the Official Rules and the submission form; choose track and theme.
2. ✅ §5 fixes deployed. 👤 Paste [JUDGE_ACCESS_MESSAGE.md](JUDGE_ACCESS_MESSAGE.md) privately, with the code filled in.
3. 👤 Record the video from the storyboard; upload; check it plays while signed out.
4. 👤 Fill in the form from `FINAL_SUBMISSION.md`: demo URL, video, repo (branch or commit), judge access code delivered privately, team.
5. 👤 Submit **before 12:00 AEDT Thu 5 Nov** and keep the confirmation.
