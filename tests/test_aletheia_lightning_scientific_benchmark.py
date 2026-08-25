from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from mystic.alethia_lightning_benchmark import PIPELINE_CANDIDATE_ID, run_lightning_t4_benchmark
from mystic.specialist_dispatcher import EvidenceCandidate, SpecialistResult


NOW = lambda: datetime(2026, 8, 25, tzinfo=UTC)


class FakeDispatcher:
    def __init__(self) -> None:
        self.jobs = []

    def execute(self, job):
        self.jobs.append(job)
        return SpecialistResult(
            job_id=job.job_id,
            status="SUCCEEDED",
            evidence_candidates=[EvidenceCandidate(
                source_identity="controlled.pdf", source_hash="abc", page=1, preview="lensing",
                text_score=1.0, visual_score=1.0, fusion_score=1.0, rerank_score=1.0,
                job_id=job.job_id, provider="lightning", gpu={"name": "Tesla T4", "memory_used_mb": 512},
                model_stack={}, runtime_seconds=1.0, input_hashes={}, created_at=NOW().isoformat(),
            )],
            runtime_seconds=1.0, input_hashes={}, specification_hash="spec",
        )


def test_lightning_bridge_preserves_raw_results_and_normalizes_three_real_dispatch_attempts(tmp_path: Path) -> None:
    pdf = tmp_path / "controlled.pdf"
    pdf.write_bytes(b"controlled fixture")
    dispatcher = FakeDispatcher()
    evidence = run_lightning_t4_benchmark(
        dispatcher=dispatcher, job_id_prefix="scientific-benchmark-acceptance",
        query="Which page explains gravitational lensing?", pdf_path=pdf, expected_page=1,
        output_dir=tmp_path / "results", now=NOW,
    )
    assert [job.job_id for job in dispatcher.jobs] == [
        "scientific-benchmark-acceptance-run-1", "scientific-benchmark-acceptance-run-2", "scientific-benchmark-acceptance-run-3",
    ]
    assert evidence.candidate_id == PIPELINE_CANDIDATE_ID
    assert evidence.suite_completed and evidence.reproducible
    assert evidence.aggregate_metrics["top_1"] == 1.0
    assert Path(evidence.raw_result_artifact_ref).exists()
    assert len(list((tmp_path / "results").glob("*.raw.json"))) == 3
