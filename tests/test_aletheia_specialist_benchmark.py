from __future__ import annotations

from pathlib import Path

from mystic.alethia_benchmark import BenchmarkHarness, available_local_candidates, load_fixture
from mystic.alethia_benchmark.adapters import PlainTextParser
from mystic.alethia_benchmark.core import write_report


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "benchmarks/alethia/v0/fixtures.json"


def test_local_benchmark_is_ranked_but_decision_neutral(tmp_path: Path) -> None:
    report = BenchmarkHarness(load_fixture(FIXTURE), FIXTURE.parent).run(available_local_candidates())
    assert set(report["rankings"]) >= {"retrieval", "embedding", "reranking", "parsing"}
    assert all(row["decision"] == "requires_human_review" for row in report["results"])
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
