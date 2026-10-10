import pytest

from conftest import staged_paths
from strayguard import cli, jev, ui

GUESSES = {"test_fix2.py": ("scratch", 0.91), "debug.json": ("output-dump", 0.87)}


@pytest.fixture
def fake_jev(monkeypatch):
    """Replace the Jev request. Count the items that it receives."""
    calls = []

    def ask(items, repo, api_key, model):
        calls.append([i.path for i in items])
        answers = {}
        for i in items:
            choice, probability = GUESSES.get(i.path, ("belongs", 0.95))
            answers[i.key] = {"choice": choice, "probabilities": {choice: probability}}
        return answers

    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setattr(jev, "ask", ask)
    return calls

