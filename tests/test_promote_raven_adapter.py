from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.promote_raven_adapter import main as promote_main


class PromoteRavenAdapterTests(unittest.TestCase):
    def test_promote_marks_model_active_and_logs_decision(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            metadata_dir = root / "mystic_data" / "metadata"
            logs_dir = root / "mystic_data" / "logs"
            metadata_dir.mkdir(parents=True, exist_ok=True)
            logs_dir.mkdir(parents=True, exist_ok=True)
            (metadata_dir / "model_versions.json").write_text(
                json.dumps(
                    {
                        "models": [
                            {
                                "model_id": "raven_lora_v0",
                                "base_model": "Qwen/Qwen2.5-0.5B-Instruct",
                                "adapter_path": "mystic_data/adapters/raven_lora_v0",
                            }
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            comparison_log = logs_dir / "raven_comparison_results.jsonl"
            comparison_log.write_text(
                json.dumps(
                    {
                        "kind": "summary",
                        "metrics": {
                            "base": {
                                "valid_json_rate": 0.5,
                                "verdict_match_rate": 0.4,
                                "first_fatal_error_nonempty_rate": 0.5,
                                "invalid_output_count": 2,
                            },
                            "adapter": {
                                "valid_json_rate": 1.0,
                                "verdict_match_rate": 0.4,
                                "first_fatal_error_nonempty_rate": 0.8,
                                "invalid_output_count": 0,
                            },
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with patch("scripts.promote_raven_adapter.ROOT", root):
                result = promote_main(
                    [
                        "--model-id",
                        "raven_lora_v0",
                        "--comparison-log",
                        str(comparison_log),
                    ]
                )

            self.assertEqual(result, 0)
            registry = json.loads((metadata_dir / "model_versions.json").read_text(encoding="utf-8"))
            self.assertTrue(registry["models"][0]["active"])
            self.assertTrue((logs_dir / "raven_promotion_log.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
