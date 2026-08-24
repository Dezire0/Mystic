# ALETHEIA Scientific Benchmark Pack v1

This pack extends the isolated Specialist Benchmark with deterministic Physics, Chemistry, Biology, and Mathematics research fixtures. Each domain exercises evidence retrieval, embedding retrieval, adversarially similar passage reranking, noisy equation/table parsing, OCR, and a deliberate no-answer retrieval case.

Run all currently available local/free adapters:

```bash
python scripts/run_aletheia_scientific_benchmark.py
```

The report records per-domain rankings, case evidence identifiers, latency, CPU, RSS, reliability, failures, and an overall comparison. A candidate is only *shortlisted for 2D integration review* when it is explicitly integration-eligible and its mean quality is at least 0.80 and reliability at least 0.95 across all four domains. Hash/lexical baselines are evaluation-only even if they score well. This is an evidence summary, not an activation or routing action.

Fixtures are CC0, versioned at `benchmarks/alethia/scientific-v1/fixtures.json`, and include scientific distractors that are plausibly related but do not answer the exact task. The local baseline's no-match failures are intentional: they expose a lack of abstention rather than being silently ignored.
