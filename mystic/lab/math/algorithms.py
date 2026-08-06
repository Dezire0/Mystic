"""Bounded standard-library numerical algorithms used by the Math engine pack."""
from __future__ import annotations

import math
import random
import statistics
from typing import Any, Callable

from .core import MathValidationError

EPS = 1e-14


def finite(value: Any, name: str = "value") -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise MathValidationError(f"{name} must be a finite number.")
    return float(value)


def vector(value: Any, name: str = "vector", maximum: int = 1_000) -> list[float]:
    if not isinstance(value, list) or not 1 <= len(value) <= maximum:
        raise MathValidationError(f"{name} must contain between 1 and {maximum} values.")
    return [finite(item, name) for item in value]


def matrix(value: Any, name: str = "matrix", maximum: int = 64) -> list[list[float]]:
    if not isinstance(value, list) or not value or len(value) > maximum or not all(isinstance(row, list) for row in value):
        raise MathValidationError(f"{name} must be a non-empty matrix up to {maximum} rows.")
    rows = [vector(row, name, maximum) for row in value]
    if len({len(row) for row in rows}) != 1:
        raise MathValidationError(f"{name} rows must have the same length.")
    return rows


def identity(n: int) -> list[list[float]]:
    return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


def transpose(a: list[list[float]]) -> list[list[float]]:
    return [list(col) for col in zip(*a)]


def dot(a: list[float], b: list[float]) -> float:
    if len(a) != len(b): raise MathValidationError("Vectors must have equal dimension.")
    return sum(x * y for x, y in zip(a, b))


def norm(a: list[float]) -> float:
    return math.sqrt(dot(a, a))


def matmul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    if len(a[0]) != len(b): raise MathValidationError("Matrix dimensions are incompatible for multiplication.")
    bt = transpose(b)
    return [[dot(row, col) for col in bt] for row in a]


def matvec(a: list[list[float]], b: list[float]) -> list[float]:
    return [dot(row, b) for row in a]


def lu(a: list[list[float]]) -> tuple[list[list[float]], list[list[float]], list[int]]:
    if len(a) != len(a[0]): raise MathValidationError("LU requires a square matrix.")
    n = len(a); u = [row[:] for row in a]; l = identity(n); permutation = list(range(n))
    for k in range(n):
        pivot = max(range(k, n), key=lambda row: abs(u[row][k]))
        if abs(u[pivot][k]) < EPS: raise MathValidationError("Matrix is singular to working tolerance.")
        if pivot != k:
            u[k], u[pivot] = u[pivot], u[k]; permutation[k], permutation[pivot] = permutation[pivot], permutation[k]
            for col in range(k): l[k][col], l[pivot][col] = l[pivot][col], l[k][col]
        for row in range(k + 1, n):
            factor = u[row][k] / u[k][k]; l[row][k] = factor
            for col in range(k, n): u[row][col] -= factor * u[k][col]
    return l, u, permutation


def solve(a: list[list[float]], b: list[float]) -> list[float]:
    l, u, p = lu(a); pb = [b[index] for index in p]; n = len(a); y = [0.0] * n
    for i in range(n): y[i] = pb[i] - sum(l[i][j] * y[j] for j in range(i))
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        if abs(u[i][i]) < EPS: raise MathValidationError("Matrix is singular to working tolerance.")
        x[i] = (y[i] - sum(u[i][j] * x[j] for j in range(i + 1, n))) / u[i][i]
    return x


def inverse(a: list[list[float]]) -> list[list[float]]:
    if len(a) != len(a[0]): raise MathValidationError("Inverse requires a square matrix.")
    return [solve(a, [1.0 if i == column else 0.0 for i in range(len(a))]) for column in range(len(a))]


