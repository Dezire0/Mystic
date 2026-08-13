from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class WorkerState(StrEnum):
    STARTING = "starting"
    READY = "ready"
    BUSY = "busy"
    DEGRADED = "degraded"
    DRAINING = "draining"
    UNHEALTHY = "unhealthy"
    STOPPED = "stopped"


@dataclass(slots=True)
class WorkerHealth:
    worker_id: str
    worker_version: str
    runtime_version: str
    process_start_time: str
    status: WorkerState = WorkerState.STARTING
    maximum_concurrency: int = 1
    active_jobs: int = 0
    supported_engines: tuple[str, ...] = ()
    supported_engine_versions: tuple[str, ...] = ()
    resource_classes: tuple[str, ...] = ()
    last_poll_at: str = ""
    last_successful_backend_contact: str = ""
    completed_count: int = 0
    failed_count: int = 0
    cancelled_count: int = 0
    stale_lease_count: int = 0
    reconciliation_count: int = 0
    safe_last_error: str = ""

    @staticmethod
    def now() -> str:
        return datetime.now(UTC).isoformat()

    def safe_payload(self) -> dict[str, object]:
        return {
            "worker_id": self.worker_id,
            "worker_version": self.worker_version,
            "runtime_version": self.runtime_version,
            "process_start_time": self.process_start_time,
            "status": self.status.value,
            "uptime_seconds": max(0, int((datetime.now(UTC) - datetime.fromisoformat(self.process_start_time)).total_seconds())),
            "capacity": self.maximum_concurrency,
            "active_jobs": self.active_jobs,
            "supported_engines": list(self.supported_engines),
            "supported_engine_versions": list(self.supported_engine_versions),
            "resource_classes": list(self.resource_classes),
            "last_poll_at": self.last_poll_at,
            "last_successful_backend_contact": self.last_successful_backend_contact,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "cancelled_count": self.cancelled_count,
            "stale_lease_count": self.stale_lease_count,
            "reconciliation_count": self.reconciliation_count,
            "safe_last_error": self.safe_last_error,
        }


def engine_capabilities(registry: object) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Build safe engine capability metadata without exposing modules or paths."""
    manifests = list(getattr(registry, "list")())
    return (
        tuple(sorted(manifest.engine_id for manifest in manifests)),
        tuple(sorted(f"{manifest.engine_id}@{manifest.version}" for manifest in manifests)),
    )
