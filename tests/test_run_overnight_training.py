from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.run_overnight_training import (
    build_progress_payload,
    decode_process_stream,
    has_cached_hf_rows,
    has_cached_numina_rows,
    step_label,
)


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

    def test_step_label_and_progress_payload_are_human_readable(self):
        label = step_label(
            [
                "python",
                "scripts/download_hf_samples.py",
                "--max-rows",
                "50",
                "--slugs",
                "openmathinstruct_2",
            ]
        )
        self.assertEqual(label, "Hugging Face 샘플 다운로드 · openmathinstruct_2")

        payload = build_progress_payload(
            run_id="overnight_1",
            run_label="overnight_1",
            iteration=1,
            iterations_total=2,
            total_steps=4,
            completed_steps=1,
            current_step_index=2,
            current_step_label="전문가 학습 배치 실행",
            status="running",
            started_at="2026-06-26T00:00:00+00:00",
            effective_numina_limit=3000,
            effective_hf_rows=200,
            effective_public_rows=300,
        )
        self.assertEqual(payload["progress_percent"], 25)
        self.assertEqual(payload["current_step_label"], "전문가 학습 배치 실행")
        self.assertEqual(payload["iteration"], 1)


if __name__ == "__main__":
    unittest.main()
