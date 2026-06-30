from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import uuid
from typing import Any

from mystic.models.mock_provider import MockProvider
from mystic.models.providers import (
    AnthropicAPIProvider,
    CLIProvider,
    GeminiAPIProvider,
    LocalAdapterProvider,
    OllamaRoutedProvider,
    OpenAIAPIProvider,
)
from mystic.models.providers.base import ModelCallRequest, ProviderInvocation, ProviderStatus, RoutedProvider
from mystic.utils.yamlish import load_yaml_file


DEFAULT_MODEL_CONFIG = "configs/mystic_models.yaml"


class MockRoutedProvider(RoutedProvider):
    def __init__(self) -> None:
        self._provider = MockProvider()

    def status(self, model_id: str, config: dict[str, Any]) -> ProviderStatus:
        return ProviderStatus(
            state="ready",
            message="Mock provider is ready.",
            available=True,
            authenticated=True,
            details={"model_id": model_id},
        )

    def call(self, model_id: str, config: dict[str, Any], request_data: ModelCallRequest) -> ProviderInvocation:
        from mystic.core.protocol import ModelSettings

        response = self._provider.generate(
            agent_name=model_id,
            prompt=request_data.task,
            problem=request_data.problem,
            settings=ModelSettings(
                provider="mock",
                model=str(config.get("model", model_id)),
                temperature=request_data.temperature,
                adapter=str(config.get("adapter_path", "")) or None,
            ),
        )
        return ProviderInvocation(
            content=response.text,
            status="OK",
            latency_sec=0.0,
            metadata=response.metadata,
        )


@dataclass(slots=True)
class RouterPolicy:
    local_first: bool = True
    api_fallback_enabled: bool = False
    require_confirmation_for_api: bool = True
    prefer_login_cli: bool = True
    max_models_per_compare: int = 3
    max_debate_rounds: int = 3
    max_turns_per_debate: int = 12
    timeout_per_model_seconds: int = 120
    max_output_chars_per_model: int = 6000
    save_full_outputs: bool = True
    return_summaries: bool = True


class ModelRouter:
    def __init__(
        self,
        *,
        root_path: str | Path | None = None,
        config_path: str | Path | None = None,
    ) -> None:
        self.root_path = Path(root_path or Path(__file__).resolve().parents[2])
        self.config_path = Path(config_path or self.root_path / DEFAULT_MODEL_CONFIG)
        raw = load_yaml_file(self.config_path)
        self.models = raw.get("models", {})
        policy = raw.get("policy", {})
        self.policy = RouterPolicy(**{key: value for key, value in policy.items() if key in RouterPolicy.__annotations__})
        self._providers: dict[str, RoutedProvider] = {
            "mock": MockRoutedProvider(),
            "ollama": OllamaRoutedProvider(),
            "local_adapter": LocalAdapterProvider(),
            "cli": CLIProvider(),
            "api:openai": OpenAIAPIProvider(),
            "api:anthropic": AnthropicAPIProvider(),
            "api:gemini": GeminiAPIProvider(),
        }
        self.data_root = self.root_path / "mystic_data"
        (self.data_root / "runs").mkdir(parents=True, exist_ok=True)

    def list_models(self) -> dict[str, dict[str, Any]]:
        return {model_id: dict(config) for model_id, config in self.models.items()}

    def get_model(self, model_id: str) -> dict[str, Any]:
        config = self.models.get(model_id)
        if not isinstance(config, dict):
            raise KeyError(f"Unknown model_id: {model_id}")
        return dict(config)

    def status_snapshot(self) -> dict[str, Any]:
        return {
            model_id: {
                "provider": str(config.get("provider", "")),
                "model_name": self._display_model_name(model_id, config),
                "status": self._provider_for_model(config).status(model_id, config).to_dict(),
                "role_defaults": self._role_defaults(config),
                "enabled": bool(config.get("enabled", True)),
            }
            for model_id, config in self.models.items()
            if isinstance(config, dict)
        }

    def call_model(
        self,
        *,
        model_id: str,
        role: str,
        task: str,
        problem: str,
        context: str = "",
        max_tokens: int | None = None,
        temperature: float | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        config = self.get_model(model_id)
        provider = self._provider_for_model(config)
        request_data = ModelCallRequest(
            role=role,
            task=task,
            problem=problem,
            context=context,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_seconds=self.policy.timeout_per_model_seconds,
        )
        invocation = provider.call(model_id, config, request_data)
        output_id = str(uuid.uuid4())
        normalized_status = self._normalize_status(role, invocation.status)
        saved_path = self._save_output_artifact(
            output_id=output_id,
            session_id=session_id or f"router-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
            payload={
                "output_id": output_id,
                "model_id": model_id,
                "provider": str(config.get("provider", "")),
                "model_name": self._display_model_name(model_id, config),
                "role": role,
                "status": normalized_status,
                "content": invocation.content[: self.policy.max_output_chars_per_model]
                if not self.policy.save_full_outputs
                else invocation.content,
                "latency_sec": invocation.latency_sec,
                "created_at": datetime.now(UTC).isoformat(),
                "metadata": invocation.metadata,
                "auth_message": invocation.auth_message,
            },
        )
        content = invocation.content
        if len(content) > self.policy.max_output_chars_per_model:
            content = content[: self.policy.max_output_chars_per_model]
        return {
            "output_id": output_id,
            "model_id": model_id,
            "provider": str(config.get("provider", "")),
            "model_name": self._display_model_name(model_id, config),
            "role": role,
            "content": content,
            "status": normalized_status,
            "latency_sec": invocation.latency_sec,
            "artifact_path": str(saved_path),
            "auth_message": invocation.auth_message,
        }

    def _provider_for_model(self, config: dict[str, Any]) -> RoutedProvider:
        provider_name = str(config.get("provider", ""))
        if provider_name == "api":
            api_provider = str(config.get("api_provider", "")).strip().lower()
            key = f"api:{api_provider}"
        else:
            key = provider_name
        provider = self._providers.get(key)
        if provider is None:
            raise KeyError(f"Unsupported provider type: {provider_name}")
        return provider

    @staticmethod
    def _role_defaults(config: dict[str, Any]) -> list[str]:
        raw = config.get("role_defaults", [])
        if isinstance(raw, list):
            return [str(item) for item in raw]
        return []

    @staticmethod
    def _display_model_name(model_id: str, config: dict[str, Any]) -> str:
        provider = str(config.get("provider", ""))
        if provider == "local_adapter":
            base_model = str(config.get("base_model", "adapter"))
            adapter_path = Path(str(config.get("adapter_path", "")))
            return f"{base_model} + {adapter_path.name}"
        return str(config.get("model", model_id))

    @staticmethod
    def _normalize_status(role: str, provider_status: str) -> str:
        if provider_status == "AUTH_REQUIRED":
            return "AUTH_REQUIRED"
        if provider_status == "ERROR":
            return "ERROR"
        return {
            "draft": "DRAFT_ONLY",
            "critique": "CRITIQUE_ONLY",
            "revise": "REVISION",
            "judge": "FINAL_JUDGE",
            "summarize": "SUMMARY_ONLY",
        }.get(role, "DRAFT_ONLY")

    def _save_output_artifact(
        self,
        *,
        output_id: str,
        session_id: str,
        payload: dict[str, Any],
    ) -> Path:
        output_dir = self.data_root / "runs" / session_id / "model_outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = output_dir / f"{output_id}.json"
        artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return artifact_path


__all__ = ["ModelRouter", "RouterPolicy"]
