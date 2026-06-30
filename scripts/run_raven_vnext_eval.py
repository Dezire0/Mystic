from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.research_table.metrics import summarize_research_table_metrics
from scripts.check_raven_training_readiness import render_console_summary
from scripts.run_mystic_cycle import extract_last_json_object
from scripts.run_research_table_e2e import run_research_table_e2e


DEFAULT_BASE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
DEFAULT_ADAPTER_PATH = "mystic_data/adapters/raven_lora_vnext"
DEFAULT_MODEL_ID = "raven_lora_vnext_qwen_auto"

QUALITY_FIELDS = [
    "raven_invalid_recall",
    "bad_candidate_refutation_rate",
    "missing_candidate_detection_rate",
    "needs_more_detail_rate",
    "valid_overaccept_rate",
    "parseable_critique_rate",
    "first_fatal_error_coverage",
    "deterministic_override_alignment",
]


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare and evaluate the Raven vNext Research Table training cycle.")
    parser.add_argument("--root-path", default=str(ROOT), help="Mystic repository root.")
    parser.add_argument("--force", action="store_true", help="Continue even if readiness status is not READY.")
    parser.add_argument("--cycle-id", default="raven_vnext", help="Cycle id used for prepare/finish steps.")
    parser.add_argument("--base-model", default=DEFAULT_BASE_MODEL)
    parser.add_argument("--adapter-path", default=DEFAULT_ADAPTER_PATH)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--skip-cycle-prepare", action="store_true", help="Skip the local cycle prepare step and only emit instructions.")
    parser.add_argument("--adapter-tar", default="", help="Optional trained adapter tarball path. When provided, run finish + post-E2E.")
    parser.add_argument("--run-limit", type=int, default=20)
    parser.add_argument("--compare-limit", type=int, default=100)
    return parser


def readiness_report_path(root_path: Path) -> Path:
    return root_path / "mystic_data" / "training" / "raven" / "readiness_report.json"


def vnext_report_paths(root_path: Path) -> dict[str, Path]:
    base = root_path / "mystic_data" / "training" / "raven"
    return {
        "json": base / "vnext_eval_report.json",
        "markdown": base / "vnext_eval_report.md",
    }


def load_readiness_status(root_path: Path) -> dict[str, Any]:
    path = readiness_report_path(root_path)
    if not path.exists():
        raise FileNotFoundError(f"Readiness report not found: {path}")
    payload = load_json(path)
    status = str(payload.get("status", "")).strip().upper()
    if not status:
        status = "READY" if bool(payload.get("ready")) else "NOT_READY"
    payload["status"] = status
    return payload


def compact_research_table_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    sessions = list(payload.get("sessions", []))
    return {
        "generated_at": str(payload.get("generated_at", "")),
        "sessions_count": len(sessions),
        "models_count": len(payload.get("models", [])),
        "tools_count": len(payload.get("tools", [])),
        "warnings_count": len(payload.get("warnings", [])),
        "total_turns": sum(int(item.get("turns_count", 0)) for item in sessions),
        "total_discoveries": sum(int(item.get("discoveries_count", 0)) for item in sessions),
        "total_verified_discoveries": sum(int(item.get("verified_discoveries_count", 0)) for item in sessions),
        "total_refuted_discoveries": sum(int(item.get("refuted_discoveries_count", 0)) for item in sessions),
        "deterministic_override_rate": (
            sum(1 for item in sessions if bool(item.get("deterministic_override_used"))) / len(sessions)
            if sessions
            else None
        ),
    }


def load_latest_e2e_summary(root_path: Path) -> dict[str, Any]:
    scenario_root = root_path / "mystic_data" / "e2e" / "research_table"
    if not scenario_root.exists():
        return {}
    candidates = [path / "summary.json" for path in scenario_root.iterdir() if path.is_dir() and (path / "summary.json").exists()]
    if not candidates:
        return {}
    latest = max(candidates, key=lambda path: path.stat().st_mtime)
    payload = load_json(latest)
    payload["summary_path"] = str(latest)
    return payload


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def load_latest_raven_comparison_snapshot(root_path: Path) -> dict[str, Any]:
    log_path = root_path / "mystic_data" / "logs" / "raven_comparison_results.jsonl"
    rows = load_jsonl(log_path)
    if not rows:
        return {"path": str(log_path), "run_id": "", "rows": [], "summary": {}}

    summary_rows = [row for row in rows if row.get("kind") == "summary" and str(row.get("run_id", "")).strip()]
    if summary_rows:
        latest_summary = max(summary_rows, key=lambda item: str(item.get("timestamp", "")))
        run_id = str(latest_summary.get("run_id", ""))
        run_rows = [row for row in rows if str(row.get("run_id", "")) == run_id and "adapter" in row and "base" in row]
        return {
            "path": str(log_path),
            "run_id": run_id,
            "rows": run_rows,
            "summary": latest_summary,
        }

    comparable_rows = [row for row in rows if "adapter" in row and "base" in row]
    if not comparable_rows:
        return {"path": str(log_path), "run_id": "", "rows": [], "summary": {}}
    latest_row = max(comparable_rows, key=lambda item: str(item.get("timestamp", "")))
    run_id = str(latest_row.get("run_id", ""))
    run_rows = [row for row in comparable_rows if str(row.get("run_id", "")) == run_id]
    return {
        "path": str(log_path),
        "run_id": run_id,
        "rows": run_rows,
        "summary": {},
    }


