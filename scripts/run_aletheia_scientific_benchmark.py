"""Run ALETHEIA's deterministic local/free scientific benchmark pack."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.alethia_benchmark import available_local_candidates, load_fixture
from mystic.alethia_benchmark.scientific import ScientificBenchmarkPack, write_scientific_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=ROOT / "benchmarks/alethia/scientific-v1/fixtures.json")
    parser.add_argument("--output", type=Path, default=ROOT / "mystic_data/reports/alethia_scientific_benchmark_v1")
    args = parser.parse_args()
    fixture = load_fixture(args.fixture)
    report = ScientificBenchmarkPack(fixture, args.fixture.parent).run(available_local_candidates())
    for path in write_scientific_report(report, args.output):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
