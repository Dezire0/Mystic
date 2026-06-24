from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mystic.core.protocol import AgentOutput, ModelSettings
from mystic.memory.archive import ArchiveStore


class ArchiveTests(unittest.TestCase):
    def test_archive_stores_and_exports_agent_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = ArchiveStore(Path(temp_dir) / "mystic.sqlite3")
            session_id = archive.create_session("problem")
            output = AgentOutput(
                agent="prime",
                division="pure_math",
                claim="claim",
                status="PROMISING",
                reasoning="reasoning",
                dependencies=["core"],
                obstruction="obstruction",
                experiment="",
                formalization="",
                next_move="next",
            )
            settings = ModelSettings(provider="mock", model="qwen", adapter="prime_lora_v0", temperature=0.1)
            archive.record_agent_output(session_id, "problem", output, settings)
            paths = archive.export_dataset("all")
            self.assertTrue(paths)
            self.assertTrue(Path(paths[0]).exists())


if __name__ == "__main__":
    unittest.main()

