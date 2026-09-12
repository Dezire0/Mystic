# ALETHEIA 2D Specialist Scientific Benchmark Suite v0

Status: implementation ready for review in [PR #142](https://github.com/Dezire0/Mystic/pull/142), resolving [Issue #141](https://github.com/Dezire0/Mystic/issues/141). The initial implementation commit is `7856443be92e6005e7d482fd5f04b1492068a120`. This suite creates reviewable evidence for the three experimental NVIDIA specialists; it does not approve, route, or activate them.

## Architecture

```text
Frozen BenchmarkSpec
  -> repeated specialist execution (three or more runs)
  -> raw per-run artifacts, including failures
  -> BenchmarkEvidence aggregation
  -> existing BenchmarkResult schema
  -> Approval Review Report
  -> separate human threshold/approval decision
```

The opt-in real path uses the same proven production boundary:

```text
BenchmarkSpec -> LightningDispatcher -> existing Lightning Studio -> T4 specialist worker
  -> raw result JSON -> BenchmarkEvidence -> Approval Review Report
```

The dispatcher remains responsible for the configured existing Studio, automatic T4 lifecycle, artifact-to-shell materialization, result publication, and cleanup. The benchmark code only consumes its result and writes local, ignored artifacts under `mystic_data/alethia_scientific_benchmark/`.

## Frozen versioning policy

`benchmarks/alethia/approval-v0/fixtures.json` is the initial frozen evaluation manifest. Each suite declares a benchmark ID/version, task schema, scoring rules, dataset ID/version, deterministic seed, and a canonical SHA-256 of the dataset object. The expected hashes are also locked in code. A changed question, label, corpus entry, or controlled figure reference fails validation until a material benchmark-version increment and deliberate hash update are reviewed.

Development/smoke examples are stored separately from `frozen_evaluation`. The experimental NVIDIA candidates must not be tuned against the frozen examples. Incorrect rankings and exceptions are retained in every raw run and aggregation; they are not filtered from metrics.

## Initial dataset scope

| Capability | Frozen evaluation scope |
| --- | --- |
| `scientific.text_retrieval` | Physics, Chemistry, Biology, Mathematics, and a no-answer abstention task; Top-1, Recall@3, Recall@5, MRR, nDCG, timing, throughput, VRAM, and failures. |
| `scientific.visual_retrieval` | Controlled CC0 scientific diagrams from the existing committed fixture assets; text-to-figure Top-1, Recall@3, Recall@5, MRR, nDCG, timing, VRAM, and repeatability. |
| `scientific.multimodal_reranking` | Text-only, image-containing, and mixed candidate sets across scientific domains; correct-item rank via Top-1/MRR/nDCG, timing, VRAM, and failures. |

The current corpus is intentionally small and controlled. It is a frozen v0 measurement harness, not a claim of broad scientific generalisation or model superiority.

## Reproducibility and evidence

Approval-grade runs require at least three executions. The evidence stores every case/run result, mean and variance where meaningful, reliability, reproducibility signatures, cold-load time separately from warm inference latency, throughput, peak VRAM, Tesla T4 backend, model revision, software versions, timestamps, seed, dataset hash, and raw artifact reference.

`BenchmarkEvidence.to_approval_result()` emits the existing `mystic.alethia_approval.BenchmarkResult` contract directly. It does not create a competing result format. A changed candidate model revision is visible to the existing approval gate as stale evidence.

## Threshold review policy

v0 intentionally defines **no approval thresholds**. The Approval Review Report always records the measured distributions, reliability, resource profile, failure modes, evidence references, and a non-mutating recommendation. Its default recommendation is `KEEP_EXPERIMENTAL`: a human/reviewed policy must first set capability-specific thresholds and determine whether the full evidence is sufficient. A benchmark result cannot mutate a candidate status.

## Current implementation status and limits

The three NVIDIA candidates stay `EXPERIMENTAL`:

- `nvidia/llama-nemotron-embed-1b-v2`
- `nvidia/llama-nemotron-embed-vl-1b-v2`
- `nvidia/llama-nemotron-rerank-vl-1b-v2`

The optional Lightning command is:

```bash
python scripts/run_aletheia_lightning_scientific_benchmark.py \
  --job-id-prefix aletheia-scientific-benchmark-001 \
  --query 'Which page explains gravitational lensing?' \
  --pdf /absolute/path/to/controlled.pdf \
  --expected-page 1
```

It requires the existing `LIGHTNING_*` configuration and controlled input PDF; it does not print credentials. The pipeline acceptance check is deliberately identified as an execution-environment check, not a substitute for a complete per-candidate scientific suite.

WORLD, HERMES, and OIKOS remain unchanged. No paid API, new model, autonomous discovery, or automatic production switching is added. Before automatic specialist evolution can be considered, the frozen corpora need broader independent scientific coverage, real model runs for all three capabilities, a reviewed threshold policy, and a separate approval decision.

Verification recorded for this implementation: the focused benchmark, approval-gate, and Lightning dispatcher suites passed (`59 passed, 1 existing credential-gated acceptance skip`); compilation and `git diff --check` also passed. The real T4 command was not run in this credential-unconfigured session, so no result artifact is claimed here.