def qr(a: list[list[float]]) -> tuple[list[list[float]], list[list[float]]]:
    m, n = len(a), len(a[0]); columns = transpose(a); q_columns: list[list[float]] = []; r = [[0.0] * n for _ in range(n)]
    for j, col in enumerate(columns):
        work = col[:]
        for i, qcol in enumerate(q_columns):
            r[i][j] = dot(qcol, work); work = [x - r[i][j] * y for x, y in zip(work, qcol)]
        r[j][j] = norm(work)
        if r[j][j] < EPS: raise MathValidationError("QR requires linearly independent columns.")
        q_columns.append([x / r[j][j] for x in work])
    return transpose(q_columns), r


def least_squares(a: list[list[float]], b: list[float]) -> list[float]:
    q, r = qr(a); qt_b = [dot(col, b) for col in transpose(q)]; return solve(r, qt_b)


def rref(a: list[list[float]]) -> tuple[list[list[float]], list[int]]:
    work = [row[:] for row in a]; rows, cols = len(work), len(work[0]); pivots: list[int] = []; pivot_row = 0
    for col in range(cols):
        candidate = max(range(pivot_row, rows), key=lambda row: abs(work[row][col]), default=pivot_row)
        if pivot_row >= rows or abs(work[candidate][col]) < EPS: continue
        work[pivot_row], work[candidate] = work[candidate], work[pivot_row]
        scale = work[pivot_row][col]; work[pivot_row] = [value / scale for value in work[pivot_row]]
        for row in range(rows):
            if row != pivot_row:
                factor = work[row][col]; work[row] = [value - factor * top for value, top in zip(work[row], work[pivot_row])]
        pivots.append(col); pivot_row += 1
        if pivot_row == rows: break
    return work, pivots


def null_space(a: list[list[float]]) -> list[list[float]]:
    reduced, pivots = rref(a); free = [col for col in range(len(a[0])) if col not in pivots]; basis: list[list[float]] = []
    for free_col in free:
        item = [0.0] * len(a[0]); item[free_col] = 1.0
        for row, pivot in enumerate(pivots): item[pivot] = -reduced[row][free_col]
        basis.append(item)
    return basis


def matrix_norm_inf(a: list[list[float]]) -> float: return max(sum(abs(value) for value in row) for row in a)


def power_eigen(a: list[list[float]], iterations: int = 200) -> tuple[float, list[float], float]:
    if len(a) != len(a[0]): raise MathValidationError("Eigenvalue computation requires a square matrix.")
    current = [1.0 / math.sqrt(len(a))] * len(a); residual = math.inf
    for _ in range(iterations):
        next_value = matvec(a, current); size = norm(next_value)
        if size < EPS: return 0.0, current, 0.0
        current = [value / size for value in next_value]
        eigen = dot(current, matvec(a, current)); residual = norm([x - eigen * y for x, y in zip(matvec(a, current), current)])
        if residual < 1e-10: break
    return dot(current, matvec(a, current)), current, residual


def function_from_spec(spec: dict[str, Any]) -> Callable[[float], float]:
    family = str(spec.get("family", ""))
    if family == "polynomial":
        coefficients = vector(spec.get("coefficients"), "coefficients", 128)
        return lambda x: sum(coefficient * x ** index for index, coefficient in enumerate(coefficients))
    if family == "quadratic":
        a = finite(spec.get("a", 1), "a"); b = finite(spec.get("b", 0), "b"); c = finite(spec.get("c", 0), "c")
        return lambda x: a * x * x + b * x + c
    if family == "sine":
        amplitude = finite(spec.get("amplitude", 1), "amplitude"); frequency = finite(spec.get("frequency", 1), "frequency"); offset = finite(spec.get("offset", 0), "offset")
        return lambda x: amplitude * math.sin(frequency * x) + offset
    raise MathValidationError("Function family is not allowlisted.")


