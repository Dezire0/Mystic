#!/usr/bin/env python3
"""Run bounded Phase 2D.2 specialist baselines or configured Wave 1 evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))
from mystic.lab.specialist_evaluation import Wave1SpecialistEvaluator


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(REPOSITORY_ROOT), help="Mystic repository/data root")
    parser.add_argument("--corpus", default="benchmarks/phase2d/v1/corpus.json", help="Versioned Phase 2D corpus JSON path")
    parser.add_argument("--live", action="store_true", help="Run only the fixed Wave 1 provider calls when server configuration permits")
    arguments = parser.parse_args()
    evaluator = Wave1SpecialistEvaluator(root_path=arguments.root, corpus_path=arguments.corpus)
    report = evaluator.run_live() if arguments.live else evaluator.run_baselines()
    print(json.dumps(report.safe_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.status in {"baseline_recorded", "completed"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
