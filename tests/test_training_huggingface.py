from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mystic.training.huggingface import get_hf_auth_status, resolve_hf_datasets


class TrainingHuggingFaceTests(unittest.TestCase):
    def test_auth_status_shape(self):
        payload = get_hf_auth_status()
        self.assertIn("token_present", payload)

    @patch("mystic.training.huggingface._make_hf_api")
    def test_resolution_writes_registry(self, api_factory):
        api = api_factory.return_value
        dataset_stub = type("DatasetStub", (), {"id": "AI-MO/NuminaMath-CoT"})
        api.list_datasets.return_value = [dataset_stub()]
        api.whoami.return_value = {"name": "stub-user"}
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = resolve_hf_datasets(Path(temp_dir), limit=1)
            self.assertTrue(Path(payload["registry_path"]).exists())


if __name__ == "__main__":
    unittest.main()
