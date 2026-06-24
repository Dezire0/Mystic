"""Safe Python runner for Forge experiments."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from mystic.core.protocol import PythonExecutionResult
from mystic.tools.sandbox import find_unsafe_pattern


class PythonRunner:
    def run(self, code: str, timeout_seconds: int = 10) -> PythonExecutionResult:
        unsafe = find_unsafe_pattern(code)
        if unsafe is not None:
            return PythonExecutionResult(
                success=False,
                returncode=1,
                stdout="",
                stderr="",
                blocked=True,
                blocked_reason=f"Blocked unsafe pattern: {unsafe}",
            )

        with tempfile.TemporaryDirectory(prefix="mystic-python-") as temp_dir:
            script_path = Path(temp_dir) / "experiment.py"
            script_path.write_text(code, encoding="utf-8")
            try:
                completed = subprocess.run(
                    [sys.executable, str(script_path)],
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    cwd=temp_dir,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                return PythonExecutionResult(
                    success=False,
                    returncode=124,
                    stdout=exc.stdout or "",
                    stderr=exc.stderr or "",
                    timeout=True,
                )
        return PythonExecutionResult(
            success=completed.returncode == 0,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

