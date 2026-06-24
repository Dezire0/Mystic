"""Config-driven model registry."""

from __future__ import annotations

from pathlib import Path

from mystic.core.protocol import ModelSettings
from mystic.models import (
    LocalToolProvider,
    MockProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
    VLLMProvider,
)
from mystic.utils.yamlish import load_yaml_file


PROVIDER_TYPES = {
    "mock": MockProvider,
    "ollama": OllamaProvider,
    "openai_compatible": OpenAICompatibleProvider,
    "vllm": VLLMProvider,
    "local_tool": LocalToolProvider,
    "local": LocalToolProvider,
}


class ModelRegistry:
    def __init__(self, config_path: str | Path) -> None:
        raw = load_yaml_file(config_path)
        self.default_provider = str(raw.get("default_provider", "mock"))
        self._agents = raw.get("agents", {})
        self._providers: dict[str, object] = {}

    def get_agent_settings(self, agent_name: str) -> ModelSettings:
        raw = self._agents.get(agent_name)
        if raw is None:
            raise KeyError(f"Unknown agent config: {agent_name}")
        provider = str(raw.get("provider", self.default_provider))
        return ModelSettings(
            provider=provider,
            model=str(raw.get("model", "unknown")),
            adapter=raw.get("adapter"),
            temperature=(
                float(raw["temperature"]) if "temperature" in raw and raw["temperature"] is not None else None
            ),
        )

    def get_provider(self, provider_name: str):
        if provider_name not in self._providers:
            provider_class = PROVIDER_TYPES.get(provider_name)
            if provider_class is None:
                raise KeyError(f"Unsupported provider: {provider_name}")
            self._providers[provider_name] = provider_class()
        return self._providers[provider_name]

    def list_agents(self) -> dict[str, ModelSettings]:
        return {name: self.get_agent_settings(name) for name in self._agents}

