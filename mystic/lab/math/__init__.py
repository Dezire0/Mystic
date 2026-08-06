"""Bounded, deterministic numerical primitives for trusted Mystic runners.

This package intentionally accepts declarative data only.  It never parses or
executes user supplied source code, imports, shell commands, or network URLs.
"""

from .core import (
    Constraint,
    ConvergenceInfo,
    ErrorEstimate,
    MathematicalProblem,
    ObjectiveFunction,
    Parameter,
    ScientificModelSpec,
    SensitivityResult,
    SolverCapabilities,
    SolverMetadata,
    SolverResult,
    Tolerance,
    Units,
    UncertaintyResult,
    Variable,
    VisualizationDescriptor,
)
from .engines import math_engine_plugins

__all__ = [
    "Constraint", "ConvergenceInfo", "ErrorEstimate", "MathematicalProblem",
    "ObjectiveFunction", "Parameter", "ScientificModelSpec", "SensitivityResult",
    "SolverCapabilities", "SolverMetadata", "SolverResult", "Tolerance", "Units",
    "UncertaintyResult", "Variable", "VisualizationDescriptor", "math_engine_plugins",
]
