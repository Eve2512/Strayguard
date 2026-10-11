"""All git calls (SPEC 7.1, 7.8, 7.11). No other module runs git."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

SUBMODULE_MODE = "160000"


class GitError(Exception):
    pass


@dataclass(frozen=True)
class NewFile:
    path: str
    blob: str


def _run(*args: str, input: bytes | None = None, cwd: Path | None = None) -> bytes:
    try:
        result = subprocess.run(["git", *args], input=input, capture_output=True, cwd=cwd)
    except FileNotFoundError:
        raise GitError("git not found") from None
    if result.returncode != 0:
        message = result.stderr.decode(errors="replace").strip()
        raise GitError(message or f"git {args[0]} failed")
    return result.stdout


@lru_cache(maxsize=None)
def root() -> Path:
    return Path(_run("rev-parse", "--show-toplevel").decode().strip())


def _in_root(*args: str, input: bytes | None = None) -> bytes:
    """Run git in the top folder, because staged paths are relative to it."""
    return _run(*args, input=input, cwd=root())


def new_files() -> list[NewFile]:
    """SG-01, SG-02: staged files with status A. Renames and submodules are skipped."""
    raw = _in_root("diff", "--cached", "--raw", "-z", "--no-abbrev",
                   "--find-renames", "--diff-filter=A").decode(errors="surrogateescape")
    fields = raw.split("\0")
    files = []
    for meta, path in zip(fields[0::2], fields[1::2]):
        _, new_mode, _, blob, _ = meta.lstrip(":").split(" ")
        if new_mode != SUBMODULE_MODE:
            files.append(NewFile(path, blob))
    return files


def tracked_files() -> list[str]:
    """All paths in the index. The caller removes the new files from this list."""
    return [p for p in _in_root("ls-files", "-z").decode(errors="surrogateescape").split("\0") if p]


def blob_sizes(blobs: list[str]) -> dict[str, int]:
    out = _run("cat-file", "--batch-check", input="\n".join(blobs).encode() + b"\n")
    sizes = {}
    for line in out.decode().splitlines():
        blob, _, size = line.split(" ")
        sizes[blob] = int(size)
    return sizes


def read_blobs(blobs: list[str]) -> dict[str, bytes]:
    """Read the staged content of many files with one git process."""
    if not blobs:
        return {}
    out = _run("cat-file", "--batch", input="\n".join(blobs).encode() + b"\n")
    contents, position = {}, 0
    for blob in blobs:
        header_end = out.index(b"\n", position)
        size = int(out[position:header_end].split(b" ")[2])
        contents[blob] = out[header_end + 1:header_end + 1 + size]
        position = header_end + 1 + size + 1
    return contents


def state_dir() -> Path:
    common = Path(_run("rev-parse", "--git-common-dir").decode().strip())
    return common.resolve() / "strayguard"


def hooks_dir() -> Path:
    """`--git-path hooks` respects core.hooksPath (SPEC 7.11)."""
    return Path(_run("rev-parse", "--git-path", "hooks").decode().strip()).resolve()


def unstage(paths: list[str]) -> None:
    """SG-64: remove the paths from the index only. The files stay on the disk."""
    _in_root("rm", "--cached", "-r", "-f", "--quiet", "--", *paths)


def _ignore_pattern(path: str) -> str:
    escaped = "".join("\\" + c if c in "*?[\\" else c for c in path)
    return "/" + escaped


def add_to_gitignore(items: list) -> None:
    """SG-65, SG-66: add one anchored line for each item, then stage .gitignore."""
    gitignore = root() / ".gitignore"
    text = gitignore.read_text() if gitignore.exists() else ""
    present = set(text.splitlines())
    new_lines = [p for p in (_ignore_pattern(i.path) for i in items) if p not in present]
    if new_lines:
        if text and not text.endswith("\n"):
            text += "\n"
        gitignore.write_text(text + "\n".join(new_lines) + "\n")
    _in_root("add", "--", ".gitignore")
