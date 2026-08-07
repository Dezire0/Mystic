from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Protocol
import uuid

from mystic.lab.campaign import (
    CampaignBudget,
    CampaignBudgetExceeded,
    CampaignConflictError,
    CampaignGraph,
    CampaignMetadata,
    CampaignNotFoundError,
    CampaignPhase,
    CampaignStatus,
    Checkpoint,
    IllegalCampaignTransition,
    ResearchCampaign,
    CampaignGoal,
    ResearchQuestion,
    canonical_hash,
    utc_now_iso,
    validate_transition,
)
from mystic.lab.campaign_storage import CampaignStorage


class HypothesisGenerator(Protocol):
    def __call__(self, campaign: ResearchCampaign) -> dict[str, Any]: ...


class ExperimentPlanner(Protocol):
    def __call__(self, campaign: ResearchCampaign) -> dict[str, Any]: ...


class ModelSelector(Protocol):
    def __call__(self, campaign: ResearchCampaign) -> dict[str, Any]: ...


class Referee(Protocol):
    def __call__(self, campaign: ResearchCampaign) -> dict[str, Any]: ...


class ReportWriter(Protocol):
    def __call__(self, campaign: ResearchCampaign) -> dict[str, Any]: ...


HOOK_FOR_PHASE = {
    CampaignPhase.HYPOTHESIS_GENERATION: "hypothesis_generator",
    CampaignPhase.MODEL_SELECTION: "model_selector",
    CampaignPhase.EXPERIMENT_PLANNING: "experiment_planner",
    CampaignPhase.REFEREE_REVIEW: "referee",
    CampaignPhase.REPORT: "report_writer",
}


