from __future__ import annotations

import math
import random
import statistics
from typing import Any

from mystic.lab.engines.base import EngineExecutionContext, EngineResult, ResourceEstimate, ScientificEnginePlugin
from mystic.lab.engines.errors import EngineError
from mystic.lab.engines.manifest import EngineManifest
from mystic.lab.engines.visualization import validate_visualization

from . import algorithms as alg
from .core import (ConvergenceInfo, ErrorEstimate, MathValidationError, ScientificModelSpec, SolverCapabilities, SolverMetadata, SolverResult, Tolerance, UncertaintyResult, VisualizationDescriptor)

VERSION = "2.0.0"
MAX_BENCHMARK_DIMENSION = 64


def _payload(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict): raise EngineError("engine_input_invalid", "Math engine input must be an object.")
    return value


def _tolerance(payload: dict[str, Any]) -> Tolerance:
    value = payload.get("tolerance", {})
    if value is None: value = {}
    if not isinstance(value, dict): raise MathValidationError("tolerance must be an object.")
    return Tolerance(float(value.get("absolute", 1e-8)), float(value.get("relative", 1e-6)), int(value.get("maximum_iterations", 1_000))).validate()


def _visualization(kind: str, title: str, data: dict[str, Any], units: dict[str, str] | None = None) -> dict[str, Any]:
    return VisualizationDescriptor(kind, title, data, units or {}).public_dict()


class MathEnginePlugin(ScientificEnginePlugin):
    def __init__(self, engine_id: str, display_name: str, capabilities: tuple[str, ...], *, uncertainty: bool = False, sensitivity: bool = False, resource: str = "tiny", limitations: tuple[str, ...] = ()) -> None:
        self._manifest = EngineManifest(engine_id, display_name, VERSION, "math", "Bounded deterministic numerical solver executed only by a trusted Mystic runner.", capabilities, {"type": "object"}, {"type": "object"}, True, True, True, True, True, expected_resource_class=resource, timeout_seconds_default=15, timeout_seconds_max=60, metadata_safe={"solver_sdk": "mystic.lab.math", "units": "declared_or_dimensionless", "assumptions": ["Declarative allowlisted problem families only."], "limitations": list(limitations), "complexity": "operation dependent; bounded input dimensions", "expected_runtime_class": resource, "deterministic": True, "supports_visualization": True, "supports_uncertainty": uncertainty, "supports_sensitivity": sensitivity})

    def manifest(self) -> EngineManifest: return self._manifest
    def estimate(self, payload: dict[str, Any]) -> ResourceEstimate: return ResourceEstimate(self._manifest.expected_resource_class, 5.0)
    def validate_input(self, payload: dict[str, Any]) -> dict[str, Any]:
        value = _payload(payload); operation = value.get("operation")
        if not isinstance(operation, str) or not operation: raise EngineError("engine_input_invalid", "Math engine input requires an allowlisted operation.")
        try:
            _tolerance(value)
            if "model_spec" in value and value["model_spec"] is not None:
                if not isinstance(value["model_spec"], dict): raise MathValidationError("model_spec must be an object.")
                ScientificModelSpec.from_dict(value["model_spec"])
            else:
                value = {**value, "model_spec": ScientificModelSpec(schema_version="1", model_id=f"{self._manifest.engine_id}:{operation}", title=self._manifest.display_name, domain="math", model_family=operation, assumptions=["Generated bounded Math Engine Pack model specification."], solver_requirements={"engine_id": self._manifest.engine_id}).public_dict()}
        except (ValueError, TypeError, MathValidationError) as exc: raise EngineError("engine_input_invalid", str(exc)) from exc
        return value
    def execute(self, payload: dict[str, Any], context: EngineExecutionContext) -> EngineResult:
        try: result = self._run(payload, context)
        except MathValidationError as exc: raise EngineError("math_input_unsupported", str(exc)) from exc
        except (OverflowError, ZeroDivisionError, ValueError) as exc: raise EngineError("math_execution_failed", "The bounded numerical computation could not complete.") from exc
        public = result.public_dict(); visualization = result.visualization.public_dict() if result.visualization else None
        return EngineResult(summary={"operation": payload["operation"], "converged": result.convergence.converged, "iterations": result.convergence.iterations, "solver_id": result.metadata.solver_id}, values=public, warnings=list(result.warnings), assumptions=list(result.metadata.assumptions), units={"declared": "model or problem units"}, visualization=validate_visualization(visualization), evidence=[{"model_spec": payload.get("model_spec", {}), "deterministic": True, "solver_version": VERSION}])
    def _result(self, operation: str, payload: dict[str, Any], values: dict[str, Any], *, iterations: int = 1, converged: bool = True, residual: float | None = None, error: float | None = None, visualization: VisualizationDescriptor | None = None, warnings: tuple[str, ...] = (), uncertainty: UncertaintyResult | None = None) -> SolverResult:
        tolerance = _tolerance(payload); caps = SolverCapabilities(supports_uncertainty=self._manifest.metadata_safe["supports_uncertainty"], supports_sensitivity=self._manifest.metadata_safe["supports_sensitivity"], complexity=self._manifest.metadata_safe["complexity"], expected_runtime_class=self._manifest.expected_resource_class, limitations=tuple(self._manifest.metadata_safe["limitations"]))
        return SolverResult(values, SolverMetadata(self._manifest.engine_id, VERSION, ("Allowlisted declarative mathematical input.",), tolerance, caps), ConvergenceInfo(converged, iterations, residual, "converged" if converged else "iteration_limit"), ErrorEstimate(error, None, "solver_estimate" if error is not None else "not_available"), warnings, visualization, (), uncertainty)
    def _run(self, payload: dict[str, Any], context: EngineExecutionContext) -> SolverResult: raise NotImplementedError


