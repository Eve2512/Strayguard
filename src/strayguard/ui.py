"""All output and the prompt (SPEC 5, 7.8, 7.9). Output goes to standard error."""

from __future__ import annotations

import os
import shlex
import sys

LABELS = {
    "scratch": "scratch / leftover",
    "output-dump": "output dump",
    "build-output": "build output",
    "local-only": "local only",
}


def _say(text: str = "") -> None:
    print(text, file=sys.stderr, flush=True)


def _color(code: str, text: str) -> str:
    if sys.stderr.isatty() and "NO_COLOR" not in os.environ:
        return f"\033[{code}m{text}\033[0m"
    return text


def note(text: str) -> None:
    _say(f"strayguard: {text}")


def can_prompt() -> bool:
    """SG-60: a person must see the output, and strayguard must read the keyboard."""
    if os.environ.get("CI") or os.name == "nt" or not sys.stderr.isatty():
        return False
    try:
        with open("/dev/tty"):
            return True
    except OSError:
        return False


def _files(count: int, word: str = "new file") -> str:
    return f"1 {word}" if count == 1 else f"{count} {word}s"


def _rows(verdicts: list) -> list[str]:
    width = max(len(v.item.path) for v in verdicts)
    rows = []
    for v in verdicts:
        score = "rule" if v.probability is None else f"{round(v.probability * 100)}%"
        rows.append(f"  {v.item.path:<{width}}   {LABELS.get(v.category, v.category):<18}   {score}")
    return rows


def _header(verdicts: list, text: str) -> None:
    _say()
    _say(_color("33", f"⚠ strayguard: {_files(len(verdicts))} {text}"))
    _say()
    for row in _rows(verdicts):
        _say(row)


def warn(verdicts: list, blocking: bool) -> None:
    """SG-70, SG-71: non-interactive mode. Show the command that fixes it."""
    status = "commit stopped" if blocking else "not blocking"
    _header(verdicts, f"may not belong ({status})")
    paths = " ".join(shlex.quote(v.item.path) for v in verdicts)
    _say()
    _say("  To unstage them:")
    _say(f"    git rm --cached -r -- {paths}")
    _say()


def _ask(question: str, keys: str) -> str:
    """Read one answer from the keyboard. Enter means keep (decision 1)."""
    with open("/dev/tty") as tty:
        while True:
            print(question, end="", file=sys.stderr, flush=True)
            answer = tty.readline().strip().lower()[:1]
            if not answer:
                return "k"
            if answer in keys:
                return answer


def prompt(verdicts: list) -> dict:
    """SG-61 to SG-63. Return {"u": [...], "g": [...], "k": [...]}."""
    _header(verdicts, "looks like it doesn't belong" if len(verdicts) == 1
            else "look like they don't belong")
    _say()
    _say("  [u] unstage   [g] add to .gitignore   [k] keep and commit   [o] one by one")
    key = _ask("  > ", "ugko")
    if key != "o":
        return {k: list(verdicts) if k == key else [] for k in "ugk"}
    choices = {"u": [], "g": [], "k": []}
    for v, row in zip(verdicts, _rows(verdicts)):
        choices[_ask(f"{row}   [u/g/k] > ", "ugk")].append(v)
    return choices


def report(choices: dict) -> None:
    """Say what strayguard did, then say if the commit stopped (SG-68)."""
    tick = _color("32", "✓")
    _say()
    if choices["g"]:
        _say(f"  {tick} Added {_files(len(choices['g']), 'file')} to .gitignore and staged .gitignore.")
    removed = len(choices["u"]) + len(choices["g"])
    if removed:
        _say(f"  {tick} Unstaged {_files(removed, 'file')}. They are still on your disk.")
    if choices["k"]:
        _say(f"  {tick} Kept {_files(len(choices['k']), 'file')}. strayguard will not ask about them again.")
    if removed:
        _say()
        _say("  Commit stopped so you can check. Run git commit again.")
    _say()


