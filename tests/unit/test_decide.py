from types import SimpleNamespace

import pytest

from strayguard import decide


def answer(choice, probability):
    return {"choice": choice, "probabilities": {choice: probability}}


def item(key, blobs=None):
    return SimpleNamespace(key=key, path=key, blob_ids=blobs or (key,))


def test_threshold_edge():  # T-05
    assert decide.is_flagged(answer("scratch", 0.70), 0.70)
    assert not decide.is_flagged(answer("scratch", 0.69), 0.70)


def test_belongs_is_never_flagged():  # T-06
    assert not decide.is_flagged(answer("belongs", 0.99), 0.70)


@pytest.mark.parametrize("raw, expected", [
    (None, 0.70), ("0.8", 0.8), ("1", 1.0), ("abc", 0.70), ("0", 0.70), ("1.5", 0.70),
])
def test_threshold_from_env(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("STRAYGUARD_THRESHOLD", raising=False)
    else:
        monkeypatch.setenv("STRAYGUARD_THRESHOLD", raw)
    assert decide.threshold_from_env() == expected


def test_decide_skips_items_without_answer():
    items = [item("a"), item("b"), item("c")]
    answers = {"a": answer("scratch", 0.9), "b": answer("belongs", 0.9)}
    verdicts = decide.decide(items, answers, 0.70)
    assert [(v.item.key, v.category, v.probability) for v in verdicts] == [("a", "scratch", 0.9)]