class LinearAlgebraPlugin(MathEnginePlugin):
    def __init__(self) -> None: super().__init__("math.linear_algebra", "Linear algebra", ("matrix_multiply", "lu", "qr", "svd", "eigenvalues", "eigenvectors", "least_squares", "pseudo_inverse", "condition_number", "rank", "null_space"), uncertainty=True, sensitivity=True, resource="small", limitations=("SVD/eigenvalue routines are bounded educational numerical implementations.",))
    def _run(self, p: dict[str, Any], context: EngineExecutionContext) -> SolverResult:
        op = p["operation"]; a = alg.matrix(p.get("matrix_a", p.get("matrix")), "matrix", 64); context.check_cancelled()
        if op == "matrix_multiply": values = {"matrix": alg.matmul(a, alg.matrix(p.get("matrix_b"), "matrix_b", 64))}
        elif op == "lu":
            lower, upper, permutation = alg.lu(a); values = {"lower": lower, "upper": upper, "permutation": permutation}
        elif op == "qr":
            q, r = alg.qr(a); values = {"q": q, "r": r}
        elif op == "least_squares": values = {"solution": alg.least_squares(a, alg.vector(p.get("vector_b"), "vector_b", 64))}
        elif op == "pseudo_inverse":
            at = alg.transpose(a); values = {"pseudo_inverse": alg.matmul(alg.inverse(alg.matmul(at, a)), at)}
        elif op in {"rank", "null_space"}:
            reduced, pivots = alg.rref(a); values = {"rank": len(pivots), "rref": reduced, "null_space": alg.null_space(a) if op == "null_space" else []}
        elif op == "condition_number": values = {"condition_number_inf": alg.matrix_norm_inf(a) * alg.matrix_norm_inf(alg.inverse(a))}
        elif op in {"eigenvalues", "eigenvectors"}:
            eigenvalue, eigenvector, residual = alg.power_eigen(a); values = {"dominant_eigenvalue": eigenvalue, "dominant_eigenvector": eigenvector}; return self._result(op, p, values, iterations=200, residual=residual, visualization=VisualizationDescriptor("matrix_heatmap", "Matrix", {"matrix": a}))
        elif op == "svd":
            ata = alg.matmul(alg.transpose(a), a); eigenvalue, eigenvector, residual = alg.power_eigen(ata); singular = math.sqrt(max(0.0, eigenvalue)); values = {"singular_values": [singular], "right_singular_vectors": [eigenvector], "residual": residual}
        else: raise MathValidationError("Linear algebra operation is not allowlisted.")
        return self._result(op, p, values, visualization=VisualizationDescriptor("matrix_heatmap", "Matrix result", {"matrix": a}))


