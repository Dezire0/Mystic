from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_raven_vnext_eval import run_raven_vnext_eval


def _metrics_payload(session_id: str, *, turns: int, discoveries: int, verified: int, refuted: int, override: bool) -> dict[str, object]:
    return {
        "generated_at": "2026-06-30T00:00:00+00:00",
        "sessions": [
            {
                "session_id": session_id,
                "turns_count": turns,
                "discoveries_count": discoveries,
                "verified_discoveries_count": verified,
                "refuted_discoveries_count": refuted,
                "deterministic_override_used": override,
            }
        ],
        "models": [],
        "tools": [],
        "warnings": [],
    }


def _comparison_snapshot(run_id: str, rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "path": "/tmp/raven_comparison_results.jsonl",
        "run_id": run_id,
        "rows": rows,
        "summary": {"run_id": run_id},
    }


def _comparison_row(*, target: str, verdict: str, parse_error=None, first_fatal_error: str = "") -> dict[str, object]:
    return {
        "run_id": "run",
        "target_verdict": target,
        "base": {},
        "adapter": {
            "verdict": verdict,
            "parse_error": parse_error,
            "first_fatal_error": first_fatal_error,
        },
    }


def _e2e_summary(*, refuted: bool, missing_ok: bool, final_source: str = "deterministic_verifier") -> dict[str, object]:
    return {
        "session_id": "scenario",
        "bad_candidates_refuted": {
            "candidate": "(2, 4, 8)",
            "appeared_in_session": True,
            "refuted": refuted,
        },
        "expected_candidates_found": {
            "found_in_final_answer": ["(2, 3, 6)", "(3, 3, 3)"],
            "missing_from_final_answer": ["(2, 4, 4)"] if not missing_ok else [],
        },
        "quality_checks": {
            "invalid_verifier_overrides_final_status": True,
            "missing_244_prevents_valid": missing_ok,
            "unknown_verifier_does_not_change_status": True,
        },
        "final_verification": {"verdict": "INVALID"},
        "final_decision_source": final_source,
    }


class RunRavenVnextEvalTests(unittest.TestCase):
    def test_refuses_when_readiness_is_not_ready(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_readiness(root, ready=False)

            with self.assertRaisesRegex(ValueError, "not READY"):
                run_raven_vnext_eval(root_path=root, skip_cycle_prepare=True)

    def test_writes_report_for_ready_baseline_without_reinjection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_readiness(root, ready=True)

            report = run_raven_vnext_eval(
                root_path=root,
                skip_cycle_prepare=True,
                metrics_loader=lambda _: _metrics_payload("baseline", turns=5, discoveries=2, verified=1, refuted=1, override=True),
                comparison_loader=lambda _: _comparison_snapshot(
                    "baseline-run",
                    [
                        _comparison_row(target="INVALID", verdict="INVALID", first_fatal_error="bad step"),
                        _comparison_row(target="VALID", verdict="NEEDS_MORE_DETAIL", first_fatal_error=""),
                    ],
                ),
                e2e_loader=lambda _: _e2e_summary(refuted=True, missing_ok=True),
            )

            self.assertEqual(report["workflow_status"], "instructions_only")
            self.assertEqual(report["baseline"]["quality_fields"]["raven_invalid_recall"], 1.0)
            self.assertEqual(report["quality_comparison"]["parseable_critique_rate"]["before"], 1.0)
            self.assertTrue((root / "mystic_data" / "training" / "raven" / "vnext_eval_report.json").exists())
            self.assertTrue((root / "mystic_data" / "training" / "raven" / "vnext_eval_report.md").exists())

    def test_post_reinjection_report_compares_before_and_after_metrics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_readiness(root, ready=True)

            metrics_values = iter(
                [
                    _metrics_payload("baseline", turns=5, discoveries=2, verified=1, refuted=0, override=False),
                    _metrics_payload("after", turns=7, discoveries=3, verified=2, refuted=1, override=True),
                ]
            )
            comparison_values = iter(
                [
                    _comparison_snapshot(
                        "before-run",
                        [
                            _comparison_row(target="INVALID", verdict="NEEDS_MORE_DETAIL", first_fatal_error=""),
                            _comparison_row(target="VALID", verdict="VALID", first_fatal_error=""),
                        ],
                    ),
                    _comparison_snapshot(
                        "after-run",
                        [
                            _comparison_row(target="INVALID", verdict="INVALID", first_fatal_error="bad step"),
                            _comparison_row(target="VALID", verdict="NEEDS_MORE_DETAIL", first_fatal_error="needs detail"),
                        ],
                    ),
                ]
            )
            e2e_values = iter(
                [
                    _e2e_summary(refuted=False, missing_ok=False, final_source="model_outputs"),
                    _e2e_summary(refuted=True, missing_ok=True, final_source="deterministic_verifier"),
                ]
            )

            report = run_raven_vnext_eval(
                root_path=root,
                adapter_tar="/tmp/raven.tar.gz",
                metrics_loader=lambda _: next(metrics_values),
                comparison_loader=lambda _: next(comparison_values),
                e2e_loader=lambda _: next(e2e_values),
                cycle_prepare_runner=lambda **_: {"payload": {"package_path": "/tmp/pkg.tar.gz"}, "stdout": "", "command": []},
                cycle_finish_runner=lambda **_: {"payload": {"processed_count": 2}, "stdout": "", "command": []},
                e2e_runner=lambda **_: {"session_id": "post-run"},
            )

            self.assertEqual(report["workflow_status"], "post_reinjection_complete")
            self.assertEqual(report["quality_comparison"]["raven_invalid_recall"]["before"], 0.0)
            self.assertEqual(report["quality_comparison"]["raven_invalid_recall"]["after"], 1.0)
            self.assertGreater(report["quality_comparison"]["bad_candidate_refutation_rate"]["delta"], 0.0)
            self.assertGreater(report["quality_comparison"]["deterministic_override_alignment"]["delta"], 0.0)

    def _write_readiness(self, root: Path, *, ready: bool) -> None:
        path = root / "mystic_data" / "training" / "raven" / "readiness_report.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "ready": ready,
                    "status": "READY" if ready else "NOT_READY",
                    "warnings": [],
                },
                indent=2,
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
