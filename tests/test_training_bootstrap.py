from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mystic.training.bootstrap import build_metadata_bundle, init_internal_data_files, write_train_ready_seed


class TrainingBootstrapTests(unittest.TestCase):
    def test_internal_dataset_files_are_created(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            created = init_internal_data_files(temp_dir)
            self.assertIn("failed_proofs.jsonl", created[0])
            for path in created:
                self.assertTrue(Path(path).exists())

    def test_metadata_bundle_contains_training_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle = build_metadata_bundle(temp_dir)
            manifest_path = Path(bundle["manifests_root"]) / "training_manifest.json"
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            agents = [item["agent"] for item in payload["targets"]]
            self.assertIn("raven", agents)
            self.assertIn("forge", agents)

    def test_train_ready_seed_files_are_created(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            created = write_train_ready_seed(temp_dir)
            self.assertTrue(created)
            self.assertTrue(Path(created[0]).exists())


if __name__ == "__main__":
    unittest.main()
