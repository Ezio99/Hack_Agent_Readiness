"""The lifecycle service behind the product API (M8). One evaluation model, three sources, all served through the same views:

  datasets     sanitized, versioned, immutable projections of recorded evaluations (the preloaded M7 experiment); integrity-checked at startup
  store        the lifecycle write-once store (suites, approvals, frozen suites, manifests, run results), when deployed with the server
  jobs         evaluations launched in the product (operator-only rehearsals in this release), projected with `projection.project` once complete,
               audited with the store's private outcomes, and cached under runs/derived/

Server-side selection only: a launch names a frozen suite reference and two registered variants of its site; the server finds or builds the
manifest (existing manifest of that exact frozen suite and variants; otherwise a regression manifest of the suite's base manifest, which may differ
only in its variants; otherwise a new exploratory manifest with the server's defaults). No task, URL, model, limit or spending field is accepted.
Web approval and paid launch are disabled (no authenticated owner identity has been chosen); the API refuses them before anything is reserved."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import threading
import time
from pathlib import Path

from . import audit, dataset as DS, jobs as J, projection as P, sites as S, stage_a as SA

EVAL_ID = re.compile(r"^(?:[a-z0-9][a-z0-9-]{2,60}|lc-[0-9a-f]{32})$")
TRIAL_ID = re.compile(r"^[a-z0-9]{1,24}-[A-Za-z0-9._-]{1,80}-r\d{1,2}$")
SHOT = re.compile(r"^step-\d{3}\.(?:png|webp)$")
SHA = re.compile(r"^[0-9a-f]{64}$")
APPROVAL_UNAVAILABLE = {"available": False, "reason": "owner_authentication_not_configured",
                        "detail": "Approving or freezing a suite from the web needs a verified owner identity; no authentication model has been chosen yet. "
                                  "Approval stays at an owner terminal (exact suite hash, typed attestation, interactive terminal)."}
PAID_UNAVAILABLE = {"available": False, "reason": "paid_launch_not_authorized",
                    "detail": "Paid evaluations need an authenticated owner authorisation bound to the exact frozen suite and manifest, and explicit "
                              "spending approval. Neither is available from the web in this release; no paid call is made."}
DEFAULTS = {"repetitions": 1, "seed": 7, "hard_cap_usd": 8.0}


class NotFound(LookupError):
    pass


class Refused(PermissionError):
    def __init__(self, code: str, detail: str, status: int = 403):
        super().__init__(detail)
        self.code, self.detail, self.status = code, detail, status


class LifecycleService:
    def __init__(self, *, datasets: Path | None = None, store_root: Path | None = None, runs_root: Path | None = None, executor=None,
                 admission=None, client_key: bytes = b"", log=print):
        self.datasets_root = Path(datasets) if datasets else None
        self.store_root = Path(store_root) if store_root and (Path(store_root) / "objects").is_dir() else None
        self.runs_root = Path(runs_root) if runs_root else None
        self.executor, self.admission, self.client_key, self.log = executor, admission, client_key, log
        self.problems: list[str] = []
        self.datasets: dict[str, Path] = {}
        self._cache: dict[str, dict] = {}
        self._lock = threading.Lock()
        self.inflight: set[str] = set()
        self._load_datasets()

    # ------------------------------------------------------------------------------------------------ sources
    def _load_datasets(self):
        if not self.datasets_root or not self.datasets_root.is_dir():
            return
        for meta in sorted(self.datasets_root.glob("*/v*/DATASET.json")):
            d = meta.parent
            rep = DS.validate(d)
            if not rep["valid"]:
                self.problems.append(f"dataset {d.parent.name}/{d.name} withheld: {rep['problems'][:3]}")
                self.log(f"lifecycle: dataset {d.parent.name}/{d.name} failed validation and is not served")
                continue
            m = json.loads(meta.read_text())
            cur = self.datasets.get(m["id"])
            if cur is None or json.loads((cur / "DATASET.json").read_text())["version"] < m["version"]:
                self.datasets[m["id"]] = d

    def store(self):
        from ..suites.store import WriteOnceStore
        if not self.store_root:
            return None
        return WriteOnceStore(self.store_root)

    def _dataset_doc(self, did: str, rel: str) -> dict:
        d = self.datasets.get(did)
        if d is None:
            raise NotFound(did)
        p = d / rel
        if not p.is_file():
            raise NotFound(rel)
        return json.loads(p.read_text())

    # ------------------------------------------------------------------------------------------------ capabilities
    def overview(self) -> dict:
        rehearsal = bool(self.executor and getattr(self.executor, "available", False) and self.store_root and self.runs_root)
        return {"schema": "lifecycle-overview-v1",
                "steps": [
                    {"id": "website", "label": "Website", "available": True, "detail": "Registered website contexts with business context and personas (synthetic, labelled)."},
                    {"id": "tasks", "label": "Task generation", "available": True, "action_available": False,
                     "detail": "Recorded AI generation and validation runs are shown. A new paid generation needs owner authorisation and is not launchable from the web."},
                    {"id": "review", "label": "Review and approval", "available": True, "action_available": False, "detail": APPROVAL_UNAVAILABLE["detail"]},
                    {"id": "evaluate", "label": "Browser-agent evaluation", "available": True, "action_available": rehearsal,
                     "detail": "Zero-cost rehearsals of a frozen suite can be launched by the operator; paid evaluations are disabled." if rehearsal
                               else "Launching needs the lifecycle store, the browser jail and an operator; recorded evaluations remain available."},
                    {"id": "report", "label": "Readiness report", "available": True, "detail": "Six measured dimensions with evidence; no composite score."},
                    {"id": "reevaluate", "label": "Re-evaluation", "available": True, "action_available": rehearsal,
                     "detail": "Re-run the same frozen suite (same manifest, or a regression manifest that differs only in its website variants)."}],
                "onboarding": S.onboarding(), "approval": APPROVAL_UNAVAILABLE, "paid": PAID_UNAVAILABLE,
                "rehearsal": {"available": rehearsal, "operator_only": True, "cost_usd": 0.0,
                              "reason": None if rehearsal else ("no_store" if not self.store_root else "no_executor")},
                "sources": {"datasets": sorted(self.datasets), "store": bool(self.store_root), "jobs": bool(self.runs_root)}, "problems": len(self.problems)}

    # ------------------------------------------------------------------------------------------------ sites and Stage A
    def sites(self) -> list[dict]:
        return [S.site_view(s) for s in S.registered()]

    def site(self, site_id: str) -> dict:
        if site_id not in S.registered():
            raise NotFound(site_id)
        v = S.site_view(site_id)
        v["suites"] = [s for s in self.suites() if s["site"] == site_id]
        v["generations"] = [g for g in self.generations() if g["site"] == site_id]
        return v

    def generations(self) -> list[dict]:
        out = []
        for did in sorted(self.datasets):
            try:
                g = self._dataset_doc(did, "generation.json")
            except NotFound:
                continue
            out.append({"id": g["id"], "dataset": did, "site": g["site"], "created_at": g["created_at"], "mode": g["mode"], "stop_reason": g["stop_reason"],
                        "admissions": g["admissions"], "proposals": len(g["proposals"]), "rounds": len(g["rounds"]), "cost": g["cost"],
                        "suite_sha256": g["suite_sha256"], "generator": g["generator"]})
        return out

    def generation(self, gid: str) -> dict:
        for g in self.generations():
            if g["id"] == gid:
                return self._dataset_doc(g["dataset"], "generation.json")
        raise NotFound(gid)

    def suites(self) -> list[dict]:
        seen, out = set(), []
        st = self.store()
        if st:
            for s in SA.suites(st):
                seen.add(s["sha256"])
                out.append({**s, "source": "store"})
        for did in sorted(self.datasets):
            for p in sorted((self.datasets[did] / "suites").glob("*.json")):
                if p.stem in seen:
                    continue
                v = json.loads(p.read_text())
                seen.add(p.stem)
                out.append({"sha256": v["sha256"], "name": v["suite_name"], "version": v["version"], "site": v["site"], "tasks": len(v["tasks"]), "state": v["state"],
                            "refs": v["refs"], "synthetic": v["synthetic"], "created_at": v["created_at"], "created_by": v["created_by"], "gaps": len(v["gaps"]),
                            "source": f"dataset {did}"})
        return sorted(out, key=lambda x: (x["synthetic"], x["site"], x["name"], -x["version"]))

    def suite(self, sha: str) -> dict:
        if not SHA.match(sha):
            raise NotFound(sha)
        st = self.store()
        if st and st.kind_of(sha) == "suite":
            v = SA.suite(st, sha)
            from ..evalruns import runner as RN
            answers = self._answers_for_suite(st, sha)
            if audit.check_evaluation(v, answers):
                raise Refused("withheld", "this suite view failed the leak audit and is withheld", 409)
            return {**v, "source": "store"}
        for did, d in sorted(self.datasets.items()):
            p = d / "suites" / f"{sha}.json"
            if p.is_file():
                return {**json.loads(p.read_text()), "source": f"dataset {did}"}
        raise NotFound(sha)

    def _answers_for_suite(self, st, suite_sha: str) -> dict[str, list[str]]:
        out = {}
        s = st.get("suite", suite_sha)
        for t in s.task_sha256s:
            task = st.get("task", t)
            if task.private_sha256:
                truth = st.get("private_outcome", task.private_sha256).expected.get("truth")
                out[task.task_id] = [truth] if isinstance(truth, str) else list(truth or [])
        return out

    def decide(self, sha: str, body: dict) -> None:
        raise Refused(APPROVAL_UNAVAILABLE["reason"], APPROVAL_UNAVAILABLE["detail"])

    # ------------------------------------------------------------------------------------------------ evaluations
    def _jobs(self) -> list[dict]:
        if not self.runs_root or not (self.runs_root / "jobs").is_dir():
            return []
        out = []
        for p in sorted((self.runs_root / "jobs").glob("lc-*.json")):
            try:
                out.append(J.load_job(self.runs_root, p.stem))
            except (OSError, ValueError):
                continue
        return sorted(out, key=lambda j: -j["created_at"])

    def evaluations(self) -> list[dict]:
        out = []
        for did in sorted(self.datasets):
            ev = self._dataset_doc(did, "evaluation.json")
            meta = json.loads((self.datasets[did] / "DATASET.json").read_text())
            out.append({**self._summary(ev), "source": "dataset", "dataset_version": meta["version"], "state": "completed"})
        for j in self._jobs():
            row = {"id": j["id"], "title": j.get("label"), "mode": j["mode"], "state": j["state"], "source": "launched", "created_at": j["created_at"],
                   "finished_at": j.get("finished_at"), "manifest_sha256": j["manifest_sha256"], "request": j.get("request")}
            if j["state"] == "completed":
                try:
                    row.update({k: v for k, v in self._summary(self.evaluation(j["id"])).items() if k not in ("id",)})
                    row["state"] = "completed"
                except Exception:
                    row["state"] = "unverified"
            out.append(row)
        return out

    @staticmethod
    def _summary(ev: dict) -> dict:
        ts = ev["dimensions"]["task_success"]["variants"]
        nav = ev["dimensions"]["navigation_efficiency"]["variants"]
        return {"id": ev["id"], "title": ev["title"], "mode": ev["mode"], "mode_label": ev["mode_label"], "site": ev["site"]["label"], "site_id": ev["site"]["id"],
                "suite": f"{ev['suite']['name']} v{ev['suite']['version']}", "frozen_suite_sha256": ev["frozen_suite"]["sha256"], "manifest_sha256": ev["manifest"]["sha256"],
                "variants": [v["name"] for v in ev["manifest"]["variants"]], "started_at": ev["started_at"], "finished_at": ev["finished_at"],
                "tasks": len([t for t in ev["tasks"] if t["executed"]]), "trials": len(ev["trials"]), "exploratory": ev["exploratory"],
                "success": ts, "requests": {v: n["model_requests_total"] for v, n in nav.items()}, "cost_usd": ev["cost"]["total_usd"]}

    def _job_doc(self, job: dict) -> dict:
        key = f"{job['id']}:{P.VERSION}"
        with self._lock:
            if key in self._cache:
                return self._cache[key]
        cache = self.runs_root / "derived" / f"{job['id']}.{P.VERSION}.json"
        if cache.is_file():
            doc = json.loads(cache.read_text())
        else:
            st = self.store()
            if st is None:
                raise Refused("no_store", "the lifecycle store is not available on this server", 503)
            runs = P.load_runs([self.runs_root / r for r in job["runs"].values()])
            doc = P.project(st, runs, evaluation_id=job["id"], title=job.get("label"), context=S.context_for(next(iter(runs.values())).state["config"]["site"]))
            from ..evalruns import runner as RN
            problems = audit.check_evaluation(doc, RN._answers(st, doc["frozen_suite"]["sha256"]))
            if problems:
                self.log(f"lifecycle: evaluation {job['id']} withheld by the leak audit ({len(problems)} problems)")
                raise Refused("withheld", "this evaluation failed the public leak audit and is withheld", 409)
            if job["state"] == "completed":
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(json.dumps(doc))
        if job["state"] == "completed":
            with self._lock:
                self._cache[key] = doc
        return doc

    def evaluation(self, eid: str) -> dict:
        if not EVAL_ID.match(eid):
            raise NotFound(eid)
        if eid in self.datasets:
            ev = self._dataset_doc(eid, "evaluation.json")
            meta = json.loads((self.datasets[eid] / "DATASET.json").read_text())
            return {**ev, "source": {"kind": "dataset", "id": meta["id"], "version": meta["version"], "built_at": meta["built_at"],
                                     "description": meta["description"], "runs": meta["source"]["runs"], "run_results": meta["source"]["run_results"]}}
        if eid.startswith("lc-") and self.runs_root:
            try:
                job = J.load_job(self.runs_root, eid)
            except (OSError, ValueError):
                raise NotFound(eid) from None
            if not job.get("runs"):
                raise Refused("not_ready", "this evaluation has not produced results yet", 409)
            return {**self._job_doc(job), "source": {"kind": "launched", "job": eid, "state": job["state"]}}
        raise NotFound(eid)

    def timeline(self, eid: str, trial: str) -> dict:
        if not TRIAL_ID.match(trial):
            raise NotFound(trial)
        if eid in self.datasets:
            return self._dataset_doc(eid, f"trials/{trial}.json")
        run = self._job_run_for(eid, trial)
        tl = P.trial_timeline(run, trial)
        st = self.store()
        if st is not None:
            from ..evalruns import runner as RN
            if audit.check(tl, [a for v in RN._answers(st, st.get("manifest", run.state["config"]["manifest_sha256"]).frozen_suite_sha256).values() for a in v],
                           exempt_agent=run.state["config"].get("mode") == "paid"):
                raise Refused("withheld", "this trial view failed the leak audit and is withheld", 409)
        return tl

    def _job_run_for(self, eid: str, trial: str):
        if not (eid.startswith("lc-") and self.runs_root):
            raise NotFound(eid)
        try:
            job = J.load_job(self.runs_root, eid)
        except (OSError, ValueError):
            raise NotFound(eid) from None
        from ..investigate.run import InvestigationRun
        for rel in (job.get("runs") or {}).values():
            run = InvestigationRun(self.runs_root / rel)
            if run.has_artifact(f"trials/{trial}"):
                return run
        raise NotFound(trial)

    def screenshot(self, eid: str, trial: str, name: str) -> tuple[Path, str]:
        if not TRIAL_ID.match(trial) or not SHOT.match(name):
            raise NotFound(name)
        if eid in self.datasets:
            p = self.datasets[eid] / "screenshots" / trial / name
            if p.is_file() and p.resolve().is_relative_to(self.datasets[eid].resolve()):
                return p, "image/webp"
            raise NotFound(name)
        run = self._job_run_for(eid, trial)
        p = P.trial_dir(run, trial) / name
        if name.endswith(".png") and p.is_file():
            return p, "image/png"
        raise NotFound(name)

    # ------------------------------------------------------------------------------------------------ launch
    def frozen_suites(self) -> list[dict]:
        st = self.store()
        if st is None:
            return []
        out = []
        rd = st.root / "refs" / "frozen_suite"
        for p in sorted(rd.glob("*.json")) if rd.is_dir() else []:
            r = json.loads(p.read_text())
            try:
                fz = st.get("frozen_suite", r["sha256"])
                s = st.get("suite", fz.suite_sha256)
            except Exception:
                continue
            if s.site not in S.registered():
                continue
            out.append({"ref": r["name"], "sha256": r["sha256"], "suite_sha256": fz.suite_sha256, "site": s.site, "synthetic": s.suite_name.startswith("synthetic-"),
                        "tasks": len(s.task_sha256s), "variants": [v["name"] for v in S.site_view(s.site, with_hashes=False)["variants"]]})
        return out

    def _manifest_for(self, st, frozen_sha: str, variants: list[tuple[str, str]]) -> tuple[str, str]:
        from ..evalruns import manifest as MF
        from ..framework.site import get
        from ..suites import plan as PL
        same, base = [], []
        md = st.root / "objects" / "manifest"
        for p in sorted(md.glob("*.json")) if md.is_dir() else []:
            m = st.get("manifest", p.stem)
            if m.frozen_suite_sha256 != frozen_sha:
                continue
            (same if [tuple(v) for v in m.variants] == variants else base).append((m.provenance.created_at, p.stem, m))
        if same:
            return sorted(same)[0][1], "existing manifest for this frozen suite and these website variants"
        at = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
        if base:
            _, bsha, _ = sorted(base)[0]
            m, _diff = MF.regression(st, bsha, variants=variants, created_at=at, notes=f"re-evaluation of manifest {bsha} launched in the product")
            return st.put(m), f"regression manifest of {bsha[:12]}: the same frozen suite, plan, agent, repetitions and seed; only the website variants differ"
        _, suite, tasks = MF.suite_tasks(st, frozen_sha)
        det = [t for t in tasks if t.spec.verifiability == "deterministic"]
        primary = "natural" if any(t.condition == "natural" for t in det) else "assisted"
        plan = PL.make_plan(n_tasks=sum(t.condition == primary for t in det), repetitions=DEFAULTS["repetitions"], requested="confirmatory",
                            allow_exploratory_fallback=True, sims=500, primary_outcome=f"evidence-supported pass (official grader v1), {primary}-wording condition")
        site = get(suite.site)
        m = MF.build(st, frozen_sha, variants=variants, oracle=site.oracle().label, plan=plan, repetitions=DEFAULTS["repetitions"], seed=DEFAULTS["seed"],
                     created_at=at, hard_cap_usd=DEFAULTS["hard_cap_usd"], notes="built by the product for a launched evaluation")
        return st.put(m), "new manifest with the server's defaults (1 repetition, seed 7, exploratory unless a confirmatory design is feasible)"

    def launch(self, *, frozen_suite: str, variants: list[str], mode: str, operator: bool, start) -> dict:
        if mode == "paid":
            raise Refused(PAID_UNAVAILABLE["reason"], PAID_UNAVAILABLE["detail"])
        if mode != "rehearsal":
            raise Refused("invalid_mode", "unknown evaluation mode", 422)
        if not operator:
            raise Refused("operator_only", "Launching evaluations is limited to the operator in this release.")
        if not (self.executor and getattr(self.executor, "available", False) and self.store_root and self.runs_root and self.admission is not None):
            raise Refused("unavailable", "Launching evaluations is unavailable on this server (store, browser jail or worker not configured).", 503)
        st = self.store()
        match = next((f for f in self.frozen_suites() if f["ref"] == frozen_suite), None)
        if match is None:
            raise Refused("unknown_suite", "No frozen suite with that reference exists on this server.", 404)
        allowed = {v["name"]: v["snapshot_sha256"] for v in S.site_view(match["site"])["variants"]}
        if len(variants) != 2 or len(set(variants)) != 2 or any(v not in allowed for v in variants):
            raise Refused("invalid_variants", f"Choose two different registered website variants of {match['site']}: {', '.join(allowed)}.", 422)
        manifest_sha, basis = self._manifest_for(st, match["sha256"], [(v, allowed[v]) for v in variants])
        job_id = J.new_id()
        client = hmac.new(self.client_key or b"lifecycle", b"operator-lifecycle", hashlib.sha256).hexdigest()
        from ..hosted.admission import Refused as AdmissionRefused
        try:
            self.admission.reserve_amount(job_id, client, 0)
        except AdmissionRefused as exc:
            raise Refused("busy", {"evaluation capacity is occupied": "Another evaluation is running. Wait for it to finish, then launch.",
                                   "rate limit exceeded": "An evaluation was launched a moment ago. Please wait a couple of minutes."}.get(str(exc), str(exc)), 429) from exc
        label = f"Rehearsal of {frozen_suite} · {variants[0]} vs {variants[1]}"
        J.new_job(self.runs_root, job_id, manifest_sha=manifest_sha, mode="rehearsal", request={"frozen_suite": frozen_suite, "variants": variants, "mode": mode,
                                                                                             "manifest_basis": basis}, label=label)
        with self._lock:
            self.inflight.add(job_id)
        start(job_id)
        return {"id": job_id, "state": "reserved", "mode": "rehearsal", "manifest_sha256": manifest_sha, "manifest_basis": basis, "label": label}

    def work(self, job_id: str) -> None:
        try:
            self.admission.transition(job_id, "reserved", "running")
            self.executor.run(job_id)
            self.admission.transition(job_id, "running", "completed")
        except Exception:
            held = self.admission.get(job_id)
            if held and held["state"] in ("reserved", "running"):
                state = "timed_out" if held["state"] == "running" and J.load_job(self.runs_root, job_id).get("state") == "timed_out" else "failed"
                self.admission.transition(job_id, held["state"], state)
        finally:
            with self._lock:
                self.inflight.discard(job_id)

    def job(self, job_id: str) -> dict:
        if not J.JOB_ID.fullmatch(job_id) or not self.runs_root:
            raise NotFound(job_id)
        try:
            job = J.load_job(self.runs_root, job_id)
        except (OSError, ValueError):
            raise NotFound(job_id) from None
        done, latest = 0, None
        from ..investigate.run import InvestigationRun
        for rel in (job.get("runs") or {}).values():
            run = InvestigationRun(self.runs_root / rel)
            done += len(list((run.dir / "artifacts" / "trials").glob("*.json")))
            for tr in (run.dir / "trial-data").glob("*/*/trace.jsonl"):
                m = tr.stat().st_mtime
                if latest is None or m > latest[0]:
                    latest = (m, tr.parent.parent.name, tr.parent, run.state["config"].get("mode"))
        live = None
        if latest and job["state"] in ("reserved", "running"):
            from ..hosted import telemetry
            tl = telemetry.timeline(latest[2])
            steps = tl["steps"][-6:] if latest[3] == "paid" else P._redact_stand_in(tl["steps"][-6:])
            live = {"trial": latest[1], "steps": steps, "current": tl["current"]}
        with self._lock:
            orphan = job["state"] in ("reserved", "running") and job_id not in self.inflight
        return {"id": job_id, "state": "interrupted" if orphan else job["state"], "mode": job["mode"], "label": job.get("label"), "request": job.get("request"),
                "manifest_sha256": job["manifest_sha256"], "created_at": job["created_at"], "started_at": job.get("started_at"), "finished_at": job.get("finished_at"),
                "planned": job.get("planned"), "completed_trials": done, "stopped": job.get("stopped"), "error": job.get("error"), "live": live,
                "notice": P.MODES["rehearsal"]["notice"] if job["mode"] == "rehearsal" else None}
