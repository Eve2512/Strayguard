"""Decide which items to flag, and remember answers and kept files (SPEC 7.6, 7.7)."""

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


class Store:
    """The kept list and the answer cache in .git/strayguard/ (SG-50 to SG-54)."""

    def __init__(self, state_dir: Path, model: str, prompt_version: str):
        self.dir = state_dir
        self.kept_file = state_dir / "kept"
        self.cache_file = state_dir / "cache.json"
        self.suffix = f":{model}:{prompt_version}"
        self.kept = self._read_kept()
        self.cache = self._read_cache()

    def _read_kept(self) -> set[str]:
        try:
            return set(self.kept_file.read_text().split())
        except OSError:
            return set()

    def _read_cache(self) -> dict:
        try:
            data = json.loads(self.cache_file.read_text())
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            data = None
        if not isinstance(data, dict):
            self.cache_file.unlink(missing_ok=True)
            return {}
        return data

    def cached_answer(self, item) -> dict | None:
        return self.cache.get(item.key + self.suffix)

    def remember(self, answers: dict) -> None:
        for key, answer in answers.items():
            self.cache[key + self.suffix] = {
                "choice": answer["choice"],
                "probabilities": answer["probabilities"],
            }
        self._write(self.cache_file, json.dumps(self.cache))

    def keep(self, items) -> None:
        for item in items:
            self.kept.update(item.blob_ids)
        self._write(self.kept_file, "".join(f"{blob}\n" for blob in sorted(self.kept)))

    def _write(self, path: Path, text: str) -> None:
        """Write to a temporary file first, so a stopped commit never leaves half a file."""
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + ".tmp")
            temporary.write_text(text)
            os.replace(temporary, path)
        except OSError:
            pass
