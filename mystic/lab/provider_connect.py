from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Any
from urllib.parse import urlencode
import base64
import os
import secrets
import uuid

from mystic.lab.schema import (
    LAB_PROVIDER_AUTH_FLOW_STATUSES,
    LAB_PROVIDER_AUTH_METHODS,
    LAB_PROVIDER_STATUSES,
    LAB_PROVIDER_TYPES,
    utc_now_iso,
    validate_choice,
)


DEFAULT_PUBLIC_BASE_URL = "https://mystic.dexproject.workers.dev"
LOCAL_PUBLIC_BASE_URL = "http://127.0.0.1:8765"

PUBLIC_PROVIDER_IDS = (
    "openai_compatible",
    "gemini",
    "google_vertex_ai",
    "anthropic",
    "future_custom",
)

TEST_PROVIDER_IDS = ("mock",)


PROVIDER_CATALOG: dict[str, dict[str, Any]] = {
    "openai_compatible": {
        "provider_id": "openai_compatible",
        "provider_type": "openai_compatible",
        "default_auth_method": "api_key",
        "supported_auth_methods": {"api_key", "oauth", "bearer_token"},
        "supports_api_key": True,
        "supports_oauth": True,
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
        "external_setup_url": "https://platform.openai.com/api-keys",
        "setup_instructions": (
            "Set Cloudflare secret MYSTIC_PROVIDER_OPENAI_COMPAT_API_KEY, "
            "set MYSTIC_PROVIDER_OPENAI_COMPAT_BASE_URL, and optionally set "
            "MYSTIC_PROVIDER_OPENAI_COMPAT_MODEL."
        ),
        "scopes": ["model:generate"],
        "default_models": ["openai-compatible"],
        "oauth_env_prefix": "MYSTIC_PROVIDER_OPENAI_COMPAT",
        "oauth_default_scopes": [],
    },
    "gemini": {
        "provider_id": "gemini",
        "provider_type": "gemini",
        "default_auth_method": "api_key",
        "supported_auth_methods": {"api_key"},
        "supports_api_key": True,
        "supports_oauth": False,
        "secret_names": [
            "MYSTIC_PROVIDER_GEMINI_API_KEY",
            "MYSTIC_PROVIDER_GEMINI_MODEL",
        ],
        "required_secret_names": ["MYSTIC_PROVIDER_GEMINI_API_KEY"],
        "optional_secret_names": ["MYSTIC_PROVIDER_GEMINI_MODEL"],
        "model_env_names": ["MYSTIC_PROVIDER_GEMINI_MODEL"],
        "external_setup_url": "https://aistudio.google.com/app/apikey",
        "setup_instructions": (
            "Set Cloudflare secret MYSTIC_PROVIDER_GEMINI_API_KEY and optionally set "
            "MYSTIC_PROVIDER_GEMINI_MODEL."
        ),
        "scopes": ["model:generate"],
        "default_models": ["gemini-1.5-flash"],
    },
    "google_vertex_ai": {
        "provider_id": "google_vertex_ai",
        "provider_type": "google_vertex_ai",
        "default_auth_method": "oauth",
        "supported_auth_methods": {"oauth"},
        "supports_api_key": False,
        "supports_oauth": True,
        "secret_names": [
            "MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_ID",
            "MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_SECRET",
            "MYSTIC_PROVIDER_GOOGLE_VERTEX_PROJECT_ID",
            "MYSTIC_PROVIDER_GOOGLE_VERTEX_LOCATION",
            "MYSTIC_PROVIDER_GOOGLE_VERTEX_MODEL",
        ],
        "required_secret_names": [
            "MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_ID",
            "MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_SECRET",
            "MYSTIC_PROVIDER_GOOGLE_VERTEX_PROJECT_ID",
            "MYSTIC_PROVIDER_GOOGLE_VERTEX_LOCATION",
        ],
        "optional_secret_names": ["MYSTIC_PROVIDER_GOOGLE_VERTEX_MODEL"],
        "model_env_names": ["MYSTIC_PROVIDER_GOOGLE_VERTEX_MODEL"],
        "external_setup_url": "https://console.cloud.google.com/apis/credentials",
        "setup_instructions": (
            "Set Cloudflare secrets MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_ID, "
            "MYSTIC_PROVIDER_GOOGLE_VERTEX_CLIENT_SECRET, "
            "MYSTIC_PROVIDER_GOOGLE_VERTEX_PROJECT_ID, "
            "MYSTIC_PROVIDER_GOOGLE_VERTEX_LOCATION, and optionally "
            "MYSTIC_PROVIDER_GOOGLE_VERTEX_MODEL for Google OAuth-backed Vertex AI Gemini access."
        ),
        "scopes": ["model:generate"],
        "default_models": ["gemini-2.5-flash"],
        "oauth_env_prefix": "MYSTIC_PROVIDER_GOOGLE_VERTEX",
        "oauth_default_scopes": [
            "openid",
            "email",
            "profile",
            "https://www.googleapis.com/auth/cloud-platform",
        ],
        "oauth_default_authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
        "oauth_default_token_endpoint": "https://oauth2.googleapis.com/token",
        "oauth_missing_status": "provider_required",
        "oauth_require_client_secret": True,
        "oauth_required_config_env_names": [
            "MYSTIC_PROVIDER_GOOGLE_VERTEX_PROJECT_ID",
            "MYSTIC_PROVIDER_GOOGLE_VERTEX_LOCATION",
        ],
        "oauth_token_storage_supported": False,
    },
    "anthropic": {
        "provider_id": "anthropic",
        "provider_type": "anthropic",
        "default_auth_method": "api_key",
        "supported_auth_methods": {"api_key", "oauth", "bearer_token"},
        "supports_api_key": True,
        "supports_oauth": True,
        "secret_names": [
            "MYSTIC_PROVIDER_ANTHROPIC_API_KEY",
            "MYSTIC_PROVIDER_ANTHROPIC_MODEL",
        ],
        "required_secret_names": ["MYSTIC_PROVIDER_ANTHROPIC_API_KEY"],
        "optional_secret_names": ["MYSTIC_PROVIDER_ANTHROPIC_MODEL"],
        "model_env_names": ["MYSTIC_PROVIDER_ANTHROPIC_MODEL"],
        "external_setup_url": "https://console.anthropic.com/settings/keys",
        "setup_instructions": (
            "Set Cloudflare secret MYSTIC_PROVIDER_ANTHROPIC_API_KEY and optionally set "
            "MYSTIC_PROVIDER_ANTHROPIC_MODEL."
        ),
        "scopes": ["model:generate"],
        "default_models": ["claude-3-5-sonnet-latest"],
        "oauth_env_prefix": "MYSTIC_PROVIDER_ANTHROPIC",
        "oauth_default_scopes": [],
    },
    "future_custom": {
        "provider_id": "future_custom",
        "provider_type": "future/custom",
        "default_auth_method": "oauth",
        "supported_auth_methods": {"api_key", "oauth", "bearer_token"},
        "supports_api_key": False,
        "supports_oauth": True,
        "secret_names": [],
        "required_secret_names": [],
        "optional_secret_names": [],
        "model_env_names": [],
        "external_setup_url": "",
        "setup_instructions": (
            "Configure OAuth metadata for the future custom provider, then use "
            "provider_connect_start to generate a real authorization URL."
        ),
        "scopes": ["model:generate"],
        "default_models": [],
        "oauth_env_prefix": "MYSTIC_PROVIDER_FUTURE_CUSTOM",
        "oauth_default_scopes": [],
    },
    "mock": {
        "provider_id": "mock",
        "provider_type": "future/custom",
        "default_auth_method": "none/mock",
        "supported_auth_methods": {"none/mock"},
        "supports_api_key": False,
        "supports_oauth": False,
        "secret_names": [],
        "required_secret_names": [],
        "optional_secret_names": [],
        "model_env_names": [],
        "external_setup_url": "",
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
        "google-vertex-ai": "google_vertex_ai",
        "google_vertex": "google_vertex_ai",
        "vertex": "google_vertex_ai",
        "vertex_ai": "google_vertex_ai",
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


def _trimmed(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _truthy_env(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _route_base_url(runtime_mode: str) -> str:
    configured = (
        os.environ.get("MYSTIC_PROVIDER_CONNECT_BASE_URL")
        or os.environ.get("MYSTIC_PUBLIC_BASE_URL")
        or os.environ.get("MYSTIC_PUBLIC_MCP_BASE_URL")
    )
    if configured:
        return configured.rstrip("/")
    if runtime_mode == "local_backend":
        return LOCAL_PUBLIC_BASE_URL
    return DEFAULT_PUBLIC_BASE_URL


def _pkce_pair() -> tuple[str, str]:
    verifier = _base64url(secrets.token_bytes(32))
    challenge = _base64url(sha256(verifier.encode("utf-8")).digest())
    return verifier, challenge


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
    authorization_url: str = ""
    redirect_url: str = ""
    state: str = ""
    state_hash: str = ""
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
        self.authorization_url = str(self.authorization_url).strip()
        self.redirect_url = str(self.redirect_url).strip()
        self.state = str(self.state).strip()
        self.state_hash = str(self.state_hash).strip()
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

    def to_public_dict(self) -> dict[str, Any]:
        payload = self.to_dict()
        payload.pop("state", None)
        return payload


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
        provider_key = spec["provider_id"]
        requested_auth = _trimmed(auth_method, spec["default_auth_method"])
        if requested_auth not in spec["supported_auth_methods"]:
            requested_auth = spec["default_auth_method"]
        if requested_auth == "none/mock" and provider_key == "mock":
            connection = self._save_connection(
                provider_id=provider_key,
                auth_method="none/mock",
                status="connected",
                model_list=["mock-model"],
                metadata={"test_only": True},
            )
            payload = self._provider_payload(provider_key)
            payload["connection_id"] = connection.connection_id
            payload["message"] = "Mock provider connected for tests."
            return payload

        oauth_metadata = self._oauth_metadata(spec)
        if requested_auth in {"oauth", "bearer_token"}:
            if oauth_metadata["configured"]:
                verifier, challenge = _pkce_pair()
                flow_id = f"flow-{uuid.uuid4().hex[:12]}"
                state_value = f"{flow_id}.{secrets.token_urlsafe(18)}"
                authorization_url = self._build_authorization_url(
                    spec=spec,
                    oauth_metadata=oauth_metadata,
                    flow_id=flow_id,
                    state_value=state_value,
                    code_challenge=challenge,
                )
                flow = ProviderAuthFlow(
                    flow_id=flow_id,
                    provider_id=provider_key,
                    auth_method="oauth",
                    status="oauth_required",
                    authorization_url=authorization_url,
                    redirect_url=oauth_metadata["redirect_uri"],
                    state_hash=self._state_hash(state_value),
                    code_challenge=challenge,
                    code_challenge_method="S256",
                    metadata={
                        "runtime_mode": self.runtime_mode,
                        "authorization_endpoint": oauth_metadata["authorization_endpoint"],
                        "token_endpoint": oauth_metadata["token_endpoint"],
                        "client_id": oauth_metadata["client_id"],
                        "scopes": oauth_metadata["scopes"],
                        "pkce_enabled": True,
                        "code_verifier_present": bool(verifier),
                        "token_storage_supported": oauth_metadata["token_storage_supported"],
                    },
                )
                self.storage.save_provider_auth_flow(flow)
                connection = self._save_connection(
                    provider_id=provider_key,
                    auth_method="oauth",
                    status="oauth_required",
                    metadata={
                        "oauth_enabled": True,
                        "oauth_redirect_uri": oauth_metadata["redirect_uri"],
                        "oauth_client_id_configured": True,
                        "oauth_client_secret_configured": oauth_metadata["client_secret_configured"],
                        "oauth_missing_config_names": oauth_metadata["missing_config_names"],
                        "oauth_token_storage_supported": oauth_metadata["token_storage_supported"],
                    },
                )
                payload = self._provider_payload(provider_key)
                payload["connection_id"] = connection.connection_id
                payload["authorization_url"] = authorization_url
                payload["flow"] = flow.to_public_dict()
                payload["message"] = "Provider connect start produced a real OAuth authorization URL."
                return payload
            if spec.get("supports_api_key", False):
                connection = self._save_connection(
                    provider_id=provider_key,
                    auth_method="api_key",
                    status="api_key_required",
                    failure_reason="oauth_not_configured",
                )
                payload = self._provider_payload(provider_key)
                payload["connection_id"] = connection.connection_id
                payload["auth_method"] = "api_key"
                payload["status"] = "api_key_required"
                payload["message"] = "OAuth is not configured for this provider. Use the secure setup page and Cloudflare secret instructions."
                return payload
            payload = self._provider_payload(provider_key)
            payload["status"] = spec.get("oauth_missing_status", "provider_required")
            payload["provider_status"] = payload["status"]
            payload["failure_reason"] = self._default_failure_reason(
                spec, payload["status"], oauth_metadata, self._secret_state(spec)
            )
            payload["message"] = self._provider_status_message(payload)
            return payload

        payload = self._provider_payload(provider_key)
        target_status = "connected" if payload["configured"] else "api_key_required"
        connection = self._save_connection(
            provider_id=provider_key,
            auth_method=requested_auth,
            status=target_status,
            failure_reason="" if payload["configured"] else payload["failure_reason"],
        )
        payload = self._provider_payload(provider_key)
        payload["connection_id"] = connection.connection_id
        payload["status"] = target_status
        payload["message"] = "Provider connect start returned the secure Mystic LAB setup page."
        return payload

    def provider_connect_callback_status(self, *, provider_id: str, flow_id: str) -> dict[str, Any]:
        flow = self._load_flow_safe(flow_id)
        if flow is None or flow.provider_id != normalize_provider_id(provider_id):
            raise ValueError(f"Unknown provider auth flow: {flow_id}")
        return {
            "provider": self._provider_payload(provider_id),
            "flow": flow.to_public_dict(),
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
                "instructions": self._manual_secret_instructions(spec),
                "direct_secret_write_supported": False,
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
            status=str(payload["provider_status"]),
            last_verified_at=utc_now_iso(),
            model_list=list(payload.get("model_list", [])),
            failure_reason=str(payload.get("failure_reason", "")),
        )
        verified = self._provider_payload(provider_key)
        verified["connection_id"] = connection.connection_id
        verified["verified_at"] = connection.last_verified_at
        verified["message"] = self._provider_status_message(verified)
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
        if payload["provider_status"] != "connected":
            return {
                "provider_id": payload["provider_id"],
                "provider_type": payload["provider_type"],
                "auth_method": payload["auth_method"],
                "status": payload["provider_status"],
                "model_list": [],
                "setup_url": payload["setup_url"],
                "setup_instructions": payload["setup_instructions"],
            }
        return {
            "provider_id": payload["provider_id"],
            "provider_type": payload["provider_type"],
            "auth_method": payload["auth_method"],
            "status": payload["provider_status"],
            "model_list": list(payload.get("model_list", [])),
        }

    def provider_call_test(self, *, provider_id: str, prompt: str) -> dict[str, Any]:
        from mystic.lab.provider_router import ProviderRouter

        provider_key = normalize_provider_id(provider_id)
        payload = self._provider_payload(provider_key) if provider_key != "mock" else {
            "provider_id": "mock",
            "provider_type": "future/custom",
            "auth_method": "none/mock",
            "connect_url": "",
            "setup_url": "",
            "setup_instructions": "Mock provider is test-only and must not be used for production routing.",
        }
        result = ProviderRouter(storage=self.storage, runtime_mode=self.runtime_mode).invoke(
            provider_id=provider_key,
            tool_name="provider_call_test",
            prompt=str(prompt).strip() or "ping",
            agent_role="ProviderTest",
            metadata={"test_only": provider_key == "mock"},
        )
        return {
            "provider_id": payload["provider_id"],
            "provider_type": payload["provider_type"],
            "auth_method": payload["auth_method"],
            "status": result["status"],
            "model": result["model"],
            "output": result["output_text"],
            "output_text": result["output_text"],
            "latency_ms": result["latency_ms"],
            "usage": result["raw_usage_safe"],
            "error_type": result["error_type"],
            "message": result["error_message_safe"],
            "error_message_safe": result["error_message_safe"],
            "call_id": result["call_id"],
            "storage_ref": result["storage_ref"],
            "test_only": provider_key == "mock",
            "connect_url": payload.get("connect_url", ""),
            "setup_url": payload.get("setup_url", ""),
            "setup_instructions": payload.get("setup_instructions", ""),
        }

    def _provider_payload(self, provider_id: str) -> dict[str, Any]:
        spec = provider_catalog(provider_id)
        connection = self._load_connection_safe(spec["provider_id"])
        secret_state = self._secret_state(spec)
        oauth_metadata = self._oauth_metadata(spec)
        provider_status = self._resolve_status(spec, connection, secret_state, oauth_metadata)
        model_list = self._model_list(spec, connection)
        auth_method = connection.auth_method if connection is not None else spec["default_auth_method"]
        route_urls = self._route_urls(spec["provider_id"])
        metadata = dict(connection.metadata if connection is not None else {})
        metadata.setdefault("external_setup_url", spec.get("external_setup_url", ""))
        metadata.setdefault("oauth_client_id_configured", oauth_metadata["client_id_configured"])
        metadata.setdefault("oauth_client_secret_configured", oauth_metadata["client_secret_configured"])
        metadata.setdefault("oauth_missing_config_names", oauth_metadata["missing_config_names"])
        metadata.setdefault("oauth_token_storage_supported", oauth_metadata["token_storage_supported"])
        return {
            "provider_id": spec["provider_id"],
            "provider_type": spec["provider_type"],
            "auth_method": auth_method,
            "auth_mode": "oauth" if oauth_metadata["configured"] else ("api_key" if spec.get("supports_api_key", False) else auth_method),
            "status": provider_status,
            "provider_status": provider_status,
            "scopes": list(connection.scopes if connection is not None and connection.scopes else spec["scopes"]),
            "model_list": model_list,
            "setup_url": route_urls["setup_url"],
            "connect_url": route_urls["connect_url"],
            "status_url": route_urls["status_url"],
            "external_setup_url": spec.get("external_setup_url", ""),
            "setup_instructions": (
                connection.setup_instructions
                if connection is not None and connection.setup_instructions
                else spec["setup_instructions"]
            ),
            "last_verified_at": connection.last_verified_at if connection is not None else "",
            "failure_reason": (
                connection.failure_reason
                if connection is not None and connection.failure_reason
                else self._default_failure_reason(spec, provider_status, oauth_metadata, secret_state)
            ),
            "metadata": metadata,
            "configured": provider_status == "connected",
            "configured_secret_names": secret_state["configured_secret_names"],
            "missing_secret_names": secret_state["missing_secret_names"],
            "required_secret_names": secret_state["required_secret_names"],
            "missing_required_secret_names": secret_state["missing_required_secret_names"],
            "runtime_mode": self.runtime_mode,
            "oauth_supported": oauth_metadata["available"],
            "oauth_configured": oauth_metadata["configured"],
            "oauth_authorization_endpoint": oauth_metadata["authorization_endpoint"],
        }

    def _resolve_status(
        self,
        spec: dict[str, Any],
        connection: ProviderConnection | None,
        secret_state: dict[str, list[str]],
        oauth_metadata: dict[str, Any],
    ) -> str:
        if connection is not None and connection.status in {
            "provider_required",
            "disconnected",
            "auth_failed",
            "rate_limited",
            "provider_unavailable",
        }:
            return connection.status
        if spec.get("test_only"):
            return "connected"
        auth_method = connection.auth_method if connection is not None else spec["default_auth_method"]
        if auth_method == "oauth":
            if connection is not None and connection.status == "connected":
                return "connected"
            if spec.get("oauth_missing_status") == "provider_required" and (
                secret_state["missing_required_secret_names"] or oauth_metadata["missing_config_names"]
            ):
                return "provider_required"
            if oauth_metadata["configured"]:
                return "oauth_required"
            if spec.get("supports_api_key", False):
                return "api_key_required"
            return spec.get("oauth_missing_status", "not_configured")
        if auth_method == "bearer_token":
            if connection is not None and connection.status == "connected":
                return "connected"
            if oauth_metadata["configured"]:
                return "oauth_required"
            if spec.get("supports_api_key", False):
                return "api_key_required"
            return spec.get("oauth_missing_status", "not_configured")
        if secret_state["required_secret_names"] and not secret_state["missing_required_secret_names"]:
            return "connected"
        if connection is None and not secret_state["configured_secret_names"]:
            return "not_configured"
        return "api_key_required"

    def _secret_state(self, spec: dict[str, Any]) -> dict[str, list[str]]:
        configured = [name for name in spec["secret_names"] if _trimmed(os.environ.get(name))]
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
        models = [_trimmed(os.environ.get(name)) for name in spec["model_env_names"] if _trimmed(os.environ.get(name))]
        if models:
            return models
        return list(spec["default_models"])

    def _manual_secret_instructions(self, spec: dict[str, Any]) -> list[str]:
        instructions = [
            "Do not store provider secrets in Supabase.",
            "Store production provider secrets only in Cloudflare Worker secret storage or approved server-side secret storage.",
            "Do not paste API keys into tool output or chat transcripts.",
        ]
        if spec["required_secret_names"]:
            instructions.extend(
                [f"wrangler secret put {name} --name mystic" for name in spec["required_secret_names"]]
            )
        for name in spec["optional_secret_names"]:
            instructions.append(f"Set optional provider variable or secret {name} if needed.")
        return instructions

    def _oauth_metadata(self, spec: dict[str, Any]) -> dict[str, Any]:
        prefix = spec.get("oauth_env_prefix", "")
        if not prefix:
            return {
                "available": False,
                "configured": False,
                "enabled": False,
                "authorization_endpoint": "",
                "token_endpoint": "",
                "client_id": "",
                "redirect_uri": "",
                "scopes": [],
                "client_id_configured": False,
                "client_secret_configured": False,
                "required_config_names": [],
                "missing_config_names": [],
                "token_storage_supported": False,
            }
        available = bool(spec.get("supports_oauth"))
        enabled = _truthy_env(os.environ.get(f"{prefix}_OAUTH_ENABLED"))
        authorization_endpoint = _trimmed(
            os.environ.get(f"{prefix}_AUTHORIZATION_ENDPOINT"),
            spec.get("oauth_default_authorization_endpoint", ""),
        )
        token_endpoint = _trimmed(
            os.environ.get(f"{prefix}_TOKEN_ENDPOINT"),
            spec.get("oauth_default_token_endpoint", ""),
        )
        client_id = _trimmed(os.environ.get(f"{prefix}_CLIENT_ID"))
        client_secret = _trimmed(os.environ.get(f"{prefix}_CLIENT_SECRET"))
        redirect_uri = _trimmed(
            os.environ.get(f"{prefix}_REDIRECT_URI"),
            f"{_route_base_url(self.runtime_mode)}/providers/oauth/callback?provider_id={spec['provider_id']}",
        )
        scopes_env = _trimmed(os.environ.get(f"{prefix}_SCOPES"))
        scopes = [item for item in scopes_env.split() if item] if scopes_env else list(spec.get("oauth_default_scopes", []))
        required_config_names = list(spec.get("oauth_required_config_env_names", []))
        missing_config_names = [
            name for name in required_config_names if not _trimmed(os.environ.get(name))
        ]
        client_secret_configured = bool(client_secret) or not spec.get("oauth_require_client_secret", False)
        configured = bool(
            available
            and enabled
            and authorization_endpoint
            and token_endpoint
            and client_id
            and redirect_uri
            and client_secret_configured
            and not missing_config_names
        )
        return {
            "available": available,
            "configured": configured,
            "enabled": enabled,
            "authorization_endpoint": authorization_endpoint,
            "token_endpoint": token_endpoint,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scopes": scopes,
            "client_id_configured": bool(client_id),
            "client_secret_configured": client_secret_configured,
            "required_config_names": required_config_names,
            "missing_config_names": missing_config_names,
            "token_storage_supported": bool(spec.get("oauth_token_storage_supported", False)),
        }

    def _build_authorization_url(
        self,
        *,
        spec: dict[str, Any],
        oauth_metadata: dict[str, Any],
        flow_id: str,
        state_value: str,
        code_challenge: str,
    ) -> str:
        params = {
            "response_type": "code",
            "client_id": oauth_metadata["client_id"],
            "redirect_uri": oauth_metadata["redirect_uri"],
            "state": state_value,
            "flow_id": flow_id,
        }
        if oauth_metadata["scopes"]:
            params["scope"] = " ".join(oauth_metadata["scopes"])
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
        if spec["provider_id"] == "google_vertex_ai":
            params.setdefault("access_type", "offline")
            params.setdefault("prompt", "consent")
        return f"{oauth_metadata['authorization_endpoint']}?{urlencode(params)}"

    def _route_urls(self, provider_id: str) -> dict[str, str]:
        base_url = _route_base_url(self.runtime_mode)
        return {
            "providers_url": f"{base_url}/providers",
            "connect_url": f"{base_url}/providers/{provider_id}/connect",
            "setup_url": f"{base_url}/providers/{provider_id}/setup",
            "status_url": f"{base_url}/providers/{provider_id}/status",
            "callback_url": f"{base_url}/providers/oauth/callback?provider_id={provider_id}",
        }

    def _default_failure_reason(
        self,
        spec: dict[str, Any],
        provider_status: str,
        oauth_metadata: dict[str, Any],
        secret_state: dict[str, list[str]],
    ) -> str:
        if provider_status == "connected":
            return ""
        if provider_status == "provider_required":
            if spec.get("provider_id") == "google_vertex_ai" and oauth_metadata["configured"]:
                return "oauth_storage_required"
            return "oauth_metadata_missing"
        if provider_status == "oauth_required" and not oauth_metadata["configured"]:
            return "oauth_metadata_missing"
        if provider_status == "api_key_required" and secret_state["missing_required_secret_names"]:
            return "missing_required_secrets"
        if provider_status == "not_configured" and spec.get("supports_api_key", False):
            return "provider_not_configured"
        return ""

    def _provider_status_message(self, payload: dict[str, Any]) -> str:
        status = str(payload.get("provider_status") or payload.get("status") or "").strip()
        failure_reason = str(payload.get("failure_reason", "")).strip()
        if status == "connected":
            return "Provider is connected."
        if status == "oauth_required":
            return "Provider OAuth connection is required. Start the secure OAuth flow and retry."
        if status == "api_key_required":
            return "Provider credentials are not configured. Complete the secure setup flow and retry."
        if status == "provider_required" and failure_reason == "oauth_storage_required":
            return (
                "OAuth callback metadata can be recorded, but encrypted server-side token storage is required "
                "before Google Vertex AI model calls can be enabled."
            )
        if status == "provider_required":
            return "Provider configuration is incomplete. Add the required OAuth metadata and retry."
        if status == "auth_failed":
            return "Provider authentication failed. Reconnect the provider and retry."
        if status == "rate_limited":
            return "Provider rate limited the last request. Retry later."
        if status == "provider_unavailable":
            return "Provider is temporarily unavailable. Retry later."
        if status == "disconnected":
            return "Provider is disconnected until an explicit reconnect."
        return "Provider configuration was checked without exposing secrets."

    def _state_hash(self, value: str) -> str:
        return sha256(value.encode("utf-8")).hexdigest()

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
        route_urls = self._route_urls(spec["provider_id"])
        connection = ProviderConnection(
            connection_id=existing.connection_id if existing is not None else f"provider-{spec['provider_id']}",
            provider_id=spec["provider_id"],
            provider_type=spec["provider_type"],
            auth_method=auth_method,
            status=status,
            scopes=list(existing.scopes if existing is not None and existing.scopes else spec["scopes"]),
            model_list=list(model_list if model_list is not None else (existing.model_list if existing is not None else self._model_list(spec, None))),
            setup_url=route_urls["setup_url"],
            setup_instructions=spec["setup_instructions"],
            last_verified_at=last_verified_at or (existing.last_verified_at if existing is not None else ""),
            failure_reason=failure_reason or (existing.failure_reason if existing is not None else ""),
            metadata={
                **(existing.metadata if existing is not None else {}),
                "connect_url": route_urls["connect_url"],
                "status_url": route_urls["status_url"],
                "external_setup_url": spec.get("external_setup_url", ""),
                **(metadata or {}),
            },
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
