"""Domain-pack reporting layered on the bounded specialist benchmark harness."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .adapters import SpecialistAdapter
from .core import BenchmarkHarness


SHORTLIST_QUALITY = 0.80
SHORTLIST_RELIABILITY = 0.95


class ScientificBenchmarkPack:
    """Evaluate each local specialist across fixed scientific research domains.

    This is deliberately an evaluation boundary.  ``shortlist`` records an
    evidence-based review recommendation and never changes model routing.
    """

    def __init__(self, fixture: dict[str, Any], fixture_root: Path):
        if fixture.get("schema_version") != "alethia-scientific-benchmark/v1":
            raise ValueError("unsupported scientific fixture schema")
        self.fixture = fixture
        self.fixture_root = fixture_root

    def _domain_fixture(self, domain: str) -> dict[str, Any]:
        filtered = deepcopy(self.fixture)
        filtered["cases"] = {
            capability: [case for case in cases if case["domain"] == domain]
            for capability, cases in self.fixture["cases"].items()
        }
        return filtered

    def _shortlist(self, per_domain: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for report in per_domain.values():
            for result in report["results"]:
                grouped[result["candidate"]["id"]].append(result)
        shortlist, rejected = [], []
        for candidate_id, results in sorted(grouped.items()):
            quality = sum(row["metrics"]["quality"] for row in results) / len(results)
            reliability = sum(row["metrics"]["reliability"] for row in results) / len(results)
            failed_cases = sum(row["metrics"]["failed_case_count"] for row in results)
            row = {
                "candidate": results[0]["candidate"], "domains_evaluated": len(results),
                "mean_quality": round(quality, 6), "mean_reliability": round(reliability, 6),
                "failed_case_count": failed_cases, "activation": "not_activated",
            }
            if not row["candidate"]["integration_eligible"]:
                row["decision"] = "reject_for_2d_candidate_stage"
                row["reason"] = "Evaluation-only baseline; not eligible for integration regardless of its fixture score."
                rejected.append(row)
            elif quality >= SHORTLIST_QUALITY and reliability >= SHORTLIST_RELIABILITY:
                row["decision"] = "shortlist_for_2d_integration_review"
                row["reason"] = "Meets v1 quality and reliability thresholds; requires separate privacy, licence, and integration review."
                shortlist.append(row)
            else:
                row["decision"] = "reject_for_2d_candidate_stage"
                row["reason"] = "Does not meet v1 quality/reliability thresholds across all scientific domains."
                rejected.append(row)
        return shortlist, rejected

    def run(self, adapters: Iterable[SpecialistAdapter]) -> dict[str, Any]:
        adapters = list(adapters)
        domains = list(self.fixture["domains"])
        per_domain = {
            domain: BenchmarkHarness(self._domain_fixture(domain), self.fixture_root).run(adapters)
            for domain in domains
        }
        shortlist, rejected = self._shortlist(per_domain)
        fixture_bytes = json.dumps(self.fixture, sort_keys=True, separators=(",", ":")).encode()
        return {
            "schema_version": "alethia-scientific-benchmark-report/v1",
            "pack_version": self.fixture["version"],
            "fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "domains": per_domain,
            "overall_comparison": {
                "shortlist": shortlist, "rejected": rejected,
                "thresholds": {"mean_quality": SHORTLIST_QUALITY, "mean_reliability": SHORTLIST_RELIABILITY},
            },
            "adoption_policy": "Shortlisting is not activation. No result changes ALETHEIA routing or production configuration.",
        }


def write_scientific_report(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path, markdown_path = output_dir / "report.json", output_dir / "report.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# ALETHEIA Scientific Benchmark Pack v1", "", f"Pack: `{report['pack_version']}`", "", "## Per-domain rankings", ""]
    for domain, domain_report in report["domains"].items():
        lines.append(f"### {domain.title()}")
        lines.extend(f"- {capability}: {', '.join(candidates)}" for capability, candidates in domain_report["rankings"].items())
        lines.append("")
    lines += ["## 2D integration-review shortlist", ""]
    rows = report["overall_comparison"]
    lines += [f"- {row['candidate']['id']}: {row['decision']} ({row['mean_quality']:.2f} quality, {row['mean_reliability']:.2f} reliability)" for row in rows["shortlist"]]
    lines += ["", "## Rejected at this stage", ""]
    lines += [f"- {row['candidate']['id']}: {row['reason']}" for row in rows["rejected"]]
    lines += ["", "## Adoption", "", report["adoption_policy"], ""]
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, markdown_path
