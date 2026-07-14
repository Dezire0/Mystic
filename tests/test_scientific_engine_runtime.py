from __future__ import annotations

import unittest

from mystic.lab.engines import EngineError, builtin_registry
from mystic.lab.engines.runtime import EngineRuntime


class ScientificEngineRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = builtin_registry()

    def test_registry_is_deterministic_and_allowlisted(self) -> None:
        self.assertEqual([manifest.engine_id for manifest in self.registry.list()], ["biology.population_dynamics", "chemistry.reaction_kinetics", "engineering.dc_circuit", "math.sympy", "physics.n_body", "physics.simple_collision", "physics.simple_projectile"])
        with self.assertRaises(EngineError) as raised:
            self.registry.get("user.supplied.module")
        self.assertEqual(raised.exception.code, "engine_not_found")

    def test_runtime_creates_and_completes_structured_projectile_result(self) -> None:
        runtime=EngineRuntime(self.registry)
        job=runtime.create_job(engine_id="physics.simple_projectile",session_id="session-1",scene_id="scene-1",input_payload={"initial_position":[0,0,0],"initial_velocity":[1,5,0],"duration_seconds":1})
        result=runtime.execute_next()
        self.assertEqual(result["status"],"completed")
        self.assertEqual(result["engine_id"],"physics.simple_projectile")
        self.assertEqual(result["reproducibility"]["level"],"exact")
        self.assertEqual(result["reproducibility"]["session_id"],"session-1")
        self.assertEqual(result["visualization"]["layers"][0]["type"],"trajectory")
        self.assertIn(job["job_id"], runtime.queue.results)

    def test_safe_low_voltage_circuit_and_resource_limits(self) -> None:
        plugin=self.registry.get("engineering.dc_circuit")
        payload=plugin.validate_input({"source_voltage_v":5,"resistance_top_ohm":1000,"resistance_bottom_ohm":1000})
        self.assertEqual(plugin.execute(payload, None).values["node_voltages_v"]["divider"],2.5)
        with self.assertRaises(EngineError) as raised:
            plugin.validate_input({"source_voltage_v":240,"resistance_top_ohm":1000,"resistance_bottom_ohm":1000})
        self.assertEqual(raised.exception.code,"engine_input_invalid")

    def test_cancellation_is_visible_before_execution(self) -> None:
        runtime=EngineRuntime(self.registry)
        job=runtime.create_job(engine_id="engineering.dc_circuit",input_payload={"source_voltage_v":5,"resistance_top_ohm":10,"resistance_bottom_ohm":10})
        runtime.queue.request_cancellation(job["job_id"])
        self.assertIsNone(runtime.execute_next())
        self.assertEqual(runtime.queue.jobs[job["job_id"]].status,"cancelled")


if __name__ == "__main__":
    unittest.main()
