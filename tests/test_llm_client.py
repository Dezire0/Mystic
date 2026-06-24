from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mystic.llm_client import AdapterClient, OpenAICompatibleClient, build_client


class LLMClientTests(unittest.TestCase):
    def test_openai_compatible_client_builds_v1_endpoint_from_root(self):
        client = OpenAICompatibleClient(base_url="http://localhost:8000")
        self.assertEqual(client.endpoint_url, "http://localhost:8000/v1/chat/completions")

    def test_openai_compatible_client_builds_chat_endpoint_from_v1(self):
        client = OpenAICompatibleClient(base_url="http://localhost:8000/v1")
        self.assertEqual(client.endpoint_url, "http://localhost:8000/v1/chat/completions")

    def test_openai_compatible_client_extracts_text_parts(self):
        client = OpenAICompatibleClient(base_url="http://localhost:8000/v1")
        text = client._extract_text(
            {
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"type": "text", "text": "hello"},
                                {"type": "text", "text": " world"},
                            ]
                        }
                    }
                ]
            },
            "",
        )
        self.assertEqual(text, "hello world")

    @patch.object(AdapterClient, "_load_runtime", autospec=True, return_value=None)
    def test_build_client_constructs_adapter_client(self, _load_runtime):
        client = build_client(
            "adapter",
            config_path="/Users/JYH/Documents/Mystic/configs/models.json",
            base_model="Qwen/Qwen2.5-0.5B-Instruct",
            adapter_path="mystic_data/adapters/raven_lora_v0",
        )
        self.assertIsInstance(client, AdapterClient)
        self.assertEqual(client.base_model, "Qwen/Qwen2.5-0.5B-Instruct")

    @patch.object(AdapterClient, "_load_runtime", autospec=True, return_value=None)
    def test_adapter_validation_rejects_mismatched_base(self, _load_runtime):
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter_dir = Path(temp_dir) / "adapter"
            adapter_dir.mkdir(parents=True, exist_ok=True)
            (adapter_dir / "adapter_config.json").write_text(
                json.dumps({"base_model_name_or_path": "sshleifer/tiny-gpt2"}) + "\n",
                encoding="utf-8",
            )
            client = AdapterClient(
                base_model="Qwen/Qwen2.5-0.5B-Instruct",
                adapter_path=adapter_dir,
            )
            with self.assertRaises(ValueError):
                client._validate_adapter_metadata()


if __name__ == "__main__":
    unittest.main()
