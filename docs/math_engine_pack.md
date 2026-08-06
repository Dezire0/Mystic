# Mathematics and Numerical Computing Engine Pack

Phase 2B.2 provides the first reusable mathematical runtime for Mystic LAB. It is additive to the seven Phase 2A engines and runs only through a trusted runner.

## Engine inventory

| Engine | Included operations |
| --- | --- |
| `math.linear_algebra` | matrix multiplication, LU, QR, bounded SVD/eigen diagnostic, least squares, pseudo-inverse, condition number, rank, null space |
| `math.root_finding` | Newton-Raphson, bisection, secant, Brent |
| `math.numerical_integration` | Simpson, adaptive Simpson, fixed Gaussian quadrature, Romberg |
| `math.ode_solver` | Euler, improved Euler, RK4, Dormand-Prince-style adaptive RK45, stiff heuristic |
| `math.optimization` | gradient descent, Newton, BFGS/L-BFGS, conjugate-gradient direction, trust region, line search, bounds |
| `math.statistics` | moments, covariance/correlation, linear/polynomial regression, normal MLE, confidence interval, z-style hypothesis test |
| `math.probability` | seeded normal sampling, Monte Carlo, normal target/proposal importance sampling, beta-Bernoulli update, Markov chains |
| `math.geometry` | vectors, planes, 2D rotations, coordinate transforms, distance metrics |
| `math.uncertainty` | finite-difference sensitivity, independent/covariance propagation, seeded Monte Carlo, floating-point and condition diagnostics |
| `math.calculus` | analytic derivatives for allowlisted families and central finite differences |
| `math.benchmark` | bounded matrix, ODE, optimization, regression, and Monte Carlo workloads |

`math.sympy` remains the existing bounded symbolic adapter. This pack does not expand its grammar or allow SymPy/Python execution from untrusted input.

## MCP and Control Center

The public MCP surface adds `lab_math_list`, `lab_math_get`, `lab_math_run`, `lab_math_compare`, `lab_math_visualize`, `lab_math_benchmark`, `lab_math_fit`, `lab_math_optimize`, `lab_math_uncertainty`, and `lab_math_sensitivity`.

Cloud tools delegate only to the existing engine-job interface. They never execute Python inside Cloudflare. If no compatible runner is online, the response is the existing structured runner-offline state.

The Control Center routes `/math` and `/math/benchmarks` use authenticated BFF calls only. They expose safe manifests, declarative problem entry, queued jobs, completed-run history, descriptor guidance, convergence, tolerance, sensitivity, and uncertainty information. They do not display credentials or execute local code in the browser.

## Reproducibility and limits

All engines publish a deterministic manifest. Every submitted math problem carries a validated `ScientificModelSpec`; the runner generates a minimal versioned spec when a caller does not supply one. Seeded probability and Monte Carlo work use the explicit seed, or the runner job seed, or `0` as a deterministic default. Algorithms are intentionally bounded: matrices are limited to 64 dimensions in this release, probability samples to 100,000, and solver iterations to 100,000. Benchmark dimensions are capped at 64 in order to keep a runner task bounded. Measured elapsed time is runner metadata (`duration_ms`), not canonical solver output, so it does not change a deterministic result hash.

The standard-library implementations are suitable for deterministic, inspectable scientific workflows and acceptance tests. They are not replacements for high-performance BLAS/LAPACK, arbitrary symbolic algebra, implicit stiff solvers, general Bayesian inference, or production-scale optimization. Those require independently accepted future engine packs.

## Verification

Run the local deterministic checks:

```bash
uv run python -m unittest tests.test_math_engine_pack -v
uv run python scripts/check_engine_runtime.py
node --input-type=module -e "import './cloudflare/mystic_public_gateway_worker.js'; console.log('worker-ok');"
```

Production registration requires a trusted runner to synchronize the allowlisted manifests. This issue does not deploy or enable any production runner automatically.
