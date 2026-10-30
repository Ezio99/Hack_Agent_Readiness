"""`readiness investigate ...` (Task 016). M1 provides only credential-free commands: a scripted end-to-end demonstration, run status, and recording an approval."""
from __future__ import annotations

import json
from pathlib import Path

COMMANDS = ("investigate",)


def register(sub) -> None:
    inv = sub.add_parser("investigate", help="Task 016 autonomous website investigator (M1: scripted demo, status, approvals; no model or network)")
    isub = inv.add_subparsers(dest="investigate_command", required=True)
    demo = isub.add_parser("demo", help="Scripted end-to-end run of the pipeline plumbing (NOT a model run, no website)")
    demo.add_argument("--root", type=Path, default=Path("investigations"))
    demo.add_argument("--id", default="scripted-demo")
    ins = isub.add_parser("inspect", help="Crawl (or load a zoo site) into a content-hashed snapshot and print its neutral observations")
    src = ins.add_mutually_exclusive_group(required=True)
    src.add_argument("--zoo", help="a local zoo site id, e.g. site-1 (offline)")
    src.add_argument("--url", help="a site you operate or have permission to test (network; needs --permission-ack)")
    ins.add_argument("--permission-ack", action="store_true", help="confirm you operate this site or have permission to crawl it")
    ins.add_argument("--allow-private-hosts", action="store_true", help="allow loopback/private addresses (your own network only)")
    ins.add_argument("--max-pages", type=int, default=60)
    ins.add_argument("--out", type=Path, help="write the snapshot directory here")
    mir = isub.add_parser("mirror", help="Serve a saved snapshot read-only on loopback")
    mir.add_argument("snapshot", type=Path)
    mir.add_argument("--port", type=int, default=8100)
    pat = isub.add_parser("patch", help="Apply a patch file to a saved snapshot, producing a new snapshot (the original is untouched)")
    pat.add_argument("snapshot", type=Path)
    pat.add_argument("patch_json", type=Path)
    pat.add_argument("--out", type=Path, required=True)
    l0 = isub.add_parser("l0", help="L0 Meta capability probe (PROPOSAL: `plan` is offline; `run` needs the owner's approval hash and --allow-model-calls)")
    lsub = l0.add_subparsers(dest="l0_command", required=True)
    lsub.add_parser("plan", help="Print the exact probe manifest and its SHA-256 (no network, no key)")
    lrun = lsub.add_parser("run", help="Execute the approved probe (paid; refuses without the exact approved hash)")
    lrun.add_argument("--approved-sha256", required=True)
    lrun.add_argument("--allow-model-calls", action="store_true")
    lrun.add_argument("--out", type=Path, default=Path("investigations/l0-probe"))
    rn = isub.add_parser("run", help="Run the investigation flow (inspect -> taskgen -> freeze -> baseline trials) on a local zoo site; resumable")
    rn.add_argument("site", help="zoo site id, e.g. site-4")
    rn.add_argument("--id", default=None, help="investigation id (default: <site>-<mode>)")
    rn.add_argument("--root", type=Path, default=Path("investigations"))
    rn.add_argument("--mode", choices=["mock", "live"], default="mock", help="mock: rule tasks + scripted agent (no key); live: Meta tasks + Meta agent, each spending stage needs your hash approval")
    rn.add_argument("--repeats", type=int, default=1)
    rn.add_argument("--n-tasks", type=int, default=8)
    rn.add_argument("--total-cap-usd", type=float, default=3.0, help="hard ceiling (USD, calculated) on ALL spend of this investigation: taskgen, both trial arms and the investigation")
    rn.add_argument("--fix", action="append", default=None, help="proposal id to apply to the local mirror and retest (needs your approval hash at apply_fix, then at post_trials); repeatable")
    rn.add_argument("--post-plan", type=Path, default=None, help="JSON retest plan for an owner-selected exploratory fix: placebo tasks, affected tasks and controls (see the pre-registration)")
    rn.add_argument("--allow-model-calls", action="store_true")
    st = isub.add_parser("status", help="Show stages, outcome and pending approvals of an investigation")
    st.add_argument("run_dir", type=Path)
    ex = isub.add_parser("export", help="Write a sanitized, read-only JSON of a run for the dashboard (no private criteria, answers, traces or credentials; tolerates incomplete runs)")
    ex.add_argument("run_dir", type=Path)
    ex.add_argument("--out", type=Path, required=True)
    ex.add_argument("--public", action="store_true", help="public-demo-safe view: internal ids aliased, no attribution narratives, no stage hashes or paths (the default private export is unchanged)")
    rb = isub.add_parser("recover-batch", help="Explicitly abandon a taskgen batch whose request was reserved/sent but whose result was never persisted (an interrupted run). It is never re-sent automatically.")
    rb.add_argument("run_dir", type=Path)
    rb.add_argument("--batch", type=int, required=True)
    rb.add_argument("--abandon", action="store_true", required=True, help="record the batch as abandoned (the request stays counted in the ledger; no re-send)")
    rb.add_argument("--note", required=True, help="who decided what")
    fk = isub.add_parser("fork", help="Free, offline: create a NEW run that imports the frozen tasks, baseline evidence and spending history of an existing run (no paid stage is re-run; every paid stage of the fork needs a fresh approval)")
    fk.add_argument("source_dir", type=Path)
    fk.add_argument("--id", required=True, help="id of the new run")
    fk.add_argument("--root", type=Path, default=Path("investigations"))
    fk.add_argument("--carry-investigation", action="store_true", help="also carry a COMPLETED investigator's result (verified evidence prefix + artifacts) so later stages report it; the investigator is not re-run")
    po = isub.add_parser("propose-owner", help="Free, offline: record an owner-selected EXPLORATORY proposal (owner-authored unverified hypothesis + validated patch). Never a finding; still needs apply_fix approval")
    po.add_argument("run_dir", type=Path)
    po.add_argument("--owner", required=True, help="who selects this change")
    po.add_argument("--claim-kind", default="info_absent_on_template")
    po.add_argument("--label", required=True, help="field label for the patch template (e.g. 'daily fee')")
    po.add_argument("--hypothesis", required=True)
    po.add_argument("--prediction", required=True, help="falsifiable prediction")
    po.add_argument("--cite", action="append", required=True, help="existing observation id (repeatable)")
    ap = isub.add_parser("approve", help="Record the owner's approval of an exact stage manifest hash")
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--stage", required=True)
    ap.add_argument("--sha256", required=True, help="the manifest hash printed by `status`")
    ap.add_argument("--note", required=True)


