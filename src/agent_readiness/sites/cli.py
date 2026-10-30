"""`readiness site ...`: build, serve and export the fictional Ironbark Hire Co. storefront (candidate Experiment-2 site). Offline only: no model call, no network, loopback server."""
from __future__ import annotations

import json
from pathlib import Path

COMMANDS = ("site",)
DEFAULT_OUT = Path("build/ironbark")


def register(sub) -> None:
    site = sub.add_parser("site", help="Ironbark Hire Co. storefront: build / serve / catalogue / tasks / variants (offline, fictional business)")
    ssub = site.add_subparsers(dest="site_command", required=True)
    b = ssub.add_parser("build", help="Write the site to a directory (default build/ironbark/<variant>)")
    b.add_argument("--variant", default="control", help="control | discoverability | availability | cost | compatibility (combine with '+')")
    b.add_argument("--out", type=Path)
    s = ssub.add_parser("serve", help="Serve a variant on loopback")
    s.add_argument("--variant", default="control")
    s.add_argument("--port", type=int, default=8200)
    ssub.add_parser("variants", help="List the variants and their build fingerprints")
    c = ssub.add_parser("catalogue", help="Print (or write) the machine-readable source-of-truth catalogue as JSON")
    c.add_argument("--out", type=Path)
    ssub.add_parser("tasks", help="Print the illustrative candidate tasks with their independently computed answers (none is a frozen task)")


def main(args) -> None:
    from .ironbark import build as B, data as D, grading, variants as V
    cmd = args.site_command
    if cmd == "build":
        v = V.parse(args.variant)
        out = B.write_site(v, args.out or DEFAULT_OUT / v.name)
        print(f"built variant '{v.name}' -> {out}  ({len(B.build_site(v))} files, fingerprint {B.site_fingerprint(v)[:16]})")
    elif cmd == "serve":
        v = V.parse(args.variant)
        server = B.serve(v, args.port)
        print(f"Serving Ironbark Hire Co. variant '{v.name}' at http://127.0.0.1:{args.port}/  (fictional site; Ctrl-C to stop)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    elif cmd == "variants":
        for v in V.all_single():
            print(f"{v.name:18} {B.site_fingerprint(v)[:16]}  {len(B.build_site(v))} files")
    elif cmd == "catalogue":
        text = json.dumps(D.export_catalogue(), indent=2, ensure_ascii=False) + "\n"
        if args.out:
            args.out.write_text(text)
            print(f"wrote {args.out}")
        else:
            print(text, end="")
    else:
        for t in grading.candidate_tasks():
            print(json.dumps({"id": t.id, "friction": t.friction, "question": t.question, "answer": t.answer, "how_graded": t.how_graded}, ensure_ascii=False))
