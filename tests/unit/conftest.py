"""Shared fixtures. The unit tests never use the network or the real TypeSafe API."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from strayguard import git  # noqa: E402

ENV_VARS = ("TYPESAFE_API_KEY", "OPENROUTER_API_KEY", "STRAYGUARD", "STRAYGUARD_PROVIDER",
            "STRAYGUARD_STRICT", "STRAYGUARD_THRESHOLD", "STRAYGUARD_MODEL",
            "STRAYGUARD_NAMES_ONLY", "CI", "NO_COLOR")


def run(*args):
    subprocess.run(args, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A new git repository with one commit. The test runs inside it."""
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.chdir(tmp_path)
    run("git", "init", "-q")
    run("git", "config", "user.email", "test@example.com")
    run("git", "config", "user.name", "Test")
    (tmp_path / "README.md").write_text("# demo\n")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "init")
    git.root.cache_clear()
    yield tmp_path
    git.root.cache_clear()


@pytest.fixture
def stage(repo):
    """Write files and stage them: stage({"a.py": "text", "b.bin": b"bytes"})."""
    def _stage(files):
        for path, content in files.items():
            target = repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                target.write_bytes(content)
            else:
                target.write_text(content)
        run("git", "add", "-A")
    return _stage


def staged_paths():
    out = subprocess.run(["git", "diff", "--cached", "--name-only"],
                         check=True, capture_output=True, text=True).stdout
    return sorted(out.split())
