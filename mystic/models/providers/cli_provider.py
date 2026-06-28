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
    provider_auth_required,
    provider_error,
    ready_status,
    run_command,
    unavailable_status,
)


AUTH_ERROR_SNIPPETS = [
    "login",
    "not authenticated",
    "authentication",
    "sign in",
    "sign-in",
]


class CLIProvider(RoutedProvider):
    def status(self, model_id: str, config: dict[str, Any]) -> ProviderStatus:
        command = str(config.get("command", "")).strip()
        if not command:
            return unavailable_status("CLI command is missing.", model_id=model_id)
        if not command_exists(command):
            return unavailable_status(
                f"CLI command '{command}' is not installed.",
                model_id=model_id,
                command=command,
            )

        auth_env = self._auth_env_name(model_id, config)
        auth_value = os.getenv(auth_env, "").strip().lower()
        if auth_value in {"1", "true", "yes", "authenticated"}:
            return ready_status(
                "CLI command is installed and marked authenticated.",
                model_id=model_id,
                command=command,
                auth_env=auth_env,
            )

        auth_label = self._auth_label(config)
        return auth_required_status(
            f"{command} appears installed but not authenticated. {auth_label}",
            model_id=model_id,
            command=command,
            auth_env=auth_env,
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

        command = [str(config.get("command", "")).strip(), *self._args(config)]
        prompt = request_data.build_prompt()
        try:
            returncode, stdout, stderr, latency = run_command(
                command,
                input_text=prompt,
                timeout_seconds=request_data.timeout_seconds,
            )
        except TimeoutError as exc:  # pragma: no cover - subprocess handles this normally
            return provider_error(str(exc), latency_sec=0.0, provider="cli", model_id=model_id)
        except Exception as exc:  # pragma: no cover - defensive
            return provider_error(str(exc), latency_sec=0.0, provider="cli", model_id=model_id)

        combined = f"{stdout}\n{stderr}".strip().lower()
        if any(snippet in combined for snippet in AUTH_ERROR_SNIPPETS):
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
        return ProviderInvocation(
            content=(stdout or stderr).strip(),
            status="OK",
            latency_sec=latency,
            metadata={"provider": "cli", "model_id": model_id, "command": command[0]},
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
