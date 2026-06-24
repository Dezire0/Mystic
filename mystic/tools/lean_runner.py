"""Lean runner with installation detection."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


class LeanRunner:
    def is_installed(self) -> bool:
        return shutil.which("lean") is not None

    def run(self, code: str, timeout_seconds: int = 10) -> str:
        if not self.is_installed():
            return "LEAN_NOT_INSTALLED"
        with tempfile.TemporaryDirectory(prefix="mystic-lean-") as temp_dir:
            path = Path(temp_dir) / "Main.lean"
            path.write_text(code, encoding="utf-8")
            completed = subprocess.run(
                ["lean", str(path)],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        return stdout or stderr or "LEAN_OK"

