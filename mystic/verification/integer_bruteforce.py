from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import product

from mystic.verification.constraint_checker import check_order_constraints, check_positive_integer_constraints
from mystic.verification.substitution_checker import verify_equations


@dataclass(slots=True)
class IntegerSearchResult:
    variable_order: list[str]
    solutions: list[tuple[int, ...]]
    searched_bounds: dict[str, tuple[int, int]]
    warnings: list[str]

    @property
    def count(self) -> int:
        return len(self.solutions)


def search_integer_solutions(
    *,
    problem: str,
    variable_order: list[str],
    bounds: dict[str, tuple[int, int]],
) -> IntegerSearchResult:
    warnings: list[str] = []
    missing_bounds = [variable for variable in variable_order if variable not in bounds]
    if missing_bounds:
        warnings.append(f"Missing bounds for variables: {', '.join(missing_bounds)}")
        return IntegerSearchResult(
            variable_order=variable_order,
            solutions=[],
            searched_bounds=bounds,
            warnings=warnings,
        )

    ranges = [range(bounds[variable][0], bounds[variable][1] + 1) for variable in variable_order]
    solutions: list[tuple[int, ...]] = []
    for values in product(*ranges):
        assignment = {
            variable: Fraction(value)
            for variable, value in zip(variable_order, values)
        }
        failures = [
            *check_positive_integer_constraints(problem, assignment),
            *check_order_constraints(problem, assignment),
            *verify_equations(problem, assignment),
        ]
        if not failures:
            solutions.append(tuple(int(value) for value in values))
    return IntegerSearchResult(
        variable_order=variable_order,
        solutions=solutions,
        searched_bounds=bounds,
        warnings=warnings,
    )


def enumerate_egyptian_fraction_solutions() -> list[tuple[int, int, int]]:
    result = search_integer_solutions(
        problem="1/x + 1/y + 1/z = 1, x <= y <= z, positive integers",
        variable_order=["x", "y", "z"],
        bounds={"x": (1, 3), "y": (1, 15), "z": (1, 31)},
    )
    return [tuple(solution) for solution in result.solutions]
