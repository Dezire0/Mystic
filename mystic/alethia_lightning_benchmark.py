"""Opt-in Lightning T4 evidence bridge for the frozen ALETHEIA benchmark flow.

The dispatcher remains the sole owner of Studio lifecycle and file-transfer
semantics.  This module only converts its observable result into benchmark
evidence; it does not approve or route any candidate.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import time
from typing import Callable

from mystic.alethia_scientific_suite import (
    BenchmarkRun, BenchmarkSpec, CaseRunResult, aggregate_observed_runs,
    _rank_metrics,
)
from mystic.specialist_dispatcher import LightningDispatcher, SpecialistJob


PIPELINE_CANDIDATE_ID = "nvidia-lightning-retrieval-stack"


def run_lightning_t4_benchmark(
    *,
    dispatcher: LightningDispatcher,
    job_id_prefix: str,
    query: str,
    pdf_path: Path,
    expected_page: int,
    output_dir: Path,
    repetitions: int = 3,
    now: Callable[[], datetime] | None = None,
):
    """Run a controlled PDF-retrieval check repeatedly and normalize its raw results.

    This is a pipeline acceptance benchmark, not a substitute for any capability's
    complete frozen evaluation suite.  Its evidence therefore remains review-only.
    """
    if repetitions < 3:
        raise ValueError("Lightning benchmark acceptance requires at least three executions")
    timestamp = now or (lambda: datetime.now(UTC))
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    dataset = {"query": query, "pdf_sha256": pdf_hash, "expected_page": expected_page}
    spec = BenchmarkSpec(
        benchmark_id="alethia-lightning-pdf-retrieval-acceptance",
        benchmark_version="v0.1.0",
        capability="scientific.pdf_retrieval",
        dataset_id="controlled-lightning-pdf-acceptance",
        dataset_version="v0.1.0",
        dataset_sha256=hashlib.sha256(json.dumps(dataset, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        random_seed=141,
        hardware_backend="Tesla T4",
        model_revision="dispatcher-v0",
        software_versions={"dispatcher": "alethia-lightning-specialist-dispatcher-v0"},
    )
    runs: list[BenchmarkRun] = []
    raw_paths: list[str] = []
    for run_number in range(1, repetitions + 1):
        started = time.perf_counter()
        try:
            result = dispatcher.execute(SpecialistJob(f"{job_id_prefix}-run-{run_number}", query, (pdf_path,)))
            elapsed_ms = (time.perf_counter() - started) * 1000
            raw_path = output_dir / f"{job_id_prefix}-run-{run_number}.raw.json"
            raw_path.write_text(json.dumps(asdict(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
            raw_paths.append(str(raw_path))
            ranked = tuple(f"page-{item.page}" for item in result.evidence_candidates)
            scores = _rank_metrics(ranked, (f"page-{expected_page}",))
            vram = result.evidence_candidates[0].gpu.get("memory_used_mb") if result.evidence_candidates else None
            runs.append(BenchmarkRun(run_number, timestamp().isoformat(), (
                CaseRunResult("controlled-pdf", ranked, *scores, elapsed_ms if run_number == 1 else 0.0, elapsed_ms, int(vram) if isinstance(vram, (int, float)) else None, str(raw_path)),
            )))
        except Exception as error:
            runs.append(BenchmarkRun(run_number, timestamp().isoformat(), (
                CaseRunResult("controlled-pdf", (), 0.0, 0.0, 0.0, 0.0, 0.0, None, None, None, None, "", f"{type(error).__name__}: {error}"),
            )))
    evidence_path = output_dir / f"{job_id_prefix}.evidence.json"
    evidence = aggregate_observed_runs(
        candidate_id=PIPELINE_CANDIDATE_ID,
        spec=spec,
        runs=tuple(runs),
        raw_result_artifact_ref=str(evidence_path),
        generated_at=timestamp().isoformat(),
        required_case_count=1,
    )
    evidence_path.write_text(json.dumps(asdict(evidence), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return evidence
