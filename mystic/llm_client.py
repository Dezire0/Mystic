"""LLM client implementations for Mystic backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import json
import os
from pathlib import Path
import time
from typing import Any
from urllib.parse import urlparse

try:
    import requests
except ModuleNotFoundError:  # pragma: no cover - handled at runtime
    requests = None


class LLMClientError(RuntimeError):
    """Raised when an LLM backend call fails after retries."""


class LLMClient(ABC):
    """Minimal text-only interface for Mystic backends."""

    @abstractmethod
    def generate_text(self, *, model: str, system_prompt: str, user_prompt: str) -> str:
        """Return plain text from a model backend."""


@dataclass(slots=True)
class ClientDefaults:
    timeout: float = 60.0
    retries: int = 2


def _require_requests() -> None:
    if requests is None:  # pragma: no cover - depends on runtime environment
        raise RuntimeError(
            "The 'requests' package is required for Mystic v1 backend calls. "
            "Use the existing .venv-training environment or install project dependencies."
        )


class BaseHTTPClient(LLMClient):
    def __init__(self, *, timeout: float = 60.0, retries: int = 2) -> None:
        self.timeout = timeout
        self.retries = retries

    @property
    @abstractmethod
    def endpoint_url(self) -> str:
        """Return the concrete POST endpoint."""

    @abstractmethod
    def _build_payload(self, *, model: str, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """Build the backend-specific request payload."""

    @abstractmethod
    def _build_headers(self) -> dict[str, str]:
        """Build the backend-specific request headers."""

    @abstractmethod
    def _extract_text(self, payload: dict[str, Any], raw_text: str) -> str:
        """Extract plain text from the backend response."""

    def _retry_after_seconds(self, exc: Exception) -> float | None:
        response = getattr(exc, "response", None)
        if response is None:
            return None
        value = response.headers.get("Retry-After")
        if not value:
            return None
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return None

    def _status_code(self, exc: Exception) -> int | None:
        response = getattr(exc, "response", None)
        if response is None:
            return None
        try:
            return int(response.status_code)
        except (TypeError, ValueError):
            return None

    def _should_retry(self, exc: Exception) -> bool:
        status_code = self._status_code(exc)
        if status_code is None:
            return True
        return status_code in {408, 409, 429, 500, 502, 503, 504}

    def _retry_delay_seconds(self, exc: Exception, attempt: int) -> float:
        retry_after = self._retry_after_seconds(exc)
        if retry_after is not None:
            return min(retry_after, 30.0)
        status_code = self._status_code(exc)
        if status_code == 429:
            return min(3.0 * (2 ** attempt), 20.0)
        return min(2 ** attempt, 6.0)

    def generate_text(self, *, model: str, system_prompt: str, user_prompt: str) -> str:
        _require_requests()
        assert requests is not None

        payload = self._build_payload(model=model, system_prompt=system_prompt, user_prompt=user_prompt)
        headers = self._build_headers()
        last_error = "unknown backend error"

        for attempt in range(self.retries + 1):
            try:
                response = requests.post(
                    self.endpoint_url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                try:
                    data = response.json()
                except json.JSONDecodeError:
                    return response.text.strip()
                text = self._extract_text(data, response.text)
                return text.strip()
            except requests.RequestException as exc:
                last_error = str(exc)
                if not self._should_retry(exc):
                    break
            except (KeyError, TypeError, ValueError) as exc:
                last_error = f"Malformed backend response: {exc}"

            if attempt < self.retries:
                time.sleep(self._retry_delay_seconds(exc, attempt))

        raise LLMClientError(f"{self.__class__.__name__} request failed: {last_error}")


class OllamaClient(BaseHTTPClient):
    def __init__(self, *, base_url: str = "http://localhost:11434", timeout: float = 60.0, retries: int = 2) -> None:
        super().__init__(timeout=timeout, retries=retries)
        self.base_url = base_url.rstrip("/")

    @property
    def endpoint_url(self) -> str:
        return f"{self.base_url}/api/generate"

    def _build_payload(self, *, model: str, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        prompt = f"{system_prompt.strip()}\n\n{user_prompt.strip()}"
        return {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }

    def _build_headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json"}

    def _extract_text(self, payload: dict[str, Any], raw_text: str) -> str:
        if "response" in payload:
            return str(payload["response"])
        return raw_text


class OpenAICompatibleClient(BaseHTTPClient):
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 60.0,
        retries: int = 2,
    ) -> None:
        super().__init__(timeout=timeout, retries=retries)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or ""

    @property
    def endpoint_url(self) -> str:
        parsed = urlparse(self.base_url)
        path = parsed.path.rstrip("/")
        if path.endswith("/chat/completions"):
            return self.base_url
        if path.endswith("/v1"):
            return f"{self.base_url}/chat/completions"
        if not path:
            return f"{self.base_url}/v1/chat/completions"
        return f"{self.base_url}/chat/completions"

    def _build_payload(self, *, model: str, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        return {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
        }

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _extract_text(self, payload: dict[str, Any], raw_text: str) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return raw_text

        choice = choices[0]
        if not isinstance(choice, dict):
            return raw_text

        message = choice.get("message")
        if isinstance(message, dict):
            content = message.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "".join(
                    str(part.get("text", ""))
                    for part in content
                    if isinstance(part, dict)
                )

        text = choice.get("text")
        if text is not None:
            return str(text)
        return raw_text


class AdapterClient(LLMClient):
    def __init__(
        self,
        *,
        base_model: str,
        adapter_path: str | Path | None = None,
        max_new_tokens: int = 256,
    ) -> None:
        self.base_model = base_model
        self.adapter_path = Path(adapter_path).expanduser() if adapter_path else None
        self.max_new_tokens = max_new_tokens
        self._warned = False
        self._load_runtime()

    def _load_runtime(self) -> None:
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency
            raise RuntimeError(f"Adapter inference dependencies are missing: {exc}") from exc

        self.torch = torch
        self.device = self._choose_device(torch)
        if self.device != "cuda" and not self._warned:
            print(
                f"[warning] AdapterClient running on {self.device}. "
                "Inference is supported, but Linux NVIDIA GPU is recommended for better throughput."
            )
            self._warned = True

        if self.adapter_path is not None and not self.adapter_path.exists():
            raise ValueError(f"Adapter path not found: {self.adapter_path}")
        self._validate_adapter_metadata()

        tokenizer = AutoTokenizer.from_pretrained(self.base_model)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token or tokenizer.unk_token

        model_kwargs: dict[str, Any] = {}
        if self.device == "cuda":
            model_kwargs["torch_dtype"] = torch.float16
        elif self.device == "mps":
            model_kwargs["torch_dtype"] = torch.float16
        base_model = AutoModelForCausalLM.from_pretrained(self.base_model, **model_kwargs)

        if self.adapter_path is not None:
            try:
                from peft import PeftModel
            except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency
                raise RuntimeError(f"PEFT is required for adapter inference: {exc}") from exc
            try:
                model = PeftModel.from_pretrained(base_model, str(self.adapter_path))
            except Exception as exc:
                raise ValueError(
                    "Failed to load the PEFT adapter. "
                    f"Adapter path: {self.adapter_path}. Base model: {self.base_model}. "
                    "This usually means the adapter was trained against a different base model or target module set. "
                    f"Original error: {exc}"
                ) from exc
        else:
            model = base_model

        if self.device == "cuda":
            model = model.to("cuda")
        elif self.device == "mps":
            model = model.to("mps")
        model.eval()
        self.tokenizer = tokenizer
        self.model = model

    def _validate_adapter_metadata(self) -> None:
        if self.adapter_path is None:
            return
        config_path = self.adapter_path / "adapter_config.json"
        if not config_path.exists():
            return
        try:
            adapter_config = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        expected_base = str(adapter_config.get("base_model_name_or_path", "")).strip()
        if expected_base and expected_base != self.base_model:
            raise ValueError(
                "Adapter/base-model mismatch detected. "
                f"Adapter expects {expected_base}, but AdapterClient was configured with {self.base_model}. "
                "Use the matching base model or retrain the adapter."
            )

    def _choose_device(self, torch_module: Any) -> str:
        if torch_module.cuda.is_available():
            return "cuda"
        if torch_module.backends.mps.is_available():
            return "mps"
        return "cpu"

    def generate_text(self, *, model: str, system_prompt: str, user_prompt: str) -> str:
        runtime_model = model or self.base_model
        if runtime_model != self.base_model:
            raise ValueError(
                f"AdapterClient loaded {self.base_model}, but generate_text requested {runtime_model}."
            )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if hasattr(self.tokenizer, "apply_chat_template"):
            prompt = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        else:
            prompt = f"SYSTEM:\n{system_prompt}\n\nUSER:\n{user_prompt}\n\nASSISTANT:\n"

        encoded = self.tokenizer(prompt, return_tensors="pt")
        if self.device == "cuda":
            encoded = {key: value.to("cuda") for key, value in encoded.items()}
        elif self.device == "mps":
            encoded = {key: value.to("mps") for key, value in encoded.items()}

        with self.torch.no_grad():
            output = self.model.generate(
                **encoded,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
            )
        new_tokens = output[0][encoded["input_ids"].shape[1] :]
        return self.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


def load_model_defaults(config_path: str | Path) -> dict[str, Any]:
    config_file = Path(config_path)
    if not config_file.exists():
        return {
            "backend": "ollama",
            "ollama_base_url": "http://localhost:11434",
            "generator_model": "qwen2.5:7b",
            "raven_model": "qwen2.5:7b",
        }
    return json.loads(config_file.read_text(encoding="utf-8"))


def build_client(
    backend: str,
    *,
    config_path: str | Path,
    base_model: str | None = None,
    adapter_path: str | Path | None = None,
) -> LLMClient:
    defaults = load_model_defaults(config_path)
    timeout = float(defaults.get("timeout", 60.0))
    retries = int(defaults.get("retries", 2))

    if backend == "ollama":
        base_url = str(defaults.get("ollama_base_url", "http://localhost:11434"))
        return OllamaClient(base_url=base_url, timeout=timeout, retries=retries)

    if backend == "openai-compatible":
        base_url = os.getenv("MYSTIC_API_BASE", "").strip()
        if not base_url:
            raise ValueError("MYSTIC_API_BASE is required for the openai-compatible backend.")
        api_key = os.getenv("MYSTIC_API_KEY", "").strip() or None
        return OpenAICompatibleClient(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            retries=retries,
        )

    if backend == "adapter":
        resolved_base_model = base_model or str(defaults.get("active_raven_base_model", defaults.get("raven_model", "")))
        if not resolved_base_model:
            raise ValueError("A base model is required for the adapter backend.")
        resolved_adapter_path = adapter_path or defaults.get("active_raven_adapter")
        return AdapterClient(
            base_model=resolved_base_model,
            adapter_path=resolved_adapter_path,
        )

    raise ValueError(f"Unsupported backend: {backend}")
