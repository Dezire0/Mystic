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
    ScientificJobReference,
    ScientificJobAttachmentReference,
    Artifact,
    Failure,
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

    def register_scientific_job_intent(
        self,
        *,
        campaign_id: str,
        job_id: str,
        job_type: str,
        engine_name: str,
        engine_version: str,
        source_campaign_revision: int,
        experiment_id: str = "",
        idempotency_key: str = "",
    ) -> ScientificJobReference:
        """Record an execution intent before any worker can lease the associated job."""
        for name, value, maximum in (
            ("job_id", job_id, 160),
            ("job_type", job_type, 80),
            ("engine_name", engine_name, 160),
            ("engine_version", engine_version, 80),
            ("experiment_id", experiment_id, 160),
            ("idempotency_key", idempotency_key, 240),
        ):
            self._validate_text(name, value, 0 if name in {"experiment_id", "idempotency_key"} else 1, maximum)
        if not isinstance(source_campaign_revision, int) or source_campaign_revision < 0:
            raise ValueError("source_campaign_revision must be a non-negative integer")
        campaign = self.get(campaign_id)
        existing = next((item for item in campaign.scientific_jobs if item.job_id == job_id), None)
        if existing is not None:
            if (
                existing.job_type == job_type
                and existing.engine_name == engine_name
                and existing.engine_version == engine_version
                and existing.source_campaign_revision == source_campaign_revision
                and existing.experiment_id == experiment_id
            ):
                return existing
            raise CampaignConflictError("Scientific job ID already belongs to another campaign intent")
        if self._idempotent(campaign, "scientific_job_intent", idempotency_key):
            raise CampaignConflictError("Scientific job idempotency record is missing its intent")
        if campaign.status != CampaignStatus.ACTIVE:
            raise IllegalCampaignTransition(f"Cannot create a scientific job from {campaign.status.value}")
        if campaign.revision != source_campaign_revision:
            raise CampaignConflictError(
                f"Scientific job source revision is stale: expected {source_campaign_revision}, found {campaign.revision}"
            )
        if experiment_id and not any(item.experiment_id == experiment_id for item in campaign.experiments):
            raise CampaignNotFoundError(f"Experiment not found for scientific job: {experiment_id}")
        expected_revision = campaign.revision
        self._touch(campaign)
        reference = ScientificJobReference(
            campaign_id=campaign_id,
            job_id=job_id,
            job_type=job_type,
            engine_name=engine_name,
            engine_version=engine_version,
            source_campaign_revision=source_campaign_revision,
            attachment_campaign_revision=campaign.revision,
            experiment_id=experiment_id,
            status="READY",
        )
        campaign.scientific_jobs.append(reference)
        self._sync_statistics(campaign)
        campaign.timeline.append(
            event_type="SCIENTIFIC_JOB_INTENT_CREATED",
            phase=campaign.phase,
            status=campaign.status,
            summary="Scientific engine job intent recorded for durable dispatch.",
            revision=campaign.revision,
            metadata={
                "job_id": job_id,
                "engine_name": engine_name,
                "engine_version": engine_version,
                "source_campaign_revision": source_campaign_revision,
            },
        )
        self._record_idempotency(campaign, "scientific_job_intent", idempotency_key)
        self.storage.save(campaign, expected_revision=expected_revision)
        return reference

    def attach_scientific_job_result(
        self,
        *,
        campaign_id: str,
        job_id: str,
        result_hash: str,
        expected_campaign_revision: int,
        engine_name: str,
        engine_version: str,
        attachment_key: str,
    ) -> ScientificJobAttachmentReference:
        """Apply one validated job result to campaign state exactly once logically."""
        for name, value, maximum in (
            ("job_id", job_id, 160),
            ("engine_name", engine_name, 160),
            ("engine_version", engine_version, 80),
            ("attachment_key", attachment_key, 240),
        ):
            self._validate_text(name, value, 1, maximum)
        if not isinstance(result_hash, str) or len(result_hash) != 64 or any(char not in "0123456789abcdef" for char in result_hash):
            raise ValueError("result_hash must be a SHA-256 hex digest")
        if not isinstance(expected_campaign_revision, int) or expected_campaign_revision < 0:
            raise ValueError("expected_campaign_revision must be a non-negative integer")
        campaign = self.get(campaign_id)
        existing = next((item for item in campaign.scientific_job_attachments if item.job_id == job_id), None)
        if existing is not None:
            if existing.result_hash == result_hash and existing.attachment_key == attachment_key:
                return existing
            raise CampaignConflictError("Conflicting scientific job result attachment was rejected")
        reference = next((item for item in campaign.scientific_jobs if item.job_id == job_id), None)
        if reference is None:
            raise CampaignConflictError("Scientific job is not referenced by the current campaign revision")
        if reference.attachment_campaign_revision != expected_campaign_revision:
            raise CampaignConflictError("Scientific job attachment revision does not match its campaign intent")
        if campaign.status != CampaignStatus.ACTIVE:
            raise IllegalCampaignTransition(f"Cannot attach a scientific job result to {campaign.status.value}")
        if campaign.revision != expected_campaign_revision:
            raise CampaignConflictError(
                f"Scientific job result is stale for campaign revision {campaign.revision}"
            )
        expected_revision = campaign.revision
        artifact = Artifact(
            campaign_id=campaign_id,
            artifact_type="scientific_job_result",
            name=f"Scientific job {job_id} result",
            uri=f"mystic://scientific-jobs/{job_id}/result",
            content_hash=result_hash,
            media_type="application/json",
        )
        campaign.artifacts.append(artifact)
        reference.status = "SUCCEEDED"
        self._touch(campaign)
        attachment = ScientificJobAttachmentReference(
            campaign_id=campaign_id,
            job_id=job_id,
            attachment_key=attachment_key,
            result_hash=result_hash,
            artifact_id=artifact.artifact_id,
            attached_campaign_revision=campaign.revision,
        )
        campaign.scientific_job_attachments.append(attachment)
        self._sync_statistics(campaign)
        campaign.timeline.append(
            event_type="SCIENTIFIC_JOB_RESULT_ATTACHED",
            phase=campaign.phase,
            status=campaign.status,
            summary="Scientific job result attached exactly once to campaign state.",
            revision=campaign.revision,
            metadata={
                "job_id": job_id,
                "result_hash": result_hash,
                "artifact_id": artifact.artifact_id,
                "engine_name": engine_name,
                "engine_version": engine_version,
            },
        )
        self._record_idempotency(campaign, "scientific_job_attachment", attachment_key)
        self.storage.save(campaign, expected_revision=expected_revision)
        return attachment

    def record_scientific_job_failure(
        self,
        *,
        campaign_id: str,
        job_id: str,
        expected_campaign_revision: int,
        failure_class: str,
        safe_error: str,
        retryable: bool,
    ) -> Failure:
        """Archive a terminal job failure through the campaign runtime, never a worker write."""
        self._validate_text("job_id", job_id, 1, 160)
        self._validate_text("failure_class", failure_class, 1, 80)
        self._validate_text("safe_error", safe_error, 1, 1000)
        if not isinstance(expected_campaign_revision, int) or expected_campaign_revision < 0:
            raise ValueError("expected_campaign_revision must be a non-negative integer")
        campaign = self.get(campaign_id)
        existing = next((item for item in campaign.failures if item.source_id == job_id), None)
        if existing is not None:
            if existing.failure_type == failure_class and existing.summary == safe_error:
                return existing
            raise CampaignConflictError("Conflicting scientific job failure was rejected")
        reference = next((item for item in campaign.scientific_jobs if item.job_id == job_id), None)
        if reference is None or reference.attachment_campaign_revision != expected_campaign_revision:
            raise CampaignConflictError("Scientific job failure is stale for the current campaign revision")
        if campaign.status != CampaignStatus.ACTIVE or campaign.revision != expected_campaign_revision:
            raise CampaignConflictError("Campaign cannot accept the terminal scientific job failure")
        expected_revision = campaign.revision
        failure = Failure(
            campaign_id=campaign_id,
            failure_type=failure_class,
            summary=safe_error,
            source_id=job_id,
            retryable=retryable,
            archived=True,
        )
        campaign.failures.append(failure)
        reference.status = "FAILED"
        self._touch(campaign)
        self._sync_statistics(campaign)
        campaign.timeline.append(
            event_type="SCIENTIFIC_JOB_FAILURE_ARCHIVED",
            phase=campaign.phase,
            status=campaign.status,
            summary="Terminal scientific job failure archived through the campaign runtime.",
            revision=campaign.revision,
            metadata={"job_id": job_id, "failure_class": failure_class},
        )
        self.storage.save(campaign, expected_revision=expected_revision)
        return failure

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
        campaign.statistics.scientific_job_count = len(campaign.scientific_jobs)
        campaign.statistics.scientific_job_attachment_count = len(campaign.scientific_job_attachments)
