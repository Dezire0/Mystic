from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

from mystic.lab.campaign import (
    ALLOWED_PHASE_TRANSITIONS,
    Artifact,
    CampaignBudget,
    CampaignConflictError,
    CampaignGraph,
    CampaignIntegrityError,
    CampaignMetadata,
    CampaignNotFoundError,
    CampaignPhase,
    CampaignStatistics,
    CampaignStatus,
    CampaignTimeline,
    Checkpoint,
    Decision,
    Evidence,
    Experiment,
    Failure,
    Hypothesis,
    IllegalCampaignTransition,
    KnowledgeEdge,
    KnowledgeNode,
    ResearchCampaign,
    ResearchQuestion,
    Review,
    ScientificModel,
    CampaignGoal,
    canonical_hash,
    validate_transition,
)
from mystic.lab.campaign_runtime import CampaignRuntime
from mystic.lab.campaign_storage import CampaignStorage
from mystic.mcp.schemas import PUBLIC_TOOL_NAMES, TOOL_SCHEMAS
from mystic.mcp.tools import MysticToolbox


class CampaignRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.runtime = CampaignRuntime(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def create(self, **overrides: object) -> ResearchCampaign:
        values: dict[str, object] = {"title": "Deterministic campaign", "goal": "Test the runtime", "question": "Does it persist?"}
        values.update(overrides)
        return self.runtime.create_campaign(**values)  # type: ignore[arg-type]

    def test_create_persists_typed_aggregate_and_initial_checkpoint(self) -> None:
        campaign = self.create()
        self.assertEqual(campaign.phase, CampaignPhase.PLANNING)
        self.assertEqual(campaign.status, CampaignStatus.ACTIVE)
        self.assertEqual(len(campaign.goals), 1)
        self.assertEqual(len(campaign.questions), 1)
        self.assertEqual(len(campaign.checkpoints), 1)
        self.assertTrue(self.runtime.storage.campaign_path(campaign.campaign_id).exists())

    def test_create_idempotency_key_returns_same_campaign(self) -> None:
        first = self.create(idempotency_key="same-create")
        second = self.create(idempotency_key="same-create")
        self.assertEqual(first.campaign_id, second.campaign_id)
        self.assertEqual(len(self.runtime.list()), 1)

    def test_concurrent_idempotent_create_returns_one_durable_campaign(self) -> None:
        barrier = threading.Barrier(4)
        results: list[ResearchCampaign] = []

        def create_campaign() -> None:
            barrier.wait()
            results.append(self.create(idempotency_key="concurrent-create"))

        threads = [threading.Thread(target=create_campaign) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(results), 4)
        self.assertEqual({item.campaign_id for item in results}, {results[0].campaign_id})
        persisted = self.runtime.get(results[0].campaign_id)
        self.assertEqual(len(persisted.checkpoints), 1)
        self.assertTrue(
            self.runtime.storage.checkpoint_path(
                persisted.campaign_id, persisted.checkpoints[0].checkpoint_id
            ).exists()
        )

    def test_create_rejects_runtime_owned_budget_usage(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported campaign budget fields"):
            self.create(budget={"iterations_used": 1})

    def test_restart_loads_identical_campaign(self) -> None:
        created = self.create()
        restarted = CampaignRuntime(self.root).get(created.campaign_id)
        self.assertEqual(restarted.to_dict(), created.to_dict())

    def test_full_linear_lifecycle_completes(self) -> None:
        campaign = self.create()
        targets = [
            CampaignPhase.BACKGROUND_RESEARCH, CampaignPhase.KNOWLEDGE_GRAPH,
            CampaignPhase.HYPOTHESIS_GENERATION, CampaignPhase.MODEL_SELECTION,
            CampaignPhase.EXPERIMENT_PLANNING, CampaignPhase.ENGINE_EXECUTION,
            CampaignPhase.RESULT_VALIDATION, CampaignPhase.REFEREE_REVIEW,
            CampaignPhase.FAILURE_ARCHIVE, CampaignPhase.KNOWLEDGE_UPDATE,
            CampaignPhase.NEXT_ACTION, CampaignPhase.REPORT, CampaignPhase.COMPLETE,
        ]
        for index, target in enumerate(targets, 1):
            campaign = self.runtime.transition(campaign.campaign_id, target, idempotency_key=f"step-{index}")
        self.assertEqual(campaign.status, CampaignStatus.COMPLETE)
        self.assertEqual(campaign.runtime.iteration, 13)
        self.assertEqual(campaign.statistics.transition_count, 13)
        self.assertEqual(len(campaign.checkpoints), 14)

    def test_next_action_can_loop_to_hypothesis_generation(self) -> None:
        campaign = self.create()
        for target in list(CampaignPhase)[1:12]:
            campaign = self.runtime.transition(campaign.campaign_id, target)
        campaign = self.runtime.transition(campaign.campaign_id, CampaignPhase.HYPOTHESIS_GENERATION)
        self.assertEqual(campaign.phase, CampaignPhase.HYPOTHESIS_GENERATION)

    def test_illegal_transition_does_not_change_persisted_state(self) -> None:
        campaign = self.create()
        with self.assertRaises(IllegalCampaignTransition):
            self.runtime.transition(campaign.campaign_id, CampaignPhase.ENGINE_EXECUTION)
        persisted = self.runtime.get(campaign.campaign_id)
        self.assertEqual(persisted.phase, CampaignPhase.PLANNING)
        self.assertEqual(persisted.revision, campaign.revision)

    def test_transition_and_iteration_checkpoint_share_one_commit_revision(self) -> None:
        campaign = self.create()
        previous_revision = campaign.revision
        transitioned = self.runtime.transition(campaign.campaign_id, CampaignPhase.BACKGROUND_RESEARCH)
        self.assertEqual(transitioned.revision, previous_revision + 1)
        self.assertEqual(transitioned.checkpoints[-1].revision, transitioned.revision)

    def test_pause_resume_preserves_phase(self) -> None:
        campaign = self.create()
        campaign = self.runtime.transition(campaign.campaign_id, CampaignPhase.BACKGROUND_RESEARCH)
        paused = self.runtime.pause(campaign.campaign_id)
        resumed = self.runtime.resume(campaign.campaign_id)
        self.assertEqual(paused.phase, CampaignPhase.BACKGROUND_RESEARCH)
        self.assertEqual(resumed.phase, CampaignPhase.BACKGROUND_RESEARCH)
        self.assertEqual(resumed.status, CampaignStatus.ACTIVE)

    def test_pause_is_idempotent_with_same_key(self) -> None:
        campaign = self.create()
        first = self.runtime.pause(campaign.campaign_id, idempotency_key="pause-1")
        second = self.runtime.pause(campaign.campaign_id, idempotency_key="pause-1")
        self.assertEqual(first.revision, second.revision)

    def test_idempotency_key_cannot_be_reused_for_other_operation(self) -> None:
        campaign = self.create()
        self.runtime.pause(campaign.campaign_id, idempotency_key="control-1")
        with self.assertRaises(CampaignConflictError):
            self.runtime.resume(campaign.campaign_id, idempotency_key="control-1")

    def test_cancel_is_terminal_for_controls(self) -> None:
        campaign = self.runtime.cancel(self.create().campaign_id)
        with self.assertRaises(IllegalCampaignTransition):
            self.runtime.resume(campaign.campaign_id)
        with self.assertRaises(IllegalCampaignTransition):
            self.runtime.transition(campaign.campaign_id, CampaignPhase.BACKGROUND_RESEARCH)

    def test_failed_campaign_can_retry_same_phase(self) -> None:
        campaign = self.create()
        failed = self.runtime.mark_failed(campaign.campaign_id, "safe failure")
        retried = self.runtime.retry(failed.campaign_id)
        self.assertEqual(retried.status, CampaignStatus.ACTIVE)
        self.assertEqual(retried.phase, CampaignPhase.PLANNING)
        self.assertEqual(retried.runtime.last_error, "")
        self.assertEqual(retried.statistics.retry_count, 1)

    def test_transition_budget_is_enforced(self) -> None:
        campaign = self.create(budget={"max_iterations": 1})
        campaign = self.runtime.transition(campaign.campaign_id, CampaignPhase.BACKGROUND_RESEARCH)
        with self.assertRaisesRegex(RuntimeError, "budget"):
            self.runtime.transition(campaign.campaign_id, CampaignPhase.KNOWLEDGE_GRAPH)

    def test_checkpoint_is_integrity_hashed(self) -> None:
        checkpoint = self.create().checkpoints[0]
        checkpoint.verify()
        self.assertEqual(len(checkpoint.hashes["state"]), 64)
        self.assertEqual(len(checkpoint.hashes["graph"]), 64)

    def test_checkpoint_survives_restart(self) -> None:
        campaign = self.create()
        checkpoint_id = campaign.checkpoints[0].checkpoint_id
        checkpoint = CampaignRuntime(self.root).storage.load_checkpoint(campaign.campaign_id, checkpoint_id)
        checkpoint.verify()
        self.assertEqual(checkpoint.phase, CampaignPhase.PLANNING.value)

    def test_corrupt_checkpoint_is_rejected(self) -> None:
        campaign = self.create()
        checkpoint = campaign.checkpoints[0]
        path = self.runtime.storage.checkpoint_path(campaign.campaign_id, checkpoint.checkpoint_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["state_snapshot"]["phase"] = "REPORT"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(CampaignIntegrityError):
            self.runtime.storage.load_checkpoint(campaign.campaign_id, checkpoint.checkpoint_id)

    def test_rollback_restores_phase_and_preserves_audit(self) -> None:
        campaign = self.create()
        checkpoint_id = campaign.checkpoints[0].checkpoint_id
        campaign = self.runtime.transition(campaign.campaign_id, CampaignPhase.BACKGROUND_RESEARCH)
        campaign = self.runtime.transition(campaign.campaign_id, CampaignPhase.KNOWLEDGE_GRAPH)
        rolled_back = self.runtime.rollback(campaign.campaign_id, checkpoint_id)
        self.assertEqual(rolled_back.phase, CampaignPhase.PLANNING)
        self.assertEqual(rolled_back.statistics.rollback_count, 1)
        self.assertIn("CAMPAIGN_ROLLBACK", [event.event_type for event in rolled_back.timeline.events])

    def test_cancelled_campaign_cannot_rollback(self) -> None:
        campaign = self.create()
        checkpoint_id = campaign.checkpoints[0].checkpoint_id
        campaign = self.runtime.cancel(campaign.campaign_id)
        with self.assertRaises(IllegalCampaignTransition):
            self.runtime.rollback(campaign.campaign_id, checkpoint_id)

    def test_graph_nodes_are_versioned_and_hashed(self) -> None:
        campaign = self.create()
        node = self.runtime.add_knowledge_node(campaign.campaign_id, node_type="claim", payload={"text": "A"})
        updated = self.runtime.update_knowledge_node(campaign.campaign_id, node_id=str(node["node_id"]), payload={"text": "B"})
        graph = self.runtime.graph(campaign.campaign_id, latest_only=False)
        self.assertEqual(updated["version"], 2)
        self.assertEqual(len(graph["nodes"]), 2)
        self.assertEqual(len(graph["graph_hash"]), 64)

    def test_graph_edge_requires_existing_endpoints(self) -> None:
        campaign = self.create()
        with self.assertRaises(CampaignNotFoundError):
            self.runtime.add_knowledge_edge(campaign.campaign_id, from_node_id="missing-a", to_node_id="missing-b", relation="supports")

    def test_graph_deserialization_rejects_dangling_edge(self) -> None:
        with self.assertRaisesRegex(CampaignIntegrityError, "missing endpoint"):
            CampaignGraph.from_dict(
                {
                    "campaign_id": "campaign_integrity",
                    "nodes": [],
                    "edges": [
                        {
                            "campaign_id": "campaign_integrity",
                            "from_node_id": "missing-a",
                            "to_node_id": "missing-b",
                            "relation": "supports",
                        }
                    ],
                }
            )

    def test_graph_edge_persists_supported_relationships(self) -> None:
        campaign = self.create()
        claim = self.runtime.add_knowledge_node(campaign.campaign_id, node_type="claim", payload={"text": "A"})
        evidence = self.runtime.add_knowledge_node(campaign.campaign_id, node_type="evidence", payload={"summary": "E"})
        edge = self.runtime.add_knowledge_edge(campaign.campaign_id, from_node_id=str(evidence["node_id"]), to_node_id=str(claim["node_id"]), relation="supports")
        self.assertEqual(edge["relation"], "supports")
        self.assertEqual(self.runtime.statistics(campaign.campaign_id)["graph_edge_count"], 1)

    def test_graph_budget_is_enforced(self) -> None:
        campaign = self.create(budget={"max_graph_nodes": 1})
        self.runtime.add_knowledge_node(campaign.campaign_id, node_type="claim", payload={})
        with self.assertRaisesRegex(RuntimeError, "budget"):
            self.runtime.add_knowledge_node(campaign.campaign_id, node_type="evidence", payload={})

    def test_checkpointed_graph_is_restored_by_rollback(self) -> None:
        campaign = self.create()
        node = self.runtime.add_knowledge_node(campaign.campaign_id, node_type="claim", payload={"text": "v1"})
        campaign = self.runtime.checkpoint(campaign.campaign_id, label="graph-v1")
        checkpoint_id = campaign.checkpoints[-1].checkpoint_id
        self.runtime.update_knowledge_node(campaign.campaign_id, node_id=str(node["node_id"]), payload={"text": "v2"})
        restored = self.runtime.rollback(campaign.campaign_id, checkpoint_id)
        self.assertEqual(restored.graph.latest_nodes()[str(node["node_id"])].payload["text"], "v1")

    def test_optimistic_concurrency_rejects_stale_write(self) -> None:
        campaign = self.create()
        first = self.runtime.storage.load(campaign.campaign_id)
        second = self.runtime.storage.load(campaign.campaign_id)
        first.revision += 1
        second.revision += 1
        self.runtime.storage.save(first, expected_revision=campaign.revision)
        with self.assertRaises(CampaignConflictError):
            self.runtime.storage.save(second, expected_revision=campaign.revision)

    def test_concurrent_writers_never_corrupt_campaign_json(self) -> None:
        campaign = self.create()
        successes: list[int] = []
        conflicts: list[int] = []
        barrier = threading.Barrier(8)
        def write(index: int) -> None:
            stale = self.runtime.storage.load(campaign.campaign_id)
            barrier.wait()
            stale.revision += 1
            try:
                self.runtime.storage.save(stale, expected_revision=campaign.revision)
                successes.append(index)
            except CampaignConflictError:
                conflicts.append(index)
        threads = [threading.Thread(target=write, args=(index,)) for index in range(8)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(conflicts), 7)
        self.assertEqual(self.runtime.get(campaign.campaign_id).revision, campaign.revision + 1)

    def test_missing_hook_is_deferred_without_state_change(self) -> None:
        campaign = self.create()
        for target in [CampaignPhase.BACKGROUND_RESEARCH, CampaignPhase.KNOWLEDGE_GRAPH, CampaignPhase.HYPOTHESIS_GENERATION]:
            campaign = self.runtime.transition(campaign.campaign_id, target)
        revision = campaign.revision
        result = self.runtime.run_hook(campaign.campaign_id)
        self.assertEqual(result["status"], "deferred")
        self.assertEqual(self.runtime.get(campaign.campaign_id).revision, revision)

    def test_registered_hook_receives_typed_campaign(self) -> None:
        campaign = self.create()
        for target in [CampaignPhase.BACKGROUND_RESEARCH, CampaignPhase.KNOWLEDGE_GRAPH, CampaignPhase.HYPOTHESIS_GENERATION]:
            campaign = self.runtime.transition(campaign.campaign_id, target)
        self.runtime.register_hook("hypothesis_generator", lambda value: {"campaign_id": value.campaign_id})
        result = self.runtime.run_hook(campaign.campaign_id)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["output"]["campaign_id"], campaign.campaign_id)

    def test_timeline_is_bounded_and_chronological(self) -> None:
        campaign = self.create()
        self.runtime.pause(campaign.campaign_id)
        self.runtime.resume(campaign.campaign_id)
        events = self.runtime.timeline(campaign.campaign_id, limit=2)
        self.assertEqual([event["event_type"] for event in events], ["CAMPAIGN_PAUSE", "CAMPAIGN_RESUME"])

    def test_list_filters_status(self) -> None:
        active = self.create(title="Active")
        cancelled = self.create(title="Cancelled")
        self.runtime.cancel(cancelled.campaign_id)
        self.assertEqual([item.campaign_id for item in self.runtime.list(status="ACTIVE")], [active.campaign_id])

    def test_storage_rejects_path_traversal_identifier(self) -> None:
        with self.assertRaises(ValueError):
            self.runtime.storage.load("../secret")

    def test_graph_operations_are_bounded_performance(self) -> None:
        graph = CampaignGraph("campaign_perf")
        started = time.perf_counter()
        for index in range(1000):
            graph.add_node("claim", {"index": index}, node_id=f"node_{index}")
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 5.0)
        self.assertEqual(len(graph.latest_nodes()), 1000)

    def test_all_requested_entities_round_trip_in_campaign(self) -> None:
        campaign = self.create()
        identifier = campaign.campaign_id
        campaign.hypotheses.append(Hypothesis(identifier, "H"))
        campaign.evidence.append(Evidence(identifier, "E", "simulation"))
        campaign.experiments.append(Experiment(identifier, "Q", "engine"))
        campaign.models.append(ScientificModel(identifier, "M", "deterministic", "1"))
        campaign.reviews.append(Review(identifier, "subject", "INCONCLUSIVE", "R"))
        campaign.failures.append(Failure(identifier, "runtime", "F"))
        campaign.decisions.append(Decision(identifier, "next_action", "REPORT", "D"))
        campaign.artifacts.append(Artifact(identifier, "report", "A", "mystic://a", "0" * 64))
        restored = ResearchCampaign.from_dict(campaign.to_dict())
        self.assertEqual(restored.to_dict(), campaign.to_dict())

    def test_canonical_hash_is_key_order_independent(self) -> None:
        self.assertEqual(canonical_hash({"a": 1, "b": 2}), canonical_hash({"b": 2, "a": 1}))

    def test_mcp_inventory_contains_exact_campaign_tools(self) -> None:
        requested = {
            "lab_campaign_create", "lab_campaign_get", "lab_campaign_list", "lab_campaign_pause",
            "lab_campaign_resume", "lab_campaign_cancel", "lab_campaign_checkpoint", "lab_campaign_graph",
            "lab_campaign_timeline", "lab_campaign_statistics",
        }
        self.assertTrue(requested.issubset(PUBLIC_TOOL_NAMES))
        self.assertTrue(requested.issubset(TOOL_SCHEMAS))

    def test_toolbox_campaign_payload_omits_private_snapshots_and_idempotency(self) -> None:
        toolbox = MysticToolbox.__new__(MysticToolbox)
        toolbox.campaign_runtime = self.runtime
        payload = toolbox.lab_campaign_create(title="MCP", goal="Safe output", idempotency_key="mcp-create")
        self.assertNotIn("idempotency_records", payload)
        self.assertNotIn("state_snapshot", payload["checkpoints"][0])
        fetched = toolbox.lab_campaign_get(campaign_id=payload["campaign_id"])
        self.assertEqual(fetched["campaign_id"], payload["campaign_id"])


class CampaignTransitionMatrixTests(unittest.TestCase):
    """One discovered case for every source/target pair guards the complete contract."""


def _transition_case(source: CampaignPhase, target: CampaignPhase):
    def test(self: CampaignTransitionMatrixTests) -> None:
        allowed = target in ALLOWED_PHASE_TRANSITIONS[source]
        if allowed:
            validate_transition(source, target)
        else:
            with self.assertRaises(IllegalCampaignTransition):
                validate_transition(source, target)
    return test


for _source in CampaignPhase:
    for _target in CampaignPhase:
        setattr(
            CampaignTransitionMatrixTests,
            f"test_transition_{_source.value.lower()}_to_{_target.value.lower()}",
            _transition_case(_source, _target),
        )
