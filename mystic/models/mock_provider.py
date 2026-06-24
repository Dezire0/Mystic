"""Deterministic mock provider for local-first development."""

from __future__ import annotations

from mystic.core.protocol import ModelSettings, ProviderResponse
from mystic.models.provider import BaseProvider


class MockProvider(BaseProvider):
    def generate(
        self,
        agent_name: str,
        prompt: str,
        problem: str,
        settings: ModelSettings,
    ) -> ProviderResponse:
        text = (
            f"[mock:{settings.model}] {agent_name} processed the prompt using "
            f"provider={settings.provider} adapter={settings.adapter or 'none'}."
        )
        return ProviderResponse(text=text, metadata={"mock": True})

