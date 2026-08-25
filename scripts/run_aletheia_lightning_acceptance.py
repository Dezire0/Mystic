"""Opt-in real acceptance for ALETHEIA's existing Lightning T4 Studio."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.specialist_dispatcher import LightningDispatcher, LightningSDKClient, LightningSettings, SpecialistJob


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--expected-page", type=int)
    args = parser.parse_args()
    settings = LightningSettings.from_env()
    dispatcher = LightningDispatcher(root_path=ROOT, settings=settings, client_factory=LightningSDKClient)
    result = dispatcher.execute(SpecialistJob(args.job_id, args.query, (args.pdf,)))
    if args.expected_page is not None and (not result.evidence_candidates or result.evidence_candidates[0].page != args.expected_page):
        raise RuntimeError("The expected evidence page was not ranked first.")
    print(f"job_id={result.job_id} status={result.status} candidates={len(result.evidence_candidates)} reused={result.reused}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