def derivative_from_spec(spec: dict[str, Any]) -> Callable[[float], float]:
    family = str(spec.get("family", ""))
    if family == "polynomial":
        coefficients = vector(spec.get("coefficients"), "coefficients", 128)
        return lambda x: sum(index * coefficient * x ** (index - 1) for index, coefficient in enumerate(coefficients) if index)
    if family == "quadratic":
        a = finite(spec.get("a", 1), "a"); b = finite(spec.get("b", 0), "b"); return lambda x: 2 * a * x + b
    if family == "sine":
        amplitude = finite(spec.get("amplitude", 1), "amplitude"); frequency = finite(spec.get("frequency", 1), "frequency"); return lambda x: amplitude * frequency * math.cos(frequency * x)
    raise MathValidationError("Function family is not allowlisted.")


def root_find(method: str, func: Callable[[float], float], derivative: Callable[[float], float] | None, lower: float, upper: float, tolerance: float, maximum_iterations: int) -> tuple[float, int, float, bool]:
    a, b = lower, upper; fa, fb = func(a), func(b)
    if method == "bisection":
        if fa * fb > 0: raise MathValidationError("Bisection needs an interval with opposite endpoint signs.")
        for iteration in range(1, maximum_iterations + 1):
            midpoint = (a + b) / 2; fm = func(midpoint)
            if abs(fm) <= tolerance or abs(b - a) <= tolerance: return midpoint, iteration, abs(fm), True
            if fa * fm <= 0: b, fb = midpoint, fm
            else: a, fa = midpoint, fm
        return midpoint, maximum_iterations, abs(func(midpoint)), False
    if method == "secant":
        x0, x1 = a, b
        for iteration in range(1, maximum_iterations + 1):
            f0, f1 = func(x0), func(x1)
            if abs(f1 - f0) < EPS: return x1, iteration, abs(f1), False
            x2 = x1 - f1 * (x1 - x0) / (f1 - f0)
            if abs(x2 - x1) <= tolerance: return x2, iteration, abs(func(x2)), True
            x0, x1 = x1, x2
        return x1, maximum_iterations, abs(func(x1)), False
    if method == "newton_raphson":
        if derivative is None: raise MathValidationError("Newton-Raphson needs an allowlisted analytic derivative.")
        x = (a + b) / 2
        for iteration in range(1, maximum_iterations + 1):
            fx, dx = func(x), derivative(x)
            if abs(dx) < EPS: return x, iteration, abs(fx), False
            next_x = x - fx / dx
            if abs(next_x - x) <= tolerance: return next_x, iteration, abs(func(next_x)), True
            x = next_x
        return x, maximum_iterations, abs(func(x)), False
    if method == "brent":
        if fa * fb > 0: raise MathValidationError("Brent needs an interval with opposite endpoint signs.")
        c, fc, d, e = a, fa, b - a, b - a
        for iteration in range(1, maximum_iterations + 1):
            if fb * fc > 0: c, fc, d, e = a, fa, b - a, b - a
            if abs(fc) < abs(fb): a, b, c, fa, fb, fc = b, c, b, fb, fc, fb
            tol = 2 * EPS * abs(b) + tolerance / 2; midpoint = (c - b) / 2
            if abs(midpoint) <= tol or fb == 0: return b, iteration, abs(fb), True
            if abs(e) >= tol and abs(fa) > abs(fb):
                s = fb / fa
                if a == c: p, q = 2 * midpoint * s, 1 - s
                else:
                    q = fa / fc; r = fb / fc; p = s * (2 * midpoint * q * (q - r) - (b - a) * (r - 1)); q = (q - 1) * (r - 1) * (s - 1)
                if p > 0: q = -q
                p = abs(p)
                if 2 * p < min(3 * midpoint * q - abs(tol * q), abs(e * q)): e, d = d, p / q
                else: d, e = midpoint, midpoint
            else: d, e = midpoint, midpoint
            a, fa = b, fb; b += d if abs(d) > tol else (tol if midpoint > 0 else -tol); fb = func(b)
        return b, maximum_iterations, abs(fb), False
    raise MathValidationError("Root method is not allowlisted.")


