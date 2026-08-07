from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
import hashlib
import json
from typing import Any, ClassVar
import uuid

from mystic.lab.schema import utc_now_iso


class CampaignError(RuntimeError):
    """Base error for safe campaign failures."""


class CampaignNotFoundError(CampaignError):
    pass


class CampaignConflictError(CampaignError):
    pass


class IllegalCampaignTransition(CampaignError):
    pass


class CampaignIntegrityError(CampaignError):
    pass


class CampaignBudgetExceeded(CampaignError):
    pass


class CampaignPhase(StrEnum):
    PLANNING = "PLANNING"
    BACKGROUND_RESEARCH = "BACKGROUND_RESEARCH"
    KNOWLEDGE_GRAPH = "KNOWLEDGE_GRAPH"
    HYPOTHESIS_GENERATION = "HYPOTHESIS_GENERATION"
    MODEL_SELECTION = "MODEL_SELECTION"
    EXPERIMENT_PLANNING = "EXPERIMENT_PLANNING"
    ENGINE_EXECUTION = "ENGINE_EXECUTION"
    RESULT_VALIDATION = "RESULT_VALIDATION"
    REFEREE_REVIEW = "REFEREE_REVIEW"
    FAILURE_ARCHIVE = "FAILURE_ARCHIVE"
    KNOWLEDGE_UPDATE = "KNOWLEDGE_UPDATE"
    NEXT_ACTION = "NEXT_ACTION"
    REPORT = "REPORT"
    COMPLETE = "COMPLETE"


