# Mystic LAB Phase 2D — Specialist Intelligence Layer

## Status

Phase 2D.1 establishes the local, vendor-neutral foundation. Phase 2D.2 adds a redistributable synthetic benchmark corpus and an operator-only Wave 1 execution gate. It does not enable a remote model, deploy a provider, modify the Phase 2C.2B staging environment, or claim model-quality results. Candidate models remain disabled until a live, task-specific benchmark records an approved result.

## Responsibility boundary

```text
User
  -> GPT / Mystic Research Controller       (reasoning and scientific judgement)
  -> Specialist Router                      (bounded instrument selection)
  -> Specialist Provider / Model            (embed, rank, parse, OCR only)
  -> traceable Evidence Bundle
  -> GPT / ResearchCampaign / Engines
```

The controller chooses whether evidence is needed and interprets it. Specialists never create campaign decisions, hypotheses, experiments, or scientific conclusions. Scientific engines remain the sole calculation/simulation boundary and `ScientificJob` remains their durable execution substrate.

## Registry and provider abstraction

`SpecialistModelRegistry` is the sole model catalogue. Each entry includes provider/model/version, role, modalities, capabilities, languages, input limit, latency/cost expectations, local/remote execution mode, free-endpoint indication, determinism, trust level, health, enablement, benchmark state/classification, fallbacks, limitations, licence metadata, and verification timestamp.

`SpecialistProvider` is capability-oriented. The Phase 2D.1 NVIDIA NIM adapter is configuration-gated and sends no request by default. It records `unavailable`, `model_disabled`, `timeout`, `rate_limited`, `invalid_output`, `unsupported_input`, or `provider_offline`; it never manufactures an embedding, rerank score, OCR text, or parse result. A local OpenAI-compatible embedding adapter is also available for explicitly registered loopback models; it is disabled unless server wiring supplies an allowlisted registry entry and opt-in configuration. A separate Hugging Face adapter is not yet implemented because its task contracts have not been live-validated.

The candidate registry starts with:

| Role | Primary / candidate | Phase 2D.1 state |
| --- | --- | --- |
| Text embedding | `nemotron-3-embed-1b` | registered, disabled, live benchmark required |
| Text embedding fallback | `llama-nemotron-embed-1b-v2` | registered, disabled, live benchmark required |
| English QA comparison | `nv-embedqa-e5-v5` | secondary, disabled |
| Text reranking | `llama-nemotron-rerank-1b-v2` | registered, disabled, live benchmark required |
| OCR | `nemotron-ocr-v2` | registered, disabled, live benchmark required |
| Document parsing | `nemotron-parse` | registered, disabled, live benchmark required |
| Visual embedding/reranking | `llama-nemotron-embed-vl-1b-v2`, `llama-nemotron-rerank-vl-1b-v2` | registered, disabled, live benchmark required |
| Page/table analysis and code retrieval | named secondary candidates | registered, disabled |

The router receives a task description rather than a model ID. It filters by role, modality, language, domain, input limit, enabled state, health, and approved benchmark status; then ranks remaining candidates using recorded quality/reliability and request latency/cost priorities. Model parameter count is never an input. An approved fallback is explicit in the returned execution record.

## Evidence and ingestion flow

```text
Source / page
  -> MIME and risk assessment
  -> parse / OCR / layout only when required
  -> normalization and chunking
  -> embedding index
  -> candidate retrieval
  -> reranking
  -> provenance validation + deduplication
  -> evidence bundle
```

Clean text and Markdown use deterministic normalization/chunking only. A scanned, image-based, or visually structured document is analysed and returned as `specialist_required` while its required OCR/parser/VL model is disabled; Phase 2D.1 does not downgrade it silently to unreliable text extraction. Raw document text is untrusted data, never an instruction. Every chunk stores source, document/page/location, transformation steps, model execution records, hashes, and timestamps.

`SpecialistEvidenceService` can attach a bounded evidence reference to a `ResearchCampaign` as an evidence/knowledge/artifact record. This has no effect on campaign policy or phase progression. The ScientificJob bridge is reference-only: it records compatible evidence/job lineage separately and does not change validated engine inputs, job state, leasing, or result attachment rules.