def simpson(func: Callable[[float], float], a: float, b: float, steps: int) -> float:
    if steps < 2 or steps % 2: raise MathValidationError("Simpson integration requires an even step count of at least two.")
    h = (b - a) / steps
    return h / 3 * (func(a) + func(b) + 4 * sum(func(a + h * i) for i in range(1, steps, 2)) + 2 * sum(func(a + h * i) for i in range(2, steps - 1, 2)))


def adaptive_simpson(func: Callable[[float], float], a: float, b: float, tolerance: float, depth: int = 20) -> tuple[float, float]:
    def recurse(left: float, right: float, whole: float, local_tolerance: float, remaining: int) -> tuple[float, float]:
        middle = (left + right) / 2; left_value = simpson(func, left, middle, 2); right_value = simpson(func, middle, right, 2); correction = left_value + right_value - whole
        if remaining <= 0 or abs(correction) <= 15 * local_tolerance: return left_value + right_value + correction / 15, abs(correction) / 15
        lval, lerr = recurse(left, middle, left_value, local_tolerance / 2, remaining - 1); rval, rerr = recurse(middle, right, right_value, local_tolerance / 2, remaining - 1); return lval + rval, lerr + rerr
    whole = simpson(func, a, b, 2); return recurse(a, b, whole, tolerance, depth)


def gaussian5(func: Callable[[float], float], a: float, b: float) -> float:
    nodes = [-0.9061798459, -0.5384693101, 0.0, 0.5384693101, 0.9061798459]; weights = [0.2369268851, 0.4786286705, 0.5688888889, 0.4786286705, 0.2369268851]
    center, half = (a + b) / 2, (b - a) / 2
    return half * sum(weight * func(center + half * node) for node, weight in zip(nodes, weights))


def romberg(func: Callable[[float], float], a: float, b: float, levels: int = 6) -> tuple[float, float]:
    if not 1 <= levels <= 12: raise MathValidationError("Romberg levels must be between 1 and 12.")
    table = [[(b - a) * (func(a) + func(b)) / 2]]
    for i in range(1, levels):
        h = (b - a) / (2 ** i); first = table[i - 1][0] / 2 + h * sum(func(a + (2 * k - 1) * h) for k in range(1, 2 ** (i - 1) + 1)); row = [first]
        for j in range(1, i + 1): row.append(row[j - 1] + (row[j - 1] - table[i - 1][j - 1]) / (4 ** j - 1))
        table.append(row)
    error = abs(table[-1][-1] - table[-2][-2]) if levels > 1 else 0.0
    return table[-1][-1], error


def rhs_from_spec(spec: dict[str, Any]) -> Callable[[float, list[float]], list[float]]:
    family = str(spec.get("family", ""))
    if family == "exponential_decay":
        rate = finite(spec.get("rate"), "rate"); return lambda _t, y: [-rate * y[0]]
    if family == "logistic":
        rate = finite(spec.get("rate"), "rate"); carrying = finite(spec.get("carrying_capacity"), "carrying_capacity"); return lambda _t, y: [rate * y[0] * (1 - y[0] / carrying)]
    if family == "harmonic":
        omega = finite(spec.get("omega"), "omega"); return lambda _t, y: [y[1], -(omega ** 2) * y[0]]
    raise MathValidationError("ODE family is not allowlisted.")


def ode_step(method: str, rhs: Callable[[float, list[float]], list[float]], t: float, y: list[float], h: float) -> tuple[list[float], float]:
    def add(base: list[float], slope: list[float], scale: float) -> list[float]: return [x + scale * z for x, z in zip(base, slope)]
    k1 = rhs(t, y)
    if method == "euler": return add(y, k1, h), 0.0
    k2 = rhs(t + h, add(y, k1, h));
    if method == "improved_euler": return [item + h * (left + right) / 2 for item, left, right in zip(y, k1, k2)], 0.0
    k2 = rhs(t + h / 2, add(y, k1, h / 2)); k3 = rhs(t + h / 2, add(y, k2, h / 2)); k4 = rhs(t + h, add(y, k3, h)); result = [item + h * (a + 2 * b + 2 * c + d) / 6 for item, a, b, c, d in zip(y, k1, k2, k3, k4)]
    return result, 0.0