class CampaignStatus(StrEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    COMPLETE = "COMPLETE"


CAMPAIGN_PHASES = tuple(CampaignPhase)
CAMPAIGN_STATUSES = tuple(CampaignStatus)

_SEQUENTIAL_PHASES = (
    CampaignPhase.PLANNING,
    CampaignPhase.BACKGROUND_RESEARCH,
    CampaignPhase.KNOWLEDGE_GRAPH,
    CampaignPhase.HYPOTHESIS_GENERATION,
    CampaignPhase.MODEL_SELECTION,
    CampaignPhase.EXPERIMENT_PLANNING,
    CampaignPhase.ENGINE_EXECUTION,
    CampaignPhase.RESULT_VALIDATION,
    CampaignPhase.REFEREE_REVIEW,
    CampaignPhase.FAILURE_ARCHIVE,
    CampaignPhase.KNOWLEDGE_UPDATE,
    CampaignPhase.NEXT_ACTION,
    CampaignPhase.REPORT,
    CampaignPhase.COMPLETE,
)

ALLOWED_PHASE_TRANSITIONS: dict[CampaignPhase, frozenset[CampaignPhase]] = {
    phase: frozenset({_SEQUENTIAL_PHASES[index + 1]})
    for index, phase in enumerate(_SEQUENTIAL_PHASES[:-1])
}
ALLOWED_PHASE_TRANSITIONS[CampaignPhase.NEXT_ACTION] = frozenset(
    {CampaignPhase.HYPOTHESIS_GENERATION, CampaignPhase.REPORT}
)
ALLOWED_PHASE_TRANSITIONS[CampaignPhase.COMPLETE] = frozenset()

KNOWLEDGE_NODE_TYPES = frozenset(
    {"claim", "evidence", "model", "hypothesis", "experiment", "failure", "citation", "artifact"}
)
KNOWLEDGE_EDGE_TYPES = frozenset(
    {
        "supports",
        "refutes",
        "uses_model",
        "tests",
        "cites",
        "depends_on",
        "caused_failure",
        "supersedes",
        "derived_from",
    }
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def validate_transition(source: CampaignPhase | str, target: CampaignPhase | str) -> None:
    current = CampaignPhase(source)
    requested = CampaignPhase(target)
    if requested not in ALLOWED_PHASE_TRANSITIONS[current]:
        raise IllegalCampaignTransition(f"Illegal campaign transition: {current.value} -> {requested.value}")


@dataclass(slots=True)
class CampaignMetadata:
    title: str
    description: str = ""
    domain: str = "general"
    tags: list[str] = field(default_factory=list)
    external_references: list[str] = field(default_factory=list)
    created_by: str = "mystic"
    schema_version: str = "2C.1"


@dataclass(slots=True)
class CampaignBudget:
    max_iterations: int = 100
    max_experiments: int = 100
    max_engine_seconds: float = 3600.0
    max_graph_nodes: int = 5000
    max_graph_edges: int = 10000
    max_checkpoints: int = 100
    iterations_used: int = 0
    experiments_used: int = 0
    engine_seconds_used: float = 0.0

    def validate(self) -> None:
        bounds = {
            "max_iterations": (1, 10000),
            "max_experiments": (1, 10000),
            "max_engine_seconds": (0.0, 31_536_000.0),
            "max_graph_nodes": (1, 100000),
            "max_graph_edges": (1, 200000),
            "max_checkpoints": (1, 1000),
        }
        for name, (minimum, maximum) in bounds.items():
            value = getattr(self, name)
            if value < minimum or value > maximum:
                raise ValueError(f"{name} must be between {minimum} and {maximum}")
        usage = {
            "iterations_used": (self.iterations_used, self.max_iterations),
            "experiments_used": (self.experiments_used, self.max_experiments),
            "engine_seconds_used": (self.engine_seconds_used, self.max_engine_seconds),
        }
        for name, (value, maximum) in usage.items():
            if value < 0 or value > maximum:
                raise ValueError(f"{name} must be between 0 and its configured maximum")


@dataclass(slots=True)
class CampaignStatistics:
    transition_count: int = 0
    checkpoint_count: int = 0
    rollback_count: int = 0
    retry_count: int = 0
    graph_node_count: int = 0
    graph_edge_count: int = 0
    evidence_count: int = 0
    experiment_count: int = 0
    failure_count: int = 0
    started_at: str = field(default_factory=utc_now_iso)
    completed_at: str = ""
    last_transition_at: str = ""


@dataclass(slots=True)
class CampaignGoal:
    campaign_id: str
    statement: str
    priority: int = 0
    status: str = "OPEN"
    goal_id: str = field(default_factory=lambda: new_id("goal"))
    created_at: str = field(default_factory=utc_now_iso)


@dataclass(slots=True)
class ResearchQuestion:
    campaign_id: str
    text: str
    goal_id: str = ""
    status: str = "OPEN"
    question_id: str = field(default_factory=lambda: new_id("question"))
    created_at: str = field(default_factory=utc_now_iso)


@dataclass(slots=True)
class Hypothesis:
    campaign_id: str
    statement: str
    question_id: str = ""
    status: str = "PROPOSED"
    rationale: str = ""
    hypothesis_id: str = field(default_factory=lambda: new_id("hypothesis"))
    version: int = 1
    created_at: str = field(default_factory=utc_now_iso)


@dataclass(slots=True)
class Evidence:
    campaign_id: str
    summary: str
    evidence_type: str
    source_id: str = ""
    supports: list[str] = field(default_factory=list)
    refutes: list[str] = field(default_factory=list)
    content_hash: str = ""
    evidence_id: str = field(default_factory=lambda: new_id("evidence"))
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        if not self.content_hash:
            self.content_hash = canonical_hash(
                {"summary": self.summary, "evidence_type": self.evidence_type, "source_id": self.source_id}
            )


@dataclass(slots=True)
class Experiment:
    campaign_id: str
    question: str
    method: str
    inputs: dict[str, Any] = field(default_factory=dict)
    hypothesis_ids: list[str] = field(default_factory=list)
    status: str = "QUEUED"
    outputs: dict[str, Any] = field(default_factory=dict)
    experiment_id: str = field(default_factory=lambda: new_id("experiment"))
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)


@dataclass(slots=True)
class ScientificModel:
    campaign_id: str
    name: str
    model_type: str
    version: str
    specification: dict[str, Any] = field(default_factory=dict)
    status: str = "CANDIDATE"
    model_id: str = field(default_factory=lambda: new_id("model"))
    created_at: str = field(default_factory=utc_now_iso)


@dataclass(slots=True)
class Review:
    campaign_id: str
    subject_id: str
    verdict: str
    summary: str
    reviewer: str = "runtime"
    review_id: str = field(default_factory=lambda: new_id("review"))
    created_at: str = field(default_factory=utc_now_iso)


@dataclass(slots=True)
class Failure:
    campaign_id: str
    failure_type: str
    summary: str
    source_id: str = ""
    retryable: bool = False
    archived: bool = False
    failure_id: str = field(default_factory=lambda: new_id("failure"))
    created_at: str = field(default_factory=utc_now_iso)


@dataclass(slots=True)
class Decision:
    campaign_id: str
    decision_type: str
    outcome: str
    rationale: str
    input_ids: list[str] = field(default_factory=list)
    decision_id: str = field(default_factory=lambda: new_id("decision"))
    created_at: str = field(default_factory=utc_now_iso)


@dataclass(slots=True)
class Artifact:
    campaign_id: str
    artifact_type: str
    name: str
    uri: str
    content_hash: str
    media_type: str = "application/octet-stream"
    artifact_id: str = field(default_factory=lambda: new_id("artifact"))
    created_at: str = field(default_factory=utc_now_iso)


@dataclass(slots=True)
class KnowledgeNode:
    campaign_id: str
    node_type: str
    payload: dict[str, Any]
    node_id: str = field(default_factory=lambda: new_id("node"))
    version: int = 1
    supersedes_version: int | None = None
    content_hash: str = ""
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        if self.node_type not in KNOWLEDGE_NODE_TYPES:
            raise ValueError(f"Unsupported knowledge node type: {self.node_type}")
        if self.version < 1:
            raise ValueError("Knowledge node version must be positive")
        expected_hash = canonical_hash(
            {"node_id": self.node_id, "node_type": self.node_type, "payload": self.payload, "version": self.version}
        )
        if self.content_hash and self.content_hash != expected_hash:
            raise CampaignIntegrityError(f"Knowledge node hash mismatch: {self.node_id}@{self.version}")
        self.content_hash = expected_hash


@dataclass(slots=True)
class KnowledgeEdge:
    campaign_id: str
    from_node_id: str
    to_node_id: str
    relation: str
    edge_id: str = field(default_factory=lambda: new_id("edge"))
    version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        if self.relation not in KNOWLEDGE_EDGE_TYPES:
            raise ValueError(f"Unsupported knowledge edge relation: {self.relation}")
        if self.from_node_id == self.to_node_id and self.relation != "supersedes":
            raise ValueError("Knowledge edges cannot self-reference")


@dataclass(slots=True)
class CampaignGraph:
    campaign_id: str
    nodes: list[KnowledgeNode] = field(default_factory=list)
    edges: list[KnowledgeEdge] = field(default_factory=list)
    _latest_cache: dict[str, KnowledgeNode] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        for node in self.nodes:
            if node.campaign_id != self.campaign_id:
                raise CampaignIntegrityError("Knowledge node belongs to another campaign")
            if node.node_id not in self._latest_cache or node.version > self._latest_cache[node.node_id].version:
                self._latest_cache[node.node_id] = node
        for edge in self.edges:
            if edge.campaign_id != self.campaign_id:
                raise CampaignIntegrityError("Knowledge edge belongs to another campaign")
            if edge.from_node_id not in self._latest_cache or edge.to_node_id not in self._latest_cache:
                raise CampaignIntegrityError(f"Knowledge edge has a missing endpoint: {edge.edge_id}")

    def latest_nodes(self) -> dict[str, KnowledgeNode]:
        return dict(self._latest_cache)

    def add_node(self, node_type: str, payload: dict[str, Any], *, node_id: str | None = None) -> KnowledgeNode:
        identifier = node_id or new_id("node")
        if identifier in self._latest_cache:
            raise CampaignConflictError(f"Knowledge node already exists: {identifier}")
        node = KnowledgeNode(campaign_id=self.campaign_id, node_type=node_type, payload=payload, node_id=identifier)
        self.nodes.append(node)
        self._latest_cache[identifier] = node
        return node

    def update_node(self, node_id: str, payload: dict[str, Any]) -> KnowledgeNode:
        current = self._latest_cache.get(node_id)
        if current is None:
            raise CampaignNotFoundError(f"Knowledge node not found: {node_id}")
        node = KnowledgeNode(
            campaign_id=self.campaign_id,
            node_type=current.node_type,
            payload=payload,
            node_id=node_id,
            version=current.version + 1,
            supersedes_version=current.version,
        )
        self.nodes.append(node)
        self._latest_cache[node_id] = node
        return node

    def add_edge(
        self,
        from_node_id: str,
        to_node_id: str,
        relation: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeEdge:
        latest = self.latest_nodes()
        missing = [identifier for identifier in (from_node_id, to_node_id) if identifier not in latest]
        if missing:
            raise CampaignNotFoundError(f"Knowledge edge endpoint not found: {', '.join(missing)}")
        edge = KnowledgeEdge(
            campaign_id=self.campaign_id,
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            relation=relation,
            metadata=metadata or {},
        )
        self.edges.append(edge)
        return edge

    def to_dict(self, *, latest_only: bool = False) -> dict[str, Any]:
        nodes = list(self.latest_nodes().values()) if latest_only else self.nodes
        return {
            "campaign_id": self.campaign_id,
            "nodes": [asdict(node) for node in nodes],
            "edges": [asdict(edge) for edge in self.edges],
            "graph_hash": canonical_hash(
                {"nodes": [asdict(node) for node in self.nodes], "edges": [asdict(edge) for edge in self.edges]}
            ),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CampaignGraph:
        return cls(
            campaign_id=str(payload["campaign_id"]),
            nodes=[KnowledgeNode(**item) for item in payload.get("nodes", [])],
            edges=[KnowledgeEdge(**item) for item in payload.get("edges", [])],
        )


@dataclass(slots=True)
class CampaignTimelineEvent:
    campaign_id: str
    event_type: str
    phase: str
    status: str
    summary: str
    revision: int
    metadata: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: new_id("event"))
    created_at: str = field(default_factory=utc_now_iso)


@dataclass(slots=True)
class CampaignTimeline:
    campaign_id: str
    events: list[CampaignTimelineEvent] = field(default_factory=list)

    def append(
        self,
        *,
        event_type: str,
        phase: CampaignPhase | str,
        status: CampaignStatus | str,
        summary: str,
        revision: int,
        metadata: dict[str, Any] | None = None,
    ) -> CampaignTimelineEvent:
        event = CampaignTimelineEvent(
            campaign_id=self.campaign_id,
            event_type=event_type,
            phase=CampaignPhase(phase).value,
            status=CampaignStatus(status).value,
            summary=summary,
            revision=revision,
            metadata=metadata or {},
        )
        self.events.append(event)
        return event


@dataclass(slots=True)
class CampaignRuntimeState:
    runtime_version: str = "2C.1"
    iteration: int = 0
    last_checkpoint_id: str = ""
    last_error: str = ""
    engine_versions: dict[str, str] = field(default_factory=dict)
    runner_versions: dict[str, str] = field(default_factory=dict)
    pending_hook: str = ""


@dataclass(slots=True)
class Checkpoint:
    campaign_id: str
    label: str
    iteration: int
    phase: str
    status: str
    revision: int
    state_snapshot: dict[str, Any]
    graph_snapshot: dict[str, Any]
    metadata: dict[str, Any]
    timing: dict[str, Any]
    engine_versions: dict[str, str]
    runner_versions: dict[str, str]
    hashes: dict[str, str]
    checkpoint_id: str = field(default_factory=lambda: new_id("checkpoint"))
    created_at: str = field(default_factory=utc_now_iso)

    def verify(self) -> None:
        expected = {
            "state": canonical_hash(self.state_snapshot),
            "graph": canonical_hash(self.graph_snapshot),
            "metadata": canonical_hash(self.metadata),
        }
        if any(self.hashes.get(key) != value for key, value in expected.items()):
            raise CampaignIntegrityError(f"Checkpoint hash mismatch: {self.checkpoint_id}")


@dataclass(slots=True)
class ResearchCampaign:
    campaign_id: str
    metadata: CampaignMetadata
    phase: CampaignPhase = CampaignPhase.PLANNING
    status: CampaignStatus = CampaignStatus.ACTIVE
    revision: int = 0
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    goals: list[CampaignGoal] = field(default_factory=list)
    questions: list[ResearchQuestion] = field(default_factory=list)
    hypotheses: list[Hypothesis] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    experiments: list[Experiment] = field(default_factory=list)
    models: list[ScientificModel] = field(default_factory=list)
    reviews: list[Review] = field(default_factory=list)
    failures: list[Failure] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    checkpoints: list[Checkpoint] = field(default_factory=list)
    graph: CampaignGraph | None = None
    timeline: CampaignTimeline | None = None
    budget: CampaignBudget = field(default_factory=CampaignBudget)
    statistics: CampaignStatistics = field(default_factory=CampaignStatistics)
    runtime: CampaignRuntimeState = field(default_factory=CampaignRuntimeState)
    idempotency_records: dict[str, dict[str, Any]] = field(default_factory=dict)

    _ENTITY_LISTS: ClassVar[dict[str, type[Any]]] = {
        "goals": CampaignGoal,
        "questions": ResearchQuestion,
        "hypotheses": Hypothesis,
        "evidence": Evidence,
        "experiments": Experiment,
        "models": ScientificModel,
        "reviews": Review,
        "failures": Failure,
        "decisions": Decision,
        "artifacts": Artifact,
        "checkpoints": Checkpoint,
    }

    def __post_init__(self) -> None:
        self.phase = CampaignPhase(self.phase)
        self.status = CampaignStatus(self.status)
        self.graph = self.graph or CampaignGraph(campaign_id=self.campaign_id)
        self.timeline = self.timeline or CampaignTimeline(campaign_id=self.campaign_id)
        if self.graph.campaign_id != self.campaign_id or self.timeline.campaign_id != self.campaign_id:
            raise CampaignIntegrityError("Campaign aggregate contains mismatched child identifiers")
        self.budget.validate()

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "metadata": asdict(self.metadata),
            "phase": self.phase.value,
            "status": self.status.value,
            "revision": self.revision,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            **{name: [asdict(item) for item in getattr(self, name)] for name in self._ENTITY_LISTS},
            "graph": self.graph.to_dict() if self.graph else {},
            "timeline": {
                "campaign_id": self.campaign_id,
                "events": [asdict(event) for event in (self.timeline.events if self.timeline else [])],
            },
            "budget": asdict(self.budget),
            "statistics": asdict(self.statistics),
            "runtime": asdict(self.runtime),
            "idempotency_records": self.idempotency_records,
        }

    def snapshot_state(self) -> dict[str, Any]:
        payload = self.to_dict()
        payload.pop("graph", None)
        payload.pop("checkpoints", None)
        payload.pop("idempotency_records", None)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ResearchCampaign:
        timeline_payload = payload.get("timeline", {})
        kwargs: dict[str, Any] = {
            "campaign_id": payload["campaign_id"],
            "metadata": CampaignMetadata(**payload["metadata"]),
            "phase": CampaignPhase(payload.get("phase", CampaignPhase.PLANNING)),
            "status": CampaignStatus(payload.get("status", CampaignStatus.ACTIVE)),
            "revision": int(payload.get("revision", 0)),
            "created_at": payload.get("created_at", utc_now_iso()),
            "updated_at": payload.get("updated_at", utc_now_iso()),
            "graph": CampaignGraph.from_dict(payload.get("graph", {"campaign_id": payload["campaign_id"]})),
            "timeline": CampaignTimeline(
                campaign_id=payload["campaign_id"],
                events=[CampaignTimelineEvent(**item) for item in timeline_payload.get("events", [])],
            ),
            "budget": CampaignBudget(**payload.get("budget", {})),
            "statistics": CampaignStatistics(**payload.get("statistics", {})),
            "runtime": CampaignRuntimeState(**payload.get("runtime", {})),
            "idempotency_records": dict(payload.get("idempotency_records", {})),
        }
        for name, entity_type in cls._ENTITY_LISTS.items():
            kwargs[name] = [entity_type(**item) for item in payload.get(name, [])]
        return cls(**kwargs)
