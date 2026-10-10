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

