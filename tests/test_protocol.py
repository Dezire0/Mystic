from __future__ import annotations

import unittest

from mystic.core.protocol import AgentOutput


class ProtocolTests(unittest.TestCase):
    def test_agent_output_serializes_protocol_fields(self):
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
        payload = output.to_structured_dict()
        self.assertEqual(payload["CLAIM"], "claim")
        self.assertEqual(payload["STATUS"], "PROMISING")


if __name__ == "__main__":
    unittest.main()

