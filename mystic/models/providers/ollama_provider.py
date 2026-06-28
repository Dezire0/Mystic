from __future__ import annotations

import os
from urllib import error

from mystic.models.providers.base import (
    ModelCallRequest,
    ProviderInvocation,
    ProviderStatus,
    RoutedProvider,
    extract_text_from_json,
    get_json,
    post_json,
    provider_transport_error,
    ready_status,
    unavailable_status,
)


class OllamaRoutedProvider(RoutedProvider):
    def status(self, model_id: str, config: dict[str, object]) -> ProviderStatus:
        base_url = str(config.get("base_url") or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434")
        try:
            get_json(f"{base_url.rstrip('/')}/api/tags", timeout_seconds=3)
        except Exception as exc:  # pragma: no cover - exercised by tests with mocks
            return unavailable_status(
                f"Ollama is not reachable: {exc}",
                model_id=model_id,
                base_url=base_url,
            )
        return ready_status(
            "Ollama is reachable.",
            model_id=model_id,
            base_url=base_url,
            model_name=str(config.get("model", "")),
        )

    def call(self, model_id: str, config: dict[str, object], request_data: ModelCallRequest) -> ProviderInvocation:
        base_url = str(config.get("base_url") or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434")
        payload = {
            "model": str(config.get("model", "")),
            "prompt": request_data.build_prompt(),
            "stream": False,
            "options": {
                "temperature": request_data.temperature if request_data.temperature is not None else 0.0,
            },
        }
        try:
            _, raw, latency = post_json(
                f"{base_url.rstrip('/')}/api/generate",
                payload,
                timeout_seconds=request_data.timeout_seconds,
            )
        except error.URLError as exc:
            return provider_transport_error(exc, model_id=model_id, provider="ollama")
        except Exception as exc:  # pragma: no cover - defensive
            return provider_transport_error(exc, model_id=model_id, provider="ollama")
        return ProviderInvocation(
            content=extract_text_from_json(raw),
            status="OK",
            latency_sec=latency,
            metadata={"provider": "ollama", "model_id": model_id},
        )
