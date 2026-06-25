from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.run_overnight_training import decode_process_stream, has_cached_hf_rows, has_cached_numina_rows


class RunOvernightTrainingTests(unittest.TestCase):
    def test_decode_process_stream_accepts_bytes(self):
        self.assertEqual(decode_process_stream(b"hello"), "hello")

    def test_cached_row_helpers_detect_existing_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir) / "mystic_data"
            (base / "raw" / "numina_math_cot_100.jsonl").parent.mkdir(parents=True, exist_ok=True)
            (base / "raw" / "openr1_mixture_of_thoughts").mkdir(parents=True, exist_ok=True)
            (base / "raw" / "proofnet").mkdir(parents=True, exist_ok=True)
            (base / "raw" / "numina_math_cot_100.jsonl").write_text('{"x":1}\n{"x":2}\n', encoding="utf-8")
            (base / "raw" / "openr1_mixture_of_thoughts" / "sample.jsonl").write_text('{"x":1}\n', encoding="utf-8")
            (base / "raw" / "proofnet" / "snapshot_manifest.json").write_text('{"snapshot_path":"/tmp/x"}\n', encoding="utf-8")

            self.assertTrue(has_cached_numina_rows(base, 2))
            self.assertTrue(has_cached_hf_rows(base, "openr1_mixture_of_thoughts"))
            self.assertTrue(has_cached_hf_rows(base, "proofnet"))


if __name__ == "__main__":
    unittest.main()