class CampaignRuntime:
    """Deterministic campaign coordinator. It contains no AI decision policy."""

    def __init__(self, root_path: str | Path, *, storage: CampaignStorage | None = None) -> None:
        self.root_path = Path(root_path)
        self.storage = storage or CampaignStorage(self.root_path)
        self._hooks: dict[str, Callable[[ResearchCampaign], dict[str, Any]]] = {}

    def register_hook(self, name: str, hook: Callable[[ResearchCampaign], dict[str, Any]]) -> None:
        if name not in set(HOOK_FOR_PHASE.values()):
            raise ValueError(f"Unsupported campaign hook: {name}")
        self._hooks[name] = hook

    def create_campaign(
        self,
        *,
        title: str,
        goal: str,
        question: str = "",
        description: str = "",
        domain: str = "general",
        tags: list[str] | None = None,
        budget: dict[str, Any] | None = None,
        idempotency_key: str = "",
    ) -> ResearchCampaign:
        self._validate_text("title", title, 1, 240)
        self._validate_text("goal", goal, 1, 4000)
        self._validate_text("question", question, 0, 4000)
        self._validate_text("description", description, 0, 8000)
        self._validate_text("domain", domain, 1, 80)
        self._validate_text("idempotency_key", idempotency_key, 0, 160)
        if len(tags or []) > 32 or any(not isinstance(tag, str) or len(tag) > 80 for tag in (tags or [])):
            raise ValueError("tags must contain at most 32 strings of at most 80 characters")
        campaign_id = (
            f"campaign_{uuid.uuid5(uuid.NAMESPACE_URL, f'mystic-campaign:{idempotency_key}').hex}"
            if idempotency_key
            else f"campaign_{uuid.uuid4().hex}"
        )
        if idempotency_key:
            try:
                return self.storage.load(campaign_id)
            except CampaignNotFoundError:
                pass
        allowed_budget_fields = {
            "max_iterations",
            "max_experiments",
            "max_engine_seconds",
            "max_graph_nodes",
            "max_graph_edges",
            "max_checkpoints",
        }
        unexpected_budget_fields = set((budget or {}).keys()) - allowed_budget_fields
        if unexpected_budget_fields:
            raise ValueError(f"Unsupported campaign budget fields: {', '.join(sorted(unexpected_budget_fields))}")
        campaign_budget = CampaignBudget(**(budget or {}))
        campaign_budget.validate()
        campaign = ResearchCampaign(
            campaign_id=campaign_id,
            metadata=CampaignMetadata(
                title=title,
                description=description,
                domain=domain,
                tags=list(tags or []),
            ),
            budget=campaign_budget,
        )
        campaign.goals.append(CampaignGoal(campaign_id=campaign_id, statement=goal))
        if question:
            campaign.questions.append(
                ResearchQuestion(campaign_id=campaign_id, text=question, goal_id=campaign.goals[0].goal_id)
            )
        campaign.timeline.append(
            event_type="CAMPAIGN_CREATED",
            phase=campaign.phase,
            status=campaign.status,
            summary="Research campaign created.",
            revision=campaign.revision,
        )
        self._touch(campaign)
        self._attach_checkpoint(campaign, label="initial", persist=False)
        self._record_idempotency(campaign, "create", idempotency_key)
        try:
            return self.storage.create(campaign)
        except CampaignConflictError:
            if idempotency_key:
                return self.storage.load(campaign_id)
            raise

    def get(self, campaign_id: str) -> ResearchCampaign:
        return self.storage.load(campaign_id)

    def list(self, *, limit: int = 50, status: str | None = None) -> list[ResearchCampaign]:
        if status:
            CampaignStatus(status)
        return self.storage.list(limit=limit, status=status)

    def transition(
        self,
        campaign_id: str,
        target_phase: CampaignPhase | str,
        *,
        idempotency_key: str = "",
    ) -> ResearchCampaign:
        campaign = self.get(campaign_id)
        cached = self._idempotent(campaign, "transition", idempotency_key)
        if cached:
            return campaign
        if campaign.status != CampaignStatus.ACTIVE:
            raise IllegalCampaignTransition(f"Campaign is not active: {campaign.status.value}")
        target = CampaignPhase(target_phase)
        validate_transition(campaign.phase, target)
        if campaign.budget.iterations_used >= campaign.budget.max_iterations:
            raise CampaignBudgetExceeded("Campaign iteration budget is exhausted")
        expected_revision = campaign.revision
        source = campaign.phase
        campaign.phase = target
        campaign.runtime.iteration += 1
        campaign.budget.iterations_used += 1
        campaign.statistics.transition_count += 1
        campaign.statistics.last_transition_at = utc_now_iso()
        campaign.runtime.pending_hook = HOOK_FOR_PHASE.get(target, "")
        if target == CampaignPhase.COMPLETE:
            campaign.status = CampaignStatus.COMPLETE
            campaign.statistics.completed_at = campaign.statistics.last_transition_at
        self._touch(campaign)
        campaign.timeline.append(
            event_type="PHASE_TRANSITION",
            phase=campaign.phase,
            status=campaign.status,
            summary=f"Campaign transitioned from {source.value} to {target.value}.",
            revision=campaign.revision,
            metadata={"from_phase": source.value, "to_phase": target.value},
        )
        self._attach_checkpoint(campaign, label=f"iteration-{campaign.runtime.iteration}")
        self._record_idempotency(campaign, "transition", idempotency_key)
        return self.storage.save(campaign, expected_revision=expected_revision)

    def run_hook(self, campaign_id: str) -> dict[str, Any]:
        campaign = self.get(campaign_id)
        hook_name = HOOK_FOR_PHASE.get(campaign.phase)
        if not hook_name:
            return {"status": "not_required", "phase": campaign.phase.value}
        hook = self._hooks.get(hook_name)
        if hook is None:
            return {"status": "deferred", "phase": campaign.phase.value, "required_hook": hook_name}
        return {"status": "completed", "phase": campaign.phase.value, "hook": hook_name, "output": hook(campaign)}

    def pause(self, campaign_id: str, *, idempotency_key: str = "") -> ResearchCampaign:
        return self._set_status(
            campaign_id,
            operation="pause",
            allowed={CampaignStatus.ACTIVE},
            target=CampaignStatus.PAUSED,
            summary="Research campaign paused.",
            idempotency_key=idempotency_key,
        )

    def resume(self, campaign_id: str, *, idempotency_key: str = "") -> ResearchCampaign:
        return self._set_status(
            campaign_id,
            operation="resume",
            allowed={CampaignStatus.PAUSED},
            target=CampaignStatus.ACTIVE,
            summary="Research campaign resumed.",
            idempotency_key=idempotency_key,
        )

    def cancel(self, campaign_id: str, *, idempotency_key: str = "") -> ResearchCampaign:
        return self._set_status(
            campaign_id,
            operation="cancel",
            allowed={CampaignStatus.ACTIVE, CampaignStatus.PAUSED, CampaignStatus.FAILED},
            target=CampaignStatus.CANCELLED,
            summary="Research campaign cancelled.",
            idempotency_key=idempotency_key,
        )

    def mark_failed(self, campaign_id: str, safe_error: str) -> ResearchCampaign:
        self._validate_text("safe_error", safe_error, 1, 1000)
        campaign = self.get(campaign_id)
        if campaign.status != CampaignStatus.ACTIVE:
            raise IllegalCampaignTransition(f"Cannot fail campaign from {campaign.status.value}")
        expected_revision = campaign.revision
        campaign.status = CampaignStatus.FAILED
        campaign.runtime.last_error = safe_error
        self._touch(campaign)
        campaign.timeline.append(
            event_type="CAMPAIGN_FAILED",
            phase=campaign.phase,
            status=campaign.status,
            summary="Research campaign failed safely.",
            revision=campaign.revision,
        )
        return self.storage.save(campaign, expected_revision=expected_revision)

    def retry(self, campaign_id: str, *, idempotency_key: str = "") -> ResearchCampaign:
        campaign = self._set_status(
            campaign_id,
            operation="retry",
            allowed={CampaignStatus.FAILED},
            target=CampaignStatus.ACTIVE,
            summary="Research campaign retry accepted.",
            idempotency_key=idempotency_key,
        )
        if campaign.runtime.last_error:
            expected_revision = campaign.revision
            campaign.runtime.last_error = ""
            campaign.statistics.retry_count += 1
            self._touch(campaign)
            campaign = self.storage.save(campaign, expected_revision=expected_revision)
        return campaign

    def checkpoint(
        self,
        campaign_id: str,
        *,
        label: str = "manual",
        idempotency_key: str = "",
    ) -> ResearchCampaign:
        self._validate_text("label", label, 1, 160)
        campaign = self.get(campaign_id)
        if self._idempotent(campaign, "checkpoint", idempotency_key):
            return campaign
        if len(campaign.checkpoints) >= campaign.budget.max_checkpoints:
            raise CampaignBudgetExceeded("Campaign checkpoint budget is exhausted")
        expected_revision = campaign.revision
        self._touch(campaign)
        self._attach_checkpoint(campaign, label=label)
        self._record_idempotency(campaign, "checkpoint", idempotency_key)
        return self.storage.save(campaign, expected_revision=expected_revision)

    def _attach_checkpoint(self, campaign: ResearchCampaign, *, label: str, persist: bool = True) -> Checkpoint:
        if len(campaign.checkpoints) >= campaign.budget.max_checkpoints:
            raise CampaignBudgetExceeded("Campaign checkpoint budget is exhausted")
        state_snapshot = campaign.snapshot_state()
        graph_snapshot = campaign.graph.to_dict() if campaign.graph else CampaignGraph(campaign.campaign_id).to_dict()
        checkpoint_metadata = {
            "campaign_schema_version": campaign.metadata.schema_version,
            "runtime_version": campaign.runtime.runtime_version,
            "label": label,
        }
        hashes = {
            "state": canonical_hash(state_snapshot),
            "graph": canonical_hash(graph_snapshot),
            "metadata": canonical_hash(checkpoint_metadata),
        }
        checkpoint = Checkpoint(
            campaign_id=campaign.campaign_id,
            label=label,
            iteration=campaign.runtime.iteration,
            phase=campaign.phase.value,
            status=campaign.status.value,
            revision=campaign.revision,
            state_snapshot=state_snapshot,
            graph_snapshot=graph_snapshot,
            metadata=checkpoint_metadata,
            timing={"created_at": utc_now_iso(), "iteration": campaign.runtime.iteration},
            engine_versions=dict(campaign.runtime.engine_versions),
            runner_versions=dict(campaign.runtime.runner_versions),
            hashes=hashes,
        )
        checkpoint.verify()
        if persist:
            self.storage.save_checkpoint(checkpoint)
        campaign.checkpoints.append(checkpoint)
        campaign.runtime.last_checkpoint_id = checkpoint.checkpoint_id
        campaign.statistics.checkpoint_count += 1
        campaign.timeline.append(
            event_type="CHECKPOINT_CREATED",
            phase=campaign.phase,
            status=campaign.status,
            summary=f"Checkpoint created: {label}.",
            revision=campaign.revision,
            metadata={"checkpoint_id": checkpoint.checkpoint_id},
        )
        return checkpoint

    def rollback(
        self,
        campaign_id: str,
        checkpoint_id: str,
        *,
        idempotency_key: str = "",
    ) -> ResearchCampaign:
        current = self.get(campaign_id)
        if self._idempotent(current, "rollback", idempotency_key):
            return current
        if current.status == CampaignStatus.CANCELLED:
            raise IllegalCampaignTransition("Cancelled campaigns cannot be rolled back")
        checkpoint = self.storage.load_checkpoint(campaign_id, checkpoint_id)
        checkpoint.verify()
        restored_payload = dict(checkpoint.state_snapshot)
        restored_payload["graph"] = checkpoint.graph_snapshot
        restored_payload["checkpoints"] = [asdict(item) for item in current.checkpoints]
        restored_payload["idempotency_records"] = dict(current.idempotency_records)
        restored = ResearchCampaign.from_dict(restored_payload)
        restored.revision = current.revision + 1
        restored.updated_at = utc_now_iso()
        restored.statistics.rollback_count = current.statistics.rollback_count + 1
        restored.timeline.events = list(current.timeline.events)
        restored.timeline.append(
            event_type="CAMPAIGN_ROLLBACK",
            phase=restored.phase,
            status=restored.status,
            summary=f"Campaign rolled back to checkpoint {checkpoint_id}.",
            revision=restored.revision,
            metadata={"checkpoint_id": checkpoint_id, "restored_revision": checkpoint.revision},
        )
        self._attach_checkpoint(restored, label=f"rollback-{checkpoint_id}")
        self._record_idempotency(restored, "rollback", idempotency_key)
        return self.storage.save(restored, expected_revision=current.revision)

    def graph(self, campaign_id: str, *, latest_only: bool = True) -> dict[str, Any]:
        campaign = self.get(campaign_id)
        return campaign.graph.to_dict(latest_only=latest_only) if campaign.graph else {}

    def add_knowledge_node(
        self,
        campaign_id: str,
        *,
        node_type: str,
        payload: dict[str, Any],
        node_id: str | None = None,
    ) -> dict[str, Any]:
        campaign = self.get(campaign_id)
        if campaign.status not in {CampaignStatus.ACTIVE, CampaignStatus.PAUSED}:
            raise IllegalCampaignTransition(f"Cannot update graph from {campaign.status.value}")
        graph = campaign.graph or CampaignGraph(campaign_id=campaign_id)
        if len(graph.latest_nodes()) >= campaign.budget.max_graph_nodes:
            raise CampaignBudgetExceeded("Campaign graph node budget is exhausted")
        expected_revision = campaign.revision
        node = graph.add_node(node_type, payload, node_id=node_id)
        campaign.graph = graph
        self._sync_statistics(campaign)
        self._touch(campaign)
        campaign.timeline.append(
            event_type="KNOWLEDGE_NODE_CREATED",
            phase=campaign.phase,
            status=campaign.status,
            summary=f"Versioned {node_type} knowledge node created.",
            revision=campaign.revision,
            metadata={"node_id": node.node_id, "version": node.version},
        )
        self.storage.save(campaign, expected_revision=expected_revision)
        return asdict(node)

    def update_knowledge_node(
        self,
        campaign_id: str,
        *,
        node_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        campaign = self.get(campaign_id)
        if campaign.status not in {CampaignStatus.ACTIVE, CampaignStatus.PAUSED}:
            raise IllegalCampaignTransition(f"Cannot update graph from {campaign.status.value}")
        graph = campaign.graph or CampaignGraph(campaign_id=campaign_id)
        expected_revision = campaign.revision
        node = graph.update_node(node_id, payload)
        campaign.graph = graph
        self._touch(campaign)
        campaign.timeline.append(
            event_type="KNOWLEDGE_NODE_VERSIONED",
            phase=campaign.phase,
            status=campaign.status,
            summary="Knowledge node version created.",
            revision=campaign.revision,
            metadata={"node_id": node.node_id, "version": node.version},
        )
        self.storage.save(campaign, expected_revision=expected_revision)
        return asdict(node)

    def add_knowledge_edge(
        self,
        campaign_id: str,
        *,
        from_node_id: str,
        to_node_id: str,
        relation: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        campaign = self.get(campaign_id)
        if campaign.status not in {CampaignStatus.ACTIVE, CampaignStatus.PAUSED}:
            raise IllegalCampaignTransition(f"Cannot update graph from {campaign.status.value}")
        graph = campaign.graph or CampaignGraph(campaign_id=campaign_id)
        if len(graph.edges) >= campaign.budget.max_graph_edges:
            raise CampaignBudgetExceeded("Campaign graph edge budget is exhausted")
        expected_revision = campaign.revision
        edge = graph.add_edge(from_node_id, to_node_id, relation, metadata=metadata)
        campaign.graph = graph
        self._sync_statistics(campaign)
        self._touch(campaign)
        campaign.timeline.append(
            event_type="KNOWLEDGE_EDGE_CREATED",
            phase=campaign.phase,
            status=campaign.status,
            summary=f"Knowledge relationship created: {relation}.",
            revision=campaign.revision,
            metadata={"edge_id": edge.edge_id},
        )
        self.storage.save(campaign, expected_revision=expected_revision)
        return asdict(edge)

    def timeline(self, campaign_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        campaign = self.get(campaign_id)
        events = campaign.timeline.events if campaign.timeline else []
        return [asdict(item) for item in events[-limit:]]

    def statistics(self, campaign_id: str) -> dict[str, Any]:
        campaign = self.get(campaign_id)
        self._sync_statistics(campaign)
        return {
            **asdict(campaign.statistics),
            "phase": campaign.phase.value,
            "status": campaign.status.value,
            "revision": campaign.revision,
            "iteration": campaign.runtime.iteration,
            "budget": asdict(campaign.budget),
        }

    def _set_status(
        self,
        campaign_id: str,
        *,
        operation: str,
        allowed: set[CampaignStatus],
        target: CampaignStatus,
        summary: str,
        idempotency_key: str,
    ) -> ResearchCampaign:
        campaign = self.get(campaign_id)
        if self._idempotent(campaign, operation, idempotency_key):
            return campaign
        if campaign.status not in allowed:
            raise IllegalCampaignTransition(
                f"Cannot {operation} campaign from {campaign.status.value}"
            )
        expected_revision = campaign.revision
        campaign.status = target
        self._touch(campaign)
        campaign.timeline.append(
            event_type=f"CAMPAIGN_{operation.upper()}",
            phase=campaign.phase,
            status=campaign.status,
            summary=summary,
            revision=campaign.revision,
        )
        self._record_idempotency(campaign, operation, idempotency_key)
        return self.storage.save(campaign, expected_revision=expected_revision)

    @staticmethod
    def _touch(campaign: ResearchCampaign) -> None:
        campaign.revision += 1
        campaign.updated_at = utc_now_iso()

    @staticmethod
    def _validate_text(name: str, value: str, minimum: int, maximum: int) -> None:
        if not isinstance(value, str) or len(value.strip()) < minimum or len(value) > maximum:
            raise ValueError(f"{name} must contain between {minimum} and {maximum} characters")

    @staticmethod
    def _idempotent(campaign: ResearchCampaign, operation: str, key: str) -> bool:
        if not key:
            return False
        record = campaign.idempotency_records.get(key)
        if not record:
            return False
        if record.get("operation") != operation:
            raise CampaignConflictError("Idempotency key was already used for another operation")
        return True

    @staticmethod
    def _record_idempotency(campaign: ResearchCampaign, operation: str, key: str) -> None:
        if not key:
            return
        campaign.idempotency_records[key] = {
            "operation": operation,
            "revision": campaign.revision,
            "recorded_at": utc_now_iso(),
        }
        while len(campaign.idempotency_records) > 256:
            campaign.idempotency_records.pop(next(iter(campaign.idempotency_records)))

    @staticmethod
    def _sync_statistics(campaign: ResearchCampaign) -> None:
        campaign.statistics.graph_node_count = len(campaign.graph.latest_nodes()) if campaign.graph else 0
        campaign.statistics.graph_edge_count = len(campaign.graph.edges) if campaign.graph else 0
        campaign.statistics.evidence_count = len(campaign.evidence)
        campaign.statistics.experiment_count = len(campaign.experiments)
        campaign.statistics.failure_count = len(campaign.failures)
