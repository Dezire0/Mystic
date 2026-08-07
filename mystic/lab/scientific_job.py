from __future__ import annotations

from dataclasses import MISSING, asdict, dataclass, field, fields
from datetime import datetime
from enum import StrEnum
import json
import math
import re
from typing import Any, TypeVar
import uuid

from mystic.lab.campaign import canonical_hash
from mystic.lab.schema import utc_now_iso


JOB_SCHEMA_VERSION = "2C.2A"
MAX_JOB_INPUT_BYTES = 131_072
MAX_JOB_RESULT_BYTES = 262_144
MAX_JOB_ERROR_CHARS = 1_000
MAX_JOB_EVENTS = 2_000

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$")
_SAFE_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+-]{0,79}$")


class ScientificJobError(RuntimeError):
    """Base error for deterministic scientific job failures."""


class ScientificJobNotFoundError(ScientificJobError):
    pass


class ScientificJobConflictError(ScientificJobError):
    pass


class ScientificJobLeaseError(ScientificJobError):
    pass


class ScientificJobIntegrityError(ScientificJobError):
    pass


class IllegalScientificJobTransition(ScientificJobError):
    pass


class ScientificJobStatus(StrEnum):
    PENDING = "PENDING"
    READY = "READY"
    LEASED = "LEASED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RETRY_WAIT = "RETRY_WAIT"
    CANCELLED = "CANCELLED"
    DEAD_LETTER = "DEAD_LETTER"


class ScientificJobOutboxStatus(StrEnum):
    PENDING = "PENDING"
    DISPATCHED = "DISPATCHED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    FAILED = "FAILED"


class ScientificJobAttachmentStatus(StrEnum):
    PENDING = "PENDING"
    ATTACHED = "ATTACHED"
    REJECTED = "REJECTED"


class ScientificJobFailureClass(StrEnum):
    VALIDATION = "VALIDATION"
    ENGINE_TRANSIENT = "ENGINE_TRANSIENT"
    ENGINE_PERMANENT = "ENGINE_PERMANENT"
    LEASE_EXPIRED = "LEASE_EXPIRED"
    DISPATCH = "DISPATCH"
    CAMPAIGN_STALE = "CAMPAIGN_STALE"
    RESULT_CONFLICT = "RESULT_CONFLICT"
    CANCELLED = "CANCELLED"
    INTERNAL = "INTERNAL"


JOB_ALLOWED_TRANSITIONS: dict[ScientificJobStatus, frozenset[ScientificJobStatus]] = {
    ScientificJobStatus.PENDING: frozenset({ScientificJobStatus.READY, ScientificJobStatus.CANCELLED}),
    ScientificJobStatus.READY: frozenset({ScientificJobStatus.LEASED, ScientificJobStatus.CANCELLED}),
    ScientificJobStatus.LEASED: frozenset({ScientificJobStatus.RUNNING, ScientificJobStatus.RETRY_WAIT, ScientificJobStatus.CANCELLED, ScientificJobStatus.DEAD_LETTER}),
    ScientificJobStatus.RUNNING: frozenset({ScientificJobStatus.SUCCEEDED, ScientificJobStatus.FAILED, ScientificJobStatus.RETRY_WAIT, ScientificJobStatus.CANCELLED, ScientificJobStatus.DEAD_LETTER}),
    ScientificJobStatus.FAILED: frozenset({ScientificJobStatus.RETRY_WAIT, ScientificJobStatus.CANCELLED, ScientificJobStatus.DEAD_LETTER}),
    ScientificJobStatus.RETRY_WAIT: frozenset({ScientificJobStatus.READY, ScientificJobStatus.CANCELLED}),
    ScientificJobStatus.SUCCEEDED: frozenset(),
    ScientificJobStatus.CANCELLED: frozenset(),
    ScientificJobStatus.DEAD_LETTER: frozenset(),
}

TERMINAL_JOB_STATUSES = frozenset(
    {ScientificJobStatus.SUCCEEDED, ScientificJobStatus.CANCELLED, ScientificJobStatus.DEAD_LETTER}
)