def integrate_ode(method: str, rhs: Callable[[float, list[float]], list[float]], initial: list[float], start: float, end: float, step: float, tolerance: float) -> tuple[list[dict[str, Any]], bool, float]:
    if method not in {"euler", "improved_euler", "rk4", "dormand_prince", "rk45"}: raise MathValidationError("ODE method is not allowlisted.")
    t, y, h = start, initial[:], step; points = [{"t": t, "values": y[:]}]; maximum = 20_000; error = 0.0
    for _ in range(maximum):
        if t >= end - EPS: return points, True, error
        h = min(h, end - t)
        if method in {"dormand_prince", "rk45"}:
            full, _ = ode_step("rk4", rhs, t, y, h); half, _ = ode_step("rk4", rhs, t, y, h / 2); half, _ = ode_step("rk4", rhs, t + h / 2, half, h / 2); error = norm([a - b for a, b in zip(full, half)])
            if error > tolerance and h > 1e-12: h /= 2; continue
            y = half; h = min(h * (1.5 if error < tolerance / 4 else 1.0), step)
        else: y, error = ode_step(method, rhs, t, y, h)
        t += h; points.append({"t": t, "values": y[:]})
    return points, False, error


def objective(spec: dict[str, Any], x: list[float]) -> tuple[float, list[float], list[list[float]]]:
    family = str(spec.get("family", ""))
    if family in {"quadratic", "least_squares_linear"}:
        a = matrix(spec.get("matrix"), "matrix", 32); center = vector(spec.get("center", [0.0] * len(a)), "center", 32)
        if len(a) != len(a[0]) or len(a) != len(x) or len(center) != len(x): raise MathValidationError("Quadratic dimensions must agree.")
        delta = [left - right for left, right in zip(x, center)]; gradient = matvec(a, delta); return 0.5 * dot(delta, gradient), gradient, a
    if family == "rosenbrock":
        if len(x) != 2: raise MathValidationError("Rosenbrock objective requires two variables.")
        a = finite(spec.get("a", 1), "a"); b = finite(spec.get("b", 100), "b"); value = (a - x[0]) ** 2 + b * (x[1] - x[0] ** 2) ** 2; gradient = [-2 * (a - x[0]) - 4 * b * x[0] * (x[1] - x[0] ** 2), 2 * b * (x[1] - x[0] ** 2)]; return value, gradient, [[2 + 12 * b * x[0] ** 2 - 4 * b * x[1], -4 * b * x[0]], [-4 * b * x[0], 2 * b]]
    raise MathValidationError("Objective family is not allowlisted.")


