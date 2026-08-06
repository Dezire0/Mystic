from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


class MathValidationError(ValueError):
    """A public-safe rejection of a non-declarative or out-of-bounds request."""


def _safe_json(value: Any, *, depth: int = 0) -> Any:
    if depth > 12:
        raise MathValidationError("Declarative math data is nested too deeply.")
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, list):
        if len(value) > 10_000:
            raise MathValidationError("Declarative math arrays are bounded to 10,000 values.")
        return [_safe_json(item, depth=depth + 1) for item in value]
    if isinstance(value, dict):
        if len(value) > 256 or not all(isinstance(key, str) for key in value):
            raise MathValidationError("Declarative math objects must have bounded string keys.")
        return {key: _safe_json(item, depth=depth + 1) for key, item in value.items()}
    raise MathValidationError("Declarative math data must be JSON-compatible.")


@dataclass(frozen=True)
class Tolerance:
    absolute: float = 1e-8
    relative: float = 1e-6
    maximum_iterations: int = 1_000

    def validate(self) -> "Tolerance":
        if self.absolute <= 0 or self.relative <= 0 or not 1 <= self.maximum_iterations <= 100_000:
            raise MathValidationError("Tolerances must be positive and iteration limits bounded.")
        return self


@dataclass(frozen=True)
class Units:
    values: dict[str, str] = field(default_factory=dict)

    def validate(self) -> "Units":
        if not all(isinstance(key, str) and isinstance(value, str) and len(value) <= 128 for key, value in self.values.items()):
            raise MathValidationError("Units must be bounded string mappings.")
        return self


@dataclass(frozen=True)
class Constraint:
    variable: str
    lower: float | None = None
    upper: float | None = None
    kind: Literal["bound", "equality", "inequality"] = "bound"

    def validate(self) -> "Constraint":
        if not self.variable or (self.lower is not None and self.upper is not None and self.lower > self.upper):
            raise MathValidationError("Constraints require a variable and ordered bounds.")
        return self


@dataclass(frozen=True)
class Variable:
    name: str
    initial_value: float | None = None
    units: str = "dimensionless"
    bounds: Constraint | None = None


@dataclass(frozen=True)
class Parameter:
    name: str
    value: float | None = None
    units: str = "dimensionless"
    bounds: Constraint | None = None


@dataclass(frozen=True)
class ObjectiveFunction:
    family: str
    parameters: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> "ObjectiveFunction":
        if self.family not in {"quadratic", "rosenbrock", "least_squares_linear", "polynomial"}:
            raise MathValidationError("Objective family is not allowlisted.")
        _safe_json(self.parameters)
        return self


@dataclass(frozen=True)
class MathematicalProblem:
    problem_id: str
    operation: str
    inputs: dict[str, Any]
    tolerance: Tolerance = field(default_factory=Tolerance)
    units: Units = field(default_factory=Units)
    constraints: tuple[Constraint, ...] = ()
    model_spec: "ScientificModelSpec | None" = None

    def validate(self) -> "MathematicalProblem":
        if not self.problem_id or not self.operation:
            raise MathValidationError("Mathematical problems require stable IDs and operations.")
        _safe_json(self.inputs)
        self.tolerance.validate(); self.units.validate()
        for constraint in self.constraints:
            constraint.validate()
        if self.model_spec:
            self.model_spec.validate()
        return self