def build_raven_quality_metrics(*, comparison_snapshot: dict[str, Any], e2e_summary: dict[str, Any]) -> dict[str, Any]:
    rows = list(comparison_snapshot.get("rows", []))
    invalid_targets = [row for row in rows if str(row.get("target_verdict", "")).strip().upper() == "INVALID"]
    non_valid_targets = [row for row in rows if str(row.get("target_verdict", "")).strip().upper() != "VALID"]
    non_valid_outputs = [row for row in rows if str(row.get("adapter", {}).get("verdict", "")).strip().upper() != "VALID"]

    bad_candidate = e2e_summary.get("bad_candidates_refuted", {}) if isinstance(e2e_summary, dict) else {}
    expected = e2e_summary.get("expected_candidates_found", {}) if isinstance(e2e_summary, dict) else {}
    quality_checks = e2e_summary.get("quality_checks", {}) if isinstance(e2e_summary, dict) else {}
    final_verification = e2e_summary.get("final_verification", {}) if isinstance(e2e_summary, dict) else {}

    deterministic_checks: list[bool] = []
    if str(final_verification.get("verdict", "")).upper() in {"VALID", "INVALID"}:
        deterministic_checks.append(str(e2e_summary.get("final_decision_source", "")) == "deterministic_verifier")
    for key in [
        "invalid_verifier_overrides_final_status",
        "unknown_verifier_does_not_change_status",
        "missing_244_prevents_valid",
    ]:
        if key in quality_checks:
            deterministic_checks.append(bool(quality_checks[key]))

    missing_final = list(expected.get("missing_from_final_answer", [])) if isinstance(expected, dict) else []
    if not missing_final:
        missing_detection = 1.0
    elif "missing_244_prevents_valid" in quality_checks:
        missing_detection = 1.0 if bool(quality_checks["missing_244_prevents_valid"]) else 0.0
    else:
        missing_detection = None

    return {
        "raven_invalid_recall": (
            sum(1 for row in invalid_targets if str(row.get("adapter", {}).get("verdict", "")).strip().upper() == "INVALID")
            / len(invalid_targets)
            if invalid_targets
            else None
        ),
        "bad_candidate_refutation_rate": (
            1.0 if bool(bad_candidate.get("refuted")) else 0.0
            if "refuted" in bad_candidate
            else None
        ),
        "missing_candidate_detection_rate": missing_detection,
        "needs_more_detail_rate": (
            sum(1 for row in rows if str(row.get("adapter", {}).get("verdict", "")).strip().upper() == "NEEDS_MORE_DETAIL") / len(rows)
            if rows
            else None
        ),
        "valid_overaccept_rate": (
            sum(1 for row in non_valid_targets if str(row.get("adapter", {}).get("verdict", "")).strip().upper() == "VALID")
            / len(non_valid_targets)
            if non_valid_targets
            else None
        ),
        "parseable_critique_rate": (
            sum(1 for row in rows if row.get("adapter", {}).get("parse_error") is None) / len(rows)
            if rows
            else None
        ),
        "first_fatal_error_coverage": (
            sum(1 for row in non_valid_outputs if str(row.get("adapter", {}).get("first_fatal_error", "")).strip()) / len(non_valid_outputs)
            if non_valid_outputs
            else None
        ),
        "deterministic_override_alignment": (
            sum(1 for item in deterministic_checks if item) / len(deterministic_checks)
            if deterministic_checks
            else None
        ),
    }


