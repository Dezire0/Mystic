from __future__ import annotations

import json
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest

from mystic.lab.specialist_benchmarks import SpecialistBenchmarkCorpus, SpecialistBenchmarkHarness
from mystic.lab.specialist_evaluation import Wave1SpecialistEvaluator
from mystic.lab.specialists import (
    BenchmarkStatus,
    LocalOpenAICompatibleEmbeddingProvider,
    NvidiaNIMSpecialistProvider,
    SpecialistClassification,
    SpecialistModel,
    SpecialistModelRegistry,
    SpecialistRuntime,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = REPOSITORY_ROOT / "benchmarks" / "phase2d" / "v1" / "corpus.json"
SYNTHETIC_CORPUS_PATH = REPOSITORY_ROOT / "benchmarks" / "specialists" / "v1" / "corpus.json"


def _candidate_model() -> SpecialistModel:
    return SpecialistModel(
        specialist_id="test.live-embedding",
        provider="test",
        model_id="test/live-embedding",
        version="test-v1",
        role="text_embedding",
        modalities=["text"],
        domains=["*"],
        capabilities=["retrieval"],
        languages=["*"],
        max_input=10000,
        expected_latency_class="low",
        expected_cost_class="free",
        local_or_remote="local",
        free_endpoint_available=True,
        deterministic_or_nondeterministic="deterministic",
        trust_level="test_only",
        enabled=False,
        health="healthy",
        benchmark_status=BenchmarkStatus.NOT_RUN.value,
        fallback_ids=[],
        limitations=["test only"],
        license_metadata={"test": "true"},
    )


class SpecialistEvaluationTests(unittest.TestCase):
    def test_corpus_is_versioned_and_explicitly_marks_non_live_asset_gaps(self):
        corpus = SpecialistBenchmarkCorpus.load(CORPUS_PATH)
        self.assertEqual(corpus.corpus_id, "mystic-phase2d-science-v1")
        self.assertEqual(len(corpus.retrieval_cases), 4)
        self.assertEqual(corpus.retrieval_cases[-1].language, "ko")
        self.assertIn("force-table-layout-en", corpus.asset_gaps)
        self.assertEqual(corpus.provenance_cases[0]["required_stages"][-1], "rerank")

    def test_synthetic_wave_one_corpus_is_versioned_hashed_and_has_real_labeled_assets(self):
        corpus = SpecialistBenchmarkCorpus.load(SYNTHETIC_CORPUS_PATH)
        self.assertEqual(corpus.corpus_id, "mystic-specialists-synthetic-v1")
        self.assertEqual(corpus.version, "1.0.0")
        self.assertTrue(corpus.dataset_hash)
        self.assertGreaterEqual(len(corpus.documents), 40)
        self.assertGreaterEqual(len(corpus.retrieval_cases), 20)
        self.assertTrue(all(len(case.relevance) >= 8 for case in corpus.retrieval_cases))
        self.assertTrue(any(case.language == "ko" for case in corpus.retrieval_cases))
        self.assertEqual(corpus.asset_gaps, [])
        force_table = corpus.ocr_inputs["ocr-force-table"]
        self.assertTrue(force_table["image_data_url"].startswith("data:image/png;base64,"))
        self.assertIn("25 N", force_table["expected_table_cells"])
        self.assertGreaterEqual(len(corpus.parsing_cases), 4)
        self.assertGreaterEqual(len(corpus.visual_cases), 3)

    def test_synthetic_corpus_rejects_tampered_dataset_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "corpus"
            shutil.copytree(SYNTHETIC_CORPUS_PATH.parent, root)
            asset = root / "assets" / "ocr-normal-paragraph.png"
            asset.write_bytes(asset.read_bytes() + b"tamper")
            with self.assertRaisesRegex(ValueError, "integrity check failed"):
                SpecialistBenchmarkCorpus.load(root / "corpus.json")

    def test_preserved_lexical_baseline_is_not_a_model_result(self):
        record = json.loads((SYNTHETIC_CORPUS_PATH.parent / "records" / "lexical_baseline.phase2d-v1.0.1.json").read_text(encoding="utf-8"))
        self.assertEqual(record["record_kind"], "lexical_baseline")
        self.assertFalse(record["is_model_result"])
        self.assertEqual(record["metrics"], {"mrr": 0.8125, "ndcg_at_10": 0.8576691395183482, "recall_at_5": 1.0})

    def test_baseline_run_persists_corpus_hash_without_any_provider_call(self):
        with tempfile.TemporaryDirectory() as temporary:
            evaluator = Wave1SpecialistEvaluator(root_path=temporary, corpus_path=CORPUS_PATH)
            report = evaluator.run_baselines()
            self.assertEqual(report.status, "baseline_recorded")
            self.assertTrue(report.corpus_hash)
            self.assertEqual({result["execution_mode"] for result in report.results}, {"baseline"})
            result_dir = Path(temporary) / "mystic_data" / "specialist_benchmarks"
            self.assertEqual(len(list(result_dir.glob("*.json"))), 2)
            self.assertIn("REAL_DOCUMENT_OCR_BASELINE_PENDING", report.blockers)

    def test_nim_embedding_serializer_is_bounded_and_redacts_the_api_key(self):
        observed: dict[str, object] = {}

        def post(url, headers, body, timeout):
            observed.update({"url": url, "headers": dict(headers), "body": json.loads(body.decode("utf-8")), "timeout": timeout})
            return 200, {"data": [{"index": 0, "embedding": [0.1, 0.2]}], "usage": {"prompt_tokens": 4}}

        provider = NvidiaNIMSpecialistProvider(
            environment={
                "MYSTIC_NVIDIA_NIM_EXECUTION_ENABLED": "true",
                "MYSTIC_NVIDIA_NIM_API_KEY": "not-for-output",
                "MYSTIC_NVIDIA_NIM_EMBED_BASE_URL": "https://integrate.api.nvidia.com",
            },
            post_json=post,
        )
        model = SpecialistModelRegistry().get("nvidia.nemotron-3-embed-1b")
        result = provider.execute(model=model, operation="embed", payload={"text": "query text", "input_type": "query"})
        self.assertTrue(result.succeeded)
        self.assertEqual(observed["url"], "https://integrate.api.nvidia.com/v1/embeddings")
        self.assertEqual(observed["body"], {"model": model.model_id, "input": "query text", "input_type": "query", "encoding_format": "float", "truncate": "NONE"})
        self.assertEqual(observed["headers"]["authorization"], "Bearer not-for-output")
        self.assertNotIn("not-for-output", json.dumps(result.safe_dict()))
        configuration = provider.safe_configuration()
        self.assertTrue(configuration["api_key_configured"])
        self.assertTrue(configuration["credential_present"])
        self.assertTrue(configuration["endpoint_configured"])
        self.assertFalse(configuration["nim_configured"])
        self.assertEqual(configuration["retry_policy"], "none")
        self.assertEqual(configuration["selected_models"]["embedding"], "nvidia/nemotron-3-embed-1b")
        self.assertNotIn("not-for-output", json.dumps(configuration))

    def test_nim_adapter_rejects_unapproved_hosts_and_unbounded_ocr_data(self):
        called = False

        def post(*args):
            nonlocal called
            called = True
            return 200, {}

        provider = NvidiaNIMSpecialistProvider(
            environment={
                "MYSTIC_NVIDIA_NIM_EXECUTION_ENABLED": "true",
                "MYSTIC_NVIDIA_NIM_API_KEY": "not-for-output",
                "MYSTIC_NVIDIA_NIM_EMBED_BASE_URL": "https://example.invalid",
            },
            post_json=post,
        )
        model = SpecialistModelRegistry().get("nvidia.nemotron-3-embed-1b")
        result = provider.execute(model=model, operation="embed", payload={"text": "query"})
        self.assertFalse(result.succeeded)
        self.assertFalse(called)
        self.assertEqual(result.failure_type, "provider_offline")
        ocr_provider = NvidiaNIMSpecialistProvider(
            environment={"MYSTIC_NVIDIA_NIM_EXECUTION_ENABLED": "true", "MYSTIC_NVIDIA_NIM_OCR_BASE_URL": "http://127.0.0.1:8000"},
            post_json=post,
        )
        ocr = ocr_provider.execute(
            model=SpecialistModelRegistry().get("nvidia.nemotron-ocr-v2"),
            operation="ocr",
            payload={"image": "data:image/svg+xml;base64,PHN2Zz4="},
        )
        self.assertEqual(ocr.failure_type, "unsupported_input")
        self.assertFalse(called)

    def test_nim_adapter_refuses_a_registry_entry_outside_the_wave_one_allowlist(self):
        provider = NvidiaNIMSpecialistProvider(
            environment={"MYSTIC_NVIDIA_NIM_EXECUTION_ENABLED": "true", "MYSTIC_NVIDIA_NIM_EMBED_BASE_URL": "http://127.0.0.1:8000"},
            post_json=lambda *args: (200, {}),
        )
        unsupported = SpecialistModelRegistry().get("nvidia.llama-nemotron-embed-1b-v2")
        result = provider.execute(model=unsupported, operation="embed", payload={"text": "not an approved Wave 1 execution"})
        self.assertEqual(result.failure_type, "unsupported_input")

    def test_local_openai_compatible_embedding_provider_is_loopback_only_and_model_bounded(self):
        observed: dict[str, object] = {}

        def post(url, headers, body, timeout):
            observed.update({"url": url, "headers": dict(headers), "body": json.loads(body.decode("utf-8")), "timeout": timeout})
            return 200, {"data": [{"index": 0, "embedding": [0.3, 0.4]}]}

        model = _candidate_model()
        model.provider = "local_openai_compatible"
        model.model_id = "mystic/local-science-embed"
        provider = LocalOpenAICompatibleEmbeddingProvider(
            allowed_model_ids={model.model_id},
            environment={
                "MYSTIC_LOCAL_OPENAI_COMPATIBLE_EXECUTION_ENABLED": "true",
                "MYSTIC_LOCAL_OPENAI_COMPATIBLE_API_KEY": "not-for-output",
                "MYSTIC_LOCAL_OPENAI_COMPATIBLE_EMBED_BASE_URL": "http://127.0.0.1:8080",
            },
            post_json=post,
        )
        result = provider.execute(model=model, operation="embed", payload={"text": "local query"})
        self.assertTrue(result.succeeded)
        self.assertEqual(observed["url"], "http://127.0.0.1:8080/v1/embeddings")
        self.assertEqual(observed["body"], {"model": model.model_id, "input": "local query", "encoding_format": "float"})
        self.assertNotIn("not-for-output", json.dumps(provider.safe_configuration()))
        self.assertNotIn("not-for-output", json.dumps(result.safe_dict()))

        remote = LocalOpenAICompatibleEmbeddingProvider(
            allowed_model_ids={model.model_id},
            environment={
                "MYSTIC_LOCAL_OPENAI_COMPATIBLE_EXECUTION_ENABLED": "true",
                "MYSTIC_LOCAL_OPENAI_COMPATIBLE_EMBED_BASE_URL": "https://example.invalid",
            },
            post_json=post,
        )
        denied = remote.execute(model=model, operation="embed", payload={"text": "must not leave loopback"})
        self.assertEqual(denied.failure_type, "provider_offline")
        self.assertEqual(observed["url"], "http://127.0.0.1:8080/v1/embeddings")

    def test_live_approval_gate_derives_a_superior_classification(self):
        with tempfile.TemporaryDirectory() as temporary:
            corpus = SpecialistBenchmarkCorpus.load(CORPUS_PATH)
            registry = SpecialistModelRegistry([_candidate_model()])
            harness = SpecialistBenchmarkHarness(root_path=temporary, registry=registry)
            baseline = harness.evaluate_ranking(
                specialist_id="mystic.baseline",
                category="embedding",
                cases=corpus.retrieval_cases,
                ranker=lambda case: sorted(case.relevance, key=lambda identifier: case.relevance[identifier]),
                execution_mode="baseline",
                corpus=corpus,
                provenance_preserved=True,
            )
            candidate = harness.evaluate_ranking(
                specialist_id="test.live-embedding",
                category="embedding",
                cases=corpus.retrieval_cases,
                ranker=lambda case: sorted(case.relevance, key=lambda identifier: case.relevance[identifier], reverse=True),
                execution_mode="live",
                corpus=corpus,
                provenance_preserved=True,
                latency_ms=1.0,
            )
            decision = harness.classify_live_candidate(candidate=candidate, baseline=baseline, quality_metric="ndcg_at_10")
            self.assertTrue(decision["approve"])
            self.assertEqual(decision["classification"], SpecialistClassification.SUPERIOR.value)
            approval = harness.approve_live_candidate(result=candidate, baseline=baseline, quality_metric="ndcg_at_10")
            self.assertEqual(approval["specialist"]["benchmark_status"], "approved")

    def test_new_corpus_baselines_add_required_metrics_without_provider_calls(self):
        with tempfile.TemporaryDirectory() as temporary:
            evaluator = Wave1SpecialistEvaluator(root_path=temporary, corpus_path=SYNTHETIC_CORPUS_PATH)
            report = evaluator.run_baselines()
            self.assertEqual(report.status, "baseline_recorded")
            results = {item["category"]: item for item in report.results}
            self.assertEqual(set(results), {"embedding", "reranking", "ocr"})
            self.assertTrue({"recall_at_1", "recall_at_5", "recall_at_10", "mrr", "ndcg_at_10", "precision_at_5", "latency_p50_ms", "latency_p95_ms"}.issubset(results["embedding"]["metrics"]))
            self.assertTrue({"character_error_rate", "word_error_rate", "numeric_unit_accuracy", "table_cell_recovery", "reading_order_correctness", "layout_element_recovery"}.issubset(results["ocr"]["metrics"]))
            self.assertEqual(results["embedding"]["configuration"]["network_calls"], 0)
            self.assertEqual(results["ocr"]["metrics"]["table_cell_recovery"], 0.0)

    def test_wave_one_readiness_exposes_only_safe_configuration_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            evaluator = Wave1SpecialistEvaluator(root_path=temporary, corpus_path=SYNTHETIC_CORPUS_PATH)
            readiness = evaluator.readiness()
            config = readiness["provider_configuration"]
            self.assertFalse(config["nim_configured"])
            self.assertFalse(config["credential_present"])
            self.assertFalse(config["endpoint_configured"])
            self.assertNotIn("API_KEY", json.dumps(readiness))

    def test_persisted_approval_replays_only_with_an_intact_live_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            corpus = SpecialistBenchmarkCorpus.load(CORPUS_PATH)
            registry = SpecialistModelRegistry([_candidate_model()])
            harness = SpecialistBenchmarkHarness(root_path=temporary, registry=registry)
            baseline = harness.evaluate_ranking(
                specialist_id="mystic.baseline",
                category="embedding",
                cases=corpus.retrieval_cases,
                ranker=lambda case: sorted(case.relevance, key=lambda identifier: case.relevance[identifier]),
                execution_mode="baseline",
                corpus=corpus,
                provenance_preserved=True,
            )
            candidate = harness.evaluate_ranking(
                specialist_id="test.live-embedding",
                category="embedding",
                cases=corpus.retrieval_cases,
                ranker=lambda case: sorted(case.relevance, key=lambda identifier: case.relevance[identifier], reverse=True),
                execution_mode="live",
                corpus=corpus,
                provenance_preserved=True,
                baseline_id="mystic.baseline",
            )
            harness.approve_live_candidate(result=candidate, baseline=baseline, quality_metric="ndcg_at_10")
            model = registry.enable(candidate.specialist_id)
            runtime = SpecialistRuntime(registry=registry, providers={}, root_path=temporary)
            runtime.approvals.record(
                model=model,
                benchmark_id=candidate.benchmark_id,
                benchmark_result_hash=hashlib.sha256(
                    (harness.result_root / f"{candidate.benchmark_id}.json").read_bytes()
                ).hexdigest(),
                quality_metric="ndcg_at_10",
            )
            restored = SpecialistRuntime(registry=SpecialistModelRegistry([_candidate_model()]), providers={}, root_path=temporary)
            self.assertTrue(restored.registry.get(candidate.specialist_id).enabled)
            (harness.result_root / f"{candidate.benchmark_id}.json").write_text("{}", encoding="utf-8")
            tampered = SpecialistRuntime(registry=SpecialistModelRegistry([_candidate_model()]), providers={}, root_path=temporary)
            self.assertFalse(tampered.registry.get(candidate.specialist_id).enabled)


if __name__ == "__main__":
    unittest.main()
