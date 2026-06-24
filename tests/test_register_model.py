from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.register_model import main as register_main


class RegisterModelTests(unittest.TestCase):
    def test_register_model_appends_entry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            metadata_dir = root / "mystic_data" / "metadata"
            metadata_dir.mkdir(parents=True, exist_ok=True)
            (metadata_dir / "model_versions.json").write_text('{"models": []}\n', encoding="utf-8")

            with patch("scripts.register_model.ROOT", root):
                result = register_main(
                    [
                        "--model-id",
                        "raven_lora_v0",
                        "--base-model",
                        "Qwen/Qwen2.5-0.5B-Instruct",
                        "--adapter-path",
                        "mystic_data/adapters/raven_lora_v0",
                        "--metrics",
                        '{"valid_json_rate": 0.9}',
                    ]
                )

            self.assertEqual(result, 0)
            payload = json.loads((metadata_dir / "model_versions.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["models"][-1]["model_id"], "raven_lora_v0")
            self.assertEqual(payload["models"][-1]["metrics"]["valid_json_rate"], 0.9)


if __name__ == "__main__":
    unittest.main()
