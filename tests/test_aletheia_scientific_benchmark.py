from __future__ import annotations

from pathlib import Path

from mystic.alethia_benchmark import load_fixture
from mystic.alethia_benchmark.adapters import (
    HashEmbeddingRetrieval,
    LexicalRetrieval,
    LexicalReranker,
    PlainTextParser,
)
from mystic.alethia_benchmark.scientific import ScientificBenchmarkPack, write_scientific_report


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "benchmarks/alethia/scientific-v1/fixtures.json"


def test_scientific_fixture_covers_each_domain_and_capability() -> None:
    fixture = load_fixture(FIXTURE)
    assert fixture["domains"] == ["physics", "chemistry", "biology", "mathematics"]
    for domain in fixture["domains"]:
        assert all(any(case["domain"] == domain for case in cases) for cases in fixture["cases"].values())
    assert any(case["expected"]["top_id"] is None for case in fixture["cases"]["retrieval"])


def test_scientific_pack_produces_domain_reports_and_nonactivating_shortlist(tmp_path: Path) -> None:
    fixture = load_fixture(FIXTURE)
    report = ScientificBenchmarkPack(fixture, FIXTURE.parent).run([
        LexicalRetrieval(), HashEmbeddingRetrieval(), LexicalReranker(), PlainTextParser()
    ])
    assert report["pack_version"] == "v1.0.0"
    assert report["fixture_sha256"] == "ac9cf8d8abf391edeac5cd9c65405cff106608a95a97f648f509d2b7e242a332"
    assert set(report["domains"]) == set(fixture["domains"])
    assert all(domain_report["rankings"] for domain_report in report["domains"].values())
    assert all(
        next(row for row in domain_report["results"] if row["candidate"]["id"] == "local.lexical-tf")["metrics"]["quality"] == 0.5
        for domain_report in report["domains"].values()
    )
    shortlist = report["overall_comparison"]["shortlist"]
    assert [row["candidate"]["id"] for row in shortlist] == ["local.plaintext-parser"]
    assert all(row["activation"] == "not_activated" for row in shortlist)
    rejected = report["overall_comparison"]["rejected"]
    assert {row["candidate"]["id"] for row in rejected} >= {
        "local.lexical-tf", "local.hash-embedding-v1", "local.lexical-reranker"
    }
    json_path, markdown_path = write_scientific_report(report, tmp_path)
    assert json_path.exists() and markdown_path.exists()
