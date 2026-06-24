from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mystic.raven_training import load_jsonl
from scripts.train_raven_lora import main as train_main
from scripts.train_raven_lora import qlora_support_status, tokenize_rows


class _FakeTokenizer:
    pad_token = None
    eos_token = "<eos>"
    unk_token = "<unk>"

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False):
        rendered = "\n".join(f"{item['role']}:{item['content']}" for item in messages)
        if add_generation_prompt:
            rendered += "\nassistant:"
        return rendered

    def __call__(self, text, truncation=True, max_length=32, padding="max_length"):
        size = min(len(text), max_length)
        return {
            "input_ids": [1] * max_length,
            "attention_mask": [1] * size + [0] * (max_length - size),
        }


class _FakeCuda:
    @staticmethod
    def is_available():
        return False


class _FakeMps:
    @staticmethod
    def is_available():
        return False


class _FakeBackends:
    mps = _FakeMps()


class _FakeTorch:
    cuda = _FakeCuda()
    backends = _FakeBackends()


class TrainRavenLoraTests(unittest.TestCase):
    def test_qlora_support_reports_unsupported_without_cuda(self):
        payload = qlora_support_status(_FakeTorch())
        self.assertFalse(payload["supported"])
        self.assertFalse(payload["cuda_available"])

    def test_tokenize_rows_returns_lengths(self):
        tokenizer = _FakeTokenizer()
        rows = [
            {
                "messages": [
                    {"role": "system", "content": "s"},
                    {"role": "user", "content": "u"},
                    {"role": "assistant", "content": "{}"},
                ]
            }
        ]
        tokenized, lengths = tokenize_rows(tokenizer, rows, 16)
        self.assertEqual(len(tokenized), 1)
        self.assertGreaterEqual(lengths["avg"], 1.0)

    def test_dry_run_writes_training_log_and_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            train_file = root / "mystic_data" / "train_ready" / "raven_train.jsonl"
            eval_file = root / "mystic_data" / "eval_holdout" / "raven_eval.jsonl"
            train_file.parent.mkdir(parents=True, exist_ok=True)
            eval_file.parent.mkdir(parents=True, exist_ok=True)
            row = {
                "sample_id": "s1",
                "messages": [
                    {"role": "system", "content": "s"},
                    {"role": "user", "content": "u"},
                    {"role": "assistant", "content": "{\"verdict\":\"INVALID\"}"},
                ],
                "assistant_output": "{\"verdict\":\"INVALID\"}",
                "target_verdict": "INVALID",
            }
            train_file.write_text(json.dumps(row) + "\n", encoding="utf-8")
            eval_file.write_text(json.dumps(row) + "\n", encoding="utf-8")

            with patch("scripts.train_raven_lora.ROOT", root), patch(
                "scripts.train_raven_lora.load_training_defaults",
                return_value={
                    "base_model": "fake/model",
                    "adapter_name": "raven_lora_v0",
                    "epochs": 1,
                    "batch_size": 1,
                    "learning_rate": 0.0002,
                    "max_length": 32,
                    "lora_r": 16,
                    "lora_alpha": 32,
                    "lora_dropout": 0.05,
                },
            ), patch("transformers.AutoTokenizer.from_pretrained", return_value=_FakeTokenizer()):
                result = train_main(
                    [
                        "--dry-run",
                        "--train-file",
                        str(train_file),
                        "--eval-file",
                        str(eval_file),
                        "--output-dir",
                        str(root / "mystic_data" / "adapters" / "raven_lora_v0"),
                    ]
                )

            self.assertEqual(result, 0)
            log_rows = load_jsonl(root / "mystic_data" / "logs" / "training_log.jsonl")
            self.assertEqual(log_rows[-1]["status"], "DRY_RUN_OK")
            snapshot = root / "mystic_data" / "adapters" / "raven_lora_v0" / "training_config.json"
            self.assertTrue(snapshot.exists())


if __name__ == "__main__":
    unittest.main()
