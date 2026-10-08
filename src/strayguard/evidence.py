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


