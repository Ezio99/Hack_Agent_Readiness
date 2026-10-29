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
    rn.add_argument("--stage-cap-usd", type=float, default=3.0)
    rn.add_argument("--allow-model-calls", action="store_true")
    st = isub.add_parser("status", help="Show stages, outcome and pending approvals of an investigation")
    st.add_argument("run_dir", type=Path)
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
                                        options={"repeats": args.repeats, "n_tasks": args.n_tasks, "stage_cap_usd": args.stage_cap_usd, "allow_model_calls": args.allow_model_calls})
            res = pipe.run(ctx)
        except Halt as exc:
            raise SystemExit(f"refused: {exc}")
        print(f"{run.state['id']}: {res.status}" + (f" at {res.stage}" if res.stage else ""))
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
    run = InvestigationRun(args.run_dir)
    if args.investigate_command == "approve":
        print(json.dumps(run.approve(args.stage, args.sha256, args.note), indent=2))
        return
    s = run.state
    print(f"{s['id']}  target={s['target']}  mode={s['mode']}  outcome={run.evidence.outcome()}")
    for name, st in s["stages"].items():
        print(f"  {name:16} {st['status']}" + (f"  needs approval of sha256 {st['manifest_sha256']}" if st["status"] == "awaiting_approval" else ""))
