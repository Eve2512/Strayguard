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


def ask_jev(items: list, model: str) -> dict:
    """Ask Jev. On any failure, show one line and return no answers (fail open)."""
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        ui.note("no TYPESAFE_API_KEY set, check skipped.")
        return {}
    try:
        return jev.ask(items, api_key, model)
    except jev.JevError as error:
        ui.note(f"{error}, check skipped.")
        return {}


def act(verdicts: list, store: decide.Store) -> int:
    """Show the verdicts and do what the user chooses (SG-60 to SG-73)."""
    if not ui.can_prompt():
        ui.warn(verdicts)
        return 1 if os.environ.get("STRAYGUARD_STRICT") == "1" else 0

    choices = ui.prompt(verdicts)
    store.keep(v.item for v in choices["k"])
    if choices["g"]:
        git.add_to_gitignore([v.item for v in choices["g"]])
    removed = choices["u"] + choices["g"]
    if removed:
        git.unstage([v.item.path for v in removed])
    ui.report(choices)
    return 1 if removed else 0


def install() -> int:
    hook = git.hooks_dir() / "pre-commit"
    if hook.exists() and MARKER not in hook.read_text(errors="replace"):
        print(f"{hook} already exists. Add this line to it:\n  strayguard check")
        return 1
    exe = shutil.which("strayguard") or os.path.abspath(sys.argv[0])
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(HOOK.format(exe=exe))
    hook.chmod(0o755)
    print(f"✓ strayguard installed in {hook}")
    return 0









