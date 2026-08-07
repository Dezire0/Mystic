from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import tempfile
from typing import Callable, Iterator, TypeVar

from mystic.lab.scientific_job import (
    ScientificJob,
    ScientificJobConflictError,
    ScientificJobIntegrityError,
    ScientificJobNotFoundError,
    validate_scientific_job_id,
)


T = TypeVar("T")


class ScientificJobStorage:
    """Atomic local aggregate persistence for ScientificJob and its durable outbox."""

    backend_name = "local_json"

    def __init__(self, root_path: str | Path) -> None:
        self.root_path = Path(root_path)
        self.base_dir = self.root_path / "mystic_data" / "scientific_jobs"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def job_dir(self, job_id: str) -> Path:
        validate_scientific_job_id(job_id)
        return self.base_dir / job_id

    def job_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "job.json"

    @contextmanager
    def _locked(self, job_id: str) -> Iterator[None]:
        directory = self.job_dir(job_id)
        directory.mkdir(parents=True, exist_ok=True)
        lock_path = directory / ".lock"
        with lock_path.open("a+", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def create(self, job: ScientificJob) -> ScientificJob:
        with self._locked(job.job_id):
            if self.job_path(job.job_id).exists():
                raise ScientificJobConflictError(f"Scientific job already exists: {job.job_id}")
            self._write_job(job)
        return job

    def load(self, job_id: str) -> ScientificJob:
        return self._load_unlocked(job_id)

    def save(self, job: ScientificJob, *, expected_revision: int) -> ScientificJob:
        with self._locked(job.job_id):
            current = self._load_unlocked(job.job_id)
            if current.revision != expected_revision:
                raise ScientificJobConflictError(
                    f"Scientific job revision conflict: expected {expected_revision}, found {current.revision}"
                )
            if job.revision != expected_revision + 1:
                raise ScientificJobConflictError("Scientific job mutations must increment revision exactly once")
            self._write_job(job)
        return job

    def mutate(self, job_id: str, mutation: Callable[[ScientificJob], T]) -> tuple[ScientificJob, T]:
        """Load, mutate, validate, and persist an aggregate while holding its lock."""
        with self._locked(job_id):
            job = self._load_unlocked(job_id)
            expected_revision = job.revision
            result = mutation(job)
            if job.revision == expected_revision:
                return job, result
            if job.revision != expected_revision + 1:
                raise ScientificJobConflictError("Scientific job mutations must increment revision exactly once")
            self._write_job(job)
            return job, result

    def list(self, *, limit: int = 50, status: str | None = None, campaign_id: str | None = None) -> list[ScientificJob]:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        jobs: list[ScientificJob] = []
        for path in sorted(self.base_dir.glob("*/job.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                job = ScientificJob.from_dict(payload)
            except (OSError, json.JSONDecodeError, TypeError, ValueError, ScientificJobIntegrityError) as exc:
                # A corrupt aggregate must halt operator/reconciler scans rather than
                # become invisible work. Atomic writes make this an integrity signal,
                # not a normal recovery path.
                raise ScientificJobIntegrityError(f"Scientific job state is unreadable: {path.parent.name}") from exc
            if status and job.status.value != status:
                continue
            if campaign_id and job.campaign_id != campaign_id:
                continue
            jobs.append(job)
            if len(jobs) >= limit:
                break
        return jobs

    def _load_unlocked(self, job_id: str) -> ScientificJob:
        path = self.job_path(job_id)
        if not path.exists():
            raise ScientificJobNotFoundError(f"Scientific job not found: {job_id}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ScientificJobIntegrityError(f"Scientific job state is unreadable: {job_id}") from exc
        if not isinstance(payload, dict):
            raise ScientificJobIntegrityError(f"Scientific job state is invalid: {job_id}")
        return ScientificJob.from_dict(payload)

    def _write_job(self, job: ScientificJob) -> None:
        payload = job.to_dict()
        # Validate the complete serialized contract at the durable boundary, not
        # only when a future process happens to reload it.
        ScientificJob.from_dict(payload)
        self._atomic_write(self.job_path(job.job_id), payload)

    @staticmethod
    def _atomic_write(path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode("utf-8")
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            directory_descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        finally:
            if temporary.exists():
                temporary.unlink()

    def describe_status(self) -> dict[str, object]:
        return {
            "backend": self.backend_name,
            "configured": True,
            "write_capable": True,
            "storage_root": str(self.base_dir),
            "integrity_algorithm": "sha256",
            "aggregate_boundary": "scientific_job_with_outbox",
        }
