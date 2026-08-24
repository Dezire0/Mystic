"""Reproducible metric collection and report generation for ALETHEIA v0."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import resource
import time
from typing import Any, Iterable

from .adapters import SpecialistAdapter


def load_fixture(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "alethia-specialist-benchmark/v0":
        raise ValueError("unsupported fixture schema")
    return payload


def _normalise(text: str) -> str:
    return " ".join(text.lower().split())


def _token_f1(actual: str, expected: str) -> float:
    actual_tokens, expected_tokens = _normalise(actual).split(), _normalise(expected).split()
    if not actual_tokens or not expected_tokens:
        return float(actual_tokens == expected_tokens)
    overlap = sum(min(actual_tokens.count(token), expected_tokens.count(token)) for token in set(actual_tokens))
    precision, recall = overlap / len(actual_tokens), overlap / len(expected_tokens)
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


@dataclass
class CaseResult:
    case_id: str
    passed: bool
    quality: float
    latency_ms: float
    cpu_ms: float
    error: str | None = None


class BenchmarkHarness:
    """Runs capability-matched adapters and records decision-neutral results."""

    def __init__(self, fixture: dict[str, Any], fixture_root: Path):
        self.fixture = fixture
        self.fixture_root = fixture_root

    def _cases(self, capability: str) -> list[dict[str, Any]]:
        return list(self.fixture["cases"].get(capability, []))

    def _evaluate(self, adapter: SpecialistAdapter, case: dict[str, Any]) -> float:
        payload = dict(case["input"])
        if "image_path" in payload:
            payload["image_path"] = str(self.fixture_root / payload["image_path"])
        output = adapter.run(payload)
        if adapter.capability in {"retrieval", "embedding", "reranking"}:
            expected = case["expected"]["top_id"]
            return 1.0 if output and output[0] == expected else 0.0
        return _token_f1(str(output), str(case["expected"]["text"]))

    def run(self, adapters: Iterable[SpecialistAdapter]) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for adapter in adapters:
            case_results: list[CaseResult] = []
            for case in self._cases(adapter.capability):
                started_wall, started_cpu = time.perf_counter(), time.process_time()
                try:
                    quality = self._evaluate(adapter, case)
                    error = None
                except Exception as exc:  # failure cases belong in the report, not the log only
                    quality, error = 0.0, f"{type(exc).__name__}: {exc}"
                latency_ms = (time.perf_counter() - started_wall) * 1000
                cpu_ms = (time.process_time() - started_cpu) * 1000
                case_results.append(CaseResult(
                    case_id=str(case["id"]), passed=quality >= float(case.get("pass_at", 1.0)),
                    quality=round(quality, 6), latency_ms=round(latency_ms, 3), cpu_ms=round(cpu_ms, 3), error=error,
                ))
            successful = [result for result in case_results if result.error is None]
            quality = sum(result.quality for result in case_results) / len(case_results) if case_results else 0.0
            reliability = len(successful) / len(case_results) if case_results else 0.0
            results.append({
                "candidate": {"id": adapter.identifier, "capability": adapter.capability, "license": adapter.license,
                              "local": adapter.local},
                "metrics": {"quality": round(quality, 6), "reliability": round(reliability, 6),
                            "mean_latency_ms": round(sum(r.latency_ms for r in case_results) / len(case_results), 3) if case_results else None,
                            "mean_cpu_ms": round(sum(r.cpu_ms for r in case_results) / len(case_results), 3) if case_results else None,
                            "estimated_cost_usd": 0.0,
                            "process_max_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
                "failures": [asdict(result) for result in case_results if result.error or not result.passed],
                "cases": [asdict(result) for result in case_results],
                "decision": "requires_human_review",
                "decision_reason": "Benchmark ranking is evidence, not an adoption decision.",
            })
        rankings: dict[str, list[str]] = {}
        for capability in sorted({row["candidate"]["capability"] for row in results}):
            ranked = sorted((row for row in results if row["candidate"]["capability"] == capability),
                            key=lambda row: (-row["metrics"]["quality"], -row["metrics"]["reliability"], row["metrics"]["mean_latency_ms"] or float("inf")))
            rankings[capability] = [row["candidate"]["id"] for row in ranked]
        fixture_bytes = json.dumps(self.fixture, sort_keys=True, separators=(",", ":")).encode()
        return {"schema_version": "alethia-specialist-benchmark-report/v0", "fixture_version": self.fixture["version"],
                "fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
                "generated_at": datetime.now(timezone.utc).isoformat(), "results": results, "rankings": rankings,
                "measurement_notes": {
                    "cost": "Bundled local candidates are measured as zero marginal API cost; hardware and operator cost are excluded.",
                    "rss": "ru_maxrss is process-wide and platform-unit dependent; use it for within-host comparison only.",
                    "failure_handling": "Exceptions and below-threshold cases are retained per candidate rather than excluded from rankings.",
                },
                "adoption_policy": "No candidate is automatically adopted; review quality, failures, licences, and operational fit."}


def write_report(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "report.json"
    markdown_path = output_dir / "report.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# ALETHEIA Specialist Benchmark v0", "", f"Fixture: `{report['fixture_version']}`", "", "## Rankings", ""]
    lines += [f"- {capability}: {', '.join(candidates)}" for capability, candidates in report["rankings"].items()]
    lines += ["", "## Adoption", "", report["adoption_policy"], ""]
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, markdown_path
