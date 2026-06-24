# Metadata

This directory contains versioned metadata that defines how Mystic data is collected, validated, and prepared for specialist training.

## Contents

- `schemas/`: JSON Schema files for internal records and train-ready rows
- `manifests/`: generated manifests for dataset splits and specialist training targets
- `dataset_catalog.json`: checklist-derived dataset catalog

Bootstrap these files with:

```bash
python3 scripts/init_internal_mystic_data.py
python3 scripts/build_training_manifests.py
python3 scripts/seed_internal_examples.py
python3 scripts/prepare_train_ready.py
```

Plan a first training run with:

```bash
python3 scripts/plan_training_run.py --agent raven
```
