from __future__ import annotations

import math
import unittest

from mystic.lab.engines import EngineExecutionContext, builtin_registry
from mystic.lab.engines.errors import EngineError
from mystic.lab.math.core import MathValidationError, ScientificModelSpec


class ScientificModelSpecTests(unittest.TestCase):
    def test_accepts_declarative_polynomial_model(self) -> None:
        spec = ScientificModelSpec.from_dict({"schema_version":"1", "model_id":"model-linear", "title":"Line", "domain":"math", "model_family":"linear", "governing_equations":[{"kind":"linear", "lhs":"y", "rhs":{"parameters":["m", "b"], "variables":["x"]}}]})
        self.assertEqual(spec.model_id, "model-linear")

    def test_rejects_missing_required_fields(self) -> None:
        with self.assertRaises(MathValidationError): ScientificModelSpec.from_dict({"schema_version":"1"})

    def test_rejects_executable_equation_shape(self) -> None:
        with self.assertRaises(MathValidationError):
            ScientificModelSpec.from_dict({"schema_version":"1", "model_id":"unsafe", "title":"Unsafe", "domain":"math", "model_family":"test", "governing_equations":[{"kind":"python", "code":"import os"}]})


class MathEnginePackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = builtin_registry()
        self.context = EngineExecutionContext(run_id="math-pack-test", seed=7)

    def execute(self, engine_id: str, payload: dict) -> dict:
        plugin = self.registry.get(engine_id)
        return plugin.execute(plugin.validate_input(payload), self.context).values

    def test_all_math_engines_publish_safe_metadata(self) -> None:
        manifests = self.registry.list(domain="math")
        self.assertGreaterEqual(len(manifests), 12)
        for manifest in manifests:
            if manifest.engine_id == "math.sympy": continue
            metadata = manifest.metadata_safe
            self.assertTrue(metadata["deterministic"])
            self.assertTrue(metadata["supports_visualization"])
            self.assertIn("limitations", metadata)
            self.assertEqual(manifest.execution_backend, "trusted_python_runner")

    def test_math_jobs_receive_a_versioned_model_spec_when_not_supplied(self) -> None:
        plugin = self.registry.get("math.statistics")
        payload = plugin.validate_input({"operation":"mean", "values":[1,2,3]})
        self.assertEqual(payload["model_spec"]["schema_version"], "1")
        self.assertEqual(payload["model_spec"]["model_id"], "math.statistics:mean")

    def test_matrix_multiplication(self) -> None:
        result = self.execute("math.linear_algebra", {"operation":"matrix_multiply", "matrix_a":[[1,2],[3,4]], "matrix_b":[[2,0],[1,2]]})
        self.assertEqual(result["values"]["matrix"], [[4.0,4.0],[10.0,8.0]])

    def test_lu_factorization(self) -> None:
        result = self.execute("math.linear_algebra", {"operation":"lu", "matrix":[[4,3],[6,3]]})
        self.assertEqual(result["values"]["permutation"], [1,0])

    def test_qr_factorization(self) -> None:
        result = self.execute("math.linear_algebra", {"operation":"qr", "matrix":[[1,0],[0,1]]})
        self.assertAlmostEqual(result["values"]["q"][0][0], 1.0)

    def test_least_squares(self) -> None:
        result = self.execute("math.linear_algebra", {"operation":"least_squares", "matrix":[[1,0],[1,1],[1,2]], "vector_b":[1,3,5]})
        self.assertAlmostEqual(result["values"]["solution"][0], 1.0, places=8)
        self.assertAlmostEqual(result["values"]["solution"][1], 2.0, places=8)

    def test_pseudo_inverse(self) -> None:
        result = self.execute("math.linear_algebra", {"operation":"pseudo_inverse", "matrix":[[1,0],[0,2],[0,0]]})
        self.assertEqual(len(result["values"]["pseudo_inverse"]), 2)

    def test_rank_and_null_space(self) -> None:
        result = self.execute("math.linear_algebra", {"operation":"null_space", "matrix":[[1,2],[2,4]]})
        self.assertEqual(result["values"]["rank"], 1)
        self.assertEqual(len(result["values"]["null_space"]), 1)

    def test_condition_number(self) -> None:
        result = self.execute("math.linear_algebra", {"operation":"condition_number", "matrix":[[2,0],[0,1]]})
        self.assertAlmostEqual(result["values"]["condition_number_inf"], 2.0)

    def test_eigenvalue(self) -> None:
        result = self.execute("math.linear_algebra", {"operation":"eigenvalues", "matrix":[[3,0],[0,1]]})
        self.assertAlmostEqual(result["values"]["dominant_eigenvalue"], 3.0, places=6)

    def test_svd(self) -> None:
        result = self.execute("math.linear_algebra", {"operation":"svd", "matrix":[[3,0],[0,1]]})
        self.assertAlmostEqual(result["values"]["singular_values"][0], 3.0, places=6)

    def test_bisection(self) -> None:
        result = self.execute("math.root_finding", {"operation":"bisection", "function":{"family":"quadratic", "a":1, "b":0, "c":-4}, "lower":0, "upper":3})
        self.assertAlmostEqual(result["values"]["root"], 2.0, places=6)

    def test_secant(self) -> None:
        result = self.execute("math.root_finding", {"operation":"secant", "function":{"family":"quadratic", "a":1, "b":0, "c":-4}, "lower":1, "upper":3})
        self.assertAlmostEqual(result["values"]["root"], 2.0, places=6)

    def test_newton_raphson(self) -> None:
        result = self.execute("math.root_finding", {"operation":"newton_raphson", "function":{"family":"quadratic", "a":1, "b":0, "c":-4}, "lower":1, "upper":3})
        self.assertAlmostEqual(result["values"]["root"], 2.0, places=6)

    def test_brent(self) -> None:
        result = self.execute("math.root_finding", {"operation":"brent", "function":{"family":"quadratic", "a":1, "b":0, "c":-4}, "lower":0, "upper":3})
        self.assertAlmostEqual(result["values"]["root"], 2.0, places=6)

    def test_simpson(self) -> None:
        result = self.execute("math.numerical_integration", {"operation":"simpson", "function":{"family":"polynomial", "coefficients":[0,1]}, "lower":0, "upper":1, "steps":100})
        self.assertAlmostEqual(result["values"]["integral"], 0.5, places=8)

    def test_adaptive_simpson(self) -> None:
        result = self.execute("math.numerical_integration", {"operation":"adaptive_simpson", "function":{"family":"sine"}, "lower":0, "upper":math.pi})
        self.assertAlmostEqual(result["values"]["integral"], 2.0, places=6)

    def test_gaussian_quadrature(self) -> None:
        result = self.execute("math.numerical_integration", {"operation":"gaussian_quadrature", "function":{"family":"polynomial", "coefficients":[0,0,1]}, "lower":0, "upper":1})
        self.assertAlmostEqual(result["values"]["integral"], 1 / 3, places=6)

    def test_romberg(self) -> None:
        result = self.execute("math.numerical_integration", {"operation":"romberg", "function":{"family":"polynomial", "coefficients":[1]}, "lower":0, "upper":4})
        self.assertAlmostEqual(result["values"]["integral"], 4.0, places=8)

    def test_rk4_ode(self) -> None:
        result = self.execute("math.ode_solver", {"operation":"rk4", "rhs":{"family":"exponential_decay", "rate":1}, "initial_state":[1], "start":0, "end":1, "step":0.01})
        self.assertAlmostEqual(result["values"]["final_state"]["values"][0], math.exp(-1), places=4)

    def test_adaptive_ode(self) -> None:
        result = self.execute("math.ode_solver", {"operation":"adaptive_rk45", "rhs":{"family":"logistic", "rate":1, "carrying_capacity":10}, "initial_state":[1], "start":0, "end":1, "step":0.1})
        self.assertTrue(result["convergence"]["converged"])

    def test_stiff_diagnostic(self) -> None:
        result = self.execute("math.ode_solver", {"operation":"stiff_detection", "rhs":{"family":"exponential_decay", "rate":1000}, "step":0.01})
        self.assertTrue(result["values"]["stiff_suspected"])

    def test_gradient_descent(self) -> None:
        result = self.execute("math.optimization", {"operation":"gradient_descent", "objective":{"family":"quadratic", "matrix":[[2]], "center":[3]}, "initial":[0]})
        self.assertAlmostEqual(result["values"]["point"][0], 3.0, places=4)

    def test_newton_optimization(self) -> None:
        result = self.execute("math.optimization", {"operation":"newton", "objective":{"family":"quadratic", "matrix":[[2]], "center":[3]}, "initial":[0]})
        self.assertAlmostEqual(result["values"]["point"][0], 3.0, places=8)

    def test_bfgs(self) -> None:
        result = self.execute("math.optimization", {"operation":"bfgs", "objective":{"family":"quadratic", "matrix":[[2]], "center":[2]}, "initial":[7]})
        self.assertTrue(result["convergence"]["converged"])

    def test_bound_constrained(self) -> None:
        result = self.execute("math.optimization", {"operation":"bound_constrained", "objective":{"family":"quadratic", "matrix":[[2]], "center":[5]}, "initial":[0], "bounds":[{"lower":0,"upper":2}]})
        self.assertLessEqual(result["values"]["point"][0], 2.0)

    def test_statistics_moments(self) -> None:
        result = self.execute("math.statistics", {"operation":"mean", "values":[1,2,3]})
        self.assertEqual(result["values"]["mean"], 2.0)
        result = self.execute("math.statistics", {"operation":"variance", "values":[1,2,3]})
        self.assertEqual(result["values"]["variance"], 1.0)

    def test_statistics_regression(self) -> None:
        result = self.execute("math.statistics", {"operation":"linear_regression", "x":[0,1,2], "values":[1,3,5]})
        self.assertAlmostEqual(result["values"]["coefficients"][1], 2.0, places=8)

    def test_statistics_confidence_interval(self) -> None:
        result = self.execute("math.statistics", {"operation":"confidence_interval", "values":[1,2,3,4,5]})
        self.assertLess(result["values"]["interval"][0], 3)
        self.assertGreater(result["values"]["interval"][1], 3)

    def test_statistics_hypothesis_test(self) -> None:
        result = self.execute("math.statistics", {"operation":"hypothesis_test", "values":[10,11,9,10,10], "null_mean":0})
        self.assertTrue(result["values"]["reject_at_0_05"])

    def test_probability_seeded_monte_carlo(self) -> None:
        payload = {"operation":"monte_carlo", "distribution":{"family":"normal", "mean":2, "standard_deviation":1}, "sample_count":1000, "seed":99}
        first = self.execute("math.probability", payload); second = self.execute("math.probability", payload)
        self.assertEqual(first["values"], second["values"])

    def test_bayesian_update(self) -> None:
        result = self.execute("math.probability", {"operation":"bayesian_update", "alpha":1, "beta":1, "successes":3, "failures":1})
        self.assertAlmostEqual(result["values"]["posterior_mean"], 4 / 6)

    def test_importance_sampling_uses_target_and_proposal_weights(self) -> None:
        result = self.execute("math.probability", {"operation":"importance_sampling", "target_distribution":{"family":"normal", "mean":2, "standard_deviation":1}, "proposal_distribution":{"family":"normal", "mean":0, "standard_deviation":2}, "quantity":"mean", "sample_count":10000, "seed":9})
        self.assertAlmostEqual(result["values"]["estimate"], 2.0, delta=0.08)
        self.assertGreater(result["values"]["effective_sample_size"], 1)

    def test_markov_chain(self) -> None:
        result = self.execute("math.probability", {"operation":"markov_chain", "transition":[[0.5,0.5],[0.2,0.8]], "initial":[1,0], "steps":2})
        self.assertEqual(len(result["values"]["states"]), 3)

    def test_geometry_operations(self) -> None:
        result = self.execute("math.geometry", {"operation":"vector", "a":[1,0,0], "b":[0,1,0]})
        self.assertEqual(result["values"]["cross"], [0.0,0.0,1.0])
        result = self.execute("math.geometry", {"operation":"distance", "a":[0,0], "b":[3,4]})
        self.assertEqual(result["values"]["euclidean"], 5.0)

    def test_geometry_rotation(self) -> None:
        result = self.execute("math.geometry", {"operation":"rotation", "a":[1,0], "angle_radians":math.pi / 2})
        self.assertAlmostEqual(result["values"]["rotated"][1], 1.0, places=8)

    def test_uncertainty_error_propagation(self) -> None:
        result = self.execute("math.uncertainty", {"operation":"error_propagation", "derivatives":[2,3], "standard_deviations":[0.1,0.2]})
        self.assertAlmostEqual(result["values"]["standard_deviation"], math.sqrt(0.4), places=8)

    def test_uncertainty_finite_difference(self) -> None:
        result = self.execute("math.uncertainty", {"operation":"finite_difference", "function":{"family":"quadratic", "a":1, "b":0}, "x":3})
        self.assertAlmostEqual(result["values"]["derivative"], 6.0, places=4)

    def test_uncertainty_seeded_monte_carlo(self) -> None:
        payload = {"operation":"monte_carlo_uncertainty", "mean":0, "standard_deviation":1, "sample_count":100, "seed":1}
        self.assertEqual(self.execute("math.uncertainty", payload)["values"], self.execute("math.uncertainty", payload)["values"])

    def test_calculus_analytic_and_finite_difference(self) -> None:
        result = self.execute("math.calculus", {"operation":"automatic_differentiation", "function":{"family":"polynomial", "coefficients":[0,0,1]}, "x":2})
        self.assertEqual(result["values"]["derivative"], 4.0)
        result = self.execute("math.calculus", {"operation":"finite_differences", "function":{"family":"polynomial", "coefficients":[0,0,1]}, "x":2})
        self.assertAlmostEqual(result["values"]["derivative"], 4.0, places=4)

    def test_bounded_benchmarks(self) -> None:
        for workload in ("matrix", "ode", "optimization", "regression", "monte_carlo"):
            result = self.execute("math.benchmark", {"operation":workload, "dimension":8})
            self.assertIn("runtime_metadata", result["values"])

    def test_rejects_free_form_expression(self) -> None:
        with self.assertRaises(EngineError) as raised:
            self.execute("math.root_finding", {"operation":"bisection", "function":{"family":"python", "expression":"__import__('os')"}, "lower":0, "upper":1})
        self.assertEqual(raised.exception.code, "math_input_unsupported")

    def test_rejects_unknown_operation(self) -> None:
        with self.assertRaises(EngineError) as raised: self.execute("math.statistics", {"operation":"execute_python", "values":[1,2]})
        self.assertEqual(raised.exception.code, "math_input_unsupported")

    def test_visualization_is_renderer_independent(self) -> None:
        result = self.execute("math.numerical_integration", {"operation":"simpson", "function":{"family":"polynomial", "coefficients":[1]}, "lower":0, "upper":1, "steps":2})
        layer = self.registry.get("math.numerical_integration").execute({"operation":"simpson", "function":{"family":"polynomial", "coefficients":[1]}, "lower":0, "upper":1, "steps":2}, self.context).visualization["layers"][0]
        self.assertEqual(layer["type"], "function_curve")
        self.assertNotIn("three", str(layer).lower())
        self.assertEqual(result["values"]["integral"], 1.0)