class RootFindingPlugin(MathEnginePlugin):
    def __init__(self) -> None: super().__init__("math.root_finding", "Root finding", ("newton_raphson", "bisection", "secant", "brent"), limitations=("Functions are fixed declarative families; free-form expressions are rejected.",))
    def _run(self, p: dict[str, Any], context: EngineExecutionContext) -> SolverResult:
        function = p.get("function");
        if not isinstance(function, dict): raise MathValidationError("function must be a declarative object.")
        root, iterations, residual, converged = alg.root_find(p["operation"], alg.function_from_spec(function), alg.derivative_from_spec(function) if p["operation"] == "newton_raphson" else None, alg.finite(p.get("lower"), "lower"), alg.finite(p.get("upper"), "upper"), _tolerance(p).absolute, _tolerance(p).maximum_iterations)
        return self._result(p["operation"], p, {"root": root, "residual": residual}, iterations=iterations, converged=converged, residual=residual, visualization=VisualizationDescriptor("function_curve", "Root function", {"function": function, "root": root}))


class IntegrationPlugin(MathEnginePlugin):
    def __init__(self) -> None: super().__init__("math.numerical_integration", "Numerical integration", ("simpson", "adaptive_simpson", "gaussian_quadrature", "romberg"))
    def _run(self, p: dict[str, Any], context: EngineExecutionContext) -> SolverResult:
        fn = p.get("function");
        if not isinstance(fn, dict): raise MathValidationError("function must be a declarative object.")
        func, a, b, op = alg.function_from_spec(fn), alg.finite(p.get("lower"), "lower"), alg.finite(p.get("upper"), "upper"), p["operation"]
        if op == "simpson": value, error = alg.simpson(func, a, b, int(p.get("steps", 100))), None
        elif op == "adaptive_simpson": value, error = alg.adaptive_simpson(func, a, b, _tolerance(p).absolute)
        elif op == "gaussian_quadrature": value, error = alg.gaussian5(func, a, b), None
        elif op == "romberg": value, error = alg.romberg(func, a, b, int(p.get("levels", 6)))
        else: raise MathValidationError("Integration operation is not allowlisted.")
        return self._result(op, p, {"integral": value}, error=error, visualization=VisualizationDescriptor("function_curve", "Integrated function", {"function": fn, "interval": [a, b]}))


class ODEPlugin(MathEnginePlugin):
    def __init__(self) -> None: super().__init__("math.ode_solver", "Ordinary differential equations", ("euler", "improved_euler", "rk4", "dormand_prince", "adaptive_rk45", "stiff_detection"), resource="small", limitations=("Stiff detection is diagnostic only; no implicit stiff solver is included.",))
    def _run(self, p: dict[str, Any], context: EngineExecutionContext) -> SolverResult:
        rhs = p.get("rhs");
        if not isinstance(rhs, dict): raise MathValidationError("rhs must be a declarative allowlisted ODE family.")
        op = "rk45" if p["operation"] == "adaptive_rk45" else p["operation"]
        if op == "stiff_detection":
            rate = abs(alg.finite(rhs.get("rate", rhs.get("omega", 0)), "rate")); return self._result(p["operation"], p, {"stiff_suspected": rate * alg.finite(p.get("step", 0.01), "step") > 2, "diagnostic": "explicit stability heuristic"})
        points, converged, error = alg.integrate_ode(op, alg.rhs_from_spec(rhs), alg.vector(p.get("initial_state"), "initial_state", 8), alg.finite(p.get("start", 0), "start"), alg.finite(p.get("end"), "end"), alg.finite(p.get("step", 0.01), "step"), _tolerance(p).absolute)
        return self._result(p["operation"], p, {"final_state": points[-1], "points": points}, iterations=len(points) - 1, converged=converged, error=error, visualization=VisualizationDescriptor("function_curve", "ODE solution", {"points": points}))


