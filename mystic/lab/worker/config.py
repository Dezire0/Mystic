from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import os
from pathlib import Path
import uuid

from .auth import WorkerCredentialVerifier


def _positive_int(name: str, value: str, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def _safe_worker_id(value: str) -> str:
    if not value or len(value) > 160 or not value.replace("_", "").replace("-", "").isalnum():
        raise ValueError("MYSTIC_SCIENTIFIC_WORKER_ID must be a bounded opaque identifier")
    return value


@dataclass(frozen=True, slots=True)
class ScientificWorkerConfig:
    """Safe configuration for a single trusted worker process."""

    worker_id: str
    worker_version: str = "scientific-job-worker-2C.2B"
    runtime_version: str = "scientific-job-runtime-2C.2A"
    root_path: Path = field(default_factory=Path.cwd)
    maximum_concurrency: int = 1
    lease_seconds: int = 60
    heartbeat_interval_seconds: int = 20
    poll_batch_size: int = 10
    idle_poll_seconds: float = 1.0
    max_idle_poll_seconds: float = 30.0
    reconciliation_interval_seconds: int = 30
    graceful_shutdown_seconds: int = 30
    resource_classes: tuple[str, ...] = ("trusted_in_process",)
    process_start_time: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __post_init__(self) -> None:
        _safe_worker_id(self.worker_id)
        if not 1 <= self.maximum_concurrency <= 32:
            raise ValueError("maximum_concurrency must be between 1 and 32")
        if not 10 <= self.lease_seconds <= 300:
            raise ValueError("lease_seconds must be between 10 and 300")
        if not 1 <= self.heartbeat_interval_seconds < self.lease_seconds:
            raise ValueError("heartbeat interval must be below lease expiry")
        if self.heartbeat_interval_seconds > self.lease_seconds // 2:
            raise ValueError("heartbeat interval must be no greater than half the lease TTL")
        if not 1 <= self.poll_batch_size <= 100:
            raise ValueError("poll_batch_size must be between 1 and 100")
        if not 0 < self.idle_poll_seconds <= self.max_idle_poll_seconds <= 30:
            raise ValueError("polling interval bounds are invalid")
        if not 1 <= self.reconciliation_interval_seconds <= 3_600:
            raise ValueError("reconciliation interval must be between 1 and 3600")
        if not 1 <= self.graceful_shutdown_seconds <= 300:
            raise ValueError("graceful shutdown must be between 1 and 300 seconds")

    @classmethod
    def from_environment(cls, *, root_path: str | Path | None = None) -> "ScientificWorkerConfig":
        process_nonce = uuid.uuid4().hex[:12]
        worker_id = os.environ.get("MYSTIC_SCIENTIFIC_WORKER_ID", f"scientific_worker_{process_nonce}")
        lease_seconds = _positive_int("MYSTIC_SCIENTIFIC_WORKER_LEASE_SECONDS", os.environ.get("MYSTIC_SCIENTIFIC_WORKER_LEASE_SECONDS", "60"), minimum=10, maximum=300)
        heartbeat_default = str(max(1, lease_seconds // 3))
        return cls(
            worker_id=worker_id,
            root_path=Path(root_path or os.environ.get("MYSTIC_SCIENTIFIC_WORKER_ROOT", Path.cwd())),
            maximum_concurrency=_positive_int("MYSTIC_SCIENTIFIC_WORKER_CONCURRENCY", os.environ.get("MYSTIC_SCIENTIFIC_WORKER_CONCURRENCY", "1"), minimum=1, maximum=32),
            lease_seconds=lease_seconds,
            heartbeat_interval_seconds=_positive_int("MYSTIC_SCIENTIFIC_WORKER_HEARTBEAT_SECONDS", os.environ.get("MYSTIC_SCIENTIFIC_WORKER_HEARTBEAT_SECONDS", heartbeat_default), minimum=1, maximum=120),
            poll_batch_size=_positive_int("MYSTIC_SCIENTIFIC_WORKER_POLL_BATCH_SIZE", os.environ.get("MYSTIC_SCIENTIFIC_WORKER_POLL_BATCH_SIZE", "10"), minimum=1, maximum=100),
            reconciliation_interval_seconds=_positive_int("MYSTIC_SCIENTIFIC_WORKER_RECONCILIATION_SECONDS", os.environ.get("MYSTIC_SCIENTIFIC_WORKER_RECONCILIATION_SECONDS", "30"), minimum=1, maximum=3600),
            graceful_shutdown_seconds=_positive_int("MYSTIC_SCIENTIFIC_WORKER_GRACEFUL_SHUTDOWN_SECONDS", os.environ.get("MYSTIC_SCIENTIFIC_WORKER_GRACEFUL_SHUTDOWN_SECONDS", "30"), minimum=1, maximum=300),
        )

    @staticmethod
    def credential_verifier_from_environment() -> WorkerCredentialVerifier:
        raw = os.environ.get("MYSTIC_SCIENTIFIC_WORKER_CREDENTIAL_HASHES", "")
        if not raw:
            raise ValueError("MYSTIC_SCIENTIFIC_WORKER_CREDENTIAL_HASHES is required to run a trusted worker")
        return WorkerCredentialVerifier.from_environment_value(raw)

    def safe_metadata(self) -> dict[str, object]:
        return {
            "worker_id": self.worker_id,
            "worker_version": self.worker_version,
            "runtime_version": self.runtime_version,
            "process_start_time": self.process_start_time,
            "maximum_concurrency": self.maximum_concurrency,
            "resource_classes": list(self.resource_classes),
            "lease_seconds": self.lease_seconds,
            "heartbeat_interval_seconds": self.heartbeat_interval_seconds,
        }
