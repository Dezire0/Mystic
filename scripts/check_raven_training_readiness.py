from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
import tarfile
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.prepare_research_table_training import MIN_INVALID_ROWS_WARNING_THRESHOLD, prepare_research_table_training
from scripts.run_mystic_cycle import create_kaggle_package, materialize_prepared_training_split
from mystic.research_table.training_quality import evaluate_raven_training_quality


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check whether Raven training from Research Table data is ready.")
    parser.add_argument("--root-path", default=str(ROOT), help="Mystic repository root.")
    parser.add_argument("--require-lab-failures", action="store_true")
    return parser


def prepared_paths(root_path: Path) -> dict[str, Path]:
    return {
        "dataset": root_path / "mystic_data" / "datasets" / "raven" / "research_table_raven.jsonl",
        "adversarial_dataset": root_path / "mystic_data" / "datasets" / "raven" / "adversarial_seed_raven.jsonl",
        "adversarial_manifest": root_path / "mystic_data" / "datasets" / "raven" / "adversarial_seed_manifest.json",
        "lab_failure_dataset": root_path / "mystic_data" / "datasets" / "lab" / "raven_lab_failures.jsonl",
        "lab_failure_summary": root_path / "mystic_data" / "datasets" / "lab" / "raven_lab_failures_summary.json",
        "prepared": root_path / "mystic_data" / "training" / "raven" / "research_table_train.jsonl",
        "manifest": root_path / "mystic_data" / "training" / "raven" / "manifest.json",
        "report": root_path / "mystic_data" / "training" / "raven" / "readiness_report.json",
        "train": root_path / "mystic_data" / "train_ready" / "raven_train.jsonl",
        "eval": root_path / "mystic_data" / "eval_holdout" / "raven_eval.jsonl",
    }


def summarize_prepared_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    verdict_counts: Counter[str] = Counter()
    invalid_with_fatal = 0
    verifier_rows = 0
    verifier_with_tool_evidence = 0
    dataset_source_counts: Counter[str] = Counter()
    lab_failure_verdict_counts: Counter[str] = Counter()

    for row in rows:
        verdict = str(row.get("target_verdict", "")).strip().upper()
        verdict_counts[verdict] += 1
        metadata = row.get("metadata", {})
        dataset_source = str(metadata.get("dataset_source", "")).strip() if isinstance(metadata, dict) else ""
        if dataset_source:
            dataset_source_counts[dataset_source] += 1
        source_payload = {}
        if isinstance(metadata, dict):
            if isinstance(metadata.get("research_table"), dict):
                source_payload = metadata["research_table"]
            elif isinstance(metadata.get("lab_failure"), dict):
                source_payload = metadata["lab_failure"]
        first_fatal_error = str(source_payload.get("first_fatal_error", "") or "").strip()
        verifier_derived = bool(source_payload.get("verifier_derived"))
        tool_evidence = str(source_payload.get("tool_evidence", "") or "").strip()
        if verdict == "INVALID" and first_fatal_error:
            invalid_with_fatal += 1
        if verifier_derived:
            verifier_rows += 1
            if tool_evidence:
                verifier_with_tool_evidence += 1
        if dataset_source == "lab_failure":
            lab_failure_verdict_counts[verdict] += 1

    invalid_total = int(verdict_counts.get("INVALID", 0))
    fatal_coverage = 1.0 if invalid_total == 0 else invalid_with_fatal / invalid_total
    verifier_coverage = 1.0 if verifier_rows == 0 else verifier_with_tool_evidence / verifier_rows
    return {
        "rows_total": len(rows),
        "verdict_counts": dict(sorted((key, value) for key, value in verdict_counts.items() if key)),
        "invalid_rows": invalid_total,
        "needs_more_detail_rows": int(verdict_counts.get("NEEDS_MORE_DETAIL", 0)),
        "valid_rows": int(verdict_counts.get("VALID", 0)),
        "first_fatal_error_coverage": {
            "covered": invalid_with_fatal,
            "total": invalid_total,
            "rate": fatal_coverage,
        },
        "verifier_tool_evidence_coverage": {
            "covered": verifier_with_tool_evidence,
            "total": verifier_rows,
            "rate": verifier_coverage,
        },
        "dataset_source_counts": dict(sorted(dataset_source_counts.items())),
        "lab_failure_verdict_counts": dict(sorted((key, value) for key, value in lab_failure_verdict_counts.items() if key)),
    }


