# Issue #1: Bootstrap Mystic v0.1 multi-specialist local-first scaffold

## Summary
Create the initial local-first Python scaffold for Mystic v0.1 with separate specialist agent classes, prompts, config entries, archive records, and dataset export paths.

## Motivation
The architecture canvas requires Mystic to behave as a multi-specialist research system rather than a single generic chatbot. The repository is currently empty, so the first deliverable is a coherent CLI-first foundation that preserves specialist separation in code structure.

## Current Behavior
There is no project structure, no configuration, no CLI, no archive layer, and no agent orchestration flow.

## Expected Behavior
The repository should contain a typed, testable Python project that can initialize local storage, route a problem to multiple specialist agents, archive outputs, run a safe Python experiment, attempt Lean verification, and generate a report.

## Scope
- Create the required repository structure from the architecture canvas.
- Implement config-driven model registry and rule-based router.
- Implement CLI-first orchestration and local archive storage.
- Implement separate specialist agent files and prompt files.
- Add minimal tests for core workflow pieces.

## Acceptance Criteria
- `mystic run "..."` executes the core planning and multi-agent workflow locally.
- Every specialist has a distinct class file, prompt file, and model config entry.
- Archive records store model/provider/adapter metadata per agent message.
- Dataset export writes JSONL files by agent type.
- Tests cover router, registry, archive, protocol, runners, and representative agents.

## Verification Plan
- Run unit tests for protocol, router, model registry, archive, Python runner, and agents.
- Manually exercise the CLI for `init`, `agents`, `config`, and `run`.

## Reproduction Steps
1. Open the repository.
2. Observe that the working tree contains only the Git metadata directory.

## Actual Result
No implementation exists.

## Expected Result
Mystic v0.1 scaffold exists and runs locally.

## Environment
- Local macOS workspace
- Python 3.11+
- No remote repository connected yet

