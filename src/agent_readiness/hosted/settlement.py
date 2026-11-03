"""Actual-cost settlement of hosted reservations (final showcase).

Admission reserves a job's WORST CASE before it starts. Once the job can never send another request (its admission state is terminal: the
worker has exited) and its durable request ledger(s) show every request reserved before sending AND settled from provider-reported usage, the job's
commitment against the hosted ceiling becomes its ACTUAL settled cost and the rest of the reservation is released:

    committed(job) = settled cost              if a settlement is recorded
                   = full reservation          otherwise (active, uncertain, unsettled or never verified)
    admission:  sum(committed) + new reservation <= hosted ceiling

Records are additive and never rewritten: `jobs.reserved` stays as written; a settlement is a separate, write-once row (`settlements`) with the
ledger's sha256 and counts. A job's state alone ("failed", "interrupted") never releases anything; only a verified ledger does.

Automatic settlement applies only to jobs admitted by settlement-aware code (`auto_settle` row written atomically with the reservation) and only
when every request is settled (no open reservations). Historical jobs, and jobs with unsettled requests, are settled only by the owner at an
interactive terminal (`python -m agent_readiness.hosted.settlement apply`), after the read-only `audit`. An unsettled request is then committed at
its full reserved bound (conservative), never at zero.

    python -m agent_readiness.hosted.settlement audit --db /data/hosted/live/admission.sqlite [--json]
    python -m agent_readiness.hosted.settlement apply --db /data/hosted/live/admission.sqlite --job eval-... --expect-settled 0.631751 [--allow-open-requests]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

TERMINAL = ("completed", "failed", "timed_out", "interrupted")
AUTO_ACTOR = "service (automatic: verified durable ledger, every request settled)"


class SettlementRefused(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code, self.detail = code, detail


def micro(usd: float) -> int:
    """US$ -> microdollars, rounded UP (a commitment is never understated)."""
    return int(math.ceil(round(float(usd) * 1e6, 3) - 1e-9))


# ----------------------------------------------------------------------------------------------------------------------------- ledgers
def ledger_state(paths: list[Path], skip: list[int] | None = None) -> dict:
    """Read one or more append-only request ledgers (reserve-before-send; `settle` replaces a reservation by the actual cost). Unsettled requests
    count at their full reserved bound. Raises SettlementRefused if a ledger is missing or malformed. `skip[i]` lines at the start of ledger i are
    a verified imported prefix (`fork_prefixes`) and are not this job's spending; the digest always covers every file in full."""
    reserved: dict[tuple, int] = {}
    settled: dict[tuple, int] = {}
    digest, lines, violations = hashlib.sha256(), 0, 0
    for i, p in enumerate(paths):
        p = Path(p)
        if not p.is_file():
            raise SettlementRefused("ledger_missing", f"a request ledger of this job is missing ({p.name})")
        raw = p.read_bytes()
        digest.update(hashlib.sha256(raw).digest())
        first = (skip or [0] * len(paths))[i]
        for n, line in enumerate(raw.decode().splitlines(), 1):
            if n <= first or not line.strip():
                continue
            try:
                e = json.loads(line)
                kind, item, usd = e["kind"], e["id"], e.get("usd", 0.0)
            except (ValueError, KeyError, TypeError):
                raise SettlementRefused("ledger_malformed", f"ledger line {n} is malformed") from None
            lines += 1
            key = (i, item)
            if kind == "reserve":
                if key in reserved:
                    raise SettlementRefused("ledger_malformed", f"ledger line {n} reserves an item twice")
                reserved[key] = micro(usd)
            elif kind == "settle":
                if key not in reserved:
                    raise SettlementRefused("ledger_malformed", f"ledger line {n} settles an item that was never reserved")
                if key in settled:
                    raise SettlementRefused("ledger_malformed", f"ledger line {n} settles an item twice")
                settled[key] = micro(usd)
                violations += settled[key] > reserved[key]
    open_ = [k for k in reserved if k not in settled]
    return {"requests": len(reserved), "settled_requests": len(settled), "open_requests": len(open_), "bound_violations": violations,
            "settled_microusd": sum(settled.values()), "open_reserved_microusd": sum(reserved[k] for k in open_),
            "committed_microusd": sum(settled.values()) + sum(reserved[k] for k in open_), "lines": lines, "sha256": digest.hexdigest()}


