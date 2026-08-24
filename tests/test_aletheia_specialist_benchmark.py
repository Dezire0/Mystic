from __future__ import annotations

from pathlib import Path

from mystic.alethia_benchmark import BenchmarkHarness, available_local_candidates, load_fixture
from mystic.alethia_benchmark.adapters import (
    HashEmbeddingRetrieval,
    LexicalRetrieval,
    LexicalReranker,
    PlainTextParser,
)
from mystic.alethia_benchmark.core import write_report


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "benchmarks/alethia/v0/fixtures.json"


def test_local_benchmark_is_ranked_but_decision_neutral(tmp_path: Path) -> None:
    report = BenchmarkHarness(load_fixture(FIXTURE), FIXTURE.parent).run(available_local_candidates())
    assert set(report["rankings"]) >= {"retrieval", "embedding", "reranking", "parsing"}
    assert all(row["decision"] == "requires_human_review" for row in report["results"])
    assert all(row["metrics"]["case_count"] >= 2 for row in report["results"])
    json_path, markdown_path = write_report(report, tmp_path)
    assert json_path.exists() and markdown_path.exists()


def test_parser_fixture_is_deterministic() -> None:
    fixture = load_fixture(FIXTURE)
    parser = PlainTextParser()
    case = fixture["cases"]["parsing"][0]
    assert parser.run(case["input"]) == case["expected"]["text"]


def test_adapter_exception_is_preserved_as_a_failure() -> None:
    class BrokenRetriever:
        identifier = "local.broken"
        capability = "retrieval"
        license = "MIT"
        local = True

        def run(self, payload: dict[str, object]) -> list[str]:
            raise RuntimeError("intentional fixture failure")

    report = BenchmarkHarness(load_fixture(FIXTURE), FIXTURE.parent).run([BrokenRetriever()])
    result = report["results"][0]
    assert result["metrics"]["reliability"] == 0.0
    assert "intentional fixture failure" in result["failures"][0]["error"]
    assert result["failures"][0]["failure_kind"] == "adapter_error"


def test_negative_fixture_cases_are_retained_in_report() -> None:
    report = BenchmarkHarness(load_fixture(FIXTURE), FIXTURE.parent).run(available_local_candidates())
    failures = [failure for result in report["results"] for failure in result["failures"]]
    assert "quality_below_threshold" in {failure["failure_kind"] for failure in failures}


def test_dependency_free_baselines_have_versioned_regression_scores() -> None:
    report = BenchmarkHarness(load_fixture(FIXTURE), FIXTURE.parent).run([
        LexicalRetrieval(), HashEmbeddingRetrieval(), LexicalReranker(), PlainTextParser()
    ])
    scores = {result["candidate"]["id"]: result["metrics"]["quality"] for result in report["results"]}
    assert report["fixture_version"] == "v0.2.0"
    assert report["fixture_sha256"] == "4c177f09615fd51ba3d393bc0c1382dd9370ad2f48f4d9a41f726f5fc843c1c1"
    assert scores == {
        "local.lexical-tf": 0.5,
        "local.hash-embedding-v1": 0.5,
        "local.lexical-reranker": 0.5,
        "local.plaintext-parser": 1.0,
    }
