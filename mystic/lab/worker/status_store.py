from __future__ import annotations

"""Redacted, local status records for trusted scientific workers.

This store is deliberately *not* job state: the durable scientific-job runtime
remains authoritative for execution, leases, results, and campaign attachment.
It exists solely to let the Control Center inspect a worker's safe operational
health without learning a credential, lease token, private path, or process
environment.  A stopped worker leaves its final status record for inspection.
"""

import json
import os
from pathlib import Path
import re
import tempfile
from datetime import UTC, datetime
from typing import Any


_WORKER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,159}$")
_WORKER_STATUS_KEYS = frozenset(
    {
        "worker_id",
        "worker_version",
        "runtime_version",
        "process_start_time",
        "status",
        "uptime_seconds",
        "capacity",
        "active_jobs",
        "supported_engines",
        "supported_engine_versions",
        "resource_classes",
        "last_poll_at",
        "last_successful_backend_contact",
        "completed_count",
        "failed_count",
        "cancelled_count",
        "stale_lease_count",
        "reconciliation_count",
        "safe_last_error",
    }
)
_WORKER_STATES = frozenset({"starting", "ready", "busy", "degraded", "draining", "unhealthy", "stopped"})


class WorkerStatusNotFoundError(KeyError):
    """Raised when no safe status record exists for the requested worker."""


def _require_bounded_string(payload: dict[str, Any], key: str, *, maximum: int = 512) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(f"Worker status field {key!r} must be a bounded string")
    return value


def validate_worker_status_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Reject unknown, malformed, or potentially sensitive status content."""
    if not isinstance(payload, dict) or set(payload) != _WORKER_STATUS_KEYS:
        raise ValueError("Worker status payload does not match the fixed safe schema")
    worker_id = _require_bounded_string(payload, "worker_id", maximum=160)
    if not _WORKER_ID.fullmatch(worker_id):
        raise ValueError("Worker status worker_id is invalid")
    status = _require_bounded_string(payload, "status", maximum=32)
    if status not in _WORKER_STATES:
        raise ValueError("Worker status state is invalid")
    for key in (
        "worker_version",
        "runtime_version",
        "process_start_time",
        "last_poll_at",
        "last_successful_backend_contact",
        "safe_last_error",
    ):
        _require_bounded_string(payload, key)
    for key in (
        "uptime_seconds",
        "capacity",
        "active_jobs",
        "completed_count",
        "failed_count",
        "cancelled_count",
        "stale_lease_count",
        "reconciliation_count",
    ):
        value = payload.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"Worker status field {key!r} must be a non-negative integer")
    if payload["active_jobs"] > payload["capacity"]:
        raise ValueError("Worker status active_jobs cannot exceed capacity")
    for key in ("supported_engines", "supported_engine_versions", "resource_classes"):
        values = payload.get(key)
        if not isinstance(values, list) or len(values) > 128 or any(not isinstance(value, str) or not value or len(value) > 160 for value in values):
            raise ValueError(f"Worker status field {key!r} must be a bounded string list")
    # Return an encoding-safe copy rather than accepting a subclass or caller
    # reference as a durable record.
    return json.loads(json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False))


class WorkerStatusStorage:
    """Atomic local storage for fixed-schema, redacted worker health only."""

    def __init__(self, root_path: str | Path) -> None:
        self.base_dir = Path(root_path) / "mystic_data" / "scientific_workers"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate_worker_id(worker_id: str) -> str:
        if not isinstance(worker_id, str) or not _WORKER_ID.fullmatch(worker_id):
            raise ValueError("worker_id must be a bounded opaque worker identifier")
        return worker_id

    def _path(self, worker_id: str) -> Path:
        return self.base_dir / f"{self._validate_worker_id(worker_id)}.json"

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        safe = validate_worker_status_payload(payload)
        target = self._path(str(safe["worker_id"]))
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{safe['worker_id']}-", suffix=".tmp", dir=self.base_dir)
        try:
            encoded = json.dumps(safe, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary_name, 0o600)
            os.replace(temporary_name, target)
            return safe
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    def get(self, worker_id: str) -> dict[str, Any]:
        target = self._path(worker_id)
        try:
            with target.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except FileNotFoundError as exc:
            raise WorkerStatusNotFoundError("Scientific worker status was not found") from exc
        return validate_worker_status_payload(payload)

    def list(self, *, limit: int = 50) -> list[dict[str, Any]]:
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        records: list[dict[str, Any]] = []
        for path in sorted(self.base_dir.glob("*.json")):
            try:
                records.append(self.get(path.stem))
            except (ValueError, WorkerStatusNotFoundError, json.JSONDecodeError):
                # A corrupt status file must not corrupt or hide durable job
                # state. It is ignored by the read-only operational view.
                continue
        records.sort(key=lambda item: (str(item["last_successful_backend_contact"]), str(item["worker_id"])), reverse=True)
        return records[:limit]


class WorkerControlStorage:
    """Local, authenticated control intent for a running worker process.

    This is intentionally separate from status and durable job state. A drain
    request prevents new acquisition while the running worker completes its
    currently leased work; the job runtime still owns cancellation, leases,
    retries, and recovery. No MCP or browser handler can create this intent.
    """

    def __init__(self, root_path: str | Path) -> None:
        self.base_dir = Path(root_path) / "mystic_data" / "scientific_worker_controls"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, worker_id: str) -> Path:
        return self.base_dir / f"{WorkerStatusStorage._validate_worker_id(worker_id)}.drain.json"

    def request_drain(self, worker_id: str) -> dict[str, str]:
        worker_id = WorkerStatusStorage._validate_worker_id(worker_id)
        payload = {"worker_id": worker_id, "action": "drain", "requested_at": datetime.now(UTC).isoformat()}
        target = self._path(worker_id)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{worker_id}-", suffix=".tmp", dir=self.base_dir)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary_name, 0o600)
            os.replace(temporary_name, target)
            return payload
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    def drain_requested(self, worker_id: str) -> bool:
        target = self._path(worker_id)
        try:
            with target.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except FileNotFoundError:
            return False
        return (
            isinstance(payload, dict)
            and payload.get("worker_id") == worker_id
            and payload.get("action") == "drain"
            and isinstance(payload.get("requested_at"), str)
        )