@dataclass(frozen=True)
class ScientificModelSpec:
    """Versioned, renderer-independent, declarative scientific model contract."""

    schema_version: str
    model_id: str
    title: str
    domain: str
    model_family: str
    state_variables: list[dict[str, Any]] = field(default_factory=list)
    parameters: list[dict[str, Any]] = field(default_factory=list)
    governing_equations: list[dict[str, Any]] = field(default_factory=list)
    initial_conditions: dict[str, Any] = field(default_factory=dict)
    boundary_conditions: dict[str, Any] = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    units: dict[str, str] = field(default_factory=dict)
    observables: list[dict[str, Any]] = field(default_factory=list)
    solver_requirements: dict[str, Any] = field(default_factory=dict)
    calibration_targets: list[dict[str, Any]] = field(default_factory=list)
    validity_limits: list[str] = field(default_factory=list)
    uncertainty_model: dict[str, Any] = field(default_factory=dict)
    safety_classification: str = "bounded_scientific_model"
    provenance: dict[str, Any] = field(default_factory=dict)
    linked_claim_ids: list[str] = field(default_factory=list)
    linked_experiment_ids: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ScientificModelSpec":
        required = {"schema_version", "model_id", "title", "domain", "model_family"}
        missing = sorted(required - set(value))
        if missing:
            raise MathValidationError(f"ScientificModelSpec missing required fields: {', '.join(missing)}.")
        known = {field.name for field in cls.__dataclass_fields__.values()}
        extra = sorted(set(value) - known)
        if extra:
            raise MathValidationError(f"ScientificModelSpec has unsupported fields: {', '.join(extra)}.")
        spec = cls(**value)
        return spec.validate()

    def validate(self) -> "ScientificModelSpec":
        for field_name in ("schema_version", "model_id", "title", "domain", "model_family", "safety_classification"):
            if not isinstance(getattr(self, field_name), str) or not getattr(self, field_name).strip():
                raise MathValidationError(f"ScientificModelSpec {field_name} must be a non-empty string.")
        for equation in self.governing_equations:
            if not isinstance(equation, dict) or set(equation) - {"kind", "lhs", "rhs", "variables", "parameters", "metadata"}:
                raise MathValidationError("Governing equations must be bounded symbolic data, not executable expressions.")
            if equation.get("kind") not in {"polynomial", "linear", "ode", "algebraic", "conservation"}:
                raise MathValidationError("Governing equation kind is not allowlisted.")
        _safe_json(asdict(self))
        if any(not isinstance(item, str) or len(item) > 512 for item in self.assumptions + self.validity_limits):
            raise MathValidationError("Assumptions and validity limits must be bounded text.")
        return self

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConvergenceInfo:
    converged: bool
    iterations: int
    residual_norm: float | None = None
    reason: str = "completed"


@dataclass(frozen=True)
class ErrorEstimate:
    absolute: float | None = None
    relative: float | None = None
    method: str = "not_available"


@dataclass(frozen=True)
class SensitivityResult:
    parameter: str
    derivative: float
    method: str = "central_finite_difference"


@dataclass(frozen=True)
class UncertaintyResult:
    method: str
    standard_deviation: float | None = None
    interval: tuple[float, float] | None = None
    sample_count: int | None = None


@dataclass(frozen=True)
class VisualizationDescriptor:
    descriptor_type: Literal["function_curve", "convergence_curve", "matrix_heatmap", "histogram", "scatter_plot", "phase_diagram", "vector_field", "confidence_interval", "error_curve"]
    title: str
    data: dict[str, Any]
    units: dict[str, str] = field(default_factory=dict)

    def public_dict(self) -> dict[str, Any]:
        return {"version": "1", "layers": [{"id": self.descriptor_type, "type": self.descriptor_type, "label": self.title, "visible": True, "data": _safe_json(self.data), "style": {}, "units": self.units, "metadata_safe": {}}]}


@dataclass(frozen=True)
class SolverCapabilities:
    deterministic: bool = True
    supports_visualization: bool = True
    supports_uncertainty: bool = False
    supports_sensitivity: bool = False
    complexity: str = "bounded"
    expected_runtime_class: str = "tiny"
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class SolverMetadata:
    solver_id: str
    solver_version: str
    assumptions: tuple[str, ...]
    tolerance: Tolerance
    capabilities: SolverCapabilities
    deterministic: bool = True


@dataclass(frozen=True)
class SolverResult:
    values: dict[str, Any]
    metadata: SolverMetadata
    convergence: ConvergenceInfo
    error_estimate: ErrorEstimate = field(default_factory=ErrorEstimate)
    warnings: tuple[str, ...] = ()
    visualization: VisualizationDescriptor | None = None
    sensitivity: tuple[SensitivityResult, ...] = ()
    uncertainty: UncertaintyResult | None = None

    def public_dict(self) -> dict[str, Any]:
        return {
            "values": _safe_json(self.values), "solver_metadata": asdict(self.metadata),
            "convergence": asdict(self.convergence), "error_estimate": asdict(self.error_estimate),
            "sensitivity": [asdict(item) for item in self.sensitivity],
            "uncertainty": asdict(self.uncertainty) if self.uncertainty else None,
        }