def looks_like_research_table_split(path: Path) -> bool:
    rows = load_jsonl(path)
    if not rows:
        return False
    for row in rows:
        metadata = row.get("metadata", {})
        if not isinstance(metadata, dict):
            return False
        dataset_source = str(metadata.get("dataset_source", "")).strip()
        has_legacy_research_metadata = isinstance(metadata.get("research_table"), dict)
        if dataset_source not in {"research_table", "adversarial_seed", "combined"} and not has_legacy_research_metadata:
            return False
    return True


def ensure_prepared_dataset(root_path: Path, paths: dict[str, Path], warnings: list[str], errors: list[str]) -> dict[str, Any]:
    prepared_exists = paths["prepared"].exists() and paths["prepared"].stat().st_size > 0
    manifest_exists = paths["manifest"].exists() and paths["manifest"].stat().st_size > 0
    generated = False
    generation_payload: dict[str, Any] | None = None

    if not paths["dataset"].exists():
        errors.append(f"Research Table Raven dataset is missing: {paths['dataset']}")
        return {
            "dataset_exists": False,
            "prepared_exists": prepared_exists,
            "manifest_exists": manifest_exists,
            "generated": generated,
            "generation_payload": generation_payload,
            "rows": [],
            "manifest": {},
        }

    if not prepared_exists or not manifest_exists:
        try:
            generation_payload = prepare_research_table_training(
                target="raven",
                input_path=paths["dataset"],
                output_path=paths["prepared"],
            )
            generated = True
            warnings.extend(str(item) for item in generation_payload.get("warnings", []))
        except (FileNotFoundError, ValueError) as exc:
            errors.append(str(exc))

    rows = load_jsonl(paths["prepared"])
    manifest = load_json(paths["manifest"]) if paths["manifest"].exists() else {}
    if not rows:
        errors.append(f"Prepared Raven training rows are missing or empty: {paths['prepared']}")
    if not manifest:
        errors.append(f"Prepared Raven training manifest is missing or empty: {paths['manifest']}")
    elif int(manifest.get("rows_written", 0)) <= 0:
        errors.append(f"Prepared Raven training manifest reports no written rows: {paths['manifest']}")

    return {
        "dataset_exists": True,
        "prepared_exists": paths["prepared"].exists(),
        "manifest_exists": paths["manifest"].exists(),
        "generated": generated,
        "generation_payload": generation_payload,
        "rows": rows,
        "manifest": manifest,
    }


def ensure_train_eval_split(paths: dict[str, Path], warnings: list[str], errors: list[str]) -> dict[str, Any]:
    train_exists = paths["train"].exists() and paths["train"].stat().st_size > 0
    eval_exists = paths["eval"].exists() and paths["eval"].stat().st_size > 0
    train_matches_source = looks_like_research_table_split(paths["train"]) if train_exists else False
    eval_matches_source = looks_like_research_table_split(paths["eval"]) if eval_exists else False
    generated = False
    split_payload: dict[str, Any] | None = None

    if not train_exists or not eval_exists or not train_matches_source or not eval_matches_source:
        if (train_exists and not train_matches_source) or (eval_exists and not eval_matches_source):
            warnings.append("Existing Raven train/eval split was not derived from Research Table data and was regenerated.")
        try:
            split_payload = materialize_prepared_training_split(
                prepared_path=paths["prepared"],
                train_path=paths["train"],
                eval_path=paths["eval"],
                eval_ratio=0.1,
            )
            generated = True
        except FileNotFoundError as exc:
            errors.append(str(exc))

    train_rows = len(load_jsonl(paths["train"]))
    eval_rows = len(load_jsonl(paths["eval"]))
    if train_rows <= 0:
        errors.append(f"Train split is missing or empty: {paths['train']}")
    if eval_rows <= 0:
        errors.append(f"Eval split is missing or empty: {paths['eval']}")

    return {
        "train_exists": paths["train"].exists(),
        "eval_exists": paths["eval"].exists(),
        "train_rows": train_rows,
        "eval_rows": eval_rows,
        "train_matches_research_table": looks_like_research_table_split(paths["train"]),
        "eval_matches_research_table": looks_like_research_table_split(paths["eval"]),
        "generated": generated,
        "split_payload": split_payload,
    }