def stage_b_root(root: Path) -> Path:
    """The Stage B root (armings, authorisations, ledgers): AR_STAGE_B_ROOT as the service uses it, else <data>/lifecycle/stage-b."""
    env = os.environ.get("AR_STAGE_B_ROOT")
    return Path(env) if env else Path(root).parent / "lifecycle" / "stage-b"


def job_ledgers(root: Path, job_id: str, stage_b: Path | None = None) -> tuple[str, list[Path]]:
    """The durable request ledger(s) of a hosted job: a Stage B launch's own experiment ledger (from its launch claim, cross-checked against the
    write-once paid authorisation), or the retired paired engine's per-repetition ledgers. Raises SettlementRefused if none can be identified."""
    root = Path(root)                                                   # the hosted root of this admission database, e.g. /data/hosted/live
    sb = root / "stageb" / "jobs" / f"{job_id}.json"
    if sb.is_file():
        job = json.loads(sb.read_text())
        if job.get("id") != job_id:
            raise SettlementRefused("job_mismatch", "the Stage B job record does not name this job")
        if job.get("mode") != "paid":
            return "stage-b rehearsal (no model calls)", []
        claim = job.get("launch") or {}
        exp = claim.get("experiment_id")
        if not exp or claim.get("job") != job_id:
            raise SettlementRefused("no_launch_claim", "the job has no launch claim naming it")
        stage_b = Path(stage_b) if stage_b else stage_b_root(root)
        auth = stage_b / "authorizations" / f"{exp}.json"
        if not auth.is_file():
            raise SettlementRefused("no_authorization", "the launch's paid authorisation record is missing")
        if json.loads(auth.read_text()).get("experiment_id", exp) != exp:
            raise SettlementRefused("authorization_mismatch", "the paid authorisation names another experiment")
        return f"stage-b launch {exp}", [stage_b / "ledgers" / exp / "ledger.jsonl"]
    legacy = root / f"{job_id}.job.json"
    if legacy.is_file():
        job = json.loads(legacy.read_text())
        runs = [r.get("run_id") for r in job.get("reps") or [] if r.get("run_id")]
        if not runs:
            raise SettlementRefused("no_ledger", "the paired job names no repetition run")
        return "paired engine (retired)", [root / r / "spend" / "ledger.jsonl" for r in runs]
    raise SettlementRefused("no_job_record", "no job record names this job")


# Copied-ledger rule `fork-prefix-1` (the retired Ironbark engine). Each hosted Ironbark repetition was a FORK of the source run live-2d58a80e14: its
# request ledger starts with a byte-exact copy of the source run's ledger (imported history, already recorded ONCE in the programme ledger as
# `ironbark-source`), followed by the repetition's own requests. The fork's own write-once `fork.json` declares the imported ledger (entries, sha256).
# A job's own spending is the remainder, and only when: the fork declares a source ledger whose sha256 is pinned here (i.e. recorded separately), the
# job ledger's first `entries` lines hash to exactly that sha256, and the remainder is a complete ledger by itself (a settle line naming a request
# of the imported part is refused as "never reserved"). Nothing is estimated, no file is changed; one differing byte refuses.
RECORDED_SOURCES = {
    "90bbc68f6b30b6b6d53bbd2f94d1854ccf4dc941b5793064def05828b70a4357": {"source_run": "live-2d58a80e14", "entries": 126, "settled_microusd": 864_825,
                                                                         "programme_entry": "ironbark-source"},
}
FORK_RULE = "fork-prefix-1"


