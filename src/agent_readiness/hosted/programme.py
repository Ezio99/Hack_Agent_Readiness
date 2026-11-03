"""The A$50 programme ledger (collaboration/budget/programme-ledger.json) and the hosted service: explicit job identity, duplicate detection, and the
programme view (actual expenditure plus the maximum outstanding exposure). Separate budgets (`budget.py`) are never part of the programme.

Identity. An entry names the hosted job(s) it records in `hosted_job` (or `hosted_jobs`); the three hosted entries written before that field existed
are mapped here explicitly (LEGACY_IDENTITY). A hosted job is matched ONLY by identity, never by searching text. `check` reports: duplicate entry ids,
a job recorded twice, a malformed job id, a non-numeric amount, an entry assigned to another budget, a job charged to a separate budget, and an
entry whose text names a full job id it does not declare.

Programme view (legacy scope: jobs not charged to a separate budget):
    spend to date   = programme ledger (recorded actual costs)
                    + legacy hosted jobs NOT recorded there whose cost is verified (a settlement row, or a terminal job with a complete ledger)
    held            = full reservations of legacy jobs not recorded and not verified (active, uncertain, unsettled)
    worst case      = spend to date + held + what the hosted ceiling could still admit (its available amount)
A reservation is never expenditure; a recorded job's remaining hold is neither.

    python -m agent_readiness.hosted.programme check   --ledger collaboration/budget/programme-ledger.json [--db admission.sqlite]
    python -m agent_readiness.hosted.programme view    --ledger ... --db ... [--json]
    python -m agent_readiness.hosted.programme propose --ledger ... --db ... --job eval-... --entry-id ... --label ... --out proposal.json
    python -m agent_readiness.hosted.programme append  --ledger ... --proposal proposal.json            # owner, interactive terminal
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

RATE_AUD_PER_USD = Decimal("1.50")
LIMIT_AUD = Decimal("50")
JOB = re.compile(r"eval-[0-9a-f]{32}")
LEGACY_IDENTITY = {                                   # entries recorded before `hosted_job` existed (their text abbreviates or omits the id)
    "hosted-live-1": ("eval-9aaac35ca488c2bf951e01e58746604a",),
    "hosted-live-2": ("eval-aa23e33012717c4a30ca21be1239e85f",),
    "hosted-stageb-live-1": ("eval-e529db2aafecbfddd21e5c571eb85243",),
}


class ProgrammeRefused(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code, self.detail = code, detail


def micro(usd) -> int:
    return int((Decimal(str(usd)) * 1_000_000).to_integral_value(rounding=ROUND_CEILING))


def entry_jobs(e: dict) -> tuple[str, ...]:
    declared = tuple(e.get("hosted_jobs") or ()) + ((e["hosted_job"],) if e.get("hosted_job") else ())
    return declared or LEGACY_IDENTITY.get(e.get("id"), ())


def recorded_jobs(doc: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for e in doc.get("entries") or []:
        for j in entry_jobs(e):
            out.setdefault(j, e.get("id"))
    return out


def check(doc: dict, budget_jobs: dict[str, str] | None = None) -> list[str]:
    problems, ids, seen = [], set(), {}
    for n, e in enumerate(doc.get("entries") or []):
        eid = e.get("id")
        if not eid:
            problems.append(f"entry {n} has no id")
        elif eid in ids:
            problems.append(f"entry id {eid} appears twice")
        ids.add(eid)
        try:
            Decimal(str(e.get("usd")))
            if e.get("usd") is None or isinstance(e.get("usd"), bool):
                raise ValueError
        except Exception:
            problems.append(f"entry {eid}: usd is not a number")
        if e.get("budget") not in (None, "programme"):
            problems.append(f"entry {eid}: belongs to budget {e['budget']}, not the programme")
        if (e.get("hosted_job") or e.get("hosted_jobs")) and eid in LEGACY_IDENTITY and set(entry_jobs(e)) != set(LEGACY_IDENTITY[eid]):
            problems.append(f"entry {eid}: declared hosted job differs from its recorded identity")
        jobs = entry_jobs(e)
        for j in jobs:
            if not JOB.fullmatch(j or ""):
                problems.append(f"entry {eid}: malformed hosted job id {j!r}")
            elif j in seen:
                problems.append(f"hosted job {j} is recorded twice ({seen[j]}, {eid})")
            else:
                seen[j] = eid
            if budget_jobs and j in budget_jobs:
                problems.append(f"hosted job {j} is charged to budget {budget_jobs[j]} and must not be in the programme ledger")
        for j in set(JOB.findall(json.dumps(e))) - set(jobs):
            problems.append(f"entry {eid}: names hosted job {j} without declaring it (hosted_job)")
    return problems


def _aud2(m: int) -> float:
    return float((Decimal(m) * RATE_AUD_PER_USD / 1_000_000).quantize(Decimal("0.01"), rounding=ROUND_CEILING))


def view_from_audit(doc: dict, rep: dict, *, rate: float = 1.50) -> dict:
    """`rep` = `settlement.audit(...)` (jobs with settlement, eligibility and budget; totals of the ceiling's legacy scope)."""
    if Decimal(str(rate)) != RATE_AUD_PER_USD:
        raise ProgrammeRefused("rate", "the programme's planning rate is 1.50 A$ per US$")
    rec = recorded_jobs(doc)
    known = sum(micro(e.get("usd") or 0) for e in doc.get("entries") or [])
    budget_jobs = {j["job"]: j["budget"] for j in rep["jobs"] if j.get("budget")}
    spent, held, missing, unverified, recorded = 0, 0, [], [], []
    for j in rep["jobs"]:
        if j.get("budget"):
            continue                                                                   # a separate budget: never programme spending
        if j["job"] in rec:
            recorded.append({"job": j["job"], "entry": rec[j["job"]]})
            continue
        s = j.get("settlement")
        if s:
            spent += s["settled_microusd"]
            missing.append({"job": j["job"], "usd": s["settled_microusd"] / 1e6, "basis": "settled actual cost", "open_requests": s.get("open_requests", 0)})
        elif j.get("eligible"):
            spent += j["commit_microusd"]
            missing.append({"job": j["job"], "usd": j["commit_microusd"] / 1e6, "basis": "verified ledger (not yet settled)", "open_requests": 0})
        else:
            held += j["reserved_microusd"]
            unverified.append({"job": j["job"], "reserved_usd": j["reserved_microusd"] / 1e6, "reason": j.get("reason")})
    to_date = known + spent
    avail = max(0, rep["totals"]["available_microusd"])
    worst = to_date + held + avail
    limit_micro_aud = int(LIMIT_AUD * 1_000_000)
    return {"rate_aud_per_usd": float(RATE_AUD_PER_USD), "limit_aud": float(LIMIT_AUD), "known_usd": known / 1e6, "recorded_jobs": recorded,
            "not_in_ledger": missing, "spend_to_date_usd": to_date / 1e6, "spend_to_date_aud": _aud2(to_date),
            "unverified": unverified, "unverified_exposure_usd": held / 1e6, "hosted_available_usd": avail / 1e6,
            "worst_case_usd": worst / 1e6, "worst_case_aud": _aud2(worst),
            "within_limit": -(-worst * 3 // 2) <= limit_micro_aud, "problems": check(doc, budget_jobs)}


def view(doc: dict, admission, root: Path) -> dict:
    from .settlement import audit
    return view_from_audit(doc, audit(admission, root))


# ----------------------------------------------------------------------------------------------------------------------------- append (proposal, then owner)
def propose(doc: dict, admission, root: Path, *, job: str, entry_id: str, label: str, authorized_by: str, recorded_on: str) -> dict:
    """An append proposal for one SETTLED legacy hosted job, at its settled actual cost. Read-only: the ledger is not changed."""
    from .settlement import assess
    a = assess(admission, root, job)
    s = a.get("settlement")
    if a.get("budget"):
        raise ProgrammeRefused("separate_budget", f"{job} is charged to budget {a['budget']}, not the programme")
    if not s:
        raise ProgrammeRefused("not_settled", f"{job} has no settlement; only a verified actual cost is recorded")
    if job in recorded_jobs(doc):
        raise ProgrammeRefused("already_recorded", f"{job} is already recorded as {recorded_jobs(doc)[job]}")
    entry = {"id": entry_id, "label": label, "usd": round(s["settled_microusd"] / 1e6, 6), "hosted_job": job,
             "basis": f"CALCULATED from provider-reported usage, verified durable ledger ({s['basis']}); not a bill",
             "source": f"hosted admission settlement (ledger sha256 {s['ledger_sha256']}, {s['ledger_requests']} requests, {s['open_requests']} unsettled)",
             "hosted_reservation_usd": a["reserved_microusd"] / 1e6,
             "hosted_reservation_note": "Admission hold against the hosted ceiling; a temporary safety commitment, not spend, and not counted here.",
             "authorized_by": authorized_by, "recorded_on": recorded_on}
    new = append(doc, entry)
    return {"schema": "programme-ledger-append-proposal-v1", "entry": entry, "known_usd_before": sum(micro(e.get("usd") or 0) for e in doc["entries"]) / 1e6,
            "known_usd_after": sum(micro(e.get("usd") or 0) for e in new["entries"]) / 1e6, "entries_before": len(doc["entries"]),
            "entries_after": len(new["entries"]), "problems_after": check(new)}


def append(doc: dict, entry: dict) -> dict:
    """Return a NEW document with `entry` appended (existing entries unchanged); refuses anything `check` rejects."""
    new = copy.deepcopy(doc)
    new.setdefault("entries", []).append(entry)
    problems = check(new)
    if problems:
        raise ProgrammeRefused("duplicate_or_invalid", "; ".join(problems))
    return new


def _entries_close(raw: str) -> int:
    """Index of the `]` closing the top-level "entries" array (string-aware scan)."""
    k = raw.index('"entries"')
    i = raw.index("[", k)
    depth, in_str, esc = 0, False, False
    for n in range(i, len(raw)):
        c = raw[n]
        if in_str:
            esc = (c == "\\" and not esc)
            if c == '"' and not esc:
                in_str = False
            continue
        if c == '"':
            in_str, esc = True, False
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                return n
    raise ProgrammeRefused("malformed", "the programme ledger's entries array is not closed")


def append_text(raw: str, entry: dict) -> str:
    """Append `entry` as text: every existing byte of the ledger is kept (it is partly hand-formatted); verified to parse to exactly the old document
    plus the new entry, and to pass `check`."""
    doc = json.loads(raw)
    new_doc = append(doc, entry)
    close = _entries_close(raw)
    head = raw[:close].rstrip()
    body = json.dumps(entry, indent=2, ensure_ascii=True).replace("\n", "\n    ")
    text = head + ",\n    " + body + "\n  " + raw[close:]
    if json.loads(text) != new_doc or not text.startswith(head) or not text.endswith(raw[close:]):
        raise ProgrammeRefused("append_unverified", "the appended ledger does not parse to the old document plus the new entry")
    return text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m agent_readiness.hosted.programme")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "view", "propose", "append"):
        s = sub.add_parser(name)
        s.add_argument("--ledger", required=True, type=Path)
        if name != "append":
            s.add_argument("--db", type=Path, required=name != "check")
            s.add_argument("--root", type=Path)
        if name == "view":
            s.add_argument("--json", action="store_true")
        if name == "propose":
            for k in ("--job", "--entry-id", "--label", "--authorized-by", "--recorded-on", "--out"):
                s.add_argument(k, required=True)
        if name == "append":
            s.add_argument("--proposal", required=True, type=Path)
    a = ap.parse_args(argv)
    doc = json.loads(a.ledger.read_text())
    try:
        if a.cmd in ("check", "view", "propose"):
            adm = None
            if a.db:
                from .admission import Admission
                adm = Admission.open_read_only(a.db)
            root = a.root or (a.db.resolve().parent if a.db else None)
            if a.cmd == "check":
                bj = {}
                if adm is not None:
                    from .settlement import audit
                    bj = {j["job"]: j["budget"] for j in audit(adm, root)["jobs"] if j.get("budget")}
                p = check(doc, bj)
                print("\n".join(p) if p else "ok: no duplicate or ambiguous programme entries")
                return 1 if p else 0
            if a.cmd == "view":
                v = view(doc, adm, root)
                print(json.dumps(v, indent=1))
                return 0
            prop = propose(doc, adm, root, job=a.job, entry_id=a.entry_id, label=a.label, authorized_by=a.authorized_by, recorded_on=a.recorded_on)
            Path(a.out).write_text(json.dumps(prop, indent=1) + "\n")
            print(f"proposal written to {a.out} (the programme ledger is unchanged)")
            return 0
        prop = json.loads(a.proposal.read_text())
        new = append(doc, prop["entry"])
        if not sys.stdin.isatty():
            print("refused: appending to the programme ledger is an owner action at an interactive terminal", file=sys.stderr)
            return 2
        text = f"I am the owner and I append {prop['entry']['id']} (US${prop['entry']['usd']:.6f}, hosted job {prop['entry'].get('hosted_job')}) to the programme ledger"
        print(text)
        if input("Type the line above exactly to confirm: ").strip() != text:
            print("refused: the confirmation did not match; nothing changed", file=sys.stderr)
            return 1
        a.ledger.write_text(append_text(a.ledger.read_text(), prop["entry"]))
        print(f"appended {prop['entry']['id']}; entries {len(new['entries'])}")
        return 0
    except ProgrammeRefused as exc:
        print(f"refused [{exc.code}]: {exc.detail}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
