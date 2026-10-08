from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, wait

from . import __version__

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"
PROMPT_VERSION = "1"
BATCH_SIZE = 20
PARALLEL_REQUESTS = 5
REQUEST_TIMEOUT = 4.0
TOTAL_TIMEOUT = 5.0
RETRY_STATUSES = {429, 529}

# SPEC 8.2. Keep `belongs` first: Jev prefers the first option a little.
OPTIONS = {
    "belongs": "Part of the project. Source code, tests in a test folder, documentation, "
               "project config, lockfiles, fixtures, assets, and example files such as "
               ".env.example. Generated code that the project commits on purpose also belongs.",
    "scratch": "A temporary file for one person or one session. Throwaway scripts, quick "
               "experiments, personal notes, copies such as file_old.py or file2.py, and "
               "files that a coding agent left behind.",
    "output-dump": "Output that a program wrote. Logs, debug dumps, stack traces, test "
                   "results, profiling data, and exported data rows.",
    "build-output": "Files that a tool can make again. Compiled files, bundles, caches, "
                    "coverage reports, and dependency folders such as node_modules/.",
    "local-only": "Settings for one machine or one person. Editor files, OS files, local "
                  "environment files, personal config, and credentials.",
}


class JevError(Exception):
    pass


def ask(items: list, repo: list[str], api_key: str, model: str) -> dict:
    """Ask one Choice question for each item. Return {item.key: answer}."""
    deadline = time.monotonic() + TOTAL_TIMEOUT
    batches = [items[i:i + BATCH_SIZE] for i in range(0, len(items), BATCH_SIZE)]
    pool = ThreadPoolExecutor(max_workers=PARALLEL_REQUESTS)
    futures = [pool.submit(_ask_batch, b, repo, api_key, model, deadline) for b in batches]
    done, not_done = wait(futures, timeout=TOTAL_TIMEOUT)
    pool.shutdown(wait=False, cancel_futures=True)
    if not_done:
        raise JevError(f"Jev did not answer in {TOTAL_TIMEOUT:g} s")
    answers = {}
    for future in done:
        answers.update(future.result())
    return answers


def _ask_batch(items: list, repo: list[str], api_key: str, model: str, deadline: float) -> dict:
    ids = {f"f{n}": item for n, item in enumerate(items, start=1)}
    body = {
        "model": model,
        "state": {"repo": {"top_level": repo},
                  "files": {fid: item.evidence for fid, item in ids.items()}},
        "questions": {fid: _question(fid, item.is_folder) for fid, item in ids.items()},
    }
    response = _post(body, api_key, deadline)
    answers = {}
    for fid, answer in response.get("answers", {}).items():
        if fid in ids and _is_valid(answer):
            answers[ids[fid].key] = answer
    return answers


def _question(fid: str, is_folder: bool) -> dict:
    """SG-44: each question points to its own item by name."""
    kind = "folder" if is_folder else "file"
    hint = "Use `repo` to see how the project is laid out." if is_folder else \
        "Use `repo` and `same_folder` to see how the project is laid out."
    return {"type": "choice",
            "instructions": f"Which category fits the new {kind} in `files.{fid}`? {hint}",
            "criteria": OPTIONS}


def _is_valid(answer: dict) -> bool:
    return answer.get("choice") in OPTIONS and isinstance(answer.get("probabilities"), dict)


def _post(body: dict, api_key: str, deadline: float) -> dict:
    """SG-40, SG-81, SG-82. The API key never appears in an error message."""
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json",
                 "User-Agent": f"strayguard/{__version__}"},
    )
    for attempt in (1, 2):
        timeout = min(REQUEST_TIMEOUT, deadline - time.monotonic())
        if timeout <= 0:
            raise JevError(f"Jev did not answer in {TOTAL_TIMEOUT:g} s")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            if error.code in RETRY_STATUSES and attempt == 1:
                time.sleep(1.0)
                continue
            raise JevError(f"Jev returned HTTP {error.code}") from None
        except (socket.timeout, TimeoutError):
            raise JevError(f"Jev did not answer in {TOTAL_TIMEOUT:g} s") from None
        except urllib.error.URLError as error:
            if isinstance(error.reason, (socket.timeout, TimeoutError)):
                raise JevError(f"Jev did not answer in {TOTAL_TIMEOUT:g} s") from None
            raise JevError(f"could not reach Jev ({error.reason})") from None
        except ValueError:
            raise JevError("Jev sent a response that is not JSON") from None

