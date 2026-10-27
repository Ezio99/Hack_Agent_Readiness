import os
import subprocess
import sys
from contextlib import asynccontextmanager
import pytest
from agent_readiness import cli, env, runner

SECRET = "sk-test-not-a-real-key-0123456789"


def test_dotenv_loads_without_overriding_process_environment(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text(f'# comment\nMETA_MODEL_API_KEY="{SECRET}"\nOTHER_VAR=from-file\n')
    path.chmod(0o600)
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    monkeypatch.setenv("OTHER_VAR", "from-process")
    assert env.load_repo_env(path) is True
    assert os.environ["META_MODEL_API_KEY"] == SECRET
    assert os.environ["OTHER_VAR"] == "from-process"
    monkeypatch.delenv("META_MODEL_API_KEY")


def test_process_key_wins_and_missing_file_is_ignored(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("META_MODEL_API_KEY=from-file\n")
    path.chmod(0o600)
    monkeypatch.setenv("META_MODEL_API_KEY", "from-process")
    env.load_repo_env(path)
    assert os.environ["META_MODEL_API_KEY"] == "from-process"
    assert env.load_repo_env(tmp_path / "absent.env") is False


def test_dotenv_is_not_searched_upward_from_cwd(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("META_MODEL_API_KEY=parent-file\n")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    env.load_repo_env()  # explicit repository-root path only
    assert os.environ.get("META_MODEL_API_KEY") != "parent-file"
    assert env.REPO_ROOT == env.Path(__file__).resolve().parents[1]


def test_loading_never_prints_values_and_warns_on_loose_permissions(tmp_path, monkeypatch, capsys):
    path = tmp_path / ".env"
    path.write_text(f"META_MODEL_API_KEY={SECRET}\n")
    path.chmod(0o644)
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    env.load_repo_env(path)
    captured = capsys.readouterr()
    assert "chmod 600" in captured.err
    assert SECRET not in captured.out + captured.err
    monkeypatch.delenv("META_MODEL_API_KEY")


def test_scrubbed_environment_hides_key_from_child_processes_and_restores(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", SECRET)
    probe = [sys.executable, "-I", "-c", "import os;print('LEAK' if 'META_MODEL_API_KEY' in os.environ else 'clean')"]
    with env.scrubbed_environment("META_MODEL_API_KEY", "ABSENT_VAR"):
        assert subprocess.run(probe, capture_output=True, text=True).stdout.strip() == "clean"
    assert subprocess.run(probe, capture_output=True, text=True).stdout.strip() == "LEAK"
    assert os.environ["META_MODEL_API_KEY"] == SECRET


def test_scrub_restores_after_exception(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", SECRET)
    with pytest.raises(RuntimeError):
        with env.scrubbed_environment("META_MODEL_API_KEY"):
            raise RuntimeError("boom")
    assert os.environ["META_MODEL_API_KEY"] == SECRET


async def test_runner_hides_key_while_agent_and_browser_run(tmp_path, monkeypatch):
    @asynccontextmanager
    async def fake_target(url):
        yield "http://127.0.0.1:8000/"
    seen = {}
    async def spy_attempt(public, url, model, recorder, effective):
        seen["during"] = os.environ.get("META_MODEL_API_KEY")
        raise RuntimeError("stop after observing environment")
    monkeypatch.setenv("META_MODEL_API_KEY", SECRET)
    monkeypatch.setattr(runner, "target", fake_target)
    monkeypatch.setattr(runner, "create_model", lambda config, effective: object())
    monkeypatch.setattr(runner, "attempt", spy_attempt)
    path, _ = await runner.run(mode="live", allow_model_calls=True, output=tmp_path)
    assert seen["during"] is None
    assert os.environ["META_MODEL_API_KEY"] == SECRET
    assert SECRET not in "".join(p.read_text() for p in path.glob("*.json*"))


def test_cli_run_loads_dotenv_only_for_run(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "load_repo_env", lambda: calls.append(1))
    monkeypatch.setattr(sys, "argv", ["readiness", "generate"])
    cli.main()
    assert calls == []


async def test_runner_hides_key_during_smoke_too(tmp_path, monkeypatch):
    @asynccontextmanager
    async def fake_target(url):
        yield "http://127.0.0.1:8000/"
    seen = {}
    async def spy_smoke(public, url, recorder, effective):
        seen["during"] = os.environ.get("META_MODEL_API_KEY")
        raise RuntimeError("stop")
    monkeypatch.setenv("META_MODEL_API_KEY", SECRET)
    monkeypatch.setattr(runner, "target", fake_target)
    monkeypatch.setattr(runner, "smoke", spy_smoke)
    await runner.run(mode="smoke", output=tmp_path)
    assert seen["during"] is None and os.environ["META_MODEL_API_KEY"] == SECRET


def test_scrub_keeps_lazy_load_dotenv_imports_from_restoring_the_key(tmp_path):
    """Replicates Browser Use: a module calling load_dotenv() at import finds a .env above its own directory.

    Runs a script file (so python-dotenv uses the importing module's directory, as in a real run, instead of the
    cwd fallback it uses for ``-c``) from an empty cwd so the repository's real .env can never be read.
    """
    (tmp_path / ".env").write_text("META_MODEL_API_KEY=file-value\n")
    pkg = tmp_path / "venv" / "site"
    pkg.mkdir(parents=True)
    (pkg / "lazy_mod.py").write_text("from dotenv import load_dotenv\nload_dotenv()\n")
    (pkg / "lazy_mod2.py").write_text("from dotenv import load_dotenv\nload_dotenv()\n")
    empty_cwd = tmp_path / "empty_cwd"
    empty_cwd.mkdir()
    script = tmp_path / "run.py"
    script.write_text(
        "import os, sys\n"
        f"sys.path.insert(0, {str(pkg)!r})\n"
        "from agent_readiness.env import scrubbed_environment\n"
        "os.environ.pop('META_MODEL_API_KEY', None)\n"
        "import lazy_mod2  # control: outside the scrub the .env IS loaded\n"
        "control = os.environ.get('META_MODEL_API_KEY') == 'file-value'\n"
        "os.environ['META_MODEL_API_KEY'] = 'process-value'\n"
        "with scrubbed_environment('META_MODEL_API_KEY'):\n"
        "    import lazy_mod\n"
        "    inside = 'META_MODEL_API_KEY' in os.environ\n"
        "import dotenv\n"
        "print(control, inside, os.environ['META_MODEL_API_KEY'], dotenv.load_dotenv.__name__)\n")
    out = subprocess.run([sys.executable, "-I", str(script)], capture_output=True, text=True, cwd=empty_cwd,
                         env={"PATH": os.environ.get("PATH", "")})
    assert out.returncode == 0, out.stderr
    assert out.stdout.split() == ["True", "False", "process-value", "load_dotenv"]
