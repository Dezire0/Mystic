"""SMT runner stub."""

from __future__ import annotations

import shutil


class SMTRunner:
    def available(self) -> bool:
        return shutil.which("z3") is not None

    def run(self, problem: str) -> str:
        if not self.available():
            return "SMT_NOT_INSTALLED"
        return f"SMT_STUB: bounded check not yet implemented for: {problem}"