## Benchmark gate

`SpecialistBenchmarkHarness` stores metrics per task and records the execution mode. Deterministic fixtures test metric calculations and pipeline wiring only; their outcome is never attributed to a named NVIDIA candidate. A named candidate can be classified only after a live provider run with a declared corpus and baseline:

- embedding: Recall@K, MRR, nDCG, latency, failure rate
- reranking: nDCG, MRR, top-N relevance, latency
- OCR: character/word accuracy, layout/table preservation, latency, failure rate
- parsing: structural/table/reading-order accuracy and provenance preservation
- visual retrieval: Recall@K, nDCG, rerank quality, latency, failure rate

Allowed classifications are `ESSENTIAL`, `SUPERIOR`, `ACCELERATOR`, `REDUNDANT`, and `REJECTED`. Unrun candidates are `UNCLASSIFIED`, cannot be enabled, and are not described as superior.

## Bounded local MCP and Control Center surface

The local Python MCP server exposes only registry inspection, bounded matching, health, fixture benchmark recording, text-document ingestion, evidence retrieval/reranking, and redacted evidence retrieval. It does not offer arbitrary endpoint/model invocation. The Cloudflare Worker and its deployed tool manifest remain unchanged in Phase 2D.1.

The local Control Center adds read-only `/specialists`, `/specialists/{id}`, and `/evidence` pages. They show safe model metadata, health/benchmark/classification state, aggregate usage/fallback rate, and provenance paths. They do not render raw document bodies by default or collect credentials.

## Security and rollout

- Provider credentials are server-side environment configuration only and never appear in tool, usage, page, or error payloads.
- Documents have size/page/chunk bounds and no filesystem-path input surface.
- Provider input is limited to the query, candidate passages, or page content required for the requested operation.
- Remote calls are opt-in and still require a model to be benchmark-approved and enabled.
- No migration, staging harness, deployment, or production configuration is changed by this phase.

## Phase 2D.2 recommendation

## Phase 2D.2 live-evaluation gate

Phase 2D.2 adds a versioned corpus manifest at `benchmarks/phase2d/v1/corpus.json`, a bounded NIM serializer, a reproducible baseline/evaluation runner, and persisted approval records. It does **not** activate a candidate merely because an endpoint returns data.

`python scripts/run_specialist_benchmarks.py` records only the non-specialist lexical baseline. `python scripts/run_specialist_benchmarks.py --readiness` performs no provider call and returns only redacted configuration status. `python scripts/run_specialist_benchmarks.py --live` may call only the fixed Wave 1 models—`nvidia.nemotron-3-embed-1b`, `nvidia.llama-nemotron-rerank-1b-v2`, and `nvidia.nemotron-ocr-v2`—and only when the operator has enabled the server-side provider configuration. These commands are deliberately not exposed through MCP or the browser.

The corpus records its ID, version, SHA-256 digest, inputs, relevance labels, languages, source references, parsing/layout/table labels, visual-document labels, and required evidence lineage. Benchmark result artifacts store that corpus identity plus safe provider configuration, request count, latency samples, throughput, failure rate, estimated cost when supplied by a provider, and whether provenance was preserved. Credentials, authorization headers, raw endpoint paths, and raw document bodies are excluded.

The initial legacy corpus remains at `benchmarks/phase2d/v1/corpus.json`; its preserved `lexical_baseline` record remains exactly MRR `0.8125`, nDCG@10 `0.8576691395183482`, and Recall@5 `1.0`. It is a non-model lexical record for that original corpus, not a GPT or specialist result, and must not be compared across corpus versions.

The Wave 1 corpus is `benchmarks/specialists/v1/` (`mystic-specialists-synthetic-v1`, version `1.0.0`). It contains 45 project-authored CC0 scientific/math/engineering passages, 20 manually judged retrieval queries with hard negatives, four rendered PNG pages (paragraph, two-column, table/equation, and Korean/English sensor page), four parsing/layout records, three visual-structure judgments, provenance records, and a hash-checked `dataset_manifest.json`. `python benchmarks/specialists/v1/generate_assets.py --check` verifies the committed corpus; it does not contact a provider. The historical baseline record is stored separately at `records/lexical_baseline.phase2d-v1.0.1.json`.

