# ALETHEIA Roadmap

## Delivered baseline

- Lightning Specialist Dispatcher v0: existing Studio/T4 lifecycle and controlled real acceptance proven.
- 2D Specialist Approval & Routing Gate v0: evidence eligibility is separate from deterministic approved-only routing; no candidate is approved by default.

## Current milestone — 2D Specialist Scientific Benchmark Suite v0

Issue [#141](https://github.com/Dezire0/Mystic/issues/141) introduces frozen, versioned, capability-specific evidence generation for the three experimental NVIDIA candidates. It records repeated runs and review reports without activation. Review is in [PR #142](https://github.com/Dezire0/Mystic/pull/142); initial implementation commit: `7856443be92e6005e7d482fd5f04b1492068a120`. See [Scientific Benchmark Suite v0](alethia_scientific_benchmark_suite_v0.md).

## Next decision gate

A human-reviewed capability threshold policy, broader independent frozen scientific data, and complete real T4 executions are required before any candidate can move from `EXPERIMENTAL` to `APPROVED`. Approval remains separate from routing and does not authorize autonomous model discovery or switching.
