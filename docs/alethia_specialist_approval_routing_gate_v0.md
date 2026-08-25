# ALETHEIA 2D Specialist Approval & Routing Gate v0

Status: implementation ready for review in [PR #140](https://github.com/Dezire0/Mystic/pull/140), resolving [Issue #139](https://github.com/Dezire0/Mystic/issues/139). The initial implementation commit is `3f0f4f357f0622d9a507d05b72b7bf760e1cc15f`.

## Purpose

Successful execution is evidence, not adoption. The gate answers **whether** a candidate may be used, while routing answers **which already-approved** candidate to use. Keeping those decisions separate prevents a successful toy benchmark or a working provider from silently becoming a production specialist.

## Architecture

```text
ScientificTask
  -> SpecialistRouter
  -> SpecialistApprovalGate
  -> approved candidate
  -> provider/dispatcher
  -> specialist execution
```

`SpecialistApprovalGate` evaluates versioned benchmark records against capability-specific rules and produces an immutable `ApprovalRecord`. `ApprovedSpecialistRouter` only selects registry records whose status is `APPROVED`; it never evaluates evidence or promotes a candidate. If no approved candidate exists, it returns an explicit `NO_APPROVED_CANDIDATE` receipt. A fallback is not configured in v0, so there is no implicit baseline or production switching.

The registry stores the candidate identity, capability, version and model revision, execution backend, modalities, status, evidence references, approval record, and timestamps. A model revision or version update clears an existing approval and returns the record to `EXPERIMENTAL` until matching evidence is evaluated again. Routing is deterministic: it chooses the lexicographically first candidate ID among approved capability matches and records every eligible and ineligible candidate, reason, evidence reference, backend, and timestamp.

## Approval policy

Policies are explicit and capability-specific. An approval requires all configured benchmark suites, required quality metric thresholds, reliability threshold, successful execution-environment acceptance, and reproducible/versioned evidence. The result schema retains the individual quality metrics, latency, VRAM, reliability, resource/cost data, hardware/backend, revision, timestamp, and raw evidence reference; it intentionally has no arbitrary aggregate score.

Failures are machine-readable (for example `MISSING_BENCHMARK:suite`, `QUALITY_BELOW_THRESHOLD:top_1:suite`, and `STALE_MODEL_REVISION:suite`). Incomplete evidence remains `EXPERIMENTAL`; failed threshold, execution, environment, reliability, or stale-revision evidence is `REJECTED`. Neither can route.

## Initial registry and evidence limitations

All initial candidates are seeded as `EXPERIMENTAL`, not `APPROVED`, with the observed evidence below. They are registry records only and do not activate a route.

| Capability | Candidate | Observed evidence | Approval status |
| --- | --- | --- | --- |
| `scientific.text_retrieval` | `nvidia/llama-nemotron-embed-1b-v2` | 2048-dimensional output; synthetic 1,000-doc run at about 354 docs/sec; toy semantic Top-1 5/5 and Recall@3 5/5; T4 execution proven | EXPERIMENTAL |
| `scientific.visual_retrieval` | `nvidia/llama-nemotron-embed-vl-1b-v2` | text-to-image retrieval and T4 execution proven | EXPERIMENTAL |
| `scientific.multimodal_reranking` | `nvidia/llama-nemotron-rerank-vl-1b-v2` | native Transformers adapter; relevant gravitational-lensing result ranked first; T4 execution proven | EXPERIMENTAL |

The Lightning dispatcher acceptance is evidence for the execution backend only: real remote execution succeeded, automatic T4 lifecycle completed, and an identical second invocation returned `reused=True`. It is not a benchmark suite or a model-quality approval. The evidence is intentionally described as small/toy where that is all that was observed; it does not establish scientific superiority.

Lightning remains an ALETHEIA implementation detail. Its production v0 file contract is artifact ingress, explicit `lightning studio cp` materialization into the running Studio filesystem, worker execution, explicit result publication back to artifacts, and local result download. This remains separate from candidate eligibility.

## Scope and next work

WORLD, HERMES, and OIKOS remain unchanged. No paid provider dependency, autonomous discovery, automatic model evolution, or automatic production model switching is introduced.

Before discovery or automatic evolution can be considered, each capability needs a versioned, reproducible scientific benchmark suite, acceptance-environment results for the exact model revision, declared thresholds, and a reviewed approval record. Any future safe fallback must be explicitly configured and independently audited.

## Implementation and verification

Issue: [#139](https://github.com/Dezire0/Mystic/issues/139). Pull request: [#140](https://github.com/Dezire0/Mystic/pull/140). Initial implementation commit: `3f0f4f357f0622d9a507d05b72b7bf760e1cc15f`.

The focused approval-gate tests cover non-routing of unapproved candidates, no silent experimental promotion, threshold and missing-evidence reasons, deterministic approval and routing, no-eligible and multiple-approved cases, route receipts, and revision invalidation. The PR records the exact final command results.
