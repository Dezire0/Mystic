from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mystic.training.ingest import build_ingestion_registry


class TrainingIngestTests(unittest.TestCase):
    def test_ingestion_registry_creates_source_manifests(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = build_ingestion_registry(temp_dir)
            registry = Path(payload["registry_path"])
            self.assertTrue(registry.exists())
            data = json.loads(registry.read_text(encoding="utf-8"))
            self.assertTrue(data["sources"])
            self.assertEqual(data["sources"][0]["slug"], "internal_mystic_data")


if __name__ == "__main__":
    unittest.main()
