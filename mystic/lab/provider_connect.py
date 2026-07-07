from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
import os
import uuid

from mystic.lab.schema import (
    LAB_PROVIDER_AUTH_FLOW_STATUSES,
    LAB_PROVIDER_AUTH_METHODS,
    LAB_PROVIDER_STATUSES,
    LAB_PROVIDER_TYPES,
    utc_now_iso,
    validate_choice,
)


PUBLIC_PROVIDER_IDS = (
    "openai_compatible",
    "gemini",
    "anthropic",
    "future_custom",
)

TEST_PROVIDER_IDS = ("mock",)


PROVIDER_CATALOG: dict[str, dict[str, Any]] = {
    "openai_compatible": {
        "provider_id": "openai_compatible",
        "provider_type": "openai_compatible",
        "default_auth_method": "api_key",
        "supported_auth_methods": {"api_key", "bearer_token"},
        "supports_oauth": False,
        "secret_names": [
            "MYSTIC_PROVIDER_OPENAI_COMPAT_API_KEY",
            "MYSTIC_PROVIDER_OPENAI_COMPAT_BASE_URL",
            "MYSTIC_PROVIDER_OPENAI_COMPAT_MODEL",
        ],
        "required_secret_names": [
            "MYSTIC_PROVIDER_OPENAI_COMPAT_API_KEY",
            "MYSTIC_PROVIDER_OPENAI_COMPAT_BASE_URL",
        ],
        "optional_secret_names": ["MYSTIC_PROVIDER_OPENAI_COMPAT_MODEL"],
        "model_env_names": ["MYSTIC_PROVIDER_OPENAI_COMPAT_MODEL"],
        "setup_url": "https://platform.openai.com/api-keys",
        "setup_instructions": (
            "Set Cloudflare secret MYSTIC_PROVIDER_OPENAI_COMPAT_API_KEY, "
            "set MYSTIC_PROVIDER_OPENAI_COMPAT_BASE_URL, and optionally set "
            "MYSTIC_PROVIDER_OPENAI_COMPAT_MODEL."
        ),
        "scopes": ["model:generate"],
        "default_models": ["openai-compatible"],
    },
    "gemini": {
        "provider_id": "gemini",
        "provider_type": "gemini",
        "default_auth_method": "api_key",
        "supported_auth_methods": {"api_key", "bearer_token"},
        "supports_oauth": False,
        "secret_names": [
            "MYSTIC_PROVIDER_GEMINI_API_KEY",
            "MYSTIC_PROVIDER_GEMINI_MODEL",
        ],
        "required_secret_names": ["MYSTIC_PROVIDER_GEMINI_API_KEY"],
        "optional_secret_names": ["MYSTIC_PROVIDER_GEMINI_MODEL"],
        "model_env_names": ["MYSTIC_PROVIDER_GEMINI_MODEL"],
        "setup_url": "https://aistudio.google.com/app/apikey",
        "setup_instructions": (
            "Set Cloudflare secret MYSTIC_PROVIDER_GEMINI_API_KEY and optionally set "
            "MYSTIC_PROVIDER_GEMINI_MODEL."
        ),
        "scopes": ["model:generate"],
        "default_models": ["gemini-1.5-flash"],
    },
    "anthropic": {
        "provider_id": "anthropic",
        "provider_type": "anthropic",
        "default_auth_method": "api_key",
        "supported_auth_methods": {"api_key", "bearer_token"},
        "supports_oauth": False,
        "secret_names": [
            "MYSTIC_PROVIDER_ANTHROPIC_API_KEY",
            "MYSTIC_PROVIDER_ANTHROPIC_MODEL",
        ],
        "required_secret_names": ["MYSTIC_PROVIDER_ANTHROPIC_API_KEY"],
        "optional_secret_names": ["MYSTIC_PROVIDER_ANTHROPIC_MODEL"],
        "model_env_names": ["MYSTIC_PROVIDER_ANTHROPIC_MODEL"],
        "setup_url": "https://console.anthropic.com/settings/keys",
        "setup_instructions": (
            "Set Cloudflare secret MYSTIC_PROVIDER_ANTHROPIC_API_KEY and optionally set "
            "MYSTIC_PROVIDER_ANTHROPIC_MODEL."
        ),
        "scopes": ["model:generate"],
        "default_models": ["claude-3-5-sonnet-latest"],
    },
    "future_custom": {
        "provider_id": "future_custom",
        "provider_type": "future/custom",
        "default_auth_method": "oauth",
        "supported_auth_methods": {"api_key", "oauth", "bearer_token"},
        "supports_oauth": True,
        "secret_names": [],
        "required_secret_names": [],
        "optional_secret_names": [],
        "model_env_names": [],
        "setup_url": "",
        "setup_instructions": (
            "Future custom providers are metadata-only in this foundation issue. "
            "Use provider_connect_start to record intent, then finish provider-specific "
            "wiring in a later issue."
        ),
        "scopes": ["model:generate"],
        "default_models": [],
    },
    "mock": {
        "provider_id": "mock",
        "provider_type": "future/custom",
        "default_auth_method": "none/mock",
        "supported_auth_methods": {"none/mock"},
        "supports_oauth": False,
        "secret_names": [],
        "required_secret_names": [],
        "optional_secret_names": [],
        "model_env_names": [],
        "setup_url": "",
        "setup_instructions": "Mock provider is test-only and must not be used for production routing.",
        "scopes": ["model:generate"],
        "default_models": ["mock-model"],
        "test_only": True,
    },
}


