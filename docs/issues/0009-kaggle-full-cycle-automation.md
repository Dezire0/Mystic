# Issue #9: Automate the free Kaggle GPU training cycle

## Summary
Extend Mystic's cycle runner so a full Raven adapter training cycle can be driven end-to-end through Kaggle's free GPU notebooks using the Kaggle CLI.

## Motivation
The current cycle runner removes most local manual work, but the remote GPU step is still manual. Because the target constraint is zero-cost GPU access, Kaggle is the only realistic default remote provider. Mystic needs a practical Kaggle-first automation path for dataset upload, kernel execution, output download, and local reinjection.

## Current Behavior
- `scripts/run_mystic_cycle.py` only handles local `prepare`, `finish`, and `status`.
- The user must still upload files to Kaggle, start a notebook, wait, and download outputs manually.
- There is no polling or download automation tied back into the local cycle runner.

## Expected Behavior
- The cycle runner can submit a prepared package to Kaggle, trigger a GPU notebook run, poll its status, download the output tarball, and then finish the local reinjection flow automatically.
- The automation uses only Kaggle CLI plus local files.
- The workflow remains Kaggle-specific and avoids paid GPU providers.

## Scope
- Extend `scripts/run_mystic_cycle.py` with Kaggle submission and polling helpers.
- Add cycle artifacts under `mystic_data/cycles/<cycle_id>/`.
- Update tests and README.

## Player Flow
1. Prepare a cycle locally.
2. Submit the cycle package to Kaggle as a dataset and notebook.
3. Poll until Kaggle finishes.
4. Download the adapter artifact.
5. Reinject it locally and register the model.

## Non-goals
- RunPod automation
- Vast.ai automation
- Colab automation
- Web dashboards
- Multi-provider orchestration

## Acceptance Criteria
- The cycle runner can create or version a Kaggle dataset for the cycle package.
- The cycle runner can push a Kaggle kernel with GPU enabled.
- The cycle runner can poll kernel status and detect completion or failure.
- The cycle runner can download outputs and locate the adapter tarball automatically.
- The cycle runner can call local `finish` after download and produce a final summary.

## Verification Plan
- Add unit tests for Kaggle status parsing and artifact discovery.
- Add mocked tests for submit/download/full helper behavior.
- Verify existing local cycle tests still pass.

## Reproduction Steps
1. Run local `prepare`.
2. Manually upload the package to Kaggle.
3. Manually configure and run the notebook.
4. Manually download the output tarball.
5. Run local `finish`.

## Actual Result
The free-GPU path works, but it still requires several manual Kaggle steps.

## Expected Result
Kaggle GPU usage becomes a CLI-driven stage of the normal Mystic cycle.

## Environment
- Local macOS workspace
- Python 3.11
- Kaggle CLI credentials required for submit/poll/download
