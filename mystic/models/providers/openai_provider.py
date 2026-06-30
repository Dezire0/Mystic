from __future__ import annotations

import os
from typing import Any

from mystic.models.providers.base import (
    ModelCallRequest,
    ProviderInvocation,
    ProviderStatus,
    RoutedProvider,
    disabled_status,
    extract_text_from_json,
    post_json,
    provider_error,
    provider_transport_error,
    ready_status,
    unavailable_status,
)


class OpenAIAPIProvider(RoutedProvider):
    default_url = "https://api.openai.com/v1/chat/completions"

    def status(self, model_id: str, config: dict[str, Any]) -> ProviderStatus:
        if not bool(config.get("enabled", False)):
            return disabled_status("API provider is disabled by default.", model_id=model_id)
        api_key = os.getenv(str(config.get("api_key_env", "OPENAI_API_KEY")), "")
        if not api_key:
            return unavailable_status("OpenAI API key is missing.", model_id=model_id)
        return ready_status("OpenAI API is configured.", model_id=model_id)

    def call(self, model_id: str, config: dict[str, Any], request_data: ModelCallRequest) -> ProviderInvocation:
        status = self.status(model_id, config)
        if status.state != "ready":
            return provider_error(status.message, latency_sec=0.0, provider="api", model_id=model_id)
        api_key_env = str(config.get("api_key_env", "OPENAI_API_KEY"))
        url = str(config.get("api_url", self.default_url))
        payload = {
            "model": str(config.get("model", "")),
            "messages": [{"role": "user", "content": request_data.build_prompt()}],
            "temperature": request_data.temperature if request_data.temperature is not None else 0.0,
        }
        try:
            _, raw, latency = post_json(
                url,
                payload,
                headers={"Authorization": f"Bearer {os.getenv(api_key_env, '')}"},
                timeout_seconds=request_data.timeout_seconds,
            )
        except Exception as exc:  # pragma: no cover - network dependent
            return provider_transport_error(exc, model_id=model_id, provider="api")
        return ProviderInvocation(
            content=extract_text_from_json(raw),
            status="OK",
            latency_sec=latency,
            metadata={"provider": "api", "api_provider": "openai", "model_id": model_id},
        )
