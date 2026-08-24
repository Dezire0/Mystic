# ALETHEIA Specialist Benchmark v0

This isolated, local-first harness evaluates bounded specialist instruments before they are considered for ALETHEIA. It does not modify or select models for WORLD Runtime, MNEME production, Event Poller, or Issue #48.

Run the committed deterministic fixture:

```bash
python scripts/run_aletheia_specialist_benchmark.py
```

The harness evaluates local/free lexical retrieval, deterministic embedding baseline, reranking, parsing, and Tesseract OCR when it is installed. Results are written as JSON and Markdown under `mystic_data/reports/alethia_specialist_benchmark_v0/` (ignored operational output).

Reports contain quality, latency, CPU time, process RSS, reliability, zero-cost estimates for bundled candidates, and per-case failures. Rankings are capability-specific. Every result is marked `requires_human_review`: a first-place score is not permission to adopt a model. Review license, privacy boundary, failure cases, provenance, and operational fit before any separate integration work.

External or paid providers are intentionally absent. A deployment may add a local adapter conforming to `SpecialistAdapter`; it must be explicitly configured and should provide its own cost and privacy review.

Fixture inputs are CC0 and versioned in `benchmarks/alethia/v0/fixtures.json`; they contain positive calibration cases plus no-match and missing-input cases. The generated OCR calibration image is checked into that same fixture directory. The report preserves failed quality thresholds and adapter errors by case, including `failure_kind`, so regression comparisons cannot hide them. Add later scientific specialists by adding a capability-specific fixture set and adapter without changing production routing.