def _make_algorithm_smoke(engine_id: str, payload: dict) -> None:
    def test(self: MathEnginePackTests) -> None:
        output = self.execute(engine_id, payload)
        self.assertIn("values", output)
        self.assertTrue(output["solver_metadata"]["deterministic"])
    test.__name__ = f"test_smoke_{engine_id.replace('.', '_')}_{payload['operation']}"
    setattr(MathEnginePackTests, test.__name__, test)


for _engine, _payload in [
    ("math.linear_algebra", {"operation":"rank", "matrix":[[1,0],[0,1]]}),
    ("math.root_finding", {"operation":"bisection", "function":{"family":"polynomial", "coefficients":[-1,1]}, "lower":0, "upper":2}),
    ("math.numerical_integration", {"operation":"gaussian_quadrature", "function":{"family":"polynomial", "coefficients":[1]}, "lower":0, "upper":1}),
    ("math.ode_solver", {"operation":"euler", "rhs":{"family":"exponential_decay", "rate":1}, "initial_state":[1], "start":0, "end":0.1, "step":0.01}),
    ("math.optimization", {"operation":"conjugate_gradient", "objective":{"family":"quadratic", "matrix":[[2]], "center":[1]}, "initial":[0]}),
    ("math.statistics", {"operation":"mle_normal", "values":[1,2,3]}),
    ("math.probability", {"operation":"distribution_sample", "distribution":{"family":"normal"}, "sample_count":2}),
    ("math.geometry", {"operation":"plane", "a":[1,0,0], "normal":[1,0,0], "point":[2,0,0]}),
    ("math.uncertainty", {"operation":"floating_point_diagnostics", "value":1.0}),
    ("math.calculus", {"operation":"symbolic_differentiation", "function":{"family":"sine"}, "x":0}),
]: _make_algorithm_smoke(_engine, _payload)


if __name__ == "__main__": unittest.main()
