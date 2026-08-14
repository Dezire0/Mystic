# Mystic LAB Phase 2D — Specialist Intelligence Layer

## Status

Phase 2D.1 establishes the local, vendor-neutral foundation. It does not enable a remote model, deploy a provider, modify the Phase 2C.2B staging environment, or claim model-quality results. Candidate models remain disabled until a live, task-specific benchmark records an approved result.

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

`SpecialistProvider` is capability-oriented. The Phase 2D.1 NVIDIA NIM adapter is configuration-gated and sends no request by default. It records `unavailable`, `model_disabled`, `timeout`, `rate_limited`, `invalid_output`, `unsupported_input`, or `provider_offline`; it never manufactures an embedding, rerank score, OCR text, or parse result. Future local Hugging Face or self-hosted providers implement the same protocol.

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

Supply a versioned scientific retrieval/OCR benchmark corpus and a deliberately configured NIM or local provider. Run live candidates through the harness, record reproducible cost/latency/availability, approve only candidates meeting thresholds, then add the corresponding provider-specific execution serializer and an authenticated cloud rollout plan.