def validate_job_transition(source: ScientificJobStatus | str, target: ScientificJobStatus | str) -> None:
    current = ScientificJobStatus(source)
    requested = ScientificJobStatus(target)
    if requested not in JOB_ALLOWED_TRANSITIONS[current]:
        raise IllegalScientificJobTransition(
            f"Illegal scientific job transition: {current.value} -> {requested.value}"
        )


def new_scientific_job_id() -> str:
    return f"job_{uuid.uuid4().hex}"


def new_scientific_job_event_id() -> str:
    return f"job_event_{uuid.uuid4().hex}"


def new_scientific_job_lease_id() -> str:
    return f"job_lease_{uuid.uuid4().hex}"


def new_scientific_job_outbox_id() -> str:
    return f"job_outbox_{uuid.uuid4().hex}"


def validate_scientific_job_id(job_id: str) -> None:
    """Validate the opaque identifier before it is used as a storage key."""
    _require_identifier("job_id", job_id)


def _require_identifier(name: str, value: str) -> None:
    if not isinstance(value, str) or not _SAFE_IDENTIFIER.fullmatch(value):
        raise ValueError(f"{name} must be a bounded opaque identifier")


def _require_text(name: str, value: str, *, minimum: int = 0, maximum: int = 160) -> None:
    if not isinstance(value, str) or len(value.strip()) < minimum or len(value) > maximum:
        raise ValueError(f"{name} must contain between {minimum} and {maximum} characters")


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(f"{name} must be a SHA-256 hex digest")


def _require_timestamp(name: str, value: str, *, allow_empty: bool = False) -> None:
    if allow_empty and value == "":
        return
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")


def _validate_json_value(value: Any, *, path: str = "$", depth: int = 0) -> None:
    if depth > 24:
        raise ValueError(f"{path} exceeds the maximum structured payload depth")
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, int) and not isinstance(value, bool):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} contains a non-finite number")
        return
    if isinstance(value, list):
        if len(value) > 10_000:
            raise ValueError(f"{path} contains too many items")
        for index, item in enumerate(value):
            _validate_json_value(item, path=f"{path}[{index}]", depth=depth + 1)
        return
    if isinstance(value, dict):
        if len(value) > 10_000:
            raise ValueError(f"{path} contains too many properties")
        for key, item in value.items():
            if not isinstance(key, str) or not key or len(key) > 160:
                raise ValueError(f"{path} has an invalid property name")
            _validate_json_value(item, path=f"{path}.{key}", depth=depth + 1)
        return
    raise ValueError(f"{path} contains a value that is not structured JSON")


