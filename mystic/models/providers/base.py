from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import json
import shutil
import subprocess
import time
from typing import Any
from urllib import error, request


DEFAULT_TIMEOUT_SECONDS = 30


@dataclass(slots=True)
class ModelCallRequest:
    role: str
    task: str
    problem: str
    context: str = ""
    max_tokens: int | None = None
    temperature: float | None = None
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS

    def build_prompt(self) -> str:
        sections = [
            f"Role: {self.role}",
            f"Task: {self.task}",
            f"Problem:\n{self.problem}",
        ]
        if self.context:
            sections.append(f"Context:\n{self.context}")
        if self.max_tokens is not None:
            sections.append(f"Max tokens: {self.max_tokens}")
        if self.temperature is not None:
            sections.append(f"Temperature: {self.temperature}")
        return "\n\n".join(sections)


@dataclass(slots=True)
class ProviderStatus:
    state: str
    message: str
    available: bool
    authenticated: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "message": self.message,
            "available": self.available,
            "authenticated": self.authenticated,
            "details": self.details,
        }


@dataclass(slots=True)
class ProviderInvocation:
    content: str
    status: str
    latency_sec: float
    auth_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class RoutedProvider(ABC):
    @abstractmethod
    def status(self, model_id: str, config: dict[str, Any]) -> ProviderStatus:
        """Return provider status for a model registration."""

    @abstractmethod
    def call(self, model_id: str, config: dict[str, Any], request_data: ModelCallRequest) -> ProviderInvocation:
        """Call the provider and return normalized output."""


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def run_command(
    command: list[str],
    *,
    input_text: str = "",
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[int, str, str, float]:
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    latency = time.perf_counter() - started
    return completed.returncode, completed.stdout, completed.stderr, latency


def post_json(
    url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[int, str, float]:
    merged_headers = {"Content-Type": "application/json"}
    if headers:
        merged_headers.update(headers)
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=merged_headers,
        method="POST",
    )
    started = time.perf_counter()
    with request.urlopen(req, timeout=timeout_seconds) as response:
        raw = response.read().decode("utf-8")
        latency = time.perf_counter() - started
        return response.status, raw, latency


def get_json(url: str, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> tuple[int, str, float]:
    started = time.perf_counter()
    with request.urlopen(url, timeout=timeout_seconds) as response:
        raw = response.read().decode("utf-8")
        latency = time.perf_counter() - started
        return response.status, raw, latency


def extract_text_from_json(raw: str) -> str:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(payload, dict):
        if "response" in payload:
            return str(payload["response"])
        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            choice = choices[0]
            if isinstance(choice, dict):
                message = choice.get("message")
                if isinstance(message, dict) and "content" in message:
                    return str(message["content"])
                if "text" in choice:
                    return str(choice["text"])
        content = payload.get("content")
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict) and "text" in first:
                return str(first["text"])
    return raw


def unavailable_status(message: str, **details: Any) -> ProviderStatus:
    return ProviderStatus(
        state="unavailable",
        message=message,
        available=False,
        authenticated=False,
        details=details,
    )


def missing_status(message: str, **details: Any) -> ProviderStatus:
    return ProviderStatus(
        state="missing",
        message=message,
        available=False,
        authenticated=False,
        details=details,
    )


def disabled_status(message: str, **details: Any) -> ProviderStatus:
    return ProviderStatus(
        state="disabled",
        message=message,
        available=False,
        authenticated=False,
        details=details,
    )


def auth_required_status(message: str, **details: Any) -> ProviderStatus:
    return ProviderStatus(
        state="not_authenticated",
        message=message,
        available=True,
        authenticated=False,
        details=details,
    )


def ready_status(message: str, authenticated: bool = True, **details: Any) -> ProviderStatus:
    return ProviderStatus(
        state="ready",
        message=message,
        available=True,
        authenticated=authenticated,
        details=details,
    )


def error_status(message: str, **details: Any) -> ProviderStatus:
    return ProviderStatus(
        state="error",
        message=message,
        available=False,
        authenticated=False,
        details=details,
    )


def provider_error(message: str, *, latency_sec: float, **details: Any) -> ProviderInvocation:
    return ProviderInvocation(
        content=message,
        status="ERROR",
        latency_sec=latency_sec,
        metadata=details,
    )


def provider_auth_required(message: str, *, latency_sec: float, **details: Any) -> ProviderInvocation:
    return ProviderInvocation(
        content="",
        status="AUTH_REQUIRED",
        latency_sec=latency_sec,
        auth_message=message,
        metadata=details,
    )


def provider_transport_error(exc: Exception, *, latency_sec: float = 0.0, **details: Any) -> ProviderInvocation:
    return provider_error(
        f"Provider request failed: {exc}",
        latency_sec=latency_sec,
        error_type=type(exc).__name__,
        **details,
    )


__all__ = [
    "ModelCallRequest",
    "ProviderInvocation",
    "ProviderStatus",
    "RoutedProvider",
    "auth_required_status",
    "command_exists",
    "DEFAULT_TIMEOUT_SECONDS",
    "disabled_status",
    "error_status",
    "extract_text_from_json",
    "get_json",
    "missing_status",
    "post_json",
    "provider_auth_required",
    "provider_error",
    "provider_transport_error",
    "ready_status",
    "run_command",
    "unavailable_status",
]