def check_package_contents(root_path: Path, warnings: list[str], errors: list[str]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as temp_dir:
        package_path = Path(temp_dir) / "readiness_package.tar.gz"
        create_kaggle_package(root_path, package_path)
        members: list[str] = []
        with tarfile.open(package_path, "r:gz") as archive:
            members = archive.getnames()
        required = {
            "mystic_data/train_ready/raven_train.jsonl",
            "mystic_data/eval_holdout/raven_eval.jsonl",
        }
        missing = sorted(required.difference(members))
        if missing:
            errors.append(f"Kaggle package is missing required files: {missing}")
        return {
            "package_checked": True,
            "package_size_bytes": package_path.stat().st_size,
            "contains_train_file": "mystic_data/train_ready/raven_train.jsonl" in members,
            "contains_eval_file": "mystic_data/eval_holdout/raven_eval.jsonl" in members,
            "missing_entries": missing,
        }


def add_quality_warnings(summary: dict[str, Any], warnings: list[str]) -> None:
    invalid_rows = int(summary["invalid_rows"])
    if summary["rows_total"] > 0 and invalid_rows < MIN_INVALID_ROWS_WARNING_THRESHOLD:
        warnings.append(
            f"Too few INVALID rows for conservative Raven training: {invalid_rows} < {MIN_INVALID_ROWS_WARNING_THRESHOLD}."
        )
    fatal = summary["first_fatal_error_coverage"]
    if int(fatal["covered"]) < int(fatal["total"]):
        warnings.append(
            f"Missing first_fatal_error on some INVALID rows: {fatal['covered']}/{fatal['total']} covered."
        )
    verifier = summary["verifier_tool_evidence_coverage"]
    if int(verifier["covered"]) < int(verifier["total"]):
        warnings.append(
            f"Missing tool_evidence on some verifier-derived rows: {verifier['covered']}/{verifier['total']} covered."
        )


def check_raven_training_readiness(root_path: str | Path, *, require_lab_failures: bool = False) -> dict[str, Any]:
    root = Path(root_path)
    paths = prepared_paths(root)
    warnings: list[str] = []
    errors: list[str] = []

    prepared_state = ensure_prepared_dataset(root, paths, warnings, errors)
    rows = list(prepared_state.get("rows", []))
    manifest = prepared_state.get("manifest", {}) if isinstance(prepared_state.get("manifest"), dict) else {}
    summary = summarize_prepared_rows(rows)

    split_state = ensure_train_eval_split(paths, warnings, errors) if rows else {
        "train_exists": paths["train"].exists(),
        "eval_exists": paths["eval"].exists(),
        "train_rows": len(load_jsonl(paths["train"])),
        "eval_rows": len(load_jsonl(paths["eval"])),
        "generated": False,
        "split_payload": None,
    }
    package_state = check_package_contents(root, warnings, errors) if rows else {
        "package_checked": False,
        "package_size_bytes": 0,
        "contains_train_file": False,
        "contains_eval_file": False,
        "missing_entries": [
            "mystic_data/train_ready/raven_train.jsonl",
            "mystic_data/eval_holdout/raven_eval.jsonl",
        ],
    }
    quality_gate = evaluate_raven_training_quality(
        rows,
        min_invalid_rows=MIN_INVALID_ROWS_WARNING_THRESHOLD,
        train_rows_count=int(split_state.get("train_rows", 0)),
        eval_rows_count=int(split_state.get("eval_rows", 0)),
    )
    warnings.extend(str(item) for item in quality_gate.get("warnings", []))
    errors.extend(str(item) for item in quality_gate.get("errors", []))
    add_quality_warnings(summary, warnings)

    adversarial_rows = load_jsonl(paths["adversarial_dataset"])
    adversarial_included_rows = int(manifest.get("adversarial_seed_rows", 0)) if manifest else 0
    adversarial_seed_status = {
        "status": (
            "included"
            if adversarial_included_rows > 0
            else "available_not_included"
            if adversarial_rows
            else "missing"
        ),
        "dataset_path": str(paths["adversarial_dataset"]),
        "manifest_path": str(paths["adversarial_manifest"]),
        "dataset_exists": paths["adversarial_dataset"].exists(),
        "manifest_exists": paths["adversarial_manifest"].exists(),
        "available_rows": len(adversarial_rows),
        "included_in_prepared_manifest": adversarial_included_rows > 0,
        "included_rows": adversarial_included_rows,
    }
    lab_failure_rows = load_jsonl(paths["lab_failure_dataset"])
    lab_failure_summary = load_json(paths["lab_failure_summary"]) if paths["lab_failure_summary"].exists() else {}
    lab_failure_included_rows = int(manifest.get("lab_failure_rows", 0)) if manifest else 0
    lab_failure_status = {
        "status": (
            "included"
            if lab_failure_included_rows > 0
            else "available_not_included"
            if lab_failure_rows
            else "missing"
        ),
        "dataset_path": str(paths["lab_failure_dataset"]),
        "summary_path": str(paths["lab_failure_summary"]),
        "dataset_exists": paths["lab_failure_dataset"].exists(),
        "summary_exists": paths["lab_failure_summary"].exists(),
        "available_rows": len(lab_failure_rows),
        "included_in_prepared_manifest": lab_failure_included_rows > 0,
        "included_rows": lab_failure_included_rows,
        "verdict_distribution": dict(sorted(Counter(str(row.get("output", {}).get("verdict", "")).strip().upper() for row in lab_failure_rows if isinstance(row.get("output"), dict)).items())),
        "summary_rows_written": int(lab_failure_summary.get("rows_written", 0)) if lab_failure_summary else 0,
        "failure_type_distribution": lab_failure_summary.get("failure_type_distribution", {}) if isinstance(lab_failure_summary, dict) else {},
    }
    recommendations: list[str] = []
    if summary["invalid_rows"] < MIN_INVALID_ROWS_WARNING_THRESHOLD:
        recommendation = (
            "INVALID row count is low. Consider generating adversarial seeds and preparing with "
            "--include-adversarial-seeds."
        )
        warnings.append(recommendation)
        recommendations.append(recommendation)
    elif adversarial_included_rows > 0:
        recommendations.append("Adversarial seeds are included and the recommended INVALID row count is satisfied.")
    if lab_failure_rows and lab_failure_included_rows == 0:
        warning = "Lab failure dataset is available but not included in the prepared Raven dataset."
        warnings.append(warning)
        recommendations.append(
            "Re-run prepare with --include-lab-failures to include Failure Museum critiques in Raven training data."
        )
    if not lab_failure_rows:
        warning = "Lab failure dataset is missing. Run export_lab_failure_datasets.py to add Failure Museum rows."
        warnings.append(warning)
        if require_lab_failures:
            errors.append(warning)
            recommendations.append(
                "Run python scripts/export_lab_failure_datasets.py --root-path /Users/JYH/Documents/Mystic --target raven."
            )
    elif require_lab_failures and lab_failure_included_rows <= 0:
        error = "Lab failure dataset exists but no lab failure rows were included in the prepared Raven dataset."
        errors.append(error)
        recommendations.append(
            "Run python scripts/prepare_research_table_training.py --root-path /Users/JYH/Documents/Mystic --target raven --include-lab-failures."
        )

    warnings = list(dict.fromkeys(warnings))
    errors = list(dict.fromkeys(errors))
    fatal_coverage = summary["first_fatal_error_coverage"]
    tool_coverage = summary["verifier_tool_evidence_coverage"]
    invalid_row_quality = {
        "count": summary["invalid_rows"],
        "ratio": summary["invalid_rows"] / summary["rows_total"] if summary["rows_total"] else 0.0,
        "minimum_recommended": MIN_INVALID_ROWS_WARNING_THRESHOLD,
        "sufficient": summary["invalid_rows"] >= MIN_INVALID_ROWS_WARNING_THRESHOLD,
        "first_fatal_error_coverage": fatal_coverage,
        "tool_evidence_coverage": tool_coverage,
    }

    report = {
        "checked_at": now_iso(),
        "root_path": str(root),
        "ready": not errors,
        "status": "READY" if not errors else "NOT_READY",
        "paths": {key: str(value) for key, value in paths.items()},
        "dataset_exists": prepared_state["dataset_exists"],
        "prepared_dataset": {
            "exists": prepared_state["prepared_exists"],
            "generated": prepared_state["generated"],
            "rows_total": summary["rows_total"],
            "dataset_source_counts": summary["dataset_source_counts"],
        },
        "manifest_exists": prepared_state["manifest_exists"],
        "manifest_rows_written": int(manifest.get("rows_written", 0)) if manifest else 0,
        "verdict_counts": summary["verdict_counts"],
        "lab_failure_verdict_counts": summary["lab_failure_verdict_counts"],
        "invalid_rows_count": summary["invalid_rows"],
        "needs_more_detail_rows_count": summary["needs_more_detail_rows"],
        "valid_rows_count": summary["valid_rows"],
        "first_fatal_error_coverage": summary["first_fatal_error_coverage"],
        "tool_evidence_coverage": summary["verifier_tool_evidence_coverage"],
        "adversarial_seed_status": adversarial_seed_status,
        "lab_failure_status": lab_failure_status,
        "invalid_row_quality": invalid_row_quality,
        "quality_gate": quality_gate,
        "train_eval_split": split_state,
        "kaggle_package": package_state,
        "warnings": warnings,
        "recommendations": recommendations,
        "errors": errors,
    }
    write_json(paths["report"], report)
    return report


def render_console_summary(report: dict[str, Any]) -> str:
    lines = [
        f"Raven readiness: {'READY' if report['ready'] else 'NOT READY'}",
        f"Dataset exists: {report['dataset_exists']}",
        f"Prepared rows: {report['prepared_dataset']['rows_total']}",
        f"Manifest rows_written: {report['manifest_rows_written']}",
        f"Verdicts: INVALID={report['invalid_rows_count']}, NEEDS_MORE_DETAIL={report['needs_more_detail_rows_count']}, VALID={report['valid_rows_count']}",
        (
            "first_fatal_error coverage: "
            f"{report['first_fatal_error_coverage']['covered']}/{report['first_fatal_error_coverage']['total']}"
        ),
        (
            "tool_evidence coverage: "
            f"{report['tool_evidence_coverage']['covered']}/{report['tool_evidence_coverage']['total']}"
        ),
        (
            "Train/eval split: "
            f"{report['train_eval_split']['train_rows']} train / {report['train_eval_split']['eval_rows']} eval"
        ),
        (
            "Kaggle package contains train/eval: "
            f"{report['kaggle_package']['contains_train_file']} / {report['kaggle_package']['contains_eval_file']}"
        ),
        (
            "Adversarial seeds: "
            f"{report.get('adversarial_seed_status', {}).get('status', 'unknown')} "
            f"({report.get('adversarial_seed_status', {}).get('included_rows', 0)} included)"
        ),
        (
            "Lab failures: "
            f"{report.get('lab_failure_status', {}).get('status', 'unknown')} "
            f"({report.get('lab_failure_status', {}).get('included_rows', 0)} included)"
        ),
        f"Report: {report['paths']['report']}",
    ]
    if report.get("recommendations"):
        lines.append("Recommendations:")
        lines.extend(f"- {item}" for item in report["recommendations"])
    if report["warnings"]:
        lines.append("Warnings:")
        lines.extend(f"- {item}" for item in report["warnings"])
    if report["errors"]:
        lines.append("Errors:")
        lines.extend(f"- {item}" for item in report["errors"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = check_raven_training_readiness(args.root_path, require_lab_failures=args.require_lab_failures)
    print(render_console_summary(report))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
