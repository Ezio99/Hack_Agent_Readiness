# Local Ironbark evaluation runner

From the repository root, install the project and browser dependencies as described in README, and ensure the private, ignored source run `scanner-data/live/live-2d58a80e14` is present. This source is not included in the repository distribution. Run:

```sh
.venv/bin/python -m agent_readiness.live.ironbark_runner
```

Open http://127.0.0.1:8765/. The service listens on IPv4 loopback only. The process must remain running for an evaluation; stopping it cancels the worker. Run IDs are shown in the review screen and can be loaded after a restart. Linux is required for the worker's parent-death guard and process-group cancellation. Do not expose or proxy this local service to a network.

Enter an explicit proposed cap for each arm, then prepare a review. Preparation is free: it creates a fresh fork in ignored `scanner-data/ironbark-operator`, applies the owner-selected change to a local snapshot, and presents the actual manifest and four frozen questions. Review its model, profile, identities, limits, grading-rule hash and caps. After reviewing the displayed configuration, select Confirm & Run Evaluation. The server binds that confirmation to the prepared manifest and caps. This action is a request for paid model calls, not approval from the project owner. Obtain that approval separately first. A repository-root `.env` or process environment can supply `META_MODEL_API_KEY`; it is never sent to the browser.

The existing driver and stage enforce the exact approved manifest, request, trial, arm and combined caps and the durable ledger. Cancellation or the 1800-second job timeout kills the worker process group; in-flight provider charges or unsettled reservations may remain. Failed, cancelled, interrupted, timed-out and partial runs are preserved and cannot be restarted through the app. The per-task status comes from durable trial records and trial directories, and a partial record is not an outcome. Calculated spending is not a bill. The sanitized download uses `investigate.export.export_run` and `check_clean`; private artifacts remain local.

The frozen assessment compares patched results to the historical compat1 baseline; the exploratory contemporaneous assessment compares the two new compat2 arms. Their limitations and profile distinction are preserved in the export. No observed difference establishes a causal improvement. Recorded fixture checks do not demonstrate a real Muse evaluation.

## Unapproved first-run proposal

The free local preparation with proposed caps US$0.80 per arm generated post-trials manifest `99f493d1558db5d925069e5ae8ea66fc21e2927e1364a69ddb45ec9ae3a550f8` (the application recomputes and displays the actual hash for each run). This is a proposal, not authorization. It specifies eight model-driven trials, Muse Spark 1.3, `suite-v2-compat2`, 14 steps and model requests and 240 seconds per task, zero retries, US$0.50 per trial, US$0.05 per request, US$1.60 combined arm cap and a US$2.50 ledger ceiling including US$0.864825 of imported committed history. The hard overall job timeout is 1800 seconds. Original snapshot SHA-256 `d2824b210ed9e9d85dac527eb0b4eeb519540a70a7c59ff8690c204ff677538f`; Modified `40c5d886963c925a7b99ff721d7971d5ebacbc52d0237d9549febe301d74f1ed`; frozen tasks manifest `1c0f546ef0b0588cdc6a81ab7abb6d0e70bbe9d01487b4f9856ccd8ed979dd95`. Each arm runs the same four questions on the respective snapshot. The proposal is subject to owner review, current credentials, remaining programme budget and the risk of interruption or unsettled provider costs.
