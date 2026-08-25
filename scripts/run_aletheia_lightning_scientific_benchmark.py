"""Opt-in real T4 path: controlled benchmark -> dispatcher -> evidence artifact."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.alethia_lightning_benchmark import run_lightning_t4_benchmark
from mystic.alethia_scientific_suite import build_approval_review
from mystic.specialist_dispatcher import LightningDispatcher, LightningSDKClient, LightningSettings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-id-prefix", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--expected-page", required=True, type=int)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "mystic_data" / "alethia_scientific_benchmark")
    args = parser.parse_args()
    dispatcher = LightningDispatcher(root_path=ROOT, settings=LightningSettings.from_env(), client_factory=LightningSDKClient)
    evidence = run_lightning_t4_benchmark(
        dispatcher=dispatcher, job_id_prefix=args.job_id_prefix, query=args.query,
        pdf_path=args.pdf, expected_page=args.expected_page, output_dir=args.output_dir,
    )
    review = build_approval_review(evidence)
    print(f"benchmark_id={evidence.spec.benchmark_id} reliability={evidence.reliability:.3f} top_1={evidence.aggregate_metrics['top_1']:.3f}")
    print(f"evidence={evidence.raw_result_artifact_ref} recommendation={review.recommended_decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
