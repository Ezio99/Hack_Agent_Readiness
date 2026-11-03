"""The lifecycle service behind the product API (M8). One evaluation model, three sources, all served through the same views:

  datasets     sanitized, versioned, immutable projections of recorded evaluations (the preloaded M7 experiment); integrity-checked at startup
  store        the lifecycle write-once store (suites, approvals, frozen suites, manifests, run results), when deployed with the server
  jobs         evaluations launched from the hosted workspace (`POST /api/ironbark/jobs`, engine hosted/stageb.py), projected with
               `projection.project` once complete, audited with the store's private outcomes, and cached under <runs>/derived/

This service launches nothing itself: the hosted evaluation is the product's one launch path. Web approval is refused (owner terminal only)."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import threading
import time
from pathlib import Path

from . import audit, dataset as DS, jobs as J, projection as P, sites as S, stage_a as SA

EVAL_ID = re.compile(r"^(?:[a-z0-9][a-z0-9-]{2,60}|eval-[0-9a-f]{32})$")
TRIAL_ID = re.compile(r"^[a-z0-9]{1,24}-[A-Za-z0-9._-]{1,80}-r\d{1,2}$")
SHOT = re.compile(r"^step-\d{3}\.(?:png|webp)$")
SHA = re.compile(r"^[0-9a-f]{64}$")
APPROVAL_UNAVAILABLE = {"available": False, "reason": "owner_authentication_not_configured",
                        "detail": "Approving or freezing a suite from the web needs a verified owner identity; no authentication model has been chosen yet. "
                                  "Approval stays at an owner terminal (exact suite hash, typed attestation, interactive terminal)."}
EVALUATE = "Live evaluations are launched from the evaluation workspace (operator token), on the frozen suite the owner armed at the server terminal."


class NotFound(LookupError):
    pass


class Refused(PermissionError):
    def __init__(self, code: str, detail: str, status: int = 403):
        super().__init__(detail)
        self.code, self.detail, self.status = code, detail, status


def project_and_audit(store, runs_root: Path, job: dict) -> tuple[dict, list[str]]:
    """The public evaluation document of a launched job and its leak-audit problems (empty = publishable). ONE policy for every stage (M9): the
    worker runs it when the evaluation finishes (recorded as the job's publication check) and the service runs it again before serving."""
    runs = P.load_runs([Path(runs_root) / r for r in job["runs"].values()])
    doc = P.project(store, runs, evaluation_id=job["id"], title=job.get("label"), context=S.context_for(next(iter(runs.values())).state["config"]["site"]))
    from ..evalruns import runner as RN
    return doc, audit.check_evaluation(doc, RN._answers(store, doc["frozen_suite"]["sha256"]))


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
        cfg = self.executor.configuration() if self.executor is not None and hasattr(self.executor, "configuration") else None
        armed = bool(cfg and cfg["armed"])
        return {"schema": "lifecycle-overview-v2",
                "steps": [
                    {"id": "website", "label": "Website", "available": True, "detail": "Registered website contexts with business context and personas (synthetic, labelled)."},
                    {"id": "tasks", "label": "Task generation", "available": True, "action_available": False,
                     "detail": "Recorded AI generation and validation runs are shown. New generation runs at the server terminal (paid, owner-authorised)."},
                    {"id": "review", "label": "Review and approval", "available": True, "action_available": False, "detail": APPROVAL_UNAVAILABLE["detail"]},
                    {"id": "evaluate", "label": "Browser-agent evaluation", "available": True, "action_available": armed, "detail": EVALUATE},
                    {"id": "report", "label": "Readiness report", "available": True, "detail": "Six measured dimensions with evidence; no composite score."},
                    {"id": "reevaluate", "label": "Re-evaluation", "available": True, "action_available": armed,
                     "detail": "The owner arms the same frozen suite on other registered website variants (a regression manifest); the operator launches it."}],
                "onboarding": S.onboarding(), "approval": APPROVAL_UNAVAILABLE, "evaluation": cfg,
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
        for p in sorted((self.runs_root / "jobs").glob("eval-*.json")):
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
        key = f"{job['id']}:{P.CACHE_KEY}"
        with self._lock:
            if key in self._cache:
                return self._cache[key]
        cache = self.runs_root / "derived" / f"{job['id']}.{P.CACHE_KEY}.json"
        if cache.is_file():
            doc = json.loads(cache.read_text())
        else:
            st = self.store()
            if st is None:
                raise Refused("no_store", "the lifecycle store is not available on this server", 503)
            doc, problems = project_and_audit(st, self.runs_root, job)
            if job.get("audit_clean") is False or (job.get("publication_check") or {}).get("runner_public_report_clean") is False:
                problems = problems + ["the runner's public report failed its leak audit"]          # fail-closed: either audit withholds publication
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
        if eid.startswith("eval-") and self.runs_root:
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
        if not (eid.startswith("eval-") and self.runs_root):
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
        d = self._attempt_dir(eid, trial)
        p = d / name
        if name.endswith(".png") and p.is_file() and p.resolve().is_relative_to(self.runs_root.resolve()):
            return p, "image/png"
        raise NotFound(name)

    def _attempt_dir(self, eid: str, trial: str) -> Path:
        """The trial's evidence directory: from its record once finished, else (live view) its latest attempt directory under trial-data/."""
        try:
            return P.trial_dir(self._job_run_for(eid, trial), trial)
        except NotFound:
            pass
        job = J.load_job(self.runs_root, eid) if (eid.startswith("eval-") and self.runs_root) else None
        for rel in ((job or {}).get("runs") or {}).values():
            base = self.runs_root / rel / "trial-data" / trial
            attempts = sorted(x for x in base.iterdir() if x.is_dir()) if base.is_dir() else []
            if attempts:
                return attempts[-1]
        raise NotFound(trial)
