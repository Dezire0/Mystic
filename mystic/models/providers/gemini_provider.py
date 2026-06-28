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


class GeminiAPIProvider(RoutedProvider):
    default_url = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def status(self, model_id: str, config: dict[str, Any]) -> ProviderStatus:
        if not bool(config.get("enabled", False)):
            return disabled_status("API provider is disabled by default.", model_id=model_id)
        api_key = os.getenv(str(config.get("api_key_env", "GEMINI_API_KEY")), "")
        if not api_key:
            return unavailable_status("Gemini API key is missing.", model_id=model_id)
        return ready_status("Gemini API is configured.", model_id=model_id)

    def call(self, model_id: str, config: dict[str, Any], request_data: ModelCallRequest) -> ProviderInvocation:
        status = self.status(model_id, config)
        if status.state != "ready":
            return provider_error(status.message, latency_sec=0.0, provider="api", model_id=model_id)
        api_key_env = str(config.get("api_key_env", "GEMINI_API_KEY"))
        model_name = str(config.get("model", ""))
        url_template = str(config.get("api_url", self.default_url))
        url = url_template.format(model=model_name)
        if "?" not in url:
            url = f"{url}?key={os.getenv(api_key_env, '')}"
        payload = {
            "contents": [{"parts": [{"text": request_data.build_prompt()}]}],
        }
        try:
            _, raw, latency = post_json(
                url,
                payload,
                timeout_seconds=request_data.timeout_seconds,
            )
        except Exception as exc:  # pragma: no cover - network dependent
            return provider_transport_error(exc, model_id=model_id, provider="api")
        return ProviderInvocation(
            content=extract_text_from_json(raw),
            status="OK",
            latency_sec=latency,
            metadata={"provider": "api", "api_provider": "gemini", "model_id": model_id},
        )
