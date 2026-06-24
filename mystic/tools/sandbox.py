"""Very small sandbox policy for local experiment code."""

from __future__ import annotations


UNSAFE_PATTERNS = [
    "import os",
    "import subprocess",
    "from os",
    "from subprocess",
    "os.system",
    "subprocess.",
    "__import__",
    "eval(",
    "exec(",
]


def find_unsafe_pattern(code: str) -> str | None:
    lowered = code.lower()
    for pattern in UNSAFE_PATTERNS:
        if pattern in lowered:
            return pattern
    return None

