from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib

from mystic.lab.engines import EngineError
from mystic.lab.scientific_job import ScientificJobFailureClass


class WorkerFailureCategory(StrEnum):
    SCIENTIFIC_INPUT = "scientific_input"
    INFRASTRUCTURE = "infrastructure"
    EXECUTION = "execution"
    POLICY_SAFETY = "policy_safety"


@dataclass(frozen=True, slots=True)
class WorkerFailureClassification:
    category: WorkerFailureCategory
    failure_class: str
    code: str
    safe_error: str
    retryable: bool
    diagnostic_id: str


def classify_execution_error(error: Exception) -> WorkerFailureClassification:
    """Map exceptions to bounded persisted failure semantics without stack traces."""
    if isinstance(error, EngineError):
        if error.code == "engine_cancelled":
            category, failure, retryable = WorkerFailureCategory.POLICY_SAFETY, ScientificJobFailureClass.CANCELLED.value, False
        elif error.code in {"engine_execution_failed", "engine_runner_offline"}:
            category, failure, retryable = WorkerFailureCategory.INFRASTRUCTURE, ScientificJobFailureClass.ENGINE_TRANSIENT.value, True
        elif error.code in {"engine_input_invalid", "engine_version_mismatch", "engine_job_type_invalid"}:
            category, failure, retryable = WorkerFailureCategory.SCIENTIFIC_INPUT, ScientificJobFailureClass.ENGINE_PERMANENT.value, False
        elif error.code in {"engine_artifact_too_large", "external_compute_required"}:
            category, failure, retryable = WorkerFailureCategory.POLICY_SAFETY, ScientificJobFailureClass.ENGINE_PERMANENT.value, False
        else:
            category, failure, retryable = WorkerFailureCategory.EXECUTION, ScientificJobFailureClass.ENGINE_PERMANENT.value, False
        code = error.code
        safe_error = error.message
    elif isinstance(error, TimeoutError):
        category, failure, code, safe_error, retryable = (
            WorkerFailureCategory.EXECUTION,
            ScientificJobFailureClass.ENGINE_TRANSIENT.value,
            "execution_timeout",
            "The trusted scientific engine timed out.",
            True,
        )
    else:
        category, failure, code, safe_error, retryable = (
            WorkerFailureCategory.INFRASTRUCTURE,
            ScientificJobFailureClass.INTERNAL.value,
            "worker_internal_error",
            "The trusted scientific engine could not complete this job.",
            True,
        )
    diagnostic_id = "diag_" + hashlib.sha256(f"{category}:{code}:{safe_error}".encode("utf-8")).hexdigest()[:24]
    return WorkerFailureClassification(category, failure, code, safe_error, retryable, diagnostic_id)