class OptimizationPlugin(MathEnginePlugin):
    def __init__(self) -> None: super().__init__("math.optimization", "Optimization", ("gradient_descent", "newton", "bfgs", "l_bfgs", "conjugate_gradient", "trust_region", "line_search", "bound_constrained"), sensitivity=True, resource="small")
    def _run(self, p: dict[str, Any], context: EngineExecutionContext) -> SolverResult:
        spec = p.get("objective");
        if not isinstance(spec, dict): raise MathValidationError("objective must be an allowlisted declarative object.")
        bounds = p.get("bounds"); parsed_bounds = None
        if bounds is not None:
            if not isinstance(bounds, list): raise MathValidationError("bounds must be a list.")
            parsed_bounds = [(item.get("lower"), item.get("upper")) if isinstance(item, dict) else (_ for _ in ()).throw(MathValidationError("Each bound must be an object.")) for item in bounds]
        method = "gradient_descent" if p["operation"] == "bound_constrained" else p["operation"]
        point, value, iterations, converged, trace = alg.optimize(method, spec, alg.vector(p.get("initial"), "initial", 32), _tolerance(p).absolute, _tolerance(p).maximum_iterations, parsed_bounds)
        return self._result(p["operation"], p, {"point": point, "objective": value}, iterations=iterations, converged=converged, residual=abs(value), visualization=VisualizationDescriptor("convergence_curve", "Optimization convergence", {"points": trace}))


class StatisticsPlugin(MathEnginePlugin):
    def __init__(self) -> None: super().__init__("math.statistics", "Statistics and regression", ("mean", "variance", "covariance", "correlation", "linear_regression", "polynomial_regression", "mle_normal", "confidence_interval", "hypothesis_test"), uncertainty=True)
    def _run(self, p: dict[str, Any], context: EngineExecutionContext) -> SolverResult:
        op = p["operation"]; values = alg.vector(p.get("values"), "values", 100_000)
        if op == "mean": result = {"mean": statistics.fmean(values)}
        elif op == "variance": result = {"variance": statistics.variance(values)}
        elif op in {"covariance", "correlation"}:
            other = alg.vector(p.get("other_values"), "other_values", 100_000)
            if len(other) != len(values): raise MathValidationError("Series lengths must match.")
            covariance = statistics.covariance(values, other); result = {"covariance": covariance, "correlation": statistics.correlation(values, other) if op == "correlation" else None}
        elif op in {"linear_regression", "polynomial_regression"}:
            x = alg.vector(p.get("x"), "x", 10_000); coefficients, residuals, rmse = alg.regression(x, values, 1 if op == "linear_regression" else int(p.get("degree", 2))); result = {"coefficients": coefficients, "residuals": residuals, "rmse": rmse}; return self._result(op, p, result, residual=rmse, visualization=VisualizationDescriptor("scatter_plot", "Regression fit", {"x": x, "y": values, "coefficients": coefficients}))
        elif op == "mle_normal": result = {"mean": statistics.fmean(values), "standard_deviation": statistics.pstdev(values)}
        elif op == "confidence_interval":
            mean, lower, upper = alg.normal_interval(values, float(p.get("confidence", 0.95))); result = {"mean": mean, "interval": [lower, upper]}; return self._result(op, p, result, uncertainty=UncertaintyResult("normal_approximation", statistics.stdev(values), (lower, upper), len(values)), visualization=VisualizationDescriptor("confidence_interval", "Mean confidence interval", result))
        elif op == "hypothesis_test":
            null_mean = alg.finite(p.get("null_mean", 0), "null_mean"); standard_error = statistics.stdev(values) / math.sqrt(len(values)); statistic = (statistics.fmean(values) - null_mean) / standard_error if standard_error else 0.0; result = {"z_statistic": statistic, "reject_at_0_05": abs(statistic) > 1.96}
        else: raise MathValidationError("Statistics operation is not allowlisted.")
        return self._result(op, p, result)