def fork_prefixes(paths: list[Path]) -> tuple[list[int], list[dict]]:
    """For each ledger path (…/<run>/spend/ledger.jsonl): the number of leading lines that are a verified imported source ledger (0 if the run is
    not a fork). Raises SettlementRefused when a fork's declared prefix does not verify."""
    skip, notes = [], []
    for p in paths:
        p = Path(p)
        fj = p.parent.parent / "fork.json"
        if not fj.is_file():
            skip.append(0)
            continue
        try:
            src = json.loads(fj.read_text()).get("source_ledger") or {}
            sha, n = src.get("sha256"), src.get("entries")
        except (ValueError, AttributeError):
            raise SettlementRefused("fork_record_malformed", "the fork record is not readable") from None
        if not sha:
            skip.append(0)
            continue
        pin = RECORDED_SOURCES.get(sha)
        if pin is None or pin["entries"] != n:
            raise SettlementRefused("fork_source_unrecorded", "the fork imports a source ledger that is not pinned as recorded separately")
        if not p.is_file():
            raise SettlementRefused("ledger_missing", f"a request ledger of this job is missing ({p.name})")
        raw = p.read_bytes().splitlines(keepends=True)
        if len(raw) < n or hashlib.sha256(b"".join(raw[:n])).hexdigest() != sha:
            raise SettlementRefused("fork_prefix_mismatch", "the ledger does not start with exactly the declared imported source ledger")
        skip.append(n)
        notes.append({"run": p.parent.parent.name, "source_run": pin["source_run"], "imported_lines": n, "imported_sha256": sha,
                      "imported_settled_microusd": pin["settled_microusd"], "recorded_as": pin["programme_entry"]})
    return skip, notes


# ----------------------------------------------------------------------------------------------------------------------------- decisions
def assess(admission, root: Path, job_id: str, *, allow_open: bool = False) -> dict:
    """Read-only: whether `job_id` may be settled now, and at what commitment. Never writes."""
    row = admission.get(job_id)
    if row is None:
        raise SettlementRefused("no_job", "no admission row for this job")
    out = {"job": job_id, "state": row["state"], "reserved_microusd": row["reserved_microusd"], "settlement": admission.settlement(job_id),
           "budget": admission.job_budget(job_id) if hasattr(admission, "job_budget") else None}
    try:
        basis, paths = job_ledgers(root, job_id)
        skip, forks = fork_prefixes(paths) if basis.startswith("paired engine") else ([0] * len(paths), [])
        if forks:
            basis += f"; {FORK_RULE}: imported source ledger {forks[0]['source_run']} ({forks[0]['imported_lines']} lines, sha256 {forks[0]['imported_sha256'][:12]}, recorded once as {forks[0]['recorded_as']}) excluded"
        led = ledger_state(paths, skip) if paths else {"requests": 0, "settled_requests": 0, "open_requests": 0, "bound_violations": 0, "settled_microusd": 0,
                                                "open_reserved_microusd": 0, "committed_microusd": 0, "lines": 0, "sha256": hashlib.sha256(b"").hexdigest()}
    except SettlementRefused as exc:
        return {**out, "eligible": False, "reason": exc.code, "detail": exc.detail}
    out.update(basis=basis, ledger=led, **({"fork": forks} if forks else {}))
    commit = led["committed_microusd"] if allow_open else led["settled_microusd"]
    why = None
    if row["state"] not in TERMINAL:
        why = ("not_terminal", "the job may still send requests")
    elif led["open_requests"] and not allow_open:
        why = ("open_requests", f"{led['open_requests']} request(s) were reserved but never settled; the full reservation is kept")
    elif commit > row["reserved_microusd"]:
        why = ("exceeds_reservation", "the ledger commits more than the job reserved; investigate before any release")
    if why:
        return {**out, "eligible": False, "reason": why[0], "detail": why[1]}
    return {**out, "eligible": True, "reason": None, "commit_microusd": commit, "release_microusd": row["reserved_microusd"] - commit}