def optimize(method: str, spec: dict[str, Any], initial: list[float], tolerance: float, maximum: int, bounds: list[tuple[float | None, float | None]] | None = None) -> tuple[list[float], float, int, bool, list[dict[str, float]]]:
    if method not in {"gradient_descent", "newton", "bfgs", "l_bfgs", "conjugate_gradient", "trust_region", "line_search"}: raise MathValidationError("Optimization method is not allowlisted.")
    x = initial[:]; trace: list[dict[str, float]] = []; hessian_approx = identity(len(x))
    def clip(values: list[float]) -> list[float]:
        if not bounds: return values
        return [min(upper, max(lower, value)) if lower is not None and upper is not None else max(lower, value) if lower is not None else min(upper, value) if upper is not None else value for value, (lower, upper) in zip(values, bounds)]
    for iteration in range(1, maximum + 1):
        value, gradient, hessian = objective(spec, x); grad_norm = norm(gradient); trace.append({"iteration": float(iteration), "objective": value, "gradient_norm": grad_norm})
        if grad_norm <= tolerance: return x, value, iteration, True, trace
        if method in {"newton", "trust_region"}:
            try: direction = [-item for item in solve(hessian, gradient)]
            except MathValidationError: direction = [-item for item in gradient]
            scale = min(1.0, 1.0 / max(1.0, norm(direction))) if method == "trust_region" else 1.0
        elif method in {"bfgs", "l_bfgs"}: direction = [-item for item in matvec(hessian_approx, gradient)]; scale = 0.2
        else: direction = [-item for item in gradient]; scale = 0.1 if method != "conjugate_gradient" else 0.2
        candidate = clip([item + scale * direction_item for item, direction_item in zip(x, direction)])
        candidate_value, candidate_gradient, _ = objective(spec, candidate)
        while candidate_value > value and scale > 1e-10:
            scale /= 2; candidate = clip([item + scale * direction_item for item, direction_item in zip(x, direction)]); candidate_value, candidate_gradient, _ = objective(spec, candidate)
        if method in {"bfgs", "l_bfgs"}:
            s = [new - old for new, old in zip(candidate, x)]; y = [new - old for new, old in zip(candidate_gradient, gradient)]; sy = dot(s, y)
            if sy > EPS:
                rho = 1 / sy; hy = matvec(hessian_approx, y); yhy = dot(y, hy)
                hessian_approx = [[hessian_approx[i][j] + (1 + yhy * rho) * rho * s[i] * s[j] - rho * (s[i] * hy[j] + hy[i] * s[j]) for j in range(len(x))] for i in range(len(x))]
        if norm([new - old for new, old in zip(candidate, x)]) <= tolerance: return candidate, candidate_value, iteration, True, trace
        x = candidate
    value, _, _ = objective(spec, x); return x, value, maximum, False, trace


def regression(x: list[float], y: list[float], degree: int = 1) -> tuple[list[float], list[float], float]:
    if len(x) != len(y) or len(x) < degree + 1: raise MathValidationError("Regression needs matching observations and sufficient data.")
    design = [[value ** power for power in range(degree + 1)] for value in x]; coefficients = least_squares(design, y); predicted = matvec(design, coefficients); residuals = [actual - fitted for actual, fitted in zip(y, predicted)]; return coefficients, residuals, math.sqrt(sum(item * item for item in residuals) / len(residuals))


def normal_interval(values: list[float], confidence: float = 0.95) -> tuple[float, float, float]:
    if len(values) < 2: raise MathValidationError("Confidence intervals need at least two observations.")
    mean = statistics.fmean(values); stddev = statistics.stdev(values); z = 1.96 if confidence == 0.95 else 2.576 if confidence == 0.99 else 1.645
    delta = z * stddev / math.sqrt(len(values)); return mean, mean - delta, mean + delta


def normal_sample(random_source: random.Random, mean: float, standard_deviation: float, count: int) -> list[float]:
    if standard_deviation < 0 or not 1 <= count <= 100_000: raise MathValidationError("Sample count or standard deviation is out of bounds.")
    return [random_source.gauss(mean, standard_deviation) for _ in range(count)]


def normal_density(value: float, mean: float, standard_deviation: float) -> float:
    if standard_deviation <= 0: raise MathValidationError("Normal standard deviation must be positive.")
    normalized = (value - mean) / standard_deviation
    return math.exp(-0.5 * normalized * normalized) / (standard_deviation * math.sqrt(2 * math.pi))


def markov_chain(transition: list[list[float]], initial: list[float], steps: int) -> list[list[float]]:
    if len(transition) != len(transition[0]) or len(initial) != len(transition) or not 1 <= steps <= 10_000: raise MathValidationError("Markov dimensions or steps are invalid.")
    if any(abs(sum(row) - 1) > 1e-9 or any(item < 0 for item in row) for row in transition): raise MathValidationError("Markov transition rows must be probability distributions.")
    current = initial[:]; result = [current[:]]
    for _ in range(steps): current = [sum(current[row] * transition[row][column] for row in range(len(current))) for column in range(len(current))]; result.append(current[:])
    return result