class ProbabilityPlugin(MathEnginePlugin):
    def __init__(self) -> None: super().__init__("math.probability", "Probability and Monte Carlo", ("distribution_sample", "monte_carlo", "importance_sampling", "bayesian_update", "markov_chain"), uncertainty=True, resource="small")
    def _run(self, p: dict[str, Any], context: EngineExecutionContext) -> SolverResult:
        op = p["operation"]; rng = random.Random(int(p.get("seed", context.seed if context.seed is not None else 0)))
        if op in {"distribution_sample", "monte_carlo"}:
            distribution = p.get("distribution", {});
            if not isinstance(distribution, dict) or distribution.get("family", "normal") != "normal": raise MathValidationError("Only the declarative normal distribution is available in this pack.")
            samples = alg.normal_sample(rng, alg.finite(distribution.get("mean", 0), "mean"), alg.finite(distribution.get("standard_deviation", 1), "standard_deviation"), int(p.get("sample_count", 1_000)))
            result = {"samples": samples if op == "distribution_sample" else [], "mean": statistics.fmean(samples), "variance": statistics.pvariance(samples), "sample_count": len(samples)}
            return self._result(op, p, result, uncertainty=UncertaintyResult("seeded_monte_carlo", statistics.pstdev(samples), None, len(samples)), visualization=VisualizationDescriptor("histogram", "Seeded distribution sample", {"values": samples[:2_000]}))
        if op == "importance_sampling":
            target, proposal = p.get("target_distribution"), p.get("proposal_distribution")
            if not isinstance(target, dict) or not isinstance(proposal, dict) or target.get("family", "normal") != "normal" or proposal.get("family", "normal") != "normal":
                raise MathValidationError("Importance sampling requires declarative normal target and proposal distributions.")
            target_mean, target_std = alg.finite(target.get("mean", 0), "target mean"), alg.finite(target.get("standard_deviation", 1), "target standard_deviation")
            proposal_mean, proposal_std = alg.finite(proposal.get("mean", 0), "proposal mean"), alg.finite(proposal.get("standard_deviation", 1), "proposal standard_deviation")
            samples = alg.normal_sample(rng, proposal_mean, proposal_std, int(p.get("sample_count", 1_000)))
            weights = [alg.normal_density(value, target_mean, target_std) / alg.normal_density(value, proposal_mean, proposal_std) for value in samples]
            quantity = str(p.get("quantity", "mean"))
            if quantity == "mean": estimates = samples
            elif quantity == "threshold_probability":
                threshold = alg.finite(p.get("threshold"), "threshold"); estimates = [1.0 if value >= threshold else 0.0 for value in samples]
            else: raise MathValidationError("Importance sampling quantity is not allowlisted.")
            weight_sum = sum(weights)
            if weight_sum <= 0: raise MathValidationError("Importance sampling produced no usable weights.")
            estimate = sum(weight * value for weight, value in zip(weights, estimates)) / weight_sum
            effective_sample_size = weight_sum * weight_sum / sum(weight * weight for weight in weights)
            return self._result(op, p, {"estimate": estimate, "effective_sample_size": effective_sample_size, "sample_count": len(samples), "quantity": quantity}, uncertainty=UncertaintyResult("seeded_importance_sampling", None, None, len(samples)), visualization=VisualizationDescriptor("histogram", "Importance sampling proposal", {"values": samples[:2_000], "weights": weights[:2_000]}))
        if op == "bayesian_update":
            alpha, beta, successes, failures = (alg.finite(p.get(key), key) for key in ("alpha", "beta", "successes", "failures")); result = {"posterior_alpha": alpha + successes, "posterior_beta": beta + failures, "posterior_mean": (alpha + successes) / (alpha + beta + successes + failures)}
        elif op == "markov_chain": result = {"states": alg.markov_chain(alg.matrix(p.get("transition"), "transition", 32), alg.vector(p.get("initial"), "initial", 32), int(p.get("steps", 10)))}
        else: raise MathValidationError("Probability operation is not allowlisted.")
        return self._result(op, p, result)


