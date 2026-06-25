from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mystic.training.continuous import normalize_rotation_slugs


class TrainingContinuousTests(unittest.TestCase):
    def test_normalize_rotation_slugs_moves_snapshot_only_sources_to_end(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir) / "mystic_data"
            (base / "raw" / "openmathinstruct_2").mkdir(parents=True, exist_ok=True)
            (base / "raw" / "proofnet").mkdir(parents=True, exist_ok=True)
            (base / "raw" / "openmathinstruct_2" / "sample.jsonl").write_text('{"x":1}\n', encoding="utf-8")
            (base / "raw" / "proofnet" / "snapshot_manifest.json").write_text('{"snapshot_path":"/tmp/proofnet"}\n', encoding="utf-8")

            ordered = normalize_rotation_slugs(base, ["proofnet", "openmathinstruct_2", "proofnet"])
            self.assertEqual(ordered, ["openmathinstruct_2", "proofnet"])


if __name__ == "__main__":
    unittest.main()