### Provider boundary

`NvidiaNIMSpecialistProvider` accepts only registry-selected `embed`, `rerank`, and `ocr` calls. It requires `MYSTIC_NVIDIA_NIM_EXECUTION_ENABLED=true`; endpoint origins come from role-specific `MYSTIC_NVIDIA_NIM_{EMBED,RERANK,OCR}_BASE_URL` variables or the shared `MYSTIC_NVIDIA_NIM_BASE_URL`. HTTPS is required for remote hosts, HTTP is restricted to loopback, and non-default self-hosted hosts must be explicitly listed in `MYSTIC_NVIDIA_NIM_ALLOWED_HOSTS`. `MYSTIC_NVIDIA_NIM_API_KEY` stays server-side and is required for remote endpoints. Timeouts are bounded by `MYSTIC_NVIDIA_NIM_TIMEOUT_SECONDS` (1–60 seconds). The three Wave 1 model IDs are fixed registry entries rather than environment/request-selected values; a safe configuration report includes only `nim_configured`, `credential_present`, `endpoint_configured`, allowed endpoint host names, fixed selected model IDs, timeout, and the zero-retry policy.

The adapters implement NVIDIA's fixed capability endpoints: embeddings at `/v1/embeddings` with explicit `query` or `passage` input type; reranking at `/v1/ranking`; and OCR at `/v1/ocr` with bounded base64 PNG/JPEG data URLs. Provider responses are normalized into only the narrow contract needed by Mystic. Failures remain explicit (`unavailable`, `timeout`, `rate_limited`, `invalid_output`, `unsupported_input`, `model_disabled`, or `provider_offline`) and never produce fabricated evidence.

`LocalOpenAICompatibleEmbeddingProvider` is not a remote-provider escape hatch. It supports only a fixed `/v1/embeddings` endpoint on `localhost`, `127.0.0.1`, or `::1`, only models supplied through its server-side `allowed_model_ids` wiring, and only the `embed` operation. Its optional server-side variables are `MYSTIC_LOCAL_OPENAI_COMPATIBLE_EXECUTION_ENABLED`, `MYSTIC_LOCAL_OPENAI_COMPATIBLE_EMBED_BASE_URL`, `MYSTIC_LOCAL_OPENAI_COMPATIBLE_API_KEY`, and `MYSTIC_LOCAL_OPENAI_COMPATIBLE_TIMEOUT_SECONDS` (1–60 seconds). No default registry candidate uses this provider, so it cannot enable or route a model until a separately registered local model has passed the same live benchmark gate.

### Baseline, classification, and activation

Wave 1 compares retrieval and reranking with Mystic's lexical non-specialist baseline on the exact same corpus. This is not a claim that GPT was evaluated; GPT remains the controller and the benchmark baseline is stated explicitly. Embedding records Recall@1/5/10, MRR, nDCG@10, precision@5, p50/p95 latency, failure rate, and safe provider usage. Reranking uses the same candidate sets. OCR records character/word accuracy and error rate, numeric/unit recovery, table-cell recovery, reading-order correctness, source-labeled layout-element recovery, p50/p95 latency, and failure rate. OCR may be classified `ESSENTIAL` only after a real document asset demonstrates at least 0.90 character accuracy with preserved provenance. A `SUPERIOR` result requires at least a 0.03 quality improvement; an `ACCELERATOR` requires quality within 0.01 of baseline plus at least 25% lower measured cost or latency. A failure rate above 5% or missing provenance is `REJECTED`; no measured advantage is `REDUNDANT`.

When and only when the live gate passes, the registry receives the derived classification, the router can enable the healthy candidate, and `mystic_data/specialist_benchmarks/approvals.json` records its result hash, benchmark ID, quality metric, reliability, and timestamp. On restart, approval metadata is reapplied only while the provider is healthy. Every normal retrieval/evidence use then records the actual executing model and fallback lineage in the existing provenance chain.

Secondary candidates—parser, VL embedding/reranking, page elements, table structure, and code embedding—remain disabled. The corpus supplies controlled labels where applicable, but each still requires its own live baseline comparison before Phase 2D.2 can assess it.
