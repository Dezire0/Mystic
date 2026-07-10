from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any


SELF_TEST_PROMPT = "Reply with exactly: mystic-gemini-cli-ok"
DEFAULT_TIMEOUT_SECONDS = 90
DEFAULT_MAX_OUTPUT_CHARS = 12000
FORBIDDEN_CLI_ARGUMENTS = {"--yolo", "-y", "--worktree", "--include-directories", "--approval-mode", "--sandbox"}
AUTH_REQUIRED_MARKERS = ("opening authentication page", "do you want to continue", "not logged in", "not authenticated", "login")


@dataclass(frozen=True)
class GeminiCommand:
    binary: str
    arguments: tuple[str, ...]
    stdin_prompt: bool = False


def safe_text(value: object, *, limit: int = 500) -> str:
    text = str(value or "").replace("\x1b", "")
    home = str(Path.home())
    if home and home != "/":
        text = text.replace(home, "~")
    text = re.sub(r"/(?:Users|home|private|var|tmp)/[^\s:]+", "[path]", text)
    text = re.sub(r"\b(?:ya29\.[A-Za-z0-9._~-]+|AIza[\w-]+)\b", "[redacted]", text)
    text = re.sub(r"(?i)(?:(?:access|refresh|id)[_-]?token|token)\s*[=:]\s*\S+", "token=[redacted]", text)
    text = re.sub(r"(?i)bearer\s+\S+", "Bearer [redacted]", text)
    return " ".join(text.split())[:limit]


def bridge_environment() -> dict[str, str]:
    allowed = ("HOME", "PATH", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "TMPDIR", "XDG_CONFIG_HOME")
    return {name: os.environ[name] for name in allowed if os.environ.get(name)}


def resolve_binary() -> str:
    configured = os.environ.get("MYSTIC_GEMINI_CLI_BIN", "").strip()
    if configured:
        if any(character in configured for character in "\r\n"):
            return ""
        return configured if shutil.which(configured) else ""
    return shutil.which("gemini") or ""


def parse_override_template(raw: str) -> tuple[str, ...] | None:
    try:
        parts = tuple(shlex.split(raw))
    except ValueError:
        return None
    if parts.count("{prompt}") != 1 or any(part in FORBIDDEN_CLI_ARGUMENTS for part in parts):
        return None
    return parts


