"""Deployment-safety tests (no network, no secrets): the publication gate, the dist scan and the workflow itself.
Run from the repository root:  .venv/bin/python -m pytest dashboard/scripts -q"""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DASH = ROOT / "dashboard"
GATE = DASH / "scripts" / "replay-gate.sh"
CHECK = DASH / "scripts" / "check-dist.mjs"
PHRASE = "REPLAY-FILES-APPROVED-FOR-PUBLICATION"


def gate(tmp_path, phrase=None, replays=False):
    work = tmp_path / "dashboard"
    (work / "public").mkdir(parents=True)
    if replays:
        (work / "public" / "replays").mkdir()
    out = tmp_path / "output.txt"
    env = {**os.environ, "GITHUB_OUTPUT": str(out)}
    env.pop("APPROVAL_PHRASE", None)
    if phrase is not None:
        env["APPROVAL_PHRASE"] = phrase
    proc = subprocess.run(["bash", str(GATE)], cwd=work, env=env, capture_output=True, text=True)
    return proc.returncode, (out.read_text() if out.exists() else ""), proc.stderr


def test_default_public_build_has_no_replays_and_allows_none(tmp_path):
    assert gate(tmp_path, phrase="")[:2] == (0, "allow=0\n")
    assert gate(tmp_path / "b", phrase=None)[:2] == (0, "allow=0\n")      # input absent entirely


def test_replay_files_present_without_the_exact_phrase_are_refused(tmp_path):
    for i, phrase in enumerate(["", None, "yes", PHRASE.lower(), PHRASE + " ", " " + PHRASE, "REPLAY-FILES"]):
        code, out, err = gate(tmp_path / str(i), phrase=phrase, replays=True)
        assert code == 1 and out == "" and "refusing to build" in err


def test_replay_files_with_the_exact_phrase_are_allowed(tmp_path):
    assert gate(tmp_path, phrase=PHRASE, replays=True)[:2] == (0, "allow=1\n")


def test_phrase_without_replay_files_is_refused(tmp_path):
    code, out, err = gate(tmp_path, phrase=PHRASE, replays=False)
    assert code == 1 and out == "" and "no replay files" in err


@pytest.mark.parametrize("payload", ['"; touch PWNED; echo "', "$(touch PWNED)", "`touch PWNED`", "x\nallow=1\n", "'; exit 0; '"])
def test_hostile_phrase_is_treated_as_data_and_never_executed_or_injected(tmp_path, payload):
    for replays in (False, True):
        sub = tmp_path / str(replays)
        code, out, _ = gate(sub, phrase=payload, replays=replays)
        assert code == 1 and out == ""                                 # refused, and no `allow=1` line smuggled into the output file
        assert not list(sub.rglob("PWNED"))                            # nothing was executed


PAGES = (ROOT / ".github" / "workflows" / "pages.yml").read_text()


def run_blocks(text):
    """Contents of every `run:` step (inline or block scalar) in a workflow file; no YAML dependency needed."""
    lines, blocks, i = text.splitlines(), [], 0
    while i < len(lines):
        m = re.match(r"^(\s*)(?:- )?run:\s*(.*)$", lines[i])
        if m:
            indent, inline = len(m.group(1)), m.group(2)
            body = [inline] if inline and inline not in ("|", ">", "|-", ">-") else []
            j = i + 1
            while j < len(lines) and (not lines[j].strip() or len(lines[j]) - len(lines[j].lstrip()) > indent):
                body.append(lines[j]); j += 1
            blocks.append("\n".join(body)); i = j
        else:
            i += 1
    return blocks


def test_workflow_passes_user_input_only_through_environment_variables():
    blocks = run_blocks(PAGES)
    assert blocks, "no run steps parsed"
    for body in blocks:
        assert "${{" not in body, f"expression interpolated into shell source: {body!r}"
    assert re.search(r"id: gate\n\s+env:\n(?:\s+#.*\n)?\s+APPROVAL_PHRASE: \$\{\{ inputs\.replay_approval_phrase \}\}\n\s+run: bash scripts/replay-gate\.sh", PAGES)
    for wf in (ROOT / ".github" / "workflows").glob("*.yml"):
        assert not any("inputs." in b or "github.event" in b for b in run_blocks(wf.read_text())), wf.name


def test_workflow_is_manual_only_default_input_is_empty_and_dist_is_scanned_before_upload():
    on_block = PAGES.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    assert re.findall(r"^  (\w+):", on_block, re.M) == ["workflow_dispatch"]            # no push / pull_request / schedule triggers
    assert re.search(r'replay_approval_phrase:[\s\S]*?default: ""', on_block)
    assert re.search(r"^permissions:\n  contents: read\n", PAGES, re.M)                  # the deploy job alone adds pages/id-token
    scan, upload = PAGES.index("npm run check:dist"), PAGES.index("actions/upload-pages-artifact")
    assert scan < upload
    assert "ALLOW_REPLAYS: ${{ steps.gate.outputs.allow }}" in PAGES
    assert PAGES.index("replay-gate.sh") < PAGES.index("npm run build")                  # gate runs before anything is built


def test_replay_directory_is_git_ignored_so_it_cannot_be_staged_by_accident():
    out = subprocess.run(["git", "check-ignore", "dashboard/public/replays/manifest.json", "dashboard/public/replays/fern-B-27-s02-B2.json"],
                         cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0 and out.stdout.split() == ["dashboard/public/replays/manifest.json", "dashboard/public/replays/fern-B-27-s02-B2.json"]
    tracked = subprocess.run(["git", "ls-files", "dashboard/public"], cwd=ROOT, capture_output=True, text=True).stdout
    assert tracked.strip() == ""                                     # nothing under dashboard/public is tracked


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
class TestDistScan:
    def run(self, dist, allow=False):
        env = {**os.environ, "DIST_DIR": str(dist), "ALLOW_REPLAYS": "1" if allow else "0"}
        return subprocess.run(["node", str(CHECK)], env=env, capture_output=True, text=True)

    def make(self, tmp_path, files):
        d = tmp_path / "dist"
        for name, text in files.items():
            (d / name).parent.mkdir(parents=True, exist_ok=True)
            (d / name).write_text(text)
        return d

    def test_clean_public_build_passes(self, tmp_path):
        assert self.run(self.make(tmp_path, {"index.html": "<html></html>", "assets/a.js": "console.log(1)"})).returncode == 0

    def test_replay_files_in_dist_fail_unless_explicitly_allowed(self, tmp_path):
        d = self.make(tmp_path, {"index.html": "x", "replays/manifest.json": "{}", "replays/fern-B-27-s02-B2.json": "{}"})
        assert self.run(d).returncode == 1
        assert self.run(d, allow=True).returncode == 0

    @pytest.mark.parametrize("name,text", [(".env", "A=1"), ("assets/x.js", "const k='META_MODEL_API_KEY'"), ("assets/x.js", "fetch('https://api.meta.ai/v1')"),
                                           ("assets/x.js", "path /home/vaibhav/x"), ("a.html", "http://127.0.0.1:41233/"), ("trace.jsonl", "{}"),
                                           ("review.zip", "z"), ("screenshots/a.png", "p"), ("assets/x.js.map", "{}")])
    def test_credentials_paths_traces_and_archives_are_rejected_even_when_replays_are_allowed(self, tmp_path, name, text):
        d = self.make(tmp_path, {"index.html": "x", name: text})
        assert self.run(d, allow=True).returncode == 1
