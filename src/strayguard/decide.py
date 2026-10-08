"""Decide which items to flag, and remember answers and kept files"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

BELONGS = "belongs"
DEFAULT_THRESHOLD = 0.70

@dataclass(frozen=True)
class Verdict:
    """One flagged item. `probability` is None when a local rule flagged it."""

    item: object
    category: str
    probability: float | None

def threshold_from_env() -> float:
    """Read STRAYGUARD_THRESHOLD (SG-47). Use the default for a bad value."""
    try:
        value = float(os.environ.get("STRAYGUARD_THRESHOLD", DEFAULT_THRESHOLD))
    except ValueError:
        return DEFAULT_THRESHOLD
    return value if 0.0 < value <= 1.0 else DEFAULT_THRESHOLDdef threshold_from_env() -> float:
    """Read STRAYGUARD_THRESHOLD (SG-47). Use the default for a bad value."""
    try:
        value = float(os.environ.get("STRAYGUARD_THRESHOLD", DEFAULT_THRESHOLD))
    except ValueError:
        return DEFAULT_THRESHOLD
    return value if 0.0 < value <= 1.0 else DEFAULT_THRESHOLD

def is_flagged(answer: dict, threshold: float) -> bool:
    """SG-46: flag when the selected option is not `belongs` and is likely enough."""
    choice = answer.get("choice")
    probability = answer.get("probabilities", {}).get(choice, 0.0)
    return choice != BELONGS and probability >= threshold

def decide(items: list, answers: dict, threshold: float) -> list[Verdict]:
    """Turn Jev answers into verdicts. Items without an answer are not flagged."""
    verdicts = []
    for item in items:
        answer = answers.get(item.key)
        if answer and is_flagged(answer, threshold):
            choice = answer["choice"]
            verdicts.append(Verdict(item, choice, answer["probabilities"][choice]))
    return verdicts
