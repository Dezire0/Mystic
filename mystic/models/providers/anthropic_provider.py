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


class AnthropicAPIProvider(RoutedProvider):
    default_url = "https://api.anthropic.com/v1/messages"

    def status(self, model_id: str, config: dict[str, Any]) -> ProviderStatus:
        if not bool(config.get("enabled", False)):
            return disabled_status("API provider is disabled by default.", model_id=model_id)
        api_key = os.getenv(str(config.get("api_key_env", "ANTHROPIC_API_KEY")), "")
        if not api_key:
            return unavailable_status("Anthropic API key is missing.", model_id=model_id)
        return ready_status("Anthropic API is configured.", model_id=model_id)

    def call(self, model_id: str, config: dict[str, Any], request_data: ModelCallRequest) -> ProviderInvocation:
        status = self.status(model_id, config)
        if status.state != "ready":
            return provider_error(status.message, latency_sec=0.0, provider="api", model_id=model_id)
        api_key_env = str(config.get("api_key_env", "ANTHROPIC_API_KEY"))
        url = str(config.get("api_url", self.default_url))
        payload = {
            "model": str(config.get("model", "")),
            "max_tokens": request_data.max_tokens or 1024,
            "messages": [{"role": "user", "content": request_data.build_prompt()}],
        }
        try:
            _, raw, latency = post_json(
                url,
                payload,
                headers={
                    "x-api-key": os.getenv(api_key_env, ""),
                    "anthropic-version": "2023-06-01",
                },
                timeout_seconds=request_data.timeout_seconds,
            )
        except Exception as exc:  # pragma: no cover - network dependent
            return provider_transport_error(exc, model_id=model_id, provider="api")
        return ProviderInvocation(
            content=extract_text_from_json(raw),
            status="OK",
            latency_sec=latency,
            metadata={"provider": "api", "api_provider": "anthropic", "model_id": model_id},
        )
