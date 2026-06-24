"""Provider abstractions for Mystic model backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
import json
import os
from urllib import error, request

from mystic.core.protocol import ModelSettings, ProviderResponse


class BaseProvider(ABC):
    @abstractmethod
    def generate(
        self,
        agent_name: str,
        prompt: str,
        problem: str,
        settings: ModelSettings,
    ) -> ProviderResponse:
        """Generate a provider response for an agent."""


class HTTPChatProvider(BaseProvider):
    env_base_url = ""
    env_api_key = ""

    def generate(
        self,
        agent_name: str,
        prompt: str,
        problem: str,
        settings: ModelSettings,
    ) -> ProviderResponse:
        base_url = os.getenv(self.env_base_url, "")
        if not base_url:
            return ProviderResponse(
                text=f"{agent_name} provider not configured; returning offline placeholder.",
                metadata={"configured": False, "provider": settings.provider},
            )

        payload = self._build_payload(prompt, problem, settings)
        headers = {"Content-Type": "application/json"}
        api_key = os.getenv(self.env_api_key, "")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        req = request.Request(
            base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=30) as response:
                raw = response.read().decode("utf-8")
        except (error.URLError, TimeoutError) as exc:
            return ProviderResponse(
                text=f"{agent_name} backend unavailable: {exc}",
                metadata={"configured": True, "reachable": False},
            )

        text = self._extract_text(raw)
        return ProviderResponse(text=text, metadata={"configured": True, "reachable": True})

    def _build_payload(self, prompt: str, problem: str, settings: ModelSettings) -> dict:
        return {
            "model": settings.model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": problem},
            ],
            "temperature": settings.temperature or 0.0,
        }

    def _extract_text(self, raw: str) -> str:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        if "response" in payload:
            return str(payload["response"])
        choices = payload.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            if "content" in message:
                return str(message["content"])
            if "text" in choices[0]:
                return str(choices[0]["text"])
        return raw

