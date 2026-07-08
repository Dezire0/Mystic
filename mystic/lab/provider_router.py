from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
import time
from typing import Any

import requests

from mystic.lab.provider_connect import ProviderConnectManager, normalize_provider_id
from mystic.lab.schema import utc_now_iso


SUPPORTED_PROVIDER_IDS = {"openai_compatible", "gemini", "anthropic", "mock"}
REDACTED_METADATA_KEYS = {
    "token",
    "bearer_token",
    "access_token",
    "refresh_token",
    "client_secret",
    "signing_secret",
    "password",
    "secret",
    "authorization",
    "api_key",
}


@dataclass(slots=True)
class ModelCallRecord:
    call_id: str
    session_id: str
    provider_id: str
    model: str
    tool_name: str
    agent_role: str
    prompt_hash: str
    prompt_excerpt_safe: str
    output_text: str
    status: str
    error_type: str = ""
    latency_ms: int = 0
    usage_json: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        self.call_id = str(self.call_id).strip()
        self.session_id = str(self.session_id or "").strip()
        self.provider_id = normalize_provider_id(self.provider_id)
        self.model = str(self.model or "").strip()
        self.tool_name = str(self.tool_name or "").strip()
        self.agent_role = str(self.agent_role or "").strip()
        self.prompt_hash = str(self.prompt_hash or "").strip()
        self.prompt_excerpt_safe = str(self.prompt_excerpt_safe or "").strip()
        self.output_text = str(self.output_text or "")
        self.status = str(self.status or "").strip()
        self.error_type = str(self.error_type or "").strip()
        self.latency_ms = max(0, int(self.latency_ms or 0))
        self.usage_json = dict(self.usage_json or {})
        self.metadata = dict(self.metadata or {})
        if not self.call_id:
            raise ValueError("call_id is required")
        if not self.provider_id:
            raise ValueError("provider_id is required")
        if not self.tool_name:
            raise ValueError("tool_name is required")
        if not self.prompt_hash:
            raise ValueError("prompt_hash is required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProviderCallError(RuntimeError):
    def __init__(self, error_type: str, safe_message: str, *, status_code: int | None = None) -> None:
        super().__init__(safe_message)
        self.error_type = error_type
        self.safe_message = safe_message
        self.status_code = status_code


class ProviderRouter:
    def __init__(self, *, storage: Any, runtime_mode: str) -> None:
        self.storage = storage
        self.runtime_mode = runtime_mode
        self.provider_connect = ProviderConnectManager(storage=storage, runtime_mode=runtime_mode)

    def invoke(
        self,
        *,
        provider_id: str,
        tool_name: str,
        prompt: str = "",
        system_prompt: str = "",
        messages: list[dict[str, str]] | None = None,
        session_id: str = "",
        agent_role: str = "",
        model: str = "",
        temperature: float = 0.2,
        max_tokens: int = 1024,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_provider = normalize_provider_id(provider_id)
        prompt_messages = self._normalize_messages(messages=messages, prompt=prompt, system_prompt=system_prompt)
        prompt_hash = self._prompt_hash(prompt_messages)
        prompt_excerpt = self._prompt_excerpt(prompt_messages)
        safe_metadata = self._safe_metadata(
            {
                "runtime_mode": self.runtime_mode,
                "requested_model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                **dict(metadata or {}),
            }
        )

        if normalized_provider not in SUPPORTED_PROVIDER_IDS:
            return self._persist_result(
                provider_id=normalized_provider,
                tool_name=tool_name,
                session_id=session_id,
                agent_role=agent_role,
                model=model,
                prompt_hash=prompt_hash,
                prompt_excerpt_safe=prompt_excerpt,
                output_text="",
                status="unsupported_provider",
                error_type="unsupported_provider",
                error_message_safe=f"Unsupported provider_id: {provider_id}",
                latency_ms=0,
                raw_usage_safe={},
                metadata=safe_metadata,
            )

        if normalized_provider == "mock":
            output_text = f"mock:{self._join_user_messages(prompt_messages).strip() or 'ping'}"
            return self._persist_result(
                provider_id="mock",
                tool_name=tool_name,
                session_id=session_id,
                agent_role=agent_role,
                model=model or "mock-model",
                prompt_hash=prompt_hash,
                prompt_excerpt_safe=prompt_excerpt,
                output_text=output_text,
                status="completed",
                error_type="",
                error_message_safe="",
                latency_ms=0,
                raw_usage_safe={"prompt_chars": len(prompt_excerpt), "completion_chars": len(output_text)},
                metadata={**safe_metadata, "test_only": True},
            )

        provider_status = self.provider_connect.provider_status(provider_id=normalized_provider)
        mapped_status = self._status_from_provider_payload(provider_status)
        if mapped_status != "connected":
            return self._persist_result(
                provider_id=provider_status["provider_id"],
                tool_name=tool_name,
                session_id=session_id,
                agent_role=agent_role,
                model=model or self._resolve_model(provider_status, model),
                prompt_hash=prompt_hash,
                prompt_excerpt_safe=prompt_excerpt,
                output_text="",
                status=mapped_status,
                error_type=mapped_status,
                error_message_safe=self._required_message(provider_status, mapped_status),
                latency_ms=0,
                raw_usage_safe={},
                metadata=safe_metadata,
            )

        resolved_model = self._resolve_model(provider_status, model)
        started_at = time.perf_counter()
        try:
            response = self._invoke_remote(
                provider_id=provider_status["provider_id"],
                model=resolved_model,
                messages=prompt_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except ProviderCallError as exc:
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            return self._persist_result(
                provider_id=provider_status["provider_id"],
                tool_name=tool_name,
                session_id=session_id,
                agent_role=agent_role,
                model=resolved_model,
                prompt_hash=prompt_hash,
                prompt_excerpt_safe=prompt_excerpt,
                output_text="",
                status=exc.error_type,
                error_type=exc.error_type,
                error_message_safe=exc.safe_message,
                latency_ms=latency_ms,
                raw_usage_safe={},
                metadata=safe_metadata,
            )

        latency_ms = int((time.perf_counter() - started_at) * 1000)
        output_text = str(response.get("output_text", "") or "")
        usage_safe = dict(response.get("raw_usage_safe") or {})
        return self._persist_result(
            provider_id=provider_status["provider_id"],
            tool_name=tool_name,
            session_id=session_id,
            agent_role=agent_role,
            model=resolved_model,
            prompt_hash=prompt_hash,
            prompt_excerpt_safe=prompt_excerpt,
            output_text=output_text,
            status="completed",
            error_type="",
            error_message_safe="",
            latency_ms=latency_ms,
            raw_usage_safe=usage_safe,
            metadata=safe_metadata,
        )

    def _persist_result(
        self,
        *,
        provider_id: str,
        tool_name: str,
        session_id: str,
        agent_role: str,
        model: str,
        prompt_hash: str,
        prompt_excerpt_safe: str,
        output_text: str,
        status: str,
        error_type: str,
        error_message_safe: str,
        latency_ms: int,
        raw_usage_safe: dict[str, Any],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        record = ModelCallRecord(
            call_id=f"call-{sha256(f'{provider_id}:{tool_name}:{prompt_hash}:{utc_now_iso()}'.encode('utf-8')).hexdigest()[:16]}",
            session_id=session_id,
            provider_id=provider_id,
            model=model,
            tool_name=tool_name,
            agent_role=agent_role,
            prompt_hash=prompt_hash,
            prompt_excerpt_safe=prompt_excerpt_safe,
            output_text=output_text,
            status=status,
            error_type=error_type,
            latency_ms=latency_ms,
            usage_json=raw_usage_safe,
            metadata=metadata,
        )
        try:
            paths = self.storage.save_model_call(record)
        except Exception:
            paths = {}
        return {
            "status": status,
            "provider_id": provider_id,
            "model": model,
            "output_text": output_text,
            "raw_usage_safe": raw_usage_safe,
            "latency_ms": latency_ms,
            "error_type": error_type,
            "error_message_safe": error_message_safe,
            "call_id": record.call_id,
            "storage_ref": paths.get("model_call", ""),
        }

    @staticmethod
    def _normalize_messages(
        *,
        messages: list[dict[str, str]] | None,
        prompt: str,
        system_prompt: str,
    ) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        for item in messages or []:
            role = str(item.get("role", "")).strip()
            content = str(item.get("content", "")).strip()
            if role and content:
                normalized.append({"role": role, "content": content})
        if normalized:
            return normalized
        if system_prompt.strip():
            normalized.append({"role": "system", "content": system_prompt.strip()})
        normalized.append({"role": "user", "content": prompt.strip() or "ping"})
        return normalized

    @staticmethod
    def _prompt_hash(messages: list[dict[str, str]]) -> str:
        payload = json.dumps(messages, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        return sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _prompt_excerpt(messages: list[dict[str, str]], *, limit: int = 240) -> str:
        raw = " | ".join(f"{item['role']}:{item['content']}" for item in messages if item.get("content"))
        compact = " ".join(raw.split())
        return compact[:limit]

    @staticmethod
    def _safe_metadata(value: Any) -> Any:
        if isinstance(value, dict):
            sanitized: dict[str, Any] = {}
            for key, item in value.items():
                key_text = str(key)
                if key_text.lower() in REDACTED_METADATA_KEYS:
                    continue
                sanitized[key_text] = ProviderRouter._safe_metadata(item)
            return sanitized
        if isinstance(value, list):
            return [ProviderRouter._safe_metadata(item) for item in value[:12]]
        if isinstance(value, str):
            return value[:500]
        return value

    @staticmethod
    def _resolve_model(provider_status: dict[str, Any], requested_model: str) -> str:
        if str(requested_model or "").strip():
            return str(requested_model).strip()
        model_list = provider_status.get("model_list", [])
        if isinstance(model_list, list) and model_list:
            return str(model_list[0]).strip()
        return provider_status["provider_id"]

    @staticmethod
    def _required_message(provider_status: dict[str, Any], mapped_status: str) -> str:
        if mapped_status == "api_key_required":
            return "Provider credentials are not configured. Complete the secure setup flow and retry."
        if mapped_status == "provider_auth_failed":
            return "Provider authentication failed. Verify credentials and retry."
        if mapped_status == "rate_limited":
            return "Provider rate limit was reached. Retry later."
        if mapped_status == "provider_unavailable":
            return "Provider is temporarily unavailable. Retry later."
        return str(provider_status.get("setup_instructions") or "Provider must be connected before this call can run.")

    @staticmethod
    def _status_from_provider_payload(provider_status: dict[str, Any]) -> str:
        status = str(provider_status.get("status", "")).strip()
        mapping = {
            "connected": "connected",
            "api_key_required": "api_key_required",
            "auth_failed": "provider_auth_failed",
            "rate_limited": "rate_limited",
            "provider_unavailable": "provider_unavailable",
        }
        if status in mapping:
            return mapping[status]
        return "provider_required"

    def _invoke_remote(
        self,
        *,
        provider_id: str,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        if provider_id == "openai_compatible":
            return self._call_openai_compatible(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens)
        if provider_id == "gemini":
            return self._call_gemini(model=model, messages=messages)
        if provider_id == "anthropic":
            return self._call_anthropic(model=model, messages=messages, max_tokens=max_tokens)
        raise ProviderCallError("unsupported_provider", f"Unsupported provider_id: {provider_id}")

    def _call_openai_compatible(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        import os

        base_url = str(os.environ.get("MYSTIC_PROVIDER_OPENAI_COMPAT_BASE_URL", "")).strip().rstrip("/")
        api_key = str(os.environ.get("MYSTIC_PROVIDER_OPENAI_COMPAT_API_KEY", "")).strip()
        if not base_url or not api_key:
            raise ProviderCallError("api_key_required", "OpenAI-compatible provider is missing required configuration.")
        payload = self._request_json(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            body={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max(1, int(max_tokens)),
            },
        )
        choice = payload.get("choices", [{}])[0] if isinstance(payload.get("choices"), list) else {}
        content = choice.get("message", {}).get("content", "") if isinstance(choice, dict) else ""
        return {
            "output_text": self._normalize_text_output(content),
            "raw_usage_safe": self._safe_usage(payload.get("usage")),
        }

    def _call_gemini(self, *, model: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        import os

        api_key = str(os.environ.get("MYSTIC_PROVIDER_GEMINI_API_KEY", "")).strip()
        bearer_token = str(os.environ.get("MYSTIC_PROVIDER_GEMINI_BEARER_TOKEN", "")).strip()
        if not api_key and not bearer_token:
            raise ProviderCallError("api_key_required", "Gemini provider is missing required configuration.")
        prompt = self._join_user_messages(messages)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers: dict[str, str] = {}
        if api_key:
            headers["x-goog-api-key"] = api_key
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        payload = self._request_json(
            url,
            headers=headers,
            body={"contents": [{"role": "user", "parts": [{"text": prompt}]}]},
        )
        candidates = payload.get("candidates", [])
        candidate = candidates[0] if isinstance(candidates, list) and candidates else {}
        parts = candidate.get("content", {}).get("parts", []) if isinstance(candidate, dict) else []
        text = "\n".join(str(item.get("text", "")) for item in parts if isinstance(item, dict))
        return {
            "output_text": self._normalize_text_output(text),
            "raw_usage_safe": self._safe_usage(payload.get("usageMetadata")),
        }

    def _call_anthropic(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int,
    ) -> dict[str, Any]:
        import os

        api_key = str(os.environ.get("MYSTIC_PROVIDER_ANTHROPIC_API_KEY", "")).strip()
        bearer_token = str(os.environ.get("MYSTIC_PROVIDER_ANTHROPIC_BEARER_TOKEN", "")).strip()
        if not api_key and not bearer_token:
            raise ProviderCallError("api_key_required", "Anthropic provider is missing required configuration.")
        headers: dict[str, str] = {"anthropic-version": "2023-06-01"}
        if api_key:
            headers["x-api-key"] = api_key
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        system_prompt = next((item["content"] for item in messages if item.get("role") == "system"), "")
        user_messages = [
            {"role": "user" if item.get("role") == "user" else "assistant", "content": item.get("content", "")}
            for item in messages
            if item.get("role") != "system"
        ]
        payload = self._request_json(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            body={
                "model": model,
                "max_tokens": max(1, int(max_tokens)),
                "system": system_prompt,
                "messages": user_messages,
            },
        )
        content = payload.get("content", [])
        text = "\n".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
        usage = payload.get("usage")
        return {
            "output_text": self._normalize_text_output(text),
            "raw_usage_safe": self._safe_usage(usage),
        }

    def _request_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        body: dict[str, Any],
    ) -> dict[str, Any]:
        request_headers = {"Content-Type": "application/json", **headers}
        try:
            response = requests.post(url, json=body, headers=request_headers, timeout=30)
        except requests.Timeout as exc:
            raise ProviderCallError("provider_unavailable", "Provider request timed out.") from exc
        except requests.RequestException as exc:
            raise ProviderCallError("provider_unavailable", "Provider request could not be completed.") from exc

        if response.status_code in {401, 403}:
            raise ProviderCallError("provider_auth_failed", f"Provider rejected credentials with HTTP {response.status_code}.", status_code=response.status_code)
        if response.status_code == 429:
            raise ProviderCallError("rate_limited", "Provider rate limit reached.", status_code=response.status_code)
        if response.status_code in {408, 500, 502, 503, 504}:
            raise ProviderCallError("provider_unavailable", f"Provider is unavailable with HTTP {response.status_code}.", status_code=response.status_code)
        if response.status_code >= 400:
            raise ProviderCallError("provider_error", f"Provider request failed with HTTP {response.status_code}.", status_code=response.status_code)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderCallError("provider_error", "Provider returned a non-JSON response.") from exc
        if not isinstance(payload, dict):
            raise ProviderCallError("provider_error", "Provider returned an unexpected response shape.")
        return payload

    @staticmethod
    def _safe_usage(payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        safe: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, (int, float, str, bool)) or value is None:
                safe[str(key)] = value
        return safe

    @staticmethod
    def _join_user_messages(messages: list[dict[str, str]]) -> str:
        user_parts = [item["content"] for item in messages if item.get("role") == "user" and item.get("content")]
        if user_parts:
            return "\n\n".join(user_parts)
        return "\n\n".join(item["content"] for item in messages if item.get("content"))

    @staticmethod
    def _normalize_text_output(value: Any) -> str:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            return "\n".join(str(item).strip() for item in value if str(item).strip())
        return str(value or "").strip()
