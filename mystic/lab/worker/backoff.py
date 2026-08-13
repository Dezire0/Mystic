from __future__ import annotations

import hashlib


class IdlePollingBackoff:
    """Bounded deterministic idle backoff with a small per-worker jitter."""

    def __init__(
        self,
        worker_id: str,
        *,
        initial_seconds: float = 1.0,
        maximum_seconds: float = 30.0,
        jitter_fraction: float = 0.1,
    ) -> None:
        if initial_seconds <= 0 or maximum_seconds < initial_seconds:
            raise ValueError("Worker polling backoff bounds are invalid")
        if not 0 <= jitter_fraction <= 0.25:
            raise ValueError("Worker polling jitter must be between zero and 0.25")
        self.worker_id = worker_id
        self.initial_seconds = initial_seconds
        self.maximum_seconds = maximum_seconds
        self.jitter_fraction = jitter_fraction
        self._idle_rounds = 0

    def reset(self) -> None:
        self._idle_rounds = 0

    def next_delay(self) -> float:
        base = min(self.maximum_seconds, self.initial_seconds * (2**self._idle_rounds))
        material = f"{self.worker_id}:{self._idle_rounds}".encode("utf-8")
        offset = (hashlib.sha256(material).digest()[0] / 255.0) * 2.0 - 1.0
        self._idle_rounds += 1
        return max(0.0, min(self.maximum_seconds, base * (1.0 + offset * self.jitter_fraction)))
