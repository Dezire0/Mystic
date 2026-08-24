"""Run the deterministic local/free ALETHEIA specialist benchmark."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.alethia_benchmark import BenchmarkHarness, available_local_candidates, load_fixture
from mystic.alethia_benchmark.core import write_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=ROOT / "benchmarks/alethia/v0/fixtures.json")
    parser.add_argument("--output", type=Path, default=ROOT / "mystic_data/reports/alethia_specialist_benchmark_v0")
    args = parser.parse_args()
    fixture = load_fixture(args.fixture)
    report = BenchmarkHarness(fixture, args.fixture.parent).run(available_local_candidates())
    json_path, markdown_path = write_report(report, args.output)
    print(json_path)
    print(markdown_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
