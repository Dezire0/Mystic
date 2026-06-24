from __future__ import annotations

from mystic.core.orchestrator import MysticOrchestrator
from mystic.evals.sample_cases import SAMPLE_CASES


def main() -> None:
    orchestrator = MysticOrchestrator()
    for problem in SAMPLE_CASES:
        result = orchestrator.run_problem(problem)
        print(result.session_id)


if __name__ == "__main__":
    main()

