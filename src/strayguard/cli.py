"""Command line: install, uninstall and check (SPEC 6, 7.11)."""

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

    provider = jev.pick_provider(os.environ)
    model = os.environ.get("STRAYGUARD_MODEL", provider.default_model if provider else "")
    # SG-51: a different provider or model gives different answers, so it gets its own cache.
    store = decide.Store(git.state_dir(), f"{provider and provider.name}/{model}",
                         jev.PROMPT_VERSION)
    new_files = [f for f in new_files if f.blob not in store.kept]
    items, total, repo = evidence.build_items(new_files)
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
        fresh = ask_jev(missing, repo, provider, model)
        store.remember(fresh)
        answers.update(fresh)

    verdicts += decide.decide(to_ask, answers, decide.threshold_from_env())
    if not verdicts:
        return 0
    return act(verdicts, store)


def ask_jev(items: list, repo: list[str], provider: jev.Provider | None, model: str) -> dict:
    """Ask Jev. On any failure, show one line and return no answers (fail open)."""
    if provider is None:
        ui.note("unknown STRAYGUARD_PROVIDER (use typesafe or openrouter), "
                "so only the local rules ran.")
        return {}
    api_key = os.environ.get(provider.key_var)
    if not api_key:
        names = provider.key_var if "STRAYGUARD_PROVIDER" in os.environ else \
            " or ".join(p.key_var for p in jev.PROVIDERS.values())
        ui.note(f"no {names} set, so only the local rules ran.")
        return {}
    try:
        return jev.ask(items, repo, api_key, model, provider.endpoint)
    except jev.JevError as error:
        ui.note(f"{error}, so only the local rules ran.")
        return {}


def act(verdicts: list, store: decide.Store) -> int:
    """Show the verdicts and do what the user chooses (SG-60 to SG-73)."""
    if not ui.can_prompt():
        strict = os.environ.get("STRAYGUARD_STRICT") == "1"
        ui.warn(verdicts, blocking=strict)
        return 1 if strict else 0

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


def uninstall() -> int:
    hook = git.hooks_dir() / "pre-commit"
    if hook.exists() and MARKER in hook.read_text(errors="replace"):
        hook.unlink()
        print(f"✓ strayguard removed from {hook}")
    else:
        print("strayguard hook not found. Nothing to remove.")
    return 0


COMMANDS = {"install": install, "uninstall": uninstall, "check": check}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="strayguard",
        description="Catch files that do not belong before you commit them.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("install", help="add the pre-commit hook to this repository")
    commands.add_parser("uninstall", help="remove the pre-commit hook")
    commands.add_parser("check", help="check the staged new files (the hook runs this)")
    args = parser.parse_args(argv)

    try:
        return COMMANDS[args.command]()
    except KeyboardInterrupt:
        return 130
    except git.GitError as error:
        ui.note(str(error))
        return 0 if args.command == "check" else 1
    except Exception as error:
        if args.command != "check":
            raise
        ui.note(f"internal error ({error!r}), check skipped.")
        return 0
