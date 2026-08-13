from __future__ import annotations

from collections import Counter
from threading import Lock
from time import monotonic


class WorkerMetrics:
    """In-process operational counters; job IDs are never metric dimensions."""

    _COUNTERS = (
        "jobs_acquired_total",
        "jobs_started_total",
        "jobs_completed_total",
        "jobs_failed_total",
        "jobs_cancelled_total",
        "jobs_retried_total",
        "jobs_dead_lettered_total",
        "leases_lost_total",
        "lease_renewal_failures_total",
        "reconciliation_actions_total",
    )

    def __init__(self) -> None:
        self._lock = Lock()
        self._counts: Counter[str] = Counter({name: 0 for name in self._COUNTERS})
        self._durations: dict[str, list[float]] = {
            "acquisition_latency_ms": [],
            "execution_duration_ms": [],
            "attachment_latency_ms": [],
            "queue_wait_duration_ms": [],
        }

    def increment(self, name: str, amount: int = 1) -> None:
        if name not in self._COUNTERS:
            raise ValueError("Unknown worker metric")
        with self._lock:
            self._counts[name] += amount

    def record_duration(self, name: str, started_at: float) -> None:
        if name not in self._durations:
            raise ValueError("Unknown worker duration metric")
        elapsed = max(0.0, (monotonic() - started_at) * 1000)
        with self._lock:
            samples = self._durations[name]
            samples.append(elapsed)
            if len(samples) > 1_000:
                del samples[: len(samples) - 1_000]

    def snapshot(self, *, active_jobs: int, worker_capacity: int) -> dict[str, object]:
        with self._lock:
            payload: dict[str, object] = dict(self._counts)
            for name, values in self._durations.items():
                payload[name] = round(sum(values) / len(values), 3) if values else 0.0
        payload["active_jobs"] = active_jobs
        payload["worker_capacity"] = worker_capacity
        return payload