def compare_metric_snapshots(before: dict[str, Any], after: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for field in QUALITY_FIELDS:
        before_value = before.get(field)
        after_value = after.get(field)
        delta = None
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            delta = float(after_value) - float(before_value)
        result[field] = {
            "before": before_value,
            "after": after_value,
            "delta": delta,
        }
    return result


def build_kaggle_instructions(*, cycle_id: str, base_model: str, adapter_path: str, model_id: str) -> list[str]:
    return [
        f"python scripts/run_mystic_cycle.py prepare --cycle-id {cycle_id} --dataset-source research_table --target raven --run-prepare-data --base-model {base_model} --adapter-path {adapter_path}",
        f"python scripts/run_mystic_cycle.py submit --cycle-id {cycle_id} --base-model {base_model} --adapter-path {adapter_path}",
        f"python scripts/run_mystic_cycle.py poll --cycle-id {cycle_id}",
        f"python scripts/run_mystic_cycle.py download --cycle-id {cycle_id}",
        f"python scripts/run_mystic_cycle.py finish --cycle-id {cycle_id} --base-model {base_model} --adapter-path {adapter_path} --adapter-tar /path/to/{Path(adapter_path).name}_qwen.tar.gz --model-id {model_id}",
    ]


def render_vnext_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Raven vNext Eval Report",
        "",
        f"- Generated at: `{report.get('generated_at', '')}`",
        f"- Workflow status: `{report.get('workflow_status', '')}`",
        f"- Readiness status: `{report.get('readiness_status', '')}`",
        f"- Root path: `{report.get('root_path', '')}`",
        "",
        "## Quality Comparison",
        "",
        "| metric | before | after | delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for field in QUALITY_FIELDS:
        payload = report.get("quality_comparison", {}).get(field, {})
        lines.append(
            "| {field} | {before} | {after} | {delta} |".format(
                field=field,
                before=_fmt_metric(payload.get("before")),
                after=_fmt_metric(payload.get("after")),
                delta=_fmt_metric(payload.get("delta")),
            )
        )

    lines.extend(["", "## Next Steps", ""])
    for command in report.get("kaggle_workflow_instructions", []):
        lines.append(f"- `{command}`")

    warnings = list(report.get("warnings", []))
    if warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")

    return "\n".join(lines) + "\n"


def _fmt_metric(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def run_json_command(command: list[str], *, cwd: Path) -> tuple[dict[str, Any], str]:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=True)
    stdout = completed.stdout.strip()
    payload = extract_last_json_object(stdout) if stdout else {}
    return payload, stdout


def default_cycle_prepare_runner(*, root_path: Path, cycle_id: str, base_model: str, adapter_path: str) -> dict[str, Any]:
    command = [
        sys.executable,
        "scripts/run_mystic_cycle.py",
        "prepare",
        "--cycle-id",
        cycle_id,
        "--base-dir",
        str(root_path / "mystic_data"),
        "--dataset-source",
        "research_table",
        "--target",
        "raven",
        "--run-prepare-data",
        "--base-model",
        base_model,
        "--adapter-path",
        adapter_path,
    ]
    payload, stdout = run_json_command(command, cwd=root_path)
    return {
        "command": command,
        "payload": payload,
        "stdout": stdout,
    }


def default_cycle_finish_runner(
    *,
    root_path: Path,
    cycle_id: str,
    base_model: str,
    adapter_path: str,
    adapter_tar: str,
    model_id: str,
    run_limit: int,
    compare_limit: int,
) -> dict[str, Any]:
    command = [
        sys.executable,
        "scripts/run_mystic_cycle.py",
        "finish",
        "--adapter-tar",
        adapter_tar,
        "--adapter-path",
        adapter_path,
        "--base-model",
        base_model,
        "--cycle-id",
        cycle_id,
        "--model-id",
        model_id,
        "--base-dir",
        str(root_path / "mystic_data"),
        "--run-limit",
        str(run_limit),
        "--compare-limit",
        str(compare_limit),
    ]
    payload, stdout = run_json_command(command, cwd=root_path)
    return {
        "command": command,
        "payload": payload,
        "stdout": stdout,
    }


def run_raven_vnext_eval(
    *,
    root_path: str | Path,
    force: bool = False,
    cycle_id: str = "raven_vnext",
    base_model: str = DEFAULT_BASE_MODEL,
    adapter_path: str = DEFAULT_ADAPTER_PATH,
    model_id: str = DEFAULT_MODEL_ID,
    skip_cycle_prepare: bool = False,
    adapter_tar: str = "",
    run_limit: int = 20,
    compare_limit: int = 100,
    metrics_loader: Callable[[str | Path], dict[str, Any]] = summarize_research_table_metrics,
    comparison_loader: Callable[[Path], dict[str, Any]] = load_latest_raven_comparison_snapshot,
    e2e_loader: Callable[[Path], dict[str, Any]] = load_latest_e2e_summary,
    cycle_prepare_runner: Callable[..., dict[str, Any]] = default_cycle_prepare_runner,
    cycle_finish_runner: Callable[..., dict[str, Any]] = default_cycle_finish_runner,
    e2e_runner: Callable[..., dict[str, Any]] = run_research_table_e2e,
) -> dict[str, Any]:
    root = Path(root_path)
    readiness = load_readiness_status(root)
    readiness_status = str(readiness.get("status", "")).strip().upper()
    if readiness_status != "READY" and not force:
        raise ValueError(f"Refusing to continue because readiness status is {readiness_status}, not READY.")

    baseline_metrics_payload = metrics_loader(root)
    baseline_comparison = comparison_loader(root)
    baseline_e2e = e2e_loader(root)
    baseline_quality = build_raven_quality_metrics(
        comparison_snapshot=baseline_comparison,
        e2e_summary=baseline_e2e,
    )

    workflow_status = "baseline_recorded"
    prepare_result: dict[str, Any] | None = None
    if not skip_cycle_prepare:
        prepare_result = cycle_prepare_runner(
            root_path=root,
            cycle_id=cycle_id,
            base_model=base_model,
            adapter_path=adapter_path,
        )
        workflow_status = "cycle_prepared"
    else:
        workflow_status = "instructions_only"

    finish_result: dict[str, Any] | None = None
    post_e2e_result: dict[str, Any] | None = None
    after_metrics_payload = baseline_metrics_payload
    after_comparison = baseline_comparison
    after_e2e = baseline_e2e
    if adapter_tar:
        finish_result = cycle_finish_runner(
            root_path=root,
            cycle_id=cycle_id,
            base_model=base_model,
            adapter_path=adapter_path,
            adapter_tar=adapter_tar,
            model_id=model_id,
            run_limit=run_limit,
            compare_limit=compare_limit,
        )
        post_e2e_result = e2e_runner(root_path=root, run_id=f"{cycle_id}-post")
        after_metrics_payload = metrics_loader(root)
        after_comparison = comparison_loader(root)
        after_e2e = e2e_loader(root)
        workflow_status = "post_reinjection_complete"
    elif workflow_status == "cycle_prepared":
        workflow_status = "awaiting_kaggle_or_reinjection"

    after_quality = build_raven_quality_metrics(
        comparison_snapshot=after_comparison,
        e2e_summary=after_e2e,
    )
    quality_comparison = compare_metric_snapshots(baseline_quality, after_quality)

    warnings = list(dict.fromkeys([*(readiness.get("warnings", []) or [])]))
    report = {
        "generated_at": now_iso(),
        "root_path": str(root),
        "readiness_status": readiness_status,
        "readiness_report": readiness,
        "workflow_status": workflow_status,
        "baseline": {
            "research_table_metrics": compact_research_table_metrics(baseline_metrics_payload),
            "latest_raven_comparison": {
                "run_id": str(baseline_comparison.get("run_id", "")),
                "rows_count": len(baseline_comparison.get("rows", [])),
                "path": str(baseline_comparison.get("path", "")),
            },
            "latest_e2e_summary": baseline_e2e,
            "quality_fields": baseline_quality,
        },
        "prepare_result": prepare_result,
        "finish_result": finish_result,
        "post_e2e_result": post_e2e_result,
        "after": {
            "research_table_metrics": compact_research_table_metrics(after_metrics_payload),
            "latest_raven_comparison": {
                "run_id": str(after_comparison.get("run_id", "")),
                "rows_count": len(after_comparison.get("rows", [])),
                "path": str(after_comparison.get("path", "")),
            },
            "latest_e2e_summary": after_e2e,
            "quality_fields": after_quality,
        },
        "quality_comparison": quality_comparison,
        "kaggle_workflow_instructions": build_kaggle_instructions(
            cycle_id=cycle_id,
            base_model=base_model,
            adapter_path=adapter_path,
            model_id=model_id,
        ),
        "warnings": warnings,
    }

    paths = vnext_report_paths(root)
    write_json(paths["json"], report)
    paths["markdown"].write_text(render_vnext_report_markdown(report), encoding="utf-8")
    report["output_paths"] = {key: str(value) for key, value in paths.items()}
    return report


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = run_raven_vnext_eval(
            root_path=args.root_path,
            force=args.force,
            cycle_id=args.cycle_id,
            base_model=args.base_model,
            adapter_path=args.adapter_path,
            model_id=args.model_id,
            skip_cycle_prepare=args.skip_cycle_prepare,
            adapter_tar=args.adapter_tar,
            run_limit=args.run_limit,
            compare_limit=args.compare_limit,
        )
    except (FileNotFoundError, ValueError, subprocess.CalledProcessError) as exc:
        print(str(exc))
        return 1

    print(render_console_summary(report["readiness_report"]))
    print("")
    print(f"Raven vNext workflow status: {report['workflow_status']}")
    print(f"Report JSON: {report['output_paths']['json']}")
    print(f"Report Markdown: {report['output_paths']['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
