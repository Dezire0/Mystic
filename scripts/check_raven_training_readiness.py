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
    return parser


def prepared_paths(root_path: Path) -> dict[str, Path]:
    return {
        "dataset": root_path / "mystic_data" / "datasets" / "raven" / "research_table_raven.jsonl",
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

    for row in rows:
        verdict = str(row.get("target_verdict", "")).strip().upper()
        verdict_counts[verdict] += 1
        metadata = row.get("metadata", {})
        research_table = metadata.get("research_table", {}) if isinstance(metadata, dict) else {}
        first_fatal_error = str(research_table.get("first_fatal_error", "") or "").strip()
        verifier_derived = bool(research_table.get("verifier_derived"))
        tool_evidence = str(research_table.get("tool_evidence", "") or "").strip()
        if verdict == "INVALID" and first_fatal_error:
            invalid_with_fatal += 1
        if verifier_derived:
            verifier_rows += 1
            if tool_evidence:
                verifier_with_tool_evidence += 1

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
    }


def looks_like_research_table_split(path: Path) -> bool:
    rows = load_jsonl(path)
    if not rows:
        return False
    for row in rows:
        metadata = row.get("metadata", {})
        if not isinstance(metadata, dict):
            return False
        if str(metadata.get("dataset_source", "")).strip() != "research_table":
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
    if paths["eval"].exists() and eval_rows < 0:
        warnings.append(f"Unexpected eval row count at {paths['eval']}")

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


def check_raven_training_readiness(root_path: str | Path) -> dict[str, Any]:
    root = Path(root_path)
    paths = prepared_paths(root)
    warnings: list[str] = []
    errors: list[str] = []

    prepared_state = ensure_prepared_dataset(root, paths, warnings, errors)
    rows = list(prepared_state.get("rows", []))
    manifest = prepared_state.get("manifest", {}) if isinstance(prepared_state.get("manifest"), dict) else {}
    summary = summarize_prepared_rows(rows)
    add_quality_warnings(summary, warnings)
    warnings = list(dict.fromkeys(warnings))

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

    report = {
        "checked_at": now_iso(),
        "root_path": str(root),
        "ready": not errors,
        "paths": {key: str(value) for key, value in paths.items()},
        "dataset_exists": prepared_state["dataset_exists"],
        "prepared_dataset": {
            "exists": prepared_state["prepared_exists"],
            "generated": prepared_state["generated"],
            "rows_total": summary["rows_total"],
        },
        "manifest_exists": prepared_state["manifest_exists"],
        "manifest_rows_written": int(manifest.get("rows_written", 0)) if manifest else 0,
        "verdict_counts": summary["verdict_counts"],
        "invalid_rows_count": summary["invalid_rows"],
        "needs_more_detail_rows_count": summary["needs_more_detail_rows"],
        "valid_rows_count": summary["valid_rows"],
        "first_fatal_error_coverage": summary["first_fatal_error_coverage"],
        "tool_evidence_coverage": summary["verifier_tool_evidence_coverage"],
        "train_eval_split": split_state,
        "kaggle_package": package_state,
        "warnings": warnings,
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
        f"Report: {report['paths']['report']}",
    ]
    if report["warnings"]:
        lines.append("Warnings:")
        lines.extend(f"- {item}" for item in report["warnings"])
    if report["errors"]:
        lines.append("Errors:")
        lines.extend(f"- {item}" for item in report["errors"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = check_raven_training_readiness(args.root_path)
    print(render_console_summary(report))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
