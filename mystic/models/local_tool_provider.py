"""Provider stub used by tool-backed or local storage agents."""

from __future__ import annotations

from mystic.core.protocol import ModelSettings, ProviderResponse
from mystic.models.provider import BaseProvider


class LocalToolProvider(BaseProvider):
    def generate(
        self,
        agent_name: str,
        prompt: str,
        problem: str,
        settings: ModelSettings,
    ) -> ProviderResponse:
        return ProviderResponse(
            text=f"{agent_name} uses local provider '{settings.model}' and does not call a text model.",
            metadata={"local": True},
        )

