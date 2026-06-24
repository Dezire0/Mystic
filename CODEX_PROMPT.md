# Mystic Codex Prompt Rules

## Core Rule

Even when multiple specialists use the same underlying open model, the codebase must treat them as different specialist models.

This separation is mandatory in:

- agent class files
- prompt files
- model config entries
- archive rows
- dataset export paths
- future LoRA or QLoRA adapter targets

## Implementation Guardrails

- Do not collapse specialists into one generic agent.
- Do not share a single prompt across domain specialists.
- Do not store mixed archive rows without agent identity and model metadata.
- Do not export one merged training file as the only source of truth.
- Keep CLI and local-first workflow ahead of frontend work.

## v0.1 Priority

1. Core planning and routing
2. Raven critique
3. Forge execution
4. Archive and dataset export
5. Lean probing
6. Additional specialist depth

