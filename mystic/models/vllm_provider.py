"""vLLM HTTP provider."""

from __future__ import annotations

from mystic.models.provider import HTTPChatProvider


class VLLMProvider(HTTPChatProvider):
    env_base_url = "VLLM_BASE_URL"
    env_api_key = "OPENAI_COMPATIBLE_API_KEY"

