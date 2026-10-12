"""Accuracy test against the real TypeSafe API (SPEC 11.2, T-20 to T-24).

Run from the repo folder:  uv run --no-project python tests/eval/run_eval.py
Needs TYPESAFE_API_KEY. Cost: two runs of about 30,000 input tokens, less than $0.01.
Exit code 0 when all targets pass, 1 when a target fails.
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cases import BASE_PROJECT, CASES  # noqa: E402
from strayguard import decide, evidence, git, jev, rules  # noqa: E402

MAX_FALSE_ALARM_RATE = 0.05   # T-21
MIN_CATCH_RATE = 0.80         # T-22
MAX_ORDER_CHANGES = 2         # T-23


def write(root: Path, files: dict) -> None:
    for path, content in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content)


def make_repo(root: Path) -> None:
    """Commit the base project, then stage all cases as new files."""
    os.chdir(root)
    os.environ["GIT_CONFIG_GLOBAL"] = "/dev/null"
    for args in (["init", "-q"], ["config", "user.email", "eval@example.com"],
                 ["config", "user.name", "eval"]):
        subprocess.run(["git", *args], check=True)
    write(root, BASE_PROJECT)
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-qm", "base"], check=True)
    write(root, {path: content for path, content, _ in CASES})
    subprocess.run(["git", "add", "-A"], check=True)
    git.root.cache_clear()


def label_of(item) -> str:
    labels = {label for path, _, label in CASES if path == item.path or path.startswith(item.path)}
    assert len(labels) == 1, f"{item.path} has mixed labels: {labels}"
    return labels.pop()


def judge(items, repo_top, api_key, model):
    """The same steps as `strayguard check`, without the cache. Returns flags and raw answers."""
    flags, to_ask = {}, []
    for item in items:
        category = rules.match(item.path)
        if category:
            flags[item.path] = (category, None)
        else:
            to_ask.append(item)
    answers = jev.ask(to_ask, repo_top, api_key, model)
    for v in decide.decide(to_ask, answers, decide.threshold_from_env()):
        flags[v.item.path] = (v.category, v.probability)
    return flags, {i.path: answers.get(i.key) for i in to_ask}


def model_version(api_key: str, model: str) -> str:
    body = {"model": model, "state": "Hello there!",
            "questions": {"q": {"type": "noul", "instructions": "Is this text a greeting?"}}}
    return jev._post(body, api_key, time.monotonic() + 20).get("model", "unknown")


def main() -> int:
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        print("Set TYPESAFE_API_KEY first.")
        return 1
    model = os.environ.get("STRAYGUARD_MODEL", jev.DEFAULT_MODEL)
    jev.REQUEST_TIMEOUT, jev.TOTAL_TIMEOUT = 30.0, 60.0  # 100 items need more time than one commit

    with tempfile.TemporaryDirectory() as tmp:
        make_repo(Path(tmp))
        items, total, repo_top = evidence.build_items(git.new_files())
        if total > len(items):
            print(f"Only {len(items)} of {total} items fit. Remove some cases.")
            return 1
        labels = {i.path: label_of(i) for i in items}

        started = time.monotonic()
        flags, answers = judge(items, repo_top, api_key, model)
        seconds = time.monotonic() - started

        original = dict(jev.OPTIONS)
        names = list(original)
        jev.OPTIONS = {name: original[name] for name in names[:1] + names[:0:-1]}  # T-23
        try:
            flags_reordered, _ = judge(items, repo_top, api_key, model)
        finally:
            jev.OPTIONS = original

    belongs = [p for p, label in labels.items() if label == "belongs"]
    strays = [p for p, label in labels.items() if label == "stray"]
    false_alarms = [p for p in belongs if p in flags]
    missed = [p for p in strays if p not in flags]
    order_changes = sorted(set(flags) ^ set(flags_reordered))

    print(f"Model: {model_version(api_key, model)}  (requested {model})")
    print(f"Items: {len(items)}  ({len(belongs)} belong, {len(strays)} stray)  "
          f"Jev time: {seconds:.1f} s for {len(answers)} items")
    print()

    if false_alarms or missed:
        print("Wrong answers:")
        for path in false_alarms:
            category, probability = flags[path]
            score = "rule" if probability is None else f"{probability:.0%}"
            print(f"  FALSE ALARM  {path:45} {category} {score}")
        for path in missed:
            answer = answers.get(path) or {}
            choice = answer.get("choice", "no answer")
            probability = answer.get("probabilities", {}).get(choice)
            score = f"{probability:.0%}" if probability is not None else ""
            print(f"  MISSED       {path:45} Jev said: {choice} {score}")
        print()

    false_alarm_rate = len(false_alarms) / len(belongs)
    catch_rate = (len(strays) - len(missed)) / len(strays)
    results = [
        ("False alarms", f"{len(false_alarms)} of {len(belongs)} ({false_alarm_rate:.1%})",
         f"at most {MAX_FALSE_ALARM_RATE:.0%}", false_alarm_rate <= MAX_FALSE_ALARM_RATE),
        ("Caught", f"{len(strays) - len(missed)} of {len(strays)} ({catch_rate:.1%})",
         f"at least {MIN_CATCH_RATE:.0%}", catch_rate >= MIN_CATCH_RATE),
        ("Option order", f"{len(order_changes)} item(s) changed",
         f"at most {MAX_ORDER_CHANGES}", len(order_changes) <= MAX_ORDER_CHANGES),
    ]
    for name, value, target, ok in results:
        print(f"  {name:13} {value:24} target: {target:12} {'PASS' if ok else 'FAIL'}")
    if order_changes:
        print(f"  Changed by option order: {', '.join(order_changes)}")
    return 0 if all(ok for *_, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
