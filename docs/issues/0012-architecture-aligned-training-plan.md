# Issue #12: Align architecture sections to checklist datasets and persist a training plan

## Summary
Map every section from `mystic_v0_1_architecture_canvas.md` to checklist datasets, persist the mapping as a Markdown training plan, and expose the same structure in metadata so training work follows the architecture instead of a reduced subset.

## Motivation
The repository currently has checklist-derived manifests for a smaller set of training targets, but the architecture canvas defines a broader multi-specialist structure. The plan needs to reflect the actual divisions and agent boundaries before more training work is queued.

## Current Behavior
- `training_manifest.json` only covers a subset of specialist targets.
- There is no persisted Markdown plan tied to the architecture canvas sections.
- The current Raven cycle exists, but the broader architecture is not represented in one place with dataset mapping.

## Expected Behavior
- Every architecture section is mapped to relevant checklist datasets.
- The mapping is saved as a Markdown training plan and a machine-readable manifest.
- The plan clearly distinguishes current executable training from planning-only targets.

## Scope
- Add architecture-aligned target metadata
- Generate a Markdown training plan under `mystic_data/metadata/`
- Keep the existing execution manifests intact
- Update tests for the new metadata artifacts

## Acceptance Criteria
- A generated file lists all architecture sections with model, adapter, and checklist dataset mapping.
- A JSON manifest exists for the same architecture-aligned targets.
- Existing manifest-driven workflow behavior remains intact.
- Targeted tests pass.

## Verification Plan
- Rebuild metadata artifacts locally.
- Inspect the generated Markdown and JSON plan files.
- Run targeted unit tests for the bootstrap and manifest workflow layers.
