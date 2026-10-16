import pytest

from conftest import staged_paths
from strayguard import cli, jev, ui

GUESSES = {"test_fix2.py": ("scratch", 0.91), "debug.json": ("output-dump", 0.87)}
REQUESTS = []  # (api_key, model, endpoint) of each fake Jev call


@pytest.fixture
def fake_jev(monkeypatch):
    """Replace the Jev request. Count the items that it receives."""
    calls = []

    def ask(items, repo, api_key, model, endpoint):
        calls.append([i.path for i in items])
        REQUESTS.append((api_key, model, endpoint))
        answers = {}
        for i in items:
            choice, probability = GUESSES.get(i.path, ("belongs", 0.95))
            answers[i.key] = {"choice": choice, "probabilities": {choice: probability}}
        return answers

    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setattr(jev, "ask", ask)
    return calls


@pytest.fixture
def keyboard(monkeypatch):
    """Make the prompt interactive. Type the given answers in order."""
    def _type(*answers):
        typed = list(answers)
        monkeypatch.setattr(ui, "can_prompt", lambda: True)
        monkeypatch.setattr(ui, "_ask", lambda question, keys: typed.pop(0))
    return _type


def check():
    return cli.main(["check"])


def test_no_new_files_is_silent(repo, fake_jev, capsys):  # T-01
    assert check() == 0
    assert capsys.readouterr().err == ""
    assert fake_jev == []


def test_all_files_belong_is_silent(repo, stage, fake_jev, capsys):
    stage({"src/app.py": "x\n"})
    assert check() == 0
    assert capsys.readouterr().err == ""


def test_off(repo, stage, fake_jev, monkeypatch):
    monkeypatch.setenv("STRAYGUARD", "off")
    stage({"test_fix2.py": "x\n"})
    assert check() == 0
    assert fake_jev == []


def test_no_key_still_runs_rules(repo, stage, capsys):  # T-10
    stage({".env.local": "S=1\n", "test_fix2.py": "x\n"})
    assert check() == 0
    err = capsys.readouterr().err
    assert "no TYPESAFE_API_KEY or OPENROUTER_API_KEY set" in err
    assert ".env.local" in err and "rule" in err
    assert "test_fix2.py" not in err


def test_openrouter_key_uses_openrouter(repo, stage, fake_jev, monkeypatch):  # T-31
    monkeypatch.delenv("TYPESAFE_API_KEY")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    stage({"test_fix2.py": "x\n"})
    check()
    assert REQUESTS[-1] == ("or-key", "~typesafe/jev-latest",
                               "https://openrouter.ai/api/alpha/decisions")


def test_unknown_provider_still_runs_rules(repo, stage, fake_jev, monkeypatch, capsys):  # T-32
    monkeypatch.setenv("STRAYGUARD_PROVIDER", "vercel")
    stage({".env.local": "S=1\n", "test_fix2.py": "x\n"})
    assert check() == 0
    err = capsys.readouterr().err
    assert "unknown STRAYGUARD_PROVIDER" in err and ".env.local" in err
    assert fake_jev == []


def test_each_provider_has_its_own_cache(repo, stage, fake_jev, monkeypatch):  # T-33
    stage({"src/app.py": "x\n"})
    check()
    check()
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("STRAYGUARD_PROVIDER", "openrouter")
    check()
    assert fake_jev == [["src/app.py"], ["src/app.py"]]


def test_rule_files_are_not_sent(repo, stage, fake_jev):  # T-02
    stage({".env.local": "S=1\n", "src/app.py": "x\n"})
    check()
    assert fake_jev == [["src/app.py"]]


def test_non_interactive_warns_and_continues(repo, stage, fake_jev, capsys):  # T-13
    stage({"test_fix2.py": "x\n"})
    assert check() == 0
    err = capsys.readouterr().err
    assert "not blocking" in err and "91%" in err
    assert "git rm --cached -r -- test_fix2.py" in err


def test_strict_blocks(repo, stage, fake_jev, monkeypatch, capsys):  # T-13
    monkeypatch.setenv("STRAYGUARD_STRICT", "1")
    stage({"test_fix2.py": "x\n"})
    assert check() == 1
    assert "commit stopped" in capsys.readouterr().err


def test_unstage(repo, stage, fake_jev, keyboard):  # T-07
    stage({"test_fix2.py": "x\n", "src/app.py": "y\n"})
    keyboard("u")
    assert check() == 1
    assert staged_paths() == ["src/app.py"]
    assert (repo / "test_fix2.py").exists()


def test_gitignore(repo, stage, fake_jev, keyboard):  # T-08
    stage({"test_fix2.py": "x\n"})
    keyboard("g")
    assert check() == 1
    assert (repo / ".gitignore").read_text() == "/test_fix2.py\n"
    assert staged_paths() == [".gitignore"]


def test_keep_then_silent(repo, stage, fake_jev, keyboard, capsys):  # T-09
    stage({"test_fix2.py": "x\n"})
    keyboard("k")
    assert check() == 0
    capsys.readouterr()
    assert check() == 0
    assert capsys.readouterr().err == ""


def test_one_by_one(repo, stage, fake_jev, keyboard):  # SG-63
    stage({"debug.json": "{}\n", "test_fix2.py": "x\n"})
    keyboard("o", "u", "k")
    assert check() == 1
    assert staged_paths() == ["test_fix2.py"]


def test_second_run_uses_cache(repo, stage, fake_jev):  # T-14
    stage({"src/app.py": "x\n"})
    check()
    check()
    assert len(fake_jev) == 1


def test_git_error_does_not_block(tmp_path, monkeypatch, capsys):  # SG-85
    monkeypatch.chdir(tmp_path)
    assert check() == 0
    assert "not a git repository" in capsys.readouterr().err


def test_install_and_uninstall(repo):
    hook = repo / ".git" / "hooks" / "pre-commit"
    assert cli.main(["install"]) == 0
    assert "# strayguard" in hook.read_text()
    assert hook.stat().st_mode & 0o111
    assert cli.main(["uninstall"]) == 0
    assert not hook.exists()


def test_install_keeps_other_hook(repo):  # T-15
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho mine\n")
    assert cli.main(["install"]) == 1
    assert hook.read_text() == "#!/bin/sh\necho mine\n"
    assert cli.main(["uninstall"]) == 0
    assert hook.exists()