class GeometryPlugin(MathEnginePlugin):
    def __init__(self) -> None: super().__init__("math.geometry", "Geometry", ("vector", "plane", "rotation", "coordinate_transform", "distance"))
    def _run(self, p: dict[str, Any], context: EngineExecutionContext) -> SolverResult:
        a = alg.vector(p.get("a"), "a", 8); b = alg.vector(p.get("b", [0] * len(a)), "b", 8); op = p["operation"]
        if len(a) != len(b): raise MathValidationError("Geometry vectors must have equal dimension.")
        if op == "vector": result = {"dot": alg.dot(a, b), "norm_a": alg.norm(a), "norm_b": alg.norm(b), "cross": [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]] if len(a) == 3 else None}
        elif op == "distance": result = {"euclidean": alg.norm([x - y for x, y in zip(a, b)]), "manhattan": sum(abs(x - y) for x, y in zip(a, b))}
        elif op == "plane":
            normal = alg.vector(p.get("normal"), "normal", 3); point = alg.vector(p.get("point"), "point", 3); result = {"plane": {"normal": normal, "offset": -alg.dot(normal, point)}}
        elif op == "rotation":
            if len(a) != 2: raise MathValidationError("Rotation currently supports two-dimensional vectors.")
            angle = alg.finite(p.get("angle_radians"), "angle_radians"); result = {"rotated": [math.cos(angle) * a[0] - math.sin(angle) * a[1], math.sin(angle) * a[0] + math.cos(angle) * a[1]]}
        elif op == "coordinate_transform": result = {"transformed": alg.matvec(alg.matrix(p.get("transform"), "transform", 8), a)}
        else: raise MathValidationError("Geometry operation is not allowlisted.")
        return self._result(op, p, result, visualization=VisualizationDescriptor("vector_field", "Geometry result", {"a": a, "b": b, "result": result}))


class UncertaintyPlugin(MathEnginePlugin):
    def __init__(self) -> None: super().__init__("math.uncertainty", "Uncertainty and sensitivity", ("finite_difference", "error_propagation", "covariance_propagation", "monte_carlo_uncertainty", "sensitivity_analysis", "floating_point_diagnostics", "condition_estimation"), uncertainty=True, sensitivity=True)
    def _run(self, p: dict[str, Any], context: EngineExecutionContext) -> SolverResult:
        op = p["operation"]
        if op in {"finite_difference", "sensitivity_analysis"}:
            spec = p.get("function");
            if not isinstance(spec, dict): raise MathValidationError("function must be declarative.")
            x, h = alg.finite(p.get("x"), "x"), alg.finite(p.get("step", 1e-5), "step"); function = alg.function_from_spec(spec); derivative = (function(x + h) - function(x - h)) / (2 * h); result = {"derivative": derivative, "point": x, "step": h}
        elif op == "error_propagation":
            derivatives, stddevs = alg.vector(p.get("derivatives"), "derivatives", 128), alg.vector(p.get("standard_deviations"), "standard_deviations", 128)
            if len(derivatives) != len(stddevs): raise MathValidationError("Derivative and uncertainty dimensions must agree.")
            sigma = math.sqrt(sum((d * s) ** 2 for d, s in zip(derivatives, stddevs))); result = {"standard_deviation": sigma}; return self._result(op, p, result, uncertainty=UncertaintyResult("independent_error_propagation", sigma))
        elif op == "covariance_propagation":
            jacobian, covariance = alg.matrix(p.get("jacobian"), "jacobian", 32), alg.matrix(p.get("covariance"), "covariance", 32); result = {"covariance": alg.matmul(alg.matmul(jacobian, covariance), alg.transpose(jacobian))}
        elif op == "monte_carlo_uncertainty":
            rng = random.Random(int(p.get("seed", context.seed or 0))); samples = alg.normal_sample(rng, alg.finite(p.get("mean", 0), "mean"), alg.finite(p.get("standard_deviation", 1), "standard_deviation"), int(p.get("sample_count", 1_000))); sigma = statistics.pstdev(samples); result = {"mean": statistics.fmean(samples), "standard_deviation": sigma}; return self._result(op, p, result, uncertainty=UncertaintyResult("seeded_monte_carlo", sigma, None, len(samples)), visualization=VisualizationDescriptor("histogram", "Uncertainty sample", {"values": samples[:2_000]}))
        elif op == "floating_point_diagnostics":
            value = alg.finite(p.get("value"), "value"); result = {"ulp": math.ulp(value), "is_finite": math.isfinite(value), "relative_spacing": math.ulp(value) / max(abs(value), 1.0)}
        elif op == "condition_estimation":
            a = alg.matrix(p.get("matrix"), "matrix", 64); result = {"condition_number_inf": alg.matrix_norm_inf(a) * alg.matrix_norm_inf(alg.inverse(a))}
        else: raise MathValidationError("Uncertainty operation is not allowlisted.")
        return self._result(op, p, result)


