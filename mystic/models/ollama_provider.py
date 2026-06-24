"""Ollama HTTP provider."""

from __future__ import annotations

from mystic.models.provider import HTTPChatProvider


class OllamaProvider(HTTPChatProvider):
    env_base_url = "OLLAMA_BASE_URL"
    env_api_key = ""

    def _build_payload(self, prompt: str, problem: str, settings):
        return {
            "model": settings.model,
            "prompt": f"{prompt}\n\nProblem:\n{problem}",
            "stream": False,
            "options": {"temperature": settings.temperature or 0.0},
        }