def main(args) -> None:
    from .run import InvestigationRun
    if args.investigate_command == "demo":
        from .demo import run_demo
        run, rep = run_demo(args.root, args.id)
        print(f"scripted demo finished: {run.dir}  outcome={rep['outcome']}  (mode={run.mode}; {rep['notices'][0]})")
        return
    if args.investigate_command == "l0":
        from . import l0
        if args.l0_command == "plan":
            m = l0.manifest()
            print(json.dumps(m, indent=1))
            print(f"manifest sha256: {l0.manifest_sha256(m)}")
            return
        from ..ledger import Halt
        try:
            rep = l0.run(args.out, approved_sha256=args.approved_sha256, allow_model_calls=args.allow_model_calls)
        except Halt as exc:
            raise SystemExit(f"refused: {exc}")
        print(json.dumps(rep["evaluation"], indent=1))
        return
    if args.investigate_command == "run":
        from . import flow
        from ..ledger import Halt
        try:
            run, pipe, ctx = flow.build(args.root, args.id or f"{args.site}-{args.mode}", args.site, mode=args.mode,
                                        options={"repeats": args.repeats, "n_tasks": args.n_tasks, "total_cap_usd": args.total_cap_usd, "allow_model_calls": args.allow_model_calls, "fix": args.fix,
                                                  **({"post_plan": json.loads(args.post_plan.read_text())} if args.post_plan else {})})
            res = pipe.run(ctx)
        except Halt as exc:
            raise SystemExit(f"refused: {exc}")
        print(f"{run.state['id']}: {res.status}" + (f" at {res.stage}" if res.stage else ""))
        if res.status == "done" and run.has_artifact("report-final"):
            rep = run.artifact("report-final")
            if rep.get("investigation_status") != "completed":
                print(f"  NOTE: investigation status is {rep.get('investigation_status')} (outcome: {rep.get('outcome')}). {rep.get('outcome_note', '')}")
        if res.status == "awaiting_approval":
            print(f"stage {res.stage} needs your approval of manifest sha256 {res.manifest_sha256}\n  manifest: {run.dir}/artifacts/manifests/{res.stage}-{res.manifest_sha256[:16]}.json\n"
                  f"  approve: readiness investigate approve {run.dir} --stage {res.stage} --sha256 {res.manifest_sha256} --note '<who approved what>'  then re-run this command" + (" --allow-model-calls" if args.mode == "live" else ""))
        elif res.status == "failed":
            raise SystemExit(f"failed at {res.stage}: {res.error}")
        return
    if args.investigate_command == "inspect":
        from .inspect.crawl import HttpFetcher, Limits, crawl
        from .inspect.profile import build_profile, observations
        if args.zoo:
            from . import zoo
            snap = zoo.snapshot(args.zoo)
        else:
            if not args.permission_ack:
                raise SystemExit("refusing: crawling a live site needs --permission-ack (only sites you operate or have permission to test)")
            snap = crawl(HttpFetcher(args.url, allow_private_hosts=args.allow_private_hosts), Limits(max_pages=args.max_pages))
        if args.out:
            snap.save(args.out)
        print(f"snapshot {snap.sha256}  pages={len(snap.pages())}  fidelity={snap.meta.get('fidelity', {}).get('level')}")
        for o in observations(build_profile(snap), mode="scripted" if args.zoo else "live"):
            print(f"- [{o.kind}] {o.summary}")
        return
    if args.investigate_command == "mirror":
        import uvicorn
        from .sitemodel.server import Mirror
        from .sitemodel.snapshot import Snapshot
        snap = Snapshot.load(args.snapshot)
        print(f"Serving snapshot {snap.sha256[:12]} read-only at http://127.0.0.1:{args.port}/")
        uvicorn.run(Mirror(snap), host="127.0.0.1", port=args.port, log_level="warning")
        return
    if args.investigate_command == "patch":
        from .sitemodel.patch import PatchError, apply_patch
        from .sitemodel.snapshot import Snapshot
        snap = Snapshot.load(args.snapshot)
        try:
            new, rep = apply_patch(snap, json.loads(args.patch_json.read_text()))
        except (PatchError, ValueError) as exc:
            raise SystemExit(f"patch refused: {exc}")
        new.save(args.out)
        print(json.dumps(rep, indent=2))
        return
    if args.investigate_command == "export":
        from .export import ExportError, write_export
        try:
            data = write_export(args.run_dir, args.out, public=args.public)
        except (ExportError, FileNotFoundError) as exc:
            raise SystemExit(f"export refused: {exc}")
        print(f"exported {data['run']['id']} -> {args.out}  complete={data['run']['complete']}  source={data['run']['report_source']}  modes={','.join(data['modes'])}")
        return
    if args.investigate_command == "fork":
        from .fork import fork, load_fork
        try:
            d = fork(args.source_dir, args.root, args.id, carry_investigation=args.carry_investigation)
        except (ValueError, FileExistsError) as exc:
            raise SystemExit(f"fork refused: {exc}")
        prov = load_fork(InvestigationRun(d))
        print(f"forked {prov['source_run']} -> {d}\n  imported {len(prov['imported_sha256'])} files; imported_files_sha256 {prov['imported_files_sha256'][:16]}...; spending history carried over: "
              f"committed US${prov['source_ledger']['committed_usd']}\n  NOT imported: approvals, evidence store, investigator output. Next (free): re-run the same `run` command with --id {args.id} to reach the investigate approval gate.")
        return
    if args.investigate_command == "propose-owner":
        from .owner import add_owner_proposal
        run = InvestigationRun(args.run_dir)
        try:
            p = add_owner_proposal(run, owner=args.owner, claim_kind=args.claim_kind, params={"label": args.label}, hypothesis=args.hypothesis, prediction=args.prediction, cites=args.cite)
        except ValueError as exc:
            raise SystemExit(f"proposal refused: {exc}")
        print(f"{p.id}  {p.label}\n  patch_sha256 {p.change['patch_sha256']}  (not applied; apply_fix needs your exact-manifest approval)")
        return
    if args.investigate_command == "recover-batch":
        from .taskgen.stage import recover_batch
        try:
            rec = recover_batch(InvestigationRun(args.run_dir), args.batch, note=args.note)
        except (ValueError, FileNotFoundError) as exc:
            raise SystemExit(f"recovery refused: {exc}")
        print(f"batch {args.batch} recorded as {rec['status']}; re-run the stage to continue with the remaining batches (the ambiguous request stays counted in the ledger)")
        return
    run = InvestigationRun(args.run_dir)
    if args.investigate_command == "approve":
        print(json.dumps(run.approve(args.stage, args.sha256, args.note), indent=2))
        return
    s = run.state
    final = run.artifact("report-final") if run.has_artifact("report-final") else None
    print(f"{s['id']}  target={s['target']}  mode={s['mode']}  outcome={(final or {}).get('outcome') or run.evidence.outcome()}" + (f"  investigation_status={final['investigation_status']}" if final and final.get("investigation_status") else ""))
    for name, st in s["stages"].items():
        print(f"  {name:16} {st['status']}" + (f"  needs approval of sha256 {st['manifest_sha256']}" if st["status"] == "awaiting_approval" else ""))