def settle(admission, root: Path, job_id: str, *, actor: str, allow_open: bool = False, expect_microusd: int | None = None) -> dict:
    """Verify, then record the settlement atomically and idempotently (a second call with the same result is a no-op)."""
    a = assess(admission, root, job_id, allow_open=allow_open)
    if not a["eligible"]:
        raise SettlementRefused(a["reason"], a["detail"])
    if expect_microusd is not None and expect_microusd != a["commit_microusd"]:
        raise SettlementRefused("unexpected_amount", f"the ledger commits {a['commit_microusd']} microdollars, not the expected {expect_microusd}")
    led = a["ledger"]
    basis = f"{a['basis']}: {led['settled_requests']}/{led['requests']} requests settled" + (
        f", {led['open_requests']} unsettled committed at their reserved bound" if led["open_requests"] else "")
    return admission.record_settlement(job_id, a["commit_microusd"], basis=basis, ledger_sha256=led["sha256"], ledger_requests=led["requests"],
                                       open_requests=led["open_requests"], actor=actor)


def settle_automatic(admission, root: Path, job_id: str, log=print) -> dict | None:
    """After a job ends (and at service start): settle a settlement-aware job whose every request is settled. Anything else keeps its full
    reservation (logged, never raised)."""
    try:
        if not admission.auto_settle_enabled(job_id) or admission.settlement(job_id) is not None:
            return None
        return settle(admission, root, job_id, actor=AUTO_ACTOR)
    except SettlementRefused as exc:
        log(f"hosted service: {job_id}: reservation kept ({exc.code})")
    except Exception as exc:                                                          # never let accounting break the service; capacity stays held
        log(f"hosted service: {job_id}: reservation kept (settlement error {type(exc).__name__})")
    return None


def reconcile_automatic(admission, root: Path, log=print) -> list[str]:
    """Service start: settle every eligible settlement-aware terminal job (recovers a crash between a job's end and its settlement)."""
    done = []
    for r in admission.recent(10_000):
        if r["state"] in TERMINAL and settle_automatic(admission, root, r["id"], log=log) is not None:
            done.append(r["id"])
    return done


# ----------------------------------------------------------------------------------------------------------------------------- owner CLI
def audit(admission, root: Path) -> dict:
    jobs = [assess(admission, root, r["id"], allow_open=False) for r in sorted(admission.recent(10_000), key=lambda r: r["created"])]
    return {"database": str(admission.path), "totals": admission.totals(), "jobs": jobs}


AUD_PER_USD = 1.50                     # the programme's agreed conservative planning rate
PROGRAMME_LIMIT_AUD = 50.0             # a limit, never an authorisation


def programme_view(rep: dict, ledger_path: Path, rate: float = AUD_PER_USD) -> dict:
    """Owner-facing A$50 programme view from an audit report (see `programme.view`): recorded spend matched by explicit job identity, never by text."""
    from . import programme
    return programme.view_from_audit(json.loads(Path(ledger_path).read_text()), rep, rate=rate)


def _usd(m: int | None) -> str:
    return "–" if m is None else f"US${m / 1e6:.6f}"


