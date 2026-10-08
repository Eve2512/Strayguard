"""Local rules: checks in code that do not use Jev (SPEC 7.3)."""

from __future__ import annotations

import posixpath
from fnmatch import fnmatchcase

LOCAL_ONLY = (
    ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa*", "id_ed25519*",
    ".DS_Store", "Thumbs.db", "desktop.ini",
)
ALLOWED = (".env.example", ".env.sample", ".env.template")


def match(path: str) -> str | None:
    """Return 'local-only' if a rule matches the file name. Else return None."""
    name = posixpath.basename(path.rstrip("/"))
    if name in ALLOWED:
        return None
    if any(fnmatchcase(name, pattern) for pattern in LOCAL_ONLY):
        return "local-only"
    return None
