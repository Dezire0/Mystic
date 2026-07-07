from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from mystic.mcp.tools import MysticToolbox
from mystic.models.router import ModelRouter


TEST_CONFIG = """
models:
  local_prime:
    provider: mock
    model: mock-prime
    role_defaults:
      - draft
  local_raven:
    provider: mock
    model: mock-raven
    role_defaults:
      - critique
policy:
  max_models_per_compare: 3
  timeout_per_model_seconds: 5
"""


class LabSceneApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        config_path = self.root / "models.yaml"
        config_path.write_text(TEST_CONFIG, encoding="utf-8")
        router = ModelRouter(root_path=self.root, config_path=config_path)
        self.toolbox = MysticToolbox(root_path=self.root, router=router)
        session = self.toolbox.lab_session_create(
            problem="Track a projectile and a collision in a persisted local scene.",
            domain="physics",
            goal="Exercise Phase 1 scene tools.",
            mode="cheap",
            participants=["local_prime", "local_raven"],
        )
        self.session_id = session["session_id"]

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_scene_crud_snapshot_and_report_round_trip(self) -> None:
        scene = self.toolbox.create_lab_scene(
            session_id=self.session_id,
            title="Projectile baseline",
            description="Local scene path.",
            units={"length": "m", "time": "s", "mass": "kg"},
            parameters={"gravity": 9.81},
        )
        scene_dir = self.root / "mystic_data" / "lab_scenes" / scene["scene_id"]
        self.assertTrue((scene_dir / "scene.json").exists())

        added = self.toolbox.add_lab_object(
            scene_id=scene["scene_id"],
            object={
                "id": "ball-1",
                "type": "rigid_body",
                "label": "Projectile",
                "position": {"x": 0, "y": 1, "z": 0},
                "rotation": {"x": 0, "y": 0, "z": 0},
                "scale": {"x": 1, "y": 1, "z": 1},
                "geometry": {"kind": "sphere", "radius": 0.1},
                "material": {"color": "#ff7a59"},
                "data": {"mass": 0.2, "velocity": {"x": 5, "y": 8, "z": 0}},
                "metadata": {"source": "test"},
            },
        )
        updated = self.toolbox.update_lab_object(
            scene_id=scene["scene_id"],
            object_id="ball-1",
            patch={"label": "Projectile A", "material": {"color": "#ffaa00"}},
        )
        params = self.toolbox.set_lab_parameters(
            scene_id=scene["scene_id"],
            parameters={"gravity": 9.5, "air_resistance": False},
            metadata={"updated_by": "unit-test"},
        )
        exported = self.toolbox.export_lab_snapshot(
            scene_id=scene["scene_id"],
            adapter_id="scene.three_json",
            include_simulations=True,
        )
        report = self.toolbox.generate_lab_report(
            scene_id=scene["scene_id"],
            format="markdown",
            include_objects=True,
            include_simulations=True,
        )
        loaded = self.toolbox.get_lab_scene(scene_id=scene["scene_id"])
        removed = self.toolbox.remove_lab_object(scene_id=scene["scene_id"], object_id="ball-1")
        loaded_after_remove = self.toolbox.get_lab_scene(scene_id=scene["scene_id"])

        self.assertEqual(added["object_id"], "ball-1")
        self.assertEqual(updated["object"]["label"], "Projectile A")
        self.assertEqual(params["parameters"]["gravity"], 9.5)
        self.assertEqual(exported["status"], "completed")
        self.assertEqual(exported["snapshot"]["scene"]["name"], "Projectile baseline")
        self.assertIn("Projectile baseline", report["markdown"])
        self.assertEqual(loaded["objects"][0]["id"], "ball-1")
        self.assertEqual(removed["removed_object_id"], "ball-1")
        self.assertEqual(loaded_after_remove["objects"], [])

    def test_simulation_adapters_and_attach_flow(self) -> None:
        scene = self.toolbox.create_lab_scene(
            session_id=self.session_id,
            title="Simulation scene",
            parameters={"gravity": 9.81},
        )
        self.toolbox.add_lab_object(
            scene_id=scene["scene_id"],
            object={
                "id": "ball-1",
                "type": "rigid_body",
                "label": "Projectile",
                "position": {"x": 0, "y": 1, "z": 0},
                "rotation": {"x": 0, "y": 0, "z": 0},
                "scale": {"x": 1, "y": 1, "z": 1},
                "geometry": {"kind": "sphere"},
                "material": {"color": "#ff7a59"},
                "data": {"mass": 0.2, "velocity": {"x": 4, "y": 6, "z": 0}},
                "metadata": {},
            },
        )
        self.toolbox.add_lab_object(
            scene_id=scene["scene_id"],
            object={
                "id": "block-1",
                "type": "rigid_body",
                "label": "Block A",
                "position": {"x": 0, "y": 0, "z": 0},
                "rotation": {"x": 0, "y": 0, "z": 0},
                "scale": {"x": 1, "y": 1, "z": 1},
                "geometry": {"kind": "cube"},
                "material": {"color": "#3355ff"},
                "data": {"mass": 2.0, "velocity": {"x": 3, "y": 0, "z": 0}},
                "metadata": {},
            },
        )
        self.toolbox.add_lab_object(
            scene_id=scene["scene_id"],
            object={
                "id": "block-2",
                "type": "rigid_body",
                "label": "Block B",
                "position": {"x": 2, "y": 0, "z": 0},
                "rotation": {"x": 0, "y": 0, "z": 0},
                "scale": {"x": 1, "y": 1, "z": 1},
                "geometry": {"kind": "cube"},
                "material": {"color": "#22aa88"},
                "data": {"mass": 1.0, "velocity": {"x": -1, "y": 0, "z": 0}},
                "metadata": {},
            },
        )

        math_result = self.toolbox.run_lab_simulation(
            scene_id=scene["scene_id"],
            adapter_id="math.sympy",
            inputs={"operation": "solve_linear", "equation": "2*x + 4 = 10", "variable": "x"},
        )
        evaluate_result = self.toolbox.run_lab_simulation(
            scene_id=scene["scene_id"],
            adapter_id="math.sympy",
            inputs={"operation": "evaluate", "expression": "2^3 + 1"},
        )
        substitute_result = self.toolbox.run_lab_simulation(
            scene_id=scene["scene_id"],
            adapter_id="math.sympy",
            inputs={"operation": "substitute", "expression": "2*x + y", "variables": {"x": 3, "y": 4}},
        )
        simplify_result = self.toolbox.run_lab_simulation(
            scene_id=scene["scene_id"],
            adapter_id="math.sympy",
            inputs={"operation": "simplify", "expression": "x + 0"},
        )
        unsupported_result = self.toolbox.run_lab_simulation(
            scene_id=scene["scene_id"],
            adapter_id="math.sympy",
            inputs={"operation": "evaluate", "expression": "sqrt(9)"},
        )
        projectile = self.toolbox.run_lab_simulation(
            scene_id=scene["scene_id"],
            adapter_id="physics.simple_projectile",
            inputs={"object_id": "ball-1", "duration": 1.0, "time_step": 0.25},
        )
        projectile_attach = self.toolbox.attach_simulation_to_scene(
            scene_id=scene["scene_id"],
            simulation_id=projectile["simulation_id"],
            object_ids=["ball-1"],
            apply_object_updates=True,
        )
        collision = self.toolbox.run_lab_simulation(
            scene_id=scene["scene_id"],
            adapter_id="physics.simple_collision",
            inputs={"object_ids": ["block-1", "block-2"], "coefficient_of_restitution": 1.0},
        )
        collision_attach = self.toolbox.attach_simulation_to_scene(
            scene_id=scene["scene_id"],
            simulation_id=collision["simulation_id"],
            object_ids=["block-1", "block-2"],
            apply_object_updates=True,
        )
        loaded = self.toolbox.get_lab_scene(scene_id=scene["scene_id"])

        self.assertEqual(math_result["status"], "completed")
        self.assertEqual(math_result["result"]["outputs"]["solution"], 3.0)
        self.assertEqual(evaluate_result["status"], "completed")
        self.assertEqual(evaluate_result["result"]["outputs"]["result"], 9.0)
        self.assertEqual(substitute_result["status"], "completed")
        self.assertEqual(substitute_result["result"]["outputs"]["result"], 10.0)
        self.assertEqual(substitute_result["result"]["outputs"]["expression"], "10")
        self.assertEqual(simplify_result["status"], "completed")
        self.assertEqual(simplify_result["result"]["outputs"]["result"], "x")
        self.assertEqual(unsupported_result["status"], "unsupported_expression")
        self.assertEqual(projectile["status"], "completed")
        self.assertEqual(projectile_attach["attached_object_ids"], ["ball-1"])
        self.assertEqual(collision["status"], "completed")
        self.assertEqual(sorted(collision_attach["attached_object_ids"]), ["block-1", "block-2"])
        self.assertEqual(len(loaded["simulations"]), 7)
        self.assertEqual(len(loaded["attached_simulations"]), 2)
        projectile_object = next(item for item in loaded["objects"] if item["id"] == "ball-1")
        self.assertNotEqual(projectile_object["position"]["y"], 1.0)
        block_one = next(item for item in loaded["objects"] if item["id"] == "block-1")
        self.assertIn("velocity", block_one["data"])


if __name__ == "__main__":
    unittest.main()
