from __future__ import annotations

import hashlib
import os
import posixpath
from dataclasses import dataclass, field

from . import git, rules

ROLL_UP_ABOVE = 10
MAX_ITEMS = 100
MAX_CONTENT_BYTES = 1_000_000
BINARY_SCAN_BYTES = 8_000
HEAD_LINES = 40
HEAD_CHARS = 2_000
SAME_FOLDER_NAMES = 10
TOP_LEVEL_NAMES = 30
FOLDER_SAMPLE = 5


@dataclass
class Item:
    path: str
    key: str
    blob_ids: tuple
    is_folder: bool = False
    evidence: dict = field(default_factory=dict)


def _parents(path: str) -> list[str]:
    """All parent folders, highest first: 'a/b/c.txt' gives ['a/', 'a/b/']."""
    parts = path.split("/")[:-1]
    return ["/".join(parts[: i + 1]) + "/" for i in range(len(parts))]


def build_items(new_files: list) -> tuple[list[Item], int, list[str]]:
    """Return (items, total number of items, repo top-level names)."""
    new_paths = {f.path for f in new_files}
    tracked = [p for p in git.tracked_files() if p not in new_paths]
    tracked_folders = {folder for p in tracked for folder in _parents(p)}

    counts: dict[str, int] = {}
    for f in new_files:
        for folder in _parents(f.path):
            counts[folder] = counts.get(folder, 0) + 1

    groups: dict[str, list] = {}
    singles = []
    for f in new_files:
        folder = next((d for d in _parents(f.path)
                       if d not in tracked_folders and counts[d] > ROLL_UP_ABOVE), None)
        if folder:
            groups.setdefault(folder, []).append(f)
        else:
            singles.append(f)

    items = [_folder_item(folder, files) for folder, files in groups.items()]
    items += _file_items(singles, tracked)
    items.sort(key=lambda item: item.path)
    return items[:MAX_ITEMS], len(items), _top_level(tracked)


def _folder_item(folder: str, files: list) -> Item:
    """SG-11: one item for a whole new folder."""
    blobs = tuple(sorted(f.blob for f in files))
    key = "folder:" + hashlib.sha1(" ".join(blobs).encode()).hexdigest()
    sample = sorted(f.path for f in files)[:FOLDER_SAMPLE]
    evidence = {"path": folder, "kind": "folder", "new_files": len(files), "sample": sample}
    return Item(folder, key, blobs, is_folder=True, evidence=evidence)


def _file_items(files: list, tracked: list[str]) -> list[Item]:
    names_only = os.environ.get("STRAYGUARD_NAMES_ONLY") == "1"
    sizes = git.blob_sizes([f.blob for f in files]) if files else {}
    readable = [f.blob for f in files
                if not names_only and not rules.match(f.path) and sizes[f.blob] <= MAX_CONTENT_BYTES]
    contents = git.read_blobs(readable)

    items = []
    for f in files:
        evidence = {"path": f.path, "size_bytes": sizes[f.blob],
                    "same_folder": _same_folder(f.path, tracked)}
        data = contents.get(f.blob)
        if data is not None:
            evidence["binary"] = b"\0" in data[:BINARY_SCAN_BYTES]
            if not evidence["binary"]:
                lines = data.decode(errors="replace").splitlines()[:HEAD_LINES]
                evidence["head"] = "\n".join(lines)[:HEAD_CHARS]
        items.append(Item(f.path, f.blob, (f.blob,), evidence=evidence))
    return items


def _same_folder(path: str, tracked: list[str]) -> list[str]:
    """SG-34: names of tracked files next to this file."""
    folder = posixpath.dirname(path)
    names = sorted(posixpath.basename(p) for p in tracked if posixpath.dirname(p) == folder)
    return names[:SAME_FOLDER_NAMES]


def _top_level(tracked: list[str]) -> list[str]:
    """SG-35: tracked top-level files and folders. Folders end with '/'."""
    names = {p.split("/")[0] + ("/" if "/" in p else "") for p in tracked}
    return sorted(names)[:TOP_LEVEL_NAMES]
