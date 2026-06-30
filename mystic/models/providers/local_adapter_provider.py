from __future__ import annotations

from pathlib import Path
import time

from mystic.models.providers.base import (
    ModelCallRequest,
    ProviderInvocation,
    ProviderStatus,
    RoutedProvider,
    ready_status,
    unavailable_status,
)


class LocalAdapterProvider(RoutedProvider):
    def status(self, model_id: str, config: dict[str, object]) -> ProviderStatus:
        adapter_path = Path(str(config.get("adapter_path", "")))
        if not adapter_path.exists():
            return unavailable_status(
                "Local adapter path does not exist.",
                model_id=model_id,
                adapter_path=str(adapter_path),
            )
        return ready_status(
            "Local adapter metadata is present.",
            model_id=model_id,
            adapter_path=str(adapter_path),
            base_model=str(config.get("base_model", "")),
        )

    def call(self, model_id: str, config: dict[str, object], request_data: ModelCallRequest) -> ProviderInvocation:
        started = time.perf_counter()
        adapter_path = Path(str(config.get("adapter_path", "")))
        if not adapter_path.exists():
            return ProviderInvocation(
                content="",
                status="ERROR",
                latency_sec=time.perf_counter() - started,
                metadata={"provider": "local_adapter", "reason": "missing_adapter"},
            )
        content = (
            f"[local_adapter:{config.get('base_model', 'unknown')}::{adapter_path.name}] "
            f"role={request_data.role} task={request_data.task}\n\n"
            f"Problem:\n{request_data.problem}"
        )
        if request_data.context:
            content += f"\n\nContext:\n{request_data.context}"
        return ProviderInvocation(
            content=content,
            status="OK",
            latency_sec=time.perf_counter() - started,
            metadata={"provider": "local_adapter", "model_id": model_id},
        )