class CalculusPlugin(MathEnginePlugin):
    def __init__(self) -> None: super().__init__("math.calculus", "Calculus and bounded symbolic differentiation", ("automatic_differentiation", "finite_differences", "symbolic_differentiation"), sensitivity=True, limitations=("Symbolic differentiation is limited to allowlisted polynomial, quadratic, and sine families.",))
    def _run(self, p: dict[str, Any], context: EngineExecutionContext) -> SolverResult:
        spec = p.get("function");
        if not isinstance(spec, dict): raise MathValidationError("function must be declarative.")
        x = alg.finite(p.get("x", 0), "x"); op = p["operation"]
        if op in {"automatic_differentiation", "symbolic_differentiation"}: result = {"derivative": alg.derivative_from_spec(spec)(x), "point": x, "representation": "allowlisted_analytic_derivative"}
        elif op == "finite_differences":
            h = alg.finite(p.get("step", 1e-5), "step"); f = alg.function_from_spec(spec); result = {"derivative": (f(x + h) - f(x - h)) / (2 * h), "point": x, "step": h}
        else: raise MathValidationError("Calculus operation is not allowlisted.")
        return self._result(op, p, result)


class BenchmarkPlugin(MathEnginePlugin):
    def __init__(self) -> None: super().__init__("math.benchmark", "Math benchmark", ("matrix", "ode", "optimization", "regression", "monte_carlo"), resource="small", limitations=("Benchmarks are bounded synthetic workloads, not hardware certification.",))
    def _run(self, p: dict[str, Any], context: EngineExecutionContext) -> SolverResult:
        workload = p["operation"]; dimension = min(MAX_BENCHMARK_DIMENSION, max(2, int(p.get("dimension", 32))))
        if workload == "matrix":
            a = [[float((i + j) % 13) for j in range(dimension)] for i in range(dimension)]; result = alg.matmul(a, a); summary = {"dimension": dimension, "checksum": sum(sum(row) for row in result)}
        elif workload == "ode": summary = {"points": len(alg.integrate_ode("rk4", alg.rhs_from_spec({"family": "exponential_decay", "rate": 1}), [1], 0, 1, 0.001, 1e-8)[0])}
        elif workload == "optimization": summary = {"objective": alg.optimize("bfgs", {"family": "quadratic", "matrix": [[2, 0], [0, 2]], "center": [1, -1]}, [5, 5], 1e-8, 200)[1]}
        elif workload == "regression": summary = {"rmse": alg.regression([float(i) for i in range(100)], [2 * i + 1 for i in range(100)])[2]}
        elif workload == "monte_carlo": summary = {"mean": statistics.fmean(alg.normal_sample(random.Random(0), 0, 1, min(50_000, dimension * dimension)))}
        else: raise MathValidationError("Benchmark workload is not allowlisted.")
        summary["memory_note"] = "bounded in-process standard-library workload"; summary["runtime_metadata"] = "Runner duration_ms records measured elapsed time outside the canonical deterministic output."; return self._result(workload, p, summary, visualization=VisualizationDescriptor("convergence_curve", "Benchmark", {"workload": workload, "dimension": dimension}))


def math_engine_plugins() -> list[ScientificEnginePlugin]:
    return [LinearAlgebraPlugin(), RootFindingPlugin(), IntegrationPlugin(), ODEPlugin(), OptimizationPlugin(), StatisticsPlugin(), ProbabilityPlugin(), GeometryPlugin(), UncertaintyPlugin(), CalculusPlugin(), BenchmarkPlugin()]