def normalize_provider_id(value: str) -> str:
    normalized = str(value or "").strip().lower()
    aliases = {
        "openai": "openai_compatible",
        "google": "gemini",
        "claude": "anthropic",
        "custom": "future_custom",
        "future/custom": "future_custom",
        "future": "future_custom",
    }
    return aliases.get(normalized, normalized)


def provider_catalog(provider_id: str) -> dict[str, Any]:
    normalized = normalize_provider_id(provider_id)
    if normalized not in PROVIDER_CATALOG:
        raise ValueError(f"Unsupported provider_id: {provider_id}")
    return PROVIDER_CATALOG[normalized]


def _coerce_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


@dataclass(slots=True)
class ProviderConnection:
    connection_id: str
    provider_id: str
    provider_type: str
    auth_method: str
    status: str
    scopes: list[str] = field(default_factory=list)
    model_list: list[str] = field(default_factory=list)
    setup_url: str = ""
    setup_instructions: str = ""
    last_verified_at: str = ""
    failure_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        self.provider_id = normalize_provider_id(self.provider_id)
        validate_choice("provider_type", self.provider_type, LAB_PROVIDER_TYPES)
        validate_choice("auth_method", self.auth_method, LAB_PROVIDER_AUTH_METHODS)
        validate_choice("status", self.status, LAB_PROVIDER_STATUSES)
        self.connection_id = str(self.connection_id).strip()
        self.setup_url = str(self.setup_url).strip()
        self.setup_instructions = str(self.setup_instructions).strip()
        self.last_verified_at = str(self.last_verified_at).strip()
        self.failure_reason = str(self.failure_reason)
        self.scopes = _coerce_string_list(self.scopes)
        self.model_list = _coerce_string_list(self.model_list)
        self.metadata = _coerce_mapping(self.metadata)
        if not self.connection_id:
            raise ValueError("connection_id is required")
        if not self.provider_id:
            raise ValueError("provider_id is required")

    def touch(self) -> None:
        self.updated_at = utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ProviderAuthFlow:
    flow_id: str
    provider_id: str
    auth_method: str
    status: str
    redirect_url: str = ""
    state: str = ""
    code_challenge: str = ""
    code_challenge_method: str = ""
    callback_received_at: str = ""
    failure_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        self.provider_id = normalize_provider_id(self.provider_id)
        validate_choice("auth_method", self.auth_method, LAB_PROVIDER_AUTH_METHODS)
        validate_choice("status", self.status, LAB_PROVIDER_AUTH_FLOW_STATUSES)
        self.flow_id = str(self.flow_id).strip()
        self.redirect_url = str(self.redirect_url).strip()
        self.state = str(self.state).strip()
        self.code_challenge = str(self.code_challenge).strip()
        self.code_challenge_method = str(self.code_challenge_method).strip()
        self.callback_received_at = str(self.callback_received_at).strip()
        self.failure_reason = str(self.failure_reason)
        self.metadata = _coerce_mapping(self.metadata)
        if not self.flow_id:
            raise ValueError("flow_id is required")
        if not self.provider_id:
            raise ValueError("provider_id is required")

    def touch(self) -> None:
        self.updated_at = utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProviderConnectManager:
    def __init__(self, *, storage: Any, runtime_mode: str) -> None:
        self.storage = storage
        self.runtime_mode = runtime_mode

    def provider_list(self) -> dict[str, Any]:
        return {"providers": [self._provider_payload(provider_id) for provider_id in PUBLIC_PROVIDER_IDS]}

    def provider_status(self, *, provider_id: str) -> dict[str, Any]:
        return self._provider_payload(provider_id)

    def provider_connect_start(self, *, provider_id: str, auth_method: str | None = None) -> dict[str, Any]:
        spec = provider_catalog(provider_id)
        requested_auth = str(auth_method or spec["default_auth_method"]).strip() or spec["default_auth_method"]
        if requested_auth == "none/mock" and normalize_provider_id(provider_id) == "mock":
            connection = self._save_connection(
                provider_id="mock",
                auth_method="none/mock",
                status="connected",
                model_list=["mock-model"],
                metadata={"test_only": True},
            )
            payload = self._provider_payload("mock")
            payload["connection_id"] = connection.connection_id
            payload["message"] = "Mock provider connected for tests."
            return payload
        if requested_auth not in spec["supported_auth_methods"]:
            requested_auth = spec["default_auth_method"]
        if requested_auth in {"oauth", "bearer_token"} and not spec.get("supports_oauth", False):
            connection = self._save_connection(
                provider_id=spec["provider_id"],
                auth_method="api_key",
                status="api_key_required",
                failure_reason="official_oauth_not_supported",
            )
            payload = self._provider_payload(spec["provider_id"])
            payload["connection_id"] = connection.connection_id
            payload["message"] = "This provider foundation does not expose official provider OAuth here. Use API key setup instructions."
            return payload
        if requested_auth == "oauth":
            flow = ProviderAuthFlow(
                flow_id=f"flow-{uuid.uuid4().hex[:12]}",
                provider_id=spec["provider_id"],
                auth_method=requested_auth,
                status="oauth_required",
                state=uuid.uuid4().hex,
                metadata={"runtime_mode": self.runtime_mode},
            )
            self.storage.save_provider_auth_flow(flow)
            connection = self._save_connection(
                provider_id=spec["provider_id"],
                auth_method=requested_auth,
                status="oauth_required",
            )
            payload = self._provider_payload(spec["provider_id"])
            payload["connection_id"] = connection.connection_id
            payload["flow"] = flow.to_dict()
            payload["message"] = "OAuth metadata flow recorded. Provider-specific callback completion is deferred."
            return payload
        resolved = self._provider_payload(spec["provider_id"])
        target_status = str(resolved["status"])
        if requested_auth == "api_key" and target_status != "connected":
            target_status = "api_key_required"
        connection = self._save_connection(
            provider_id=spec["provider_id"],
            auth_method=requested_auth,
            status=target_status,
        )
        resolved = self._provider_payload(spec["provider_id"])
        resolved["connection_id"] = connection.connection_id
        resolved["status"] = target_status
        resolved["message"] = "Provider connect foundation recorded setup intent."
        return resolved

    def provider_connect_callback_status(self, *, provider_id: str, flow_id: str) -> dict[str, Any]:
        flow = self._load_flow_safe(flow_id)
        if flow is None or flow.provider_id != normalize_provider_id(provider_id):
            raise ValueError(f"Unknown provider auth flow: {flow_id}")
        return {
            "provider": self._provider_payload(provider_id),
            "flow": flow.to_dict(),
            "callback_received": bool(flow.callback_received_at),
        }

    def provider_configure_secret_instructions(self, *, provider_id: str) -> dict[str, Any]:
        spec = provider_catalog(provider_id)
        secret_state = self._secret_state(spec)
        payload = self._provider_payload(spec["provider_id"])
        payload.update(
            {
                "secret_names": list(spec["secret_names"]),
                "required_secret_names": list(spec["required_secret_names"]),
                "optional_secret_names": list(spec["optional_secret_names"]),
                "configured_secret_names": secret_state["configured_secret_names"],
                "missing_secret_names": secret_state["missing_secret_names"],
                "instructions": [
                    "Do not store provider secrets in Supabase.",
                    "Store production provider secrets only in Cloudflare Worker secret storage or approved server-side secret storage.",
                    "Do not paste API keys into tool output or chat transcripts.",
                ],
                "runtime_mode": self.runtime_mode,
            }
        )
        return payload

    def provider_verify(self, *, provider_id: str) -> dict[str, Any]:
        payload = self._provider_payload(provider_id)
        provider_key = normalize_provider_id(provider_id)
        existing = self._load_connection_safe(provider_key)
        if existing is not None and existing.status == "disconnected":
            verified = dict(payload)
            verified["verified_at"] = utc_now_iso()
            verified["message"] = "Provider remains disconnected until an explicit reconnect."
            return verified
        connection = self._save_connection(
            provider_id=provider_key,
            auth_method=str(payload["auth_method"]),
            status=str(payload["status"]),
            last_verified_at=utc_now_iso(),
            model_list=list(payload.get("model_list", [])),
        )
        verified = self._provider_payload(provider_key)
        verified["connection_id"] = connection.connection_id
        verified["verified_at"] = connection.last_verified_at
        verified["message"] = "Provider configuration was checked without exposing secrets."
        return verified

    def provider_disconnect(self, *, provider_id: str) -> dict[str, Any]:
        provider_key = normalize_provider_id(provider_id)
        connection = self._load_connection_safe(provider_key)
        model_list = connection.model_list if connection is not None else []
        updated = self._save_connection(
            provider_id=provider_key,
            auth_method=connection.auth_method if connection is not None else provider_catalog(provider_key)["default_auth_method"],
            status="disconnected",
            model_list=model_list,
            metadata={"disconnected_at": utc_now_iso()},
        )
        payload = self._provider_payload(provider_key)
        payload["connection_id"] = updated.connection_id
        payload["message"] = "Provider was marked disconnected. Existing secrets were not deleted."
        return payload

    def provider_model_list(self, *, provider_id: str) -> dict[str, Any]:
        payload = self._provider_payload(provider_id)
        status = str(payload["status"])
        if status != "connected":
            return {
                "provider_id": payload["provider_id"],
                "provider_type": payload["provider_type"],
                "auth_method": payload["auth_method"],
                "status": status,
                "model_list": [],
                "setup_url": payload["setup_url"],
                "setup_instructions": payload["setup_instructions"],
            }
        return {
            "provider_id": payload["provider_id"],
            "provider_type": payload["provider_type"],
            "auth_method": payload["auth_method"],
            "status": status,
            "model_list": list(payload.get("model_list", [])),
        }

    def provider_call_test(self, *, provider_id: str, prompt: str) -> dict[str, Any]:
        provider_key = normalize_provider_id(provider_id)
        if provider_key == "mock":
            return {
                "provider_id": "mock",
                "provider_type": "future/custom",
                "auth_method": "none/mock",
                "status": "completed",
                "output": f"mock:{str(prompt).strip() or 'ping'}",
                "test_only": True,
            }
        payload = self._provider_payload(provider_key)
        return {
            "provider_id": payload["provider_id"],
            "provider_type": payload["provider_type"],
            "auth_method": payload["auth_method"],
            "status": "provider_required",
            "message": "Provider Connect foundation does not expose direct real provider test calls yet.",
            "setup_url": payload["setup_url"],
            "setup_instructions": payload["setup_instructions"],
        }

    def _provider_payload(self, provider_id: str) -> dict[str, Any]:
        spec = provider_catalog(provider_id)
        connection = self._load_connection_safe(spec["provider_id"])
        secret_state = self._secret_state(spec)
        status = self._resolve_status(spec, connection, secret_state)
        model_list = self._model_list(spec, connection)
        auth_method = connection.auth_method if connection is not None else spec["default_auth_method"]
        return {
            "provider_id": spec["provider_id"],
            "provider_type": spec["provider_type"],
            "auth_method": auth_method,
            "status": status,
            "scopes": list(connection.scopes if connection is not None and connection.scopes else spec["scopes"]),
            "model_list": model_list,
            "setup_url": connection.setup_url if connection is not None and connection.setup_url else spec["setup_url"],
            "setup_instructions": (
                connection.setup_instructions
                if connection is not None and connection.setup_instructions
                else spec["setup_instructions"]
            ),
            "last_verified_at": connection.last_verified_at if connection is not None else "",
            "failure_reason": connection.failure_reason if connection is not None else "",
            "metadata": connection.metadata if connection is not None else {},
            "configured_secret_names": secret_state["configured_secret_names"],
            "missing_secret_names": secret_state["missing_secret_names"],
            "runtime_mode": self.runtime_mode,
        }

    def _resolve_status(
        self,
        spec: dict[str, Any],
        connection: ProviderConnection | None,
        secret_state: dict[str, list[str]],
    ) -> str:
        if connection is not None and connection.status in {
            "disconnected",
            "auth_failed",
            "rate_limited",
            "provider_unavailable",
        }:
            return connection.status
        if spec.get("test_only"):
            return "connected"
        auth_method = connection.auth_method if connection is not None else spec["default_auth_method"]
        if auth_method in {"oauth", "bearer_token"} and not spec.get("supports_oauth", False):
            return "api_key_required"
        if auth_method == "oauth":
            return "oauth_required"
        if secret_state["required_secret_names"] and not secret_state["missing_required_secret_names"]:
            return "connected"
        if auth_method == "bearer_token":
            return "oauth_required"
        if connection is None and not secret_state["configured_secret_names"]:
            return "not_configured"
        return "api_key_required"

    def _secret_state(self, spec: dict[str, Any]) -> dict[str, list[str]]:
        configured = [name for name in spec["secret_names"] if str(os.environ.get(name, "")).strip()]
        missing = [name for name in spec["secret_names"] if name not in configured]
        missing_required = [name for name in spec["required_secret_names"] if name not in configured]
        return {
            "configured_secret_names": configured,
            "missing_secret_names": missing,
            "required_secret_names": list(spec["required_secret_names"]),
            "missing_required_secret_names": missing_required,
        }

    def _model_list(self, spec: dict[str, Any], connection: ProviderConnection | None) -> list[str]:
        if connection is not None and connection.model_list:
            return list(connection.model_list)
        models = [str(os.environ.get(name, "")).strip() for name in spec["model_env_names"] if str(os.environ.get(name, "")).strip()]
        if models:
            return models
        return list(spec["default_models"])

    def _save_connection(
        self,
        *,
        provider_id: str,
        auth_method: str,
        status: str,
        model_list: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        failure_reason: str = "",
        last_verified_at: str = "",
    ) -> ProviderConnection:
        spec = provider_catalog(provider_id)
        existing = self._load_connection_safe(spec["provider_id"])
        connection = ProviderConnection(
            connection_id=existing.connection_id if existing is not None else f"provider-{spec['provider_id']}",
            provider_id=spec["provider_id"],
            provider_type=spec["provider_type"],
            auth_method=auth_method,
            status=status,
            scopes=list(existing.scopes if existing is not None and existing.scopes else spec["scopes"]),
            model_list=list(model_list if model_list is not None else (existing.model_list if existing is not None else self._model_list(spec, None))),
            setup_url=spec["setup_url"],
            setup_instructions=spec["setup_instructions"],
            last_verified_at=last_verified_at or (existing.last_verified_at if existing is not None else ""),
            failure_reason=failure_reason,
            metadata={**(existing.metadata if existing is not None else {}), **(metadata or {})},
            created_at=existing.created_at if existing is not None else utc_now_iso(),
        )
        connection.touch()
        self.storage.save_provider_connection(connection)
        return connection

    def _load_connection_safe(self, provider_id: str) -> ProviderConnection | None:
        try:
            return self.storage.load_provider_connection(provider_id)
        except Exception:
            return None

    def _load_flow_safe(self, flow_id: str) -> ProviderAuthFlow | None:
        try:
            return self.storage.load_provider_auth_flow(flow_id)
        except Exception:
            return None
