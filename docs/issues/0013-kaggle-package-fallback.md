# Issue #13: Add a Kaggle kernel package fallback when dataset mounts fail

## Summary
Patch the Kaggle cycle so the uploaded training tarball is also bundled with the kernel payload and the Kaggle training script can load it locally if the dataset mount never appears.

## Motivation
The current Kaggle cycle can publish the dataset and push the kernel successfully, but the runtime still fails before training if `/kaggle/input/<dataset-slug>` does not appear. This blocks free-GPU training even when the local package is small and could be shipped with the kernel itself.

## Current Behavior
- `run_mystic_cycle.py submit` pushes a dataset and a kernel.
- The generated Kaggle script only searches `/kaggle/input/...` for the tarball.
- If Kaggle never mounts the dataset, the cycle fails before extraction and training.

## Expected Behavior
- The kernel directory also includes the cycle tarball.
- The generated Kaggle script first checks local bundle locations, then dataset mounts.
- The cycle can still start training when the dataset mount is missing but the kernel bundle is present.

## Scope
- Update `scripts/run_mystic_cycle.py`
- Update `tests/test_run_mystic_cycle.py`
- Keep existing dataset-source behavior intact as a preferred path

## Acceptance Criteria
- The generated Kaggle script searches both local bundle paths and `/kaggle/input`.
- `submit` copies the package tarball into the Kaggle kernel directory.
- Targeted tests pass.

## Verification Plan
- Run unit tests for `test_run_mystic_cycle.py`.
- Re-submit `cycle_1` to Kaggle and confirm the script can find a tarball without relying solely on dataset mounts.
