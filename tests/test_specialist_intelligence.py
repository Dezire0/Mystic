from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest

from fastapi.testclient import TestClient

from mystic.app.api import create_app
from mystic.app.pages import EvidencePage, SpecialistDetailPage, SpecialistsPage
from mystic.lab.campaign_runtime import CampaignRuntime
from mystic.lab.evidence import (
    DeterministicFixtureSpecialistProvider,
    DocumentIngestRequest,
    SpecialistEvidenceService,
)
from mystic.lab.specialist_benchmarks import BenchmarkCase, SpecialistBenchmarkHarness
from mystic.lab.specialists import (
    BenchmarkStatus,
    SpecialistClassification,
    SpecialistExecutionResult,
    SpecialistFailureType,
    SpecialistModel,
    SpecialistModelRegistry,
    SpecialistRuntime,
    SpecialistTaskRequest,
)
from mystic.lab.scientific_job_runtime import ScientificJobRuntime
from mystic.mcp.server import MysticMCPServer
from mystic.mcp.tools import MysticToolbox


class _UnavailableProvider:
    provider_id = "unavailable_fixture"

    def health(self) -> str:
        return "healthy"

    def execute(self, *, model, operation, payload):
        del payload
        return SpecialistExecutionResult(
            specialist_id=model.specialist_id,
            provider=model.provider,
            operation=operation,
            status="failed",
            failure_type=SpecialistFailureType.UNAVAILABLE.value,
            safe_error="Fixture primary unavailable.",
        )


def _fixture_model(
    specialist_id: str,
    role: str,
    *,
    provider: str = "fixture",
    fallback_ids: list[str] | None = None,
    quality: float = 0.9,
) -> SpecialistModel:
    return SpecialistModel(
        specialist_id=specialist_id,
        provider=provider,
        model_id=specialist_id,
        version="test-v1",
        role=role,
        modalities=["text"],
        domains=["*"],
        capabilities=["fixture"],
        languages=["*"],
        max_input=100_000,
        expected_latency_class="low",
        expected_cost_class="free",
        local_or_remote="local",
        free_endpoint_available=True,
        deterministic_or_nondeterministic="deterministic",
        trust_level="test_only",
        enabled=True,
        health="healthy",
        benchmark_status=BenchmarkStatus.APPROVED.value,
        fallback_ids=fallback_ids or [],
        limitations=["Fixture test model only."],
        license_metadata={"test": "true"},
        classification=SpecialistClassification.ACCELERATOR.value,
        benchmark_quality=quality,
        reliability=1.0,
    )


class SpecialistIntelligenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        registry = SpecialistModelRegistry(
            [
                _fixture_model("fixture.embed", "text_embedding"),
                _fixture_model("fixture.rerank", "text_reranking"),
            ]
        )
        self.runtime = SpecialistRuntime(
            registry=registry,
            providers={"fixture": DeterministicFixtureSpecialistProvider()},
            root_path=self.root,
        )
        self.service = SpecialistEvidenceService(root_path=self.root, runtime=self.runtime)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_default_registry_has_all_candidate_roles_disabled_and_unclassified(self):
        registry = SpecialistModelRegistry()
        models = registry.list()
        self.assertEqual(len(models), 11)
        self.assertTrue(all(not model.enabled for model in models))
        self.assertTrue(all(model.classification == "unclassified" for model in models))
        self.assertEqual(registry.get("nvidia.nemotron-3-embed-1b").fallback_ids, ["nvidia.llama-nemotron-embed-1b-v2"])
        self.assertEqual(registry.get("nvidia.nv-embedcode-7b-v1").role, "code_embedding")

    def test_router_refuses_unapproved_candidates_without_selecting_by_size(self):
        runtime = SpecialistRuntime(registry=SpecialistModelRegistry(), root_path=self.root)
        match = runtime.router.match(SpecialistTaskRequest(task="retrieve_scientific_evidence", modality="text"))
        self.assertEqual(match.status, "unavailable")
        self.assertIsNone(match.specialist)
        self.assertIn("benchmark-approved", match.reason)

    def test_router_records_explicit_approved_fallback(self):
        registry = SpecialistModelRegistry(
            [
                _fixture_model(
                    "fixture.primary",
                    "text_embedding",
                    provider="unavailable_fixture",
                    fallback_ids=["fixture.fallback"],
                    quality=1.0,
                ),
                _fixture_model("fixture.fallback", "text_embedding", quality=0.8),
            ]
        )
        runtime = SpecialistRuntime(
            registry=registry,
            providers={
                "fixture": DeterministicFixtureSpecialistProvider(),
                "unavailable_fixture": _UnavailableProvider(),
            },
            root_path=self.root,
        )
        result = runtime.execute(
            SpecialistTaskRequest(task="retrieve_scientific_evidence", modality="text"),
            operation="embed",
            payload={"text": "gravity affects projectile motion"},
        )
        self.assertTrue(result.succeeded)
        self.assertTrue(result.used_fallback)
        self.assertEqual(result.specialist_id, "fixture.fallback")
        self.assertEqual(runtime.usage.summary()["fallback_calls"], 1)

    def test_text_ingestion_search_provenance_and_campaign_attachment(self):
        ingested = self.service.ingest(
            DocumentIngestRequest(
                source_id="paper-42",
                source_type="paper",
                title="Projectile experiments",
                mime_type="text/markdown",
                content="Gravity affects projectile range. Air resistance can reduce the observed range.",
                domain="physics",
            )
        )
        self.assertEqual(ingested.status, "indexed")
        self.assertEqual(len(ingested.evidence), 1)
        evidence = ingested.evidence[0]
        self.assertEqual([step.stage for step in evidence.provenance], ["source", "normalize", "chunk", "embedding"])
        search = self.service.search(query="How does gravity affect projectile range?", domain="physics")
        self.assertEqual(search["status"], "ok")
        self.assertEqual(search["count"], 1)
        stages = [step["stage"] for step in search["evidence"][0]["provenance"]]
        self.assertEqual(stages[-2:], ["retrieval", "rerank"])
        campaigns = CampaignRuntime(self.root)
        campaign = campaigns.create_campaign(title="Projectile research", goal="Trace evidence")
        attached = self.service.attach_to_campaign(
            campaign_runtime=campaigns,
            campaign_id=campaign.campaign_id,
            evidence_id=evidence.evidence_id,
        )
        self.assertFalse(attached["duplicate"])
        persisted = campaigns.get(campaign.campaign_id)
        self.assertEqual(len(persisted.evidence), 1)
        self.assertEqual(len(persisted.artifacts), 1)
        self.assertEqual(persisted.timeline.events[-1].event_type, "SPECIALIST_EVIDENCE_ATTACHED")
        jobs = ScientificJobRuntime(self.root, campaign_runtime=campaigns)
        job = jobs.create_job(
            campaign_id=campaign.campaign_id,
            engine_name="physics.simple_projectile",
            input_payload={
                "initial_position": [0, 0, 0],
                "initial_velocity": [1, 4, 0],
                "duration_seconds": 1,
            },
        )
        input_hash = job.input_hash
        linked = self.service.link_to_scientific_job(
            job_runtime=jobs,
            campaign_id=campaign.campaign_id,
            job_id=job.job_id,
            evidence_ids=[evidence.evidence_id],
        )
        self.assertEqual(linked["mode"], "reference_only")
        self.assertNotIn("Gravity affects", str(linked))
        self.assertEqual(jobs.get(job.job_id).input_hash, input_hash)

    def test_scanned_document_requires_specialist_and_does_not_create_text_evidence(self):
        result = self.service.ingest(
            DocumentIngestRequest(
                source_id="scan-1",
                source_type="paper",
                title="Scanned paper",
                mime_type="application/pdf",
                content="untrusted extracted placeholder",
                scanned=True,
            )
        )
        self.assertEqual(result.status, "specialist_required")
        self.assertEqual(result.routing_plan.required_tasks, ["extract_document_text"])
        self.assertEqual(result.evidence, [])
        self.assertIn("untrusted data", result.warnings[0])

    def test_benchmark_metrics_cover_ranking_ocr_parsing_and_fixture_cannot_approve_candidate(self):
        harness = SpecialistBenchmarkHarness(root_path=self.root, registry=self.runtime.registry)
        cases = [BenchmarkCase(case_id="case", query="q", relevance={"good": 3, "bad": 0}, expected_text="cell membrane", expected_layout={"title": "A", "tables": {"0": "T"}}, expected_reading_order=["title", "table"])]
        ranked = harness.evaluate_ranking(
            specialist_id="fixture.embed",
            category="embedding",
            cases=cases,
            ranker=lambda case: ["good", "bad"],
        )
        self.assertEqual(ranked.metrics["recall_at_5"], 1.0)
        reranked = harness.evaluate_ranking(
            specialist_id="fixture.rerank",
            category="reranking",
            cases=cases,
            ranker=lambda case: ["good", "bad"],
        )
        self.assertEqual(reranked.metrics["ndcg_at_10"], 1.0)
        visual = harness.evaluate_ranking(
            specialist_id="fixture.visual",
            category="visual",
            cases=cases,
            ranker=lambda case: ["good", "bad"],
        )
        self.assertEqual(visual.metrics["top_5_relevance"], 1.0)
        self.assertEqual(self.runtime.registry.get("fixture.embed").benchmark_status, "approved")
        ocr = harness.evaluate_ocr(
            specialist_id="fixture.ocr",
            cases=cases,
            extractor=lambda case: (case.expected_text, case.expected_layout),
        )
        self.assertEqual(ocr.metrics["character_accuracy"], 1.0)
        parsing = harness.evaluate_parsing(
            specialist_id="fixture.parse",
            cases=cases,
            parser=lambda case: {"source_id": "source", "page": 1, "structure": case.expected_layout, "tables": case.expected_layout["tables"], "reading_order": case.expected_reading_order},
        )
        self.assertEqual(parsing.metrics["provenance_preservation"], 1.0)
        with self.assertRaises(ValueError):
            harness.approve_live_candidate(
                result=ranked,
                baseline=ranked,
                classification="superior",
                quality_metric="ndcg_at_10",
                reliability=1.0,
            )
        candidate_registry = SpecialistModelRegistry()
        candidate_harness = SpecialistBenchmarkHarness(root_path=self.root, registry=candidate_registry)
        candidate_harness.evaluate_ranking(
            specialist_id="nvidia.nemotron-3-embed-1b",
            category="embedding",
            cases=cases,
            ranker=lambda case: ["good", "bad"],
        )
        candidate = candidate_registry.get("nvidia.nemotron-3-embed-1b")
        self.assertEqual(candidate.benchmark_status, "fixture_only")
        with self.assertRaises(ValueError):
            candidate_registry.enable(candidate.specialist_id)

    def test_pages_render_conservative_specialist_and_provenance_states(self):
        specialists = SpecialistsPage(
            specialists=[
                {
                    **self.runtime.registry.get("fixture.embed").safe_dict(),
                    "usage": {"calls": 0, "fallback_rate": 0.0},
                }
            ]
        )
        detail = SpecialistDetailPage(specialist=self.runtime.registry.get("fixture.embed").safe_dict(), usage={"calls": 0, "failures": 0, "fallback_rate": 0.0, "recent": []})
        evidence = EvidencePage(evidence=[])
        self.assertIn("Specialists", specialists)
        self.assertIn("Benchmark evidence", detail)
        self.assertIn("No indexed evidence", evidence)


class SpecialistMCPAndRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        source_root = Path(__file__).resolve().parents[1]
        shutil.copytree(source_root / "configs", self.root / "configs")
        self.toolbox = MysticToolbox(root_path=self.root)
        self.server = MysticMCPServer(toolbox=self.toolbox)
        self.client = TestClient(create_app(root_path=self.root, toolbox=self.toolbox))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_mcp_surface_is_bounded_and_fixture_benchmark_does_not_enable_models(self):
        tools = self.server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        names = {item["name"] for item in tools["result"]["tools"]}
        self.assertIn("lab_specialist_list", names)
        self.assertIn("lab_document_ingest", names)
        self.assertNotIn("lab_specialist_execute", names)
        benchmark = self.server.handle_request(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "lab_specialist_benchmark", "arguments": {"fixture": "retrieval_smoke"}}}
        )
        payload = benchmark["result"]["structuredContent"]
        self.assertEqual(payload["result"]["execution_mode"], "fixture")
        self.assertFalse(any(model.enabled for model in self.toolbox.specialist_runtime.registry.list()))

    def test_mcp_rejects_oversized_document_and_default_ingest_fails_closed(self):
        oversized = self.server.handle_request(
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "lab_document_ingest", "arguments": {"source_id": "x", "source_type": "paper", "title": "x", "mime_type": "text/plain", "content": "x" * 120001}}}
        )
        self.assertIn("at most 120000", oversized["error"]["message"])
        response = self.server.handle_request(
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "lab_document_ingest", "arguments": {"source_id": "paper-x", "source_type": "paper", "title": "Default disabled", "mime_type": "text/plain", "content": "Evidence text."}}}
        )
        payload = response["result"]["structuredContent"]
        self.assertEqual(payload["status"], "specialist_unavailable")
        self.assertEqual(payload["failure"]["failure_type"], "unavailable")

    def test_control_center_routes_render_without_provider_execution(self):
        list_page = self.client.get("/specialists")
        detail_page = self.client.get("/specialists/nvidia.nemotron-3-embed-1b")
        evidence_page = self.client.get("/evidence")
        self.assertEqual(list_page.status_code, 200)
        self.assertEqual(detail_page.status_code, 200)
        self.assertEqual(evidence_page.status_code, 200)
        self.assertIn("unclassified", list_page.text)
        self.assertIn("Fixture results do not approve", detail_page.text)
        self.assertIn("No indexed evidence", evidence_page.text)


if __name__ == "__main__":
    unittest.main()
