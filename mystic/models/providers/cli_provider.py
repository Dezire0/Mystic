from __future__ import annotations

import os
from typing import Any

from mystic.models.providers.base import (
    ModelCallRequest,
    ProviderInvocation,
    ProviderStatus,
    RoutedProvider,
    auth_required_status,
    command_exists,
    error_status,
    extract_text_from_json,
    missing_status,
    provider_auth_required,
    provider_error,
    ready_status,
    run_command,
    unavailable_status,
)


AUTH_ERROR_SNIPPETS = [
    "login",
    "logged out",
    "not logged in",
    "not authenticated",
    "authentication",
    "sign in",
    "sign-in",
    "auth required",
    "reauth",
    '"loggedin": false',
    '"authmethod": "none"',
]


class CLIProvider(RoutedProvider):
    def status(self, model_id: str, config: dict[str, Any]) -> ProviderStatus:
        command = str(config.get("command", "")).strip()
        if not command:
            return unavailable_status("CLI command is missing.", model_id=model_id)
        if not command_exists(command):
            return missing_status(
                f"CLI command '{command}' is not installed.",
                model_id=model_id,
                command=command,
                installed=False,
            )

        auth_env = self._auth_env_name(model_id, config)
        auth_value = os.getenv(auth_env, "").strip().lower()
        if auth_value in {"1", "true", "yes", "authenticated"}:
            return ready_status(
                "CLI command is installed and marked authenticated.",
                model_id=model_id,
                command=command,
                auth_env=auth_env,
                installed=True,
            )
        if auth_value in {"0", "false", "no", "logged_out", "not_authenticated"}:
            auth_label = self._auth_label(config)
            return auth_required_status(
                f"{command} appears installed but not authenticated. {auth_label}",
                model_id=model_id,
                command=command,
                auth_env=auth_env,
                installed=True,
            )

        try:
            probe = self._probe_status(model_id, config)
        except TimeoutError:
            return error_status(
                f"{command} status probe timed out.",
                model_id=model_id,
                command=command,
                auth_env=auth_env,
                installed=True,
            )
        except Exception as exc:  # pragma: no cover - defensive
            return error_status(
                f"{command} status probe failed: {exc}",
                model_id=model_id,
                command=command,
                auth_env=auth_env,
                installed=True,
            )
        if probe is not None:
            return probe

        auth_label = self._auth_label(config)
        return auth_required_status(
            f"{command} appears installed but not authenticated. {auth_label}",
            model_id=model_id,
            command=command,
            auth_env=auth_env,
            installed=True,
        )

    def call(self, model_id: str, config: dict[str, Any], request_data: ModelCallRequest) -> ProviderInvocation:
        status = self.status(model_id, config)
        if status.state == "not_authenticated":
            return provider_auth_required(
                status.message,
                latency_sec=0.0,
                provider="cli",
                model_id=model_id,
                command=str(config.get("command", "")),
            )
        if status.state != "ready":
            return provider_error(
                status.message,
                latency_sec=0.0,
                provider="cli",
                model_id=model_id,
                command=str(config.get("command", "")),
            )

        prompt = request_data.build_prompt()
        command = self._invoke_command(model_id, config, prompt)
        try:
            returncode, stdout, stderr, latency = run_command(
                command,
                timeout_seconds=request_data.timeout_seconds,
            )
        except TimeoutError as exc:  # pragma: no cover - subprocess handles this normally
            return provider_error(str(exc), latency_sec=0.0, provider="cli", model_id=model_id)
        except Exception as exc:  # pragma: no cover - defensive
            return provider_error(str(exc), latency_sec=0.0, provider="cli", model_id=model_id)

        combined = self._combined_output(stdout, stderr)
        if self._is_auth_required_output(combined):
            return provider_auth_required(
                self._auth_label(config),
                latency_sec=latency,
                provider="cli",
                model_id=model_id,
                command=command[0],
                stderr=stderr.strip(),
            )
        if returncode != 0:
            return provider_error(
                stderr.strip() or stdout.strip() or f"{command[0]} exited with status {returncode}",
                latency_sec=latency,
                provider="cli",
                model_id=model_id,
                command=command[0],
                returncode=returncode,
            )
        content = extract_text_from_json(stdout.strip()) if stdout.strip() else stderr.strip()
        return ProviderInvocation(
            content=content.strip(),
            status="OK",
            latency_sec=latency,
            metadata={"provider": "cli", "model_id": model_id, "command": command[0]},
        )

    def _probe_status(self, model_id: str, config: dict[str, Any]) -> ProviderStatus | None:
        command = str(config.get("command", "")).strip()
        auth_label = self._auth_label(config)
        for probe in self._status_probe_commands(model_id, config):
            returncode, stdout, stderr, _ = run_command(
                probe,
                timeout_seconds=self._status_timeout_seconds(config),
            )
            combined = self._combined_output(stdout, stderr)
            if returncode == 0 and not self._is_auth_required_output(combined):
                return ready_status(
                    f"{command} is installed and authenticated.",
                    model_id=model_id,
                    command=command,
                    installed=True,
                )
            if self._is_auth_required_output(combined):
                return auth_required_status(
                    f"{command} appears installed but not authenticated. {auth_label}",
                    model_id=model_id,
                    command=command,
                    installed=True,
                )
            if self._is_unsupported_probe_output(combined):
                continue
            if returncode != 0:
                return error_status(
                    stderr.strip() or stdout.strip() or f"{command} status probe failed.",
                    model_id=model_id,
                    command=command,
                    installed=True,
                )
        return None

    def _status_probe_commands(self, model_id: str, config: dict[str, Any]) -> list[list[str]]:
        command = str(config.get("command", "")).strip()
        if model_id == "claude_cli":
            return [[command, "auth", "status"]]
        if model_id == "gemini_cli":
            return [
                [command, "auth", "status"],
                [command, "-p", "Reply with OK only.", "--output-format", "json"],
            ]
        return [[command, "--version"]]

    def _invoke_command(self, model_id: str, config: dict[str, Any], prompt: str) -> list[str]:
        command = str(config.get("command", "")).strip()
        if model_id == "gemini_cli":
            return [command, "-p", prompt, "--output-format", "json", *self._args(config)]
        if model_id == "claude_cli":
            return [command, "-p", prompt, "--output-format", "json", *self._args(config)]
        return [command, *self._args(config)]

    @staticmethod
    def _status_timeout_seconds(config: dict[str, Any]) -> int:
        raw = config.get("status_timeout_seconds", 5)
        try:
            return max(1, int(raw))
        except (TypeError, ValueError):
            return 5

    @staticmethod
    def _combined_output(stdout: str, stderr: str) -> str:
        return f"{stdout}\n{stderr}".strip().lower()

    @staticmethod
    def _is_auth_required_output(output: str) -> bool:
        return any(snippet in output for snippet in AUTH_ERROR_SNIPPETS)

    @staticmethod
    def _is_unsupported_probe_output(output: str) -> bool:
        return any(
            snippet in output
            for snippet in [
                "unknown command",
                "unknown subcommand",
                "unexpected argument",
                "unrecognized option",
                "invalid choice",
            ]
        )

    @staticmethod
    def _auth_env_name(model_id: str, config: dict[str, Any]) -> str:
        explicit = str(config.get("auth_env", "")).strip()
        if explicit:
            return explicit
        return f"MYSTIC_{model_id.upper()}_AUTH"

    @staticmethod
    def _auth_label(config: dict[str, Any]) -> str:
        auth = str(config.get("auth", "")).strip().lower()
        if auth == "google_login":
            return "Login with Google."
        if auth == "claude_login":
            return "Login with Claude."
        return "Authentication is required."

    @staticmethod
    def _args(config: dict[str, Any]) -> list[str]:
        raw = config.get("args", [])
        if isinstance(raw, list):
            return [str(item) for item in raw]
        return []