def detect_command(*, timeout_seconds: int = 10) -> tuple[GeminiCommand | None, str]:
    binary = resolve_binary()
    if not binary:
        return None, "Gemini CLI is not installed. Install it and run its Google login flow first."
    try:
        help_result = subprocess.run(
            [binary, "--help"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            env=bridge_environment(),
        )
    except subprocess.TimeoutExpired:
        return None, "Gemini CLI help check timed out."
    except OSError:
        return None, "Gemini CLI could not be started."
    if help_result.returncode != 0:
        return None, "Gemini CLI help check failed."

    override = os.environ.get("MYSTIC_GEMINI_CLI_ARGS_TEMPLATE", "").strip()
    if override:
        arguments = parse_override_template(override)
        if arguments is None:
            return None, "MYSTIC_GEMINI_CLI_ARGS_TEMPLATE must contain exactly one {prompt} and no workspace or auto-approval flags."
        return GeminiCommand(binary=binary, arguments=arguments), "override_template"

    help_text = f"{help_result.stdout}\n{help_result.stderr}"
    if "--prompt" in help_text:
        return GeminiCommand(binary=binary, arguments=("--prompt", "{prompt}")), "--prompt"
    if re.search(r"(?:^|\s)-p(?:,|\s)", help_text):
        return GeminiCommand(binary=binary, arguments=("-p", "{prompt}")), "-p"
    return GeminiCommand(binary=binary, arguments=(), stdin_prompt=True), "stdin"


def run_bridge(
    prompt: str,
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
) -> dict[str, Any]:
    started_at = time.monotonic()
    prompt = str(prompt or "").strip()
    if not prompt:
        return bridge_result("error", safe_error="An explicit prompt is required.", latency_ms=0)
    command, detection = detect_command()
    if command is None:
        return bridge_result("error", safe_error=detection, latency_ms=elapsed_ms(started_at))
    arguments = [prompt if argument == "{prompt}" else argument for argument in command.arguments]
    try:
        with tempfile.TemporaryDirectory(prefix="mystic-gemini-cli-") as workspace:
            completed = subprocess.run(
                [command.binary, *arguments],
                # Always close stdin for flag-based calls so a local auth prompt cannot block the bridge.
                input=prompt if command.stdin_prompt else "",
                capture_output=True,
                text=True,
                timeout=max(1, int(timeout_seconds)),
                check=False,
                cwd=workspace,
                env=bridge_environment(),
            )
    except subprocess.TimeoutExpired:
        return bridge_result("error", safe_error="Gemini CLI request timed out.", latency_ms=elapsed_ms(started_at), detection=detection)
    except OSError:
        return bridge_result("error", safe_error="Gemini CLI could not be started.", latency_ms=elapsed_ms(started_at), detection=detection)

    latency_ms = elapsed_ms(started_at)
    output = str(completed.stdout or "").strip()
    combined_output = f"{completed.stdout}\n{completed.stderr}".lower()
    if any(marker in combined_output for marker in AUTH_REQUIRED_MARKERS):
        return bridge_result(
            "error",
            safe_error="Gemini CLI requires a local Google login. Run gemini interactively on this machine, then retry the bridge.",
            latency_ms=latency_ms,
            detection=detection,
        )
    if completed.returncode != 0:
        return bridge_result(
            "error",
            safe_error=safe_text(completed.stderr) or f"Gemini CLI exited with status {completed.returncode}.",
            latency_ms=latency_ms,
            detection=detection,
        )
    if not output:
        return bridge_result(
            "error",
            safe_error=safe_text(completed.stderr) or "Gemini CLI returned no text output.",
            latency_ms=latency_ms,
            detection=detection,
        )
    truncated = len(output) > max(1, int(max_output_chars))
    return bridge_result(
        "ok",
        output=output[: max(1, int(max_output_chars))],
        latency_ms=latency_ms,
        detection=detection,
        output_truncated=truncated,
    )


def bridge_result(
    status: str,
    *,
    output: str = "",
    safe_error: str = "",
    latency_ms: int,
    detection: str = "",
    output_truncated: bool = False,
) -> dict[str, Any]:
    return {
        "status": status,
        "provider_id": "gemini_cli",
        "model_source": "gemini_cli",
        "execution_location": "user_machine",
        "output": output,
        "safe_error": safe_error,
        "latency_ms": latency_ms,
        "command_detection": detection,
        "output_truncated": output_truncated,
    }


def elapsed_ms(started_at: float) -> int:
    return max(0, round((time.monotonic() - started_at) * 1000))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an explicit prompt through the locally logged-in Gemini CLI.")
    parser.add_argument("--prompt", default="", help="Explicit prompt sent to Gemini CLI.")
    parser.add_argument("--stdin", action="store_true", help="Read the explicit prompt from standard input.")
    parser.add_argument("--self-test", action="store_true", help="Run the fixed local provider self-test prompt.")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--max-output-chars", type=int, default=DEFAULT_MAX_OUTPUT_CHARS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    prompt = SELF_TEST_PROMPT if args.self_test else args.prompt
    if args.stdin and not args.self_test:
        prompt = sys.stdin.read()
    result = run_bridge(prompt, timeout_seconds=args.timeout_seconds, max_output_chars=args.max_output_chars)
    print(json.dumps(result, ensure_ascii=True))
    if args.self_test:
        return 0 if result["status"] == "ok" and SELF_TEST_PROMPT in result["output"] else 1
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
