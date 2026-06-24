"""OpenAI-compatible HTTP provider."""

from __future__ import annotations

from mystic.models.provider import HTTPChatProvider


class OpenAICompatibleProvider(HTTPChatProvider):
    env_base_url = "OPENAI_COMPATIBLE_BASE_URL"
    env_api_key = "OPENAI_COMPATIBLE_API_KEY"

