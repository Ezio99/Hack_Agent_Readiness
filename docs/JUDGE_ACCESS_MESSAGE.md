# Judge access message: NOT USED

> **Superseded (2026-11-05).** The organizers confirmed that there is no private channel for sharing credentials, and that the operator token must not appear in the submission, the public repository, the README or the video description. No access code is given to judges. Judges use the public evidence (canonical report, agent replays, raw traces and outputs) and the optional reproducibility paths in the [README's "Evaluate it" section](../README.md#evaluate-it), with their own Meta Model API key if they choose. The earlier draft below is kept only as a record; do not send it.

## Superseded draft

Paste it into a **private** submission field or a private message to the organisers, never a public page, README or video. Replace `<ACCESS CODE>` with the value of `deploy/secrets/judge_token` on the VM; the owner copies it at a terminal and never commits it.

---

**Live demo: Agent Readiness**

- **Product:** https://209-38-84-72.sslip.io
- **No code needed to explore:**
  - The results (canonical paired evaluation, Original website vs Agent-ready website): open **See the results** in the top menu, or https://209-38-84-72.sslip.io/#/reports/eval-1cf64d5eae90bcaeab531b4886140c14
  - How it works, on the real example: open **How it works** (the Larkspur journey).
  - Every report includes each agent's recorded screenshots and working notes.
- **To run a live evaluation yourself:**
  1. Open **Run an evaluation** (the Workspace): https://209-38-84-72.sslip.io/#/run
  2. Paste this access code into the **Access code** box: `<ACCESS CODE>`
  3. Press **Run live evaluation**. Six Meta Muse Spark browser agents run the same three tasks on both versions of the Larkspur Community College website, the Original website and the Agent-ready website (about 8 minutes); you can watch each one live.
  4. When they finish, open the **Readiness report** tab.

**About the code:**
- It is held only in your browser tab's memory: it is not saved, and you re-enter it after a reload.
- It is sent only when you press Run.
- One evaluation runs at a time. If another is running, the Workspace shows that one live instead.
- Runs come from a fixed evaluation budget, so please start one run per judge.

---
