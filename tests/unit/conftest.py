import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from strayguard import git  # noqa: E402

ENV_VARS = ("TYPESAFE_API_KEY", "STRAYGUARD", "STRAYGUARD_STRICT", "STRAYGUARD_THRESHOLD",
            "STRAYGUARD_MODEL", "STRAYGUARD_NAMES_ONLY", "CI", "NO_COLOR")


def run(*args):
    subprocess.run(args, check=True, capture_output=True)