def _print_audit(rep: dict) -> None:
    t = rep["totals"]
    print(f"database        {rep['database']}")
    print(f"ceiling         {_usd(t['ceiling_microusd'])}")
    print(f"reserved        {_usd(t['reserved_microusd'])} (all reservations as written; never rewritten)")
    print(f"settled         {_usd(t['settled_microusd'])} actual cost of {t['settled_jobs']} settled job(s), releasing {_usd(t['released_microusd'])}")
    print(f"outstanding     {_usd(t['outstanding_microusd'])} held in full by {t['unsettled_jobs']} unsettled job(s)")
    print(f"committed       {_usd(t['committed_microusd'])} = settled + outstanding; available {_usd(t['available_microusd'])}")
    pv = rep.get("programme")
    if pv:
        extra = "; ".join(f"{m['job'][:13]} US${m['usd']:.6f}" for m in pv["not_in_ledger"]) or "none"
        if pv.get("unverified_exposure_usd"):
            extra += f" (+ US${pv['unverified_exposure_usd']:.6f} held for unverified runs)"
        print(f"programme       known US${pv['known_usd']:.6f} (programme ledger) + not yet recorded: {extra} = US${pv['spend_to_date_usd']:.6f} = A${pv['spend_to_date_aud']:.2f}"
              f" at {pv['rate_aud_per_usd']:.2f} AUD/USD")
        print(f"worst case      + the hosted ceiling's available US${pv['hosted_available_usd']:.6f} = A${pv['worst_case_aud']:.2f} of the A${pv['limit_aud']:.0f} limit"
              f" ({'within' if pv['within_limit'] else 'ABOVE'} the limit; a limit, never an authorisation)")
    for j in rep["jobs"]:
        led = j.get("ledger") or {}
        s = j["settlement"]
        line = f"{j['job']}  {j['state']:<11} reserved {_usd(j['reserved_microusd'])}"
        if s:
            line += f"  SETTLED {_usd(s['settled_microusd'])} ({s['actor']})"
        elif j["eligible"]:
            line += f"  eligible: commit {_usd(j['commit_microusd'])}, release {_usd(j['release_microusd'])}"
        else:
            line += f"  kept in full: {j['reason']} ({j['detail']})"
        if led:
            line += f"  | ledger {led['settled_requests']}/{led['requests']} settled, {led['open_requests']} open, {led['bound_violations']} above bound, sha256 {led['sha256'][:12]}"
        print(line)


def main(argv=None) -> int:
    from .admission import Admission
    ap = argparse.ArgumentParser(prog="python -m agent_readiness.hosted.settlement", description="Actual-cost settlement of hosted reservations (owner tools).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("audit", "apply"):
        s = sub.add_parser(name)
        s.add_argument("--db", required=True, type=Path)
        s.add_argument("--root", type=Path, help="hosted root of this database (default: its directory, e.g. /data/hosted/live)")
        if name == "audit":
            s.add_argument("--json", action="store_true")
            s.add_argument("--programme-ledger", type=Path, help="collaboration/budget/programme-ledger.json: adds the A$ programme view")
        else:
            s.add_argument("--job", required=True)
            s.add_argument("--expect-settled", required=True, help="the US$ amount the audit printed as the commitment (6 decimals)")
            s.add_argument("--allow-open-requests", action="store_true", help="commit unsettled requests at their full reserved bound (recovery)")
    a = ap.parse_args(argv)
    data = a.root or a.db.resolve().parent
    if a.cmd == "audit":
        adm = Admission.open_read_only(a.db)
        rep = audit(adm, data)
        if a.programme_ledger:
            rep["programme"] = programme_view(rep, a.programme_ledger)
        print(json.dumps(rep, indent=1, default=str)) if a.json else _print_audit(rep)
        return 0
    if not sys.stdin.isatty():
        print("refused: settlement is an owner action at an interactive terminal", file=sys.stderr)
        return 2
    adm = Admission.open_existing(a.db)
    expect = micro(float(a.expect_settled))
    pre = assess(adm, data, a.job, allow_open=a.allow_open_requests)
    if not pre["eligible"]:
        print(f"refused: {pre['reason']}: {pre['detail']}", file=sys.stderr)
        return 1
    text = (f"I am the owner and I settle hosted job {a.job} at {_usd(pre['commit_microusd'])} (reserved {_usd(pre['reserved_microusd'])}, release "
            f"{_usd(pre['release_microusd'])}), verified against ledger sha256 {pre['ledger']['sha256']}")
    print(text)
    if input("Type the line above exactly to confirm: ").strip() != text:
        print("refused: the confirmation did not match; nothing changed", file=sys.stderr)
        return 1
    out = settle(adm, data, a.job, actor=f"owner terminal (uid {os.getuid()})", allow_open=a.allow_open_requests, expect_microusd=expect)
    print(f"settled {a.job}: {_usd(out['settled_microusd'])}{' (already recorded)' if out.get('already') else ''}; available now "
          f"{_usd(adm.totals()['available_microusd'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