def validate_structured_payload(value: Any, *, name: str, maximum_bytes: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    _validate_json_value(value)
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be JSON serializable") from exc
    if len(encoded) > maximum_bytes:
        raise ValueError(f"{name} exceeds {maximum_bytes} bytes")
    return value


T = TypeVar("T")


def _strict_dataclass_payload(payload: dict[str, Any], model: type[T]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ScientificJobIntegrityError(f"{model.__name__} must be an object")
    model_fields = {item.name: item for item in fields(model)}
    unknown = set(payload) - set(model_fields)
    if unknown:
        raise ScientificJobIntegrityError(
            f"{model.__name__} contains unknown fields: {', '.join(sorted(unknown))}"
        )
    missing = [
        name
        for name, item in model_fields.items()
        if name not in payload and item.default is MISSING and item.default_factory is MISSING
    ]
    if missing:
        raise ScientificJobIntegrityError(
            f"{model.__name__} is missing fields: {', '.join(sorted(missing))}"
        )
    return dict(payload)


@dataclass(slots=True)
class ScientificJobRequest:
    campaign_id: str
    campaign_revision: int
    job_type: str
    engine_name: str
    engine_version: str
    input_payload: dict[str, Any]
    input_hash: str
    experiment_id: str = ""
    correlation_id: str = ""
    schema_version: str = JOB_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_identifier("campaign_id", self.campaign_id)
        if not isinstance(self.campaign_revision, int) or self.campaign_revision < 0:
            raise ValueError("campaign_revision must be a non-negative integer")
        _require_text("job_type", self.job_type, minimum=1, maximum=80)
        _require_identifier("engine_name", self.engine_name)
        if not isinstance(self.engine_version, str) or not _SAFE_VERSION.fullmatch(self.engine_version):
            raise ValueError("engine_version is invalid")
        validate_structured_payload(self.input_payload, name="input_payload", maximum_bytes=MAX_JOB_INPUT_BYTES)
        expected = canonical_hash(self.input_payload)
        if self.input_hash and self.input_hash != expected:
            raise ScientificJobIntegrityError("Scientific job request input hash mismatch")
        self.input_hash = expected
        if self.experiment_id:
            _require_identifier("experiment_id", self.experiment_id)
        if self.correlation_id:
            _require_text("correlation_id", self.correlation_id, minimum=1, maximum=160)
        if self.schema_version != JOB_SCHEMA_VERSION:
            raise ValueError("Unsupported scientific job request schema version")


@dataclass(slots=True)
class ScientificJobResult:
    job_id: str
    engine_name: str
    engine_version: str
    result_payload: dict[str, Any]
    result_hash: str = ""
    runner_version: str = ""
    schema_version: str = JOB_SCHEMA_VERSION
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        _require_identifier("job_id", self.job_id)
        _require_identifier("engine_name", self.engine_name)
        if not isinstance(self.engine_version, str) or not _SAFE_VERSION.fullmatch(self.engine_version):
            raise ValueError("engine_version is invalid")
        validate_structured_payload(self.result_payload, name="result_payload", maximum_bytes=MAX_JOB_RESULT_BYTES)
        expected = canonical_hash(self.result_payload)
        if self.result_hash and self.result_hash != expected:
            raise ScientificJobIntegrityError("Scientific job result hash mismatch")
        self.result_hash = expected
        _require_text("runner_version", self.runner_version, maximum=160)
        _require_timestamp("created_at", self.created_at)
        if self.schema_version != JOB_SCHEMA_VERSION:
            raise ValueError("Unsupported scientific job result schema version")


@dataclass(slots=True)
class ScientificJobFailure:
    job_id: str
    failure_class: str
    safe_error: str
    retryable: bool
    failure_id: str = field(default_factory=lambda: f"job_failure_{uuid.uuid4().hex}")
    schema_version: str = JOB_SCHEMA_VERSION
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        _require_identifier("job_id", self.job_id)
        self.failure_class = ScientificJobFailureClass(self.failure_class).value
        _require_text("safe_error", self.safe_error, minimum=1, maximum=MAX_JOB_ERROR_CHARS)
        if not isinstance(self.retryable, bool):
            raise ValueError("retryable must be boolean")
        _require_identifier("failure_id", self.failure_id)
        _require_timestamp("created_at", self.created_at)
        if self.schema_version != JOB_SCHEMA_VERSION:
            raise ValueError("Unsupported scientific job failure schema version")


@dataclass(slots=True)
class ScientificJobLease:
    job_id: str
    lease_owner: str
    token_hash: str
    acquired_at: str
    expires_at: str
    lease_id: str = field(default_factory=new_scientific_job_lease_id)
    heartbeat_count: int = 0
    released_at: str = ""
    release_reason: str = ""
    schema_version: str = JOB_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_identifier("job_id", self.job_id)
        _require_text("lease_owner", self.lease_owner, minimum=1, maximum=160)
        _require_hash("token_hash", self.token_hash)
        _require_identifier("lease_id", self.lease_id)
        _require_timestamp("acquired_at", self.acquired_at)
        _require_timestamp("expires_at", self.expires_at)
        _require_timestamp("released_at", self.released_at, allow_empty=True)
        acquired_at = datetime.fromisoformat(self.acquired_at)
        expires_at = datetime.fromisoformat(self.expires_at)
        if expires_at <= acquired_at:
            raise ValueError("lease expiry must be after acquisition")
        if self.released_at and datetime.fromisoformat(self.released_at) < acquired_at:
            raise ValueError("lease release cannot precede acquisition")
        if not isinstance(self.heartbeat_count, int) or self.heartbeat_count < 0:
            raise ValueError("heartbeat_count must be a non-negative integer")
        _require_text("release_reason", self.release_reason, maximum=160)
        if self.schema_version != JOB_SCHEMA_VERSION:
            raise ValueError("Unsupported scientific job lease schema version")


@dataclass(slots=True)
class ScientificJobOutboxEvent:
    job_id: str
    payload_hash: str
    status: ScientificJobOutboxStatus = ScientificJobOutboxStatus.PENDING
    event_type: str = "SCIENTIFIC_JOB_READY"
    attempt: int = 0
    available_at: str = field(default_factory=utc_now_iso)
    dispatched_at: str = ""
    acknowledged_at: str = ""
    safe_error: str = ""
    event_id: str = field(default_factory=new_scientific_job_outbox_id)
    revision: int = 0
    schema_version: str = JOB_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_identifier("job_id", self.job_id)
        _require_hash("payload_hash", self.payload_hash)
        self.status = ScientificJobOutboxStatus(self.status)
        _require_text("event_type", self.event_type, minimum=1, maximum=80)
        if not isinstance(self.attempt, int) or self.attempt < 0:
            raise ValueError("outbox attempt must be a non-negative integer")
        _require_text("safe_error", self.safe_error, maximum=MAX_JOB_ERROR_CHARS)
        _require_identifier("event_id", self.event_id)
        _require_timestamp("available_at", self.available_at)
        _require_timestamp("dispatched_at", self.dispatched_at, allow_empty=True)
        _require_timestamp("acknowledged_at", self.acknowledged_at, allow_empty=True)
        if not isinstance(self.revision, int) or self.revision < 0:
            raise ValueError("outbox revision must be a non-negative integer")
        if self.schema_version != JOB_SCHEMA_VERSION:
            raise ValueError("Unsupported scientific job outbox schema version")


@dataclass(slots=True)
class ScientificJobAttachment:
    job_id: str
    campaign_id: str
    campaign_revision: int
    attachment_key: str
    result_hash: str
    status: ScientificJobAttachmentStatus = ScientificJobAttachmentStatus.PENDING
    artifact_id: str = ""
    safe_error: str = ""
    attached_at: str = ""
    schema_version: str = JOB_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_identifier("job_id", self.job_id)
        _require_identifier("campaign_id", self.campaign_id)
        if not isinstance(self.campaign_revision, int) or self.campaign_revision < 0:
            raise ValueError("attachment campaign_revision must be non-negative")
        _require_text("attachment_key", self.attachment_key, minimum=1, maximum=240)
        _require_hash("result_hash", self.result_hash)
        self.status = ScientificJobAttachmentStatus(self.status)
        if self.artifact_id:
            _require_identifier("artifact_id", self.artifact_id)
        _require_text("safe_error", self.safe_error, maximum=MAX_JOB_ERROR_CHARS)
        _require_timestamp("attached_at", self.attached_at, allow_empty=True)
        if self.schema_version != JOB_SCHEMA_VERSION:
            raise ValueError("Unsupported scientific job attachment schema version")


@dataclass(slots=True)
class ScientificJobEvent:
    job_id: str
    event_type: str
    status: str
    revision: int
    summary: str
    metadata: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=new_scientific_job_event_id)
    created_at: str = field(default_factory=utc_now_iso)
    schema_version: str = JOB_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_identifier("job_id", self.job_id)
        _require_text("event_type", self.event_type, minimum=1, maximum=80)
        self.status = ScientificJobStatus(self.status).value
        if not isinstance(self.revision, int) or self.revision < 0:
            raise ValueError("event revision must be non-negative")
        _require_text("summary", self.summary, minimum=1, maximum=MAX_JOB_ERROR_CHARS)
        validate_structured_payload(self.metadata, name="event metadata", maximum_bytes=32_768)
        _require_identifier("event_id", self.event_id)
        _require_timestamp("created_at", self.created_at)
        if self.schema_version != JOB_SCHEMA_VERSION:
            raise ValueError("Unsupported scientific job event schema version")


@dataclass(slots=True)
class ScientificJob:
    job_id: str
    campaign_id: str
    campaign_revision: int
    job_type: str
    engine_name: str
    engine_version: str
    input_payload: dict[str, Any]
    input_hash: str
    status: ScientificJobStatus = ScientificJobStatus.PENDING
    attempt: int = 0
    max_attempts: int = 3
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    ready_at: str = field(default_factory=utc_now_iso)
    lease_owner: str = ""
    lease_token_hash: str = ""
    lease_acquired_at: str = ""
    lease_expires_at: str = ""
    started_at: str = ""
    finished_at: str = ""
    completed_lease_owner: str = ""
    completed_lease_token_hash: str = ""
    result: ScientificJobResult | None = None
    result_hash: str = ""
    error: str = ""
    failure_class: str = ""
    failure: ScientificJobFailure | None = None
    failure_attachment_state: str = ""
    failure_attachment_error: str = ""
    idempotency_key: str = ""
    correlation_id: str = ""
    experiment_id: str = ""
    attachment_campaign_revision: int = 0
    cancellation_requested: bool = False
    attachment: ScientificJobAttachment | None = None
    lease_history: list[ScientificJobLease] = field(default_factory=list)
    outbox_events: list[ScientificJobOutboxEvent] = field(default_factory=list)
    events: list[ScientificJobEvent] = field(default_factory=list)
    duplicate_completion_count: int = 0
    duplicate_completion_rejected_count: int = 0
    result_replay_count: int = 0
    conflicting_result_count: int = 0
    reconciliation_count: int = 0
    revision: int = 0
    schema_version: str = JOB_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_identifier("job_id", self.job_id)
        _require_identifier("campaign_id", self.campaign_id)
        if not isinstance(self.campaign_revision, int) or self.campaign_revision < 0:
            raise ValueError("campaign_revision must be a non-negative integer")
        _require_text("job_type", self.job_type, minimum=1, maximum=80)
        _require_identifier("engine_name", self.engine_name)
        if not isinstance(self.engine_version, str) or not _SAFE_VERSION.fullmatch(self.engine_version):
            raise ValueError("engine_version is invalid")
        validate_structured_payload(self.input_payload, name="input_payload", maximum_bytes=MAX_JOB_INPUT_BYTES)
        expected_input_hash = canonical_hash(self.input_payload)
        if self.input_hash != expected_input_hash:
            raise ScientificJobIntegrityError("Scientific job input hash mismatch")
        self.status = ScientificJobStatus(self.status)
        if not isinstance(self.attempt, int) or self.attempt < 0:
            raise ValueError("attempt must be a non-negative integer")
        if not isinstance(self.max_attempts, int) or not 1 <= self.max_attempts <= 10:
            raise ValueError("max_attempts must be between 1 and 10")
        if self.attempt > self.max_attempts:
            raise ScientificJobIntegrityError("attempt exceeds max_attempts")
        _require_timestamp("created_at", self.created_at)
        _require_timestamp("updated_at", self.updated_at)
        _require_timestamp("ready_at", self.ready_at)
        _require_timestamp("lease_acquired_at", self.lease_acquired_at, allow_empty=True)
        _require_timestamp("lease_expires_at", self.lease_expires_at, allow_empty=True)
        _require_timestamp("started_at", self.started_at, allow_empty=True)
        _require_timestamp("finished_at", self.finished_at, allow_empty=True)
        if self.lease_owner:
            _require_text("lease_owner", self.lease_owner, minimum=1, maximum=160)
            _require_hash("lease_token_hash", self.lease_token_hash)
        elif self.lease_token_hash:
            raise ScientificJobIntegrityError("lease token hash requires a lease owner")
        if self.completed_lease_owner:
            _require_text("completed_lease_owner", self.completed_lease_owner, minimum=1, maximum=160)
            _require_hash("completed_lease_token_hash", self.completed_lease_token_hash)
        elif self.completed_lease_token_hash:
            raise ScientificJobIntegrityError("completed lease token hash requires a completed lease owner")
        _require_text("error", self.error, maximum=MAX_JOB_ERROR_CHARS)
        if self.failure_class:
            self.failure_class = ScientificJobFailureClass(self.failure_class).value
        _require_text("idempotency_key", self.idempotency_key, maximum=160)
        _require_text("correlation_id", self.correlation_id, maximum=160)
        if self.experiment_id:
            _require_identifier("experiment_id", self.experiment_id)
        if not isinstance(self.attachment_campaign_revision, int) or self.attachment_campaign_revision < 0:
            raise ValueError("attachment_campaign_revision must be non-negative")
        if not isinstance(self.cancellation_requested, bool):
            raise ValueError("cancellation_requested must be boolean")
        if self.result is not None:
            if self.result.job_id != self.job_id:
                raise ScientificJobIntegrityError("result belongs to another job")
            if self.result_hash != self.result.result_hash:
                raise ScientificJobIntegrityError("Scientific job result hash mismatch")
        elif self.result_hash:
            raise ScientificJobIntegrityError("result hash requires a result")
        if self.failure is not None:
            if self.failure.job_id != self.job_id:
                raise ScientificJobIntegrityError("failure belongs to another job")
            if self.failure_class != self.failure.failure_class:
                raise ScientificJobIntegrityError("failure class mismatch")
        if self.failure_attachment_state not in {"", "ATTACHED", "REJECTED"}:
            raise ValueError("failure_attachment_state is invalid")
        _require_text("failure_attachment_error", self.failure_attachment_error, maximum=MAX_JOB_ERROR_CHARS)
        if self.attachment is not None:
            if self.attachment.job_id != self.job_id or self.attachment.campaign_id != self.campaign_id:
                raise ScientificJobIntegrityError("attachment belongs to another job or campaign")
            if self.attachment.campaign_revision != self.attachment_campaign_revision:
                raise ScientificJobIntegrityError("attachment campaign revision does not match the job")
            if self.result_hash != self.attachment.result_hash:
                raise ScientificJobIntegrityError("attachment result hash does not match the job")
            if self.status != ScientificJobStatus.SUCCEEDED:
                raise ScientificJobIntegrityError("only succeeded jobs may retain a result attachment")
            if self.attachment.status == ScientificJobAttachmentStatus.ATTACHED:
                if not self.attachment.artifact_id or not self.attachment.attached_at:
                    raise ScientificJobIntegrityError("attached results require an artifact and attachment timestamp")
            if self.attachment.status == ScientificJobAttachmentStatus.REJECTED and not self.attachment.safe_error:
                raise ScientificJobIntegrityError("rejected results require a safe rejection reason")
        for lease in self.lease_history:
            if lease.job_id != self.job_id:
                raise ScientificJobIntegrityError("lease belongs to another job")
        for event in self.outbox_events:
            if event.job_id != self.job_id:
                raise ScientificJobIntegrityError("outbox event belongs to another job")
        if len(self.events) > MAX_JOB_EVENTS:
            raise ScientificJobIntegrityError("scientific job event history exceeds the configured bound")
        for event in self.events:
            if event.job_id != self.job_id:
                raise ScientificJobIntegrityError("audit event belongs to another job")
        for name in (
            "duplicate_completion_count",
            "duplicate_completion_rejected_count",
            "result_replay_count",
            "conflicting_result_count",
            "reconciliation_count",
            "revision",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.schema_version != JOB_SCHEMA_VERSION:
            raise ValueError("Unsupported scientific job schema version")
        if self.status == ScientificJobStatus.SUCCEEDED and self.result is None:
            raise ScientificJobIntegrityError("succeeded jobs require an accepted result")
        active_statuses = {ScientificJobStatus.LEASED, ScientificJobStatus.RUNNING}
        active_leases = [lease for lease in self.lease_history if not lease.released_at]
        if len(active_leases) > 1:
            raise ScientificJobIntegrityError("only one active scientific job lease may exist")
        if self.status in active_statuses:
            if not (self.lease_owner and self.lease_token_hash and self.lease_acquired_at and self.lease_expires_at):
                raise ScientificJobIntegrityError("leased and running jobs require an active lease")
            if len(active_leases) != 1 or self.active_lease is None:
                raise ScientificJobIntegrityError("active scientific job lease is missing from lease history")
            if active_leases[0].token_hash != self.lease_token_hash:
                raise ScientificJobIntegrityError("active lease token does not match the job")
        elif self.lease_owner or self.lease_token_hash or self.lease_acquired_at or self.lease_expires_at or active_leases:
            raise ScientificJobIntegrityError("non-active scientific jobs cannot retain an active lease")
        if self.status == ScientificJobStatus.FAILED and self.failure is None:
            raise ScientificJobIntegrityError("failed jobs require a failure record")
        if self.status == ScientificJobStatus.DEAD_LETTER and self.failure is None:
            raise ScientificJobIntegrityError("dead-letter jobs require a terminal failure record")
        if self.status == ScientificJobStatus.SUCCEEDED and self.failure is not None:
            raise ScientificJobIntegrityError("succeeded jobs cannot contain a failure record")

    @property
    def active_lease(self) -> ScientificJobLease | None:
        if not self.lease_owner:
            return None
        for lease in reversed(self.lease_history):
            if lease.lease_owner == self.lease_owner and not lease.released_at:
                return lease
        return None

    def append_event(
        self,
        event_type: str,
        summary: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ScientificJobEvent:
        event = ScientificJobEvent(
            job_id=self.job_id,
            event_type=event_type,
            status=self.status.value,
            revision=self.revision,
            summary=summary,
            metadata=metadata or {},
        )
        self.events.append(event)
        if len(self.events) > MAX_JOB_EVENTS:
            self.events = self.events[-MAX_JOB_EVENTS:]
        return event

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "campaign_id": self.campaign_id,
            "campaign_revision": self.campaign_revision,
            "job_type": self.job_type,
            "engine_name": self.engine_name,
            "engine_version": self.engine_version,
            "input_payload": self.input_payload,
            "input_hash": self.input_hash,
            "status": self.status.value,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "ready_at": self.ready_at,
            "lease_owner": self.lease_owner,
            "lease_token_hash": self.lease_token_hash,
            "lease_acquired_at": self.lease_acquired_at,
            "lease_expires_at": self.lease_expires_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "completed_lease_owner": self.completed_lease_owner,
            "completed_lease_token_hash": self.completed_lease_token_hash,
            "result": asdict(self.result) if self.result else None,
            "result_hash": self.result_hash,
            "error": self.error,
            "failure_class": self.failure_class,
            "failure": asdict(self.failure) if self.failure else None,
            "failure_attachment_state": self.failure_attachment_state,
            "failure_attachment_error": self.failure_attachment_error,
            "idempotency_key": self.idempotency_key,
            "correlation_id": self.correlation_id,
            "experiment_id": self.experiment_id,
            "attachment_campaign_revision": self.attachment_campaign_revision,
            "cancellation_requested": self.cancellation_requested,
            "attachment": asdict(self.attachment) if self.attachment else None,
            "lease_history": [asdict(item) for item in self.lease_history],
            "outbox_events": [asdict(item) for item in self.outbox_events],
            "events": [asdict(item) for item in self.events],
            "duplicate_completion_count": self.duplicate_completion_count,
            "duplicate_completion_rejected_count": self.duplicate_completion_rejected_count,
            "result_replay_count": self.result_replay_count,
            "conflicting_result_count": self.conflicting_result_count,
            "reconciliation_count": self.reconciliation_count,
            "revision": self.revision,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ScientificJob:
        values = _strict_dataclass_payload(payload, cls)
        try:
            values["status"] = ScientificJobStatus(values["status"])
            values["result"] = ScientificJobResult(**_strict_dataclass_payload(values["result"], ScientificJobResult)) if values["result"] is not None else None
            values["failure"] = ScientificJobFailure(**_strict_dataclass_payload(values["failure"], ScientificJobFailure)) if values["failure"] is not None else None
            values["attachment"] = ScientificJobAttachment(**_strict_dataclass_payload(values["attachment"], ScientificJobAttachment)) if values["attachment"] is not None else None
            values["lease_history"] = [ScientificJobLease(**_strict_dataclass_payload(item, ScientificJobLease)) for item in values["lease_history"]]
            values["outbox_events"] = [ScientificJobOutboxEvent(**_strict_dataclass_payload(item, ScientificJobOutboxEvent)) for item in values["outbox_events"]]
            values["events"] = [ScientificJobEvent(**_strict_dataclass_payload(item, ScientificJobEvent)) for item in values["events"]]
            return cls(**values)
        except (TypeError, ValueError, ScientificJobIntegrityError) as exc:
            if isinstance(exc, ScientificJobIntegrityError):
                raise
            raise ScientificJobIntegrityError("Scientific job state is malformed") from exc
