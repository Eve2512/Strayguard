from __future__ import annotations

import argparse
import os
import shutil
import sys

from . import __version__, decide, evidence, git, jev, rules, ui

MARKER = "# strayguard"
HOOK = """#!/bin/sh
# strayguard
exe="{exe}"
[ -x "$exe" ] || exe="$(command -v strayguard)" || exit 0
exec "$exe" check
"""


def check() -> int:
    """Run the full check on the staged new files. Return the exit code."""
    if os.environ.get("STRAYGUARD", "on").lower() == "off":
        return 0

    new_files = git.new_files()
    if not new_files:
        return 0

    model = os.environ.get("STRAYGUARD_MODEL", jev.DEFAULT_MODEL)
    store = decide.Store(git.state_dir(), model, jev.PROMPT_VERSION)
    new_files = [f for f in new_files if f.blob not in store.kept]
    items, total = evidence.build_items(new_files)
    if total > len(items):
        ui.note(f"checked {len(items)} of {total} new items.")

    verdicts, to_ask = [], []
    for item in items:
        category = rules.match(item.path)
        if category:
            verdicts.append(decide.Verdict(item, category, None))
        else:
            to_ask.append(item)

    answers = {}
    for item in to_ask:
        cached = store.cached_answer(item)
        if cached:
            answers[item.key] = cached
    missing = [item for item in to_ask if item.key not in answers]
    if missing:
        fresh = ask_jev(missing, model)
        store.remember(fresh)
        answers.update(fresh)

    verdicts += decide.decide(to_ask, answers, decide.threshold_from_env())
    if not verdicts:
        return 0
    return act(verdicts, store)



