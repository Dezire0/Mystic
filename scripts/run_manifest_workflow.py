from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.training.blueprints import INGESTION_SOURCES


DEFAULT_BASE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
DEFAULT_ADAPTER_PATH = "mystic_data/adapters/raven_lora_v1"


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def workflow_dir(base_dir: Path, workflow_id: str) -> Path:
    return base_dir / "workflows" / workflow_id


def workflow_summary_path(base_dir: Path, workflow_id: str) -> Path:
    return workflow_dir(base_dir, workflow_id) / "summary.json"


def verify_project_root(root: Path) -> None:
    required = [
        root / "scripts" / "init_internal_mystic_data.py",
        root / "scripts" / "resolve_hf_datasets.py",
        root / "scripts" / "download_hf_samples.py",
        root / "scripts" / "download_numina_sample.py",
        root / "scripts" / "export_raven_lora.py",
        root / "scripts" / "prepare_raven_training_data.py",
        root / "scripts" / "prepare_train_ready.py",
        root / "scripts" / "run_specialist_training.py",
        root / "scripts" / "run_mystic_cycle.py",
        root / "mystic_data" / "metadata" / "manifests" / "training_manifest.json",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Project root validation failed. Missing: {missing}")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def extract_last_json_object(stdout: str) -> dict[str, Any]:
    lines = [line.rstrip() for line in stdout.splitlines() if line.strip()]
    for index in range(len(lines)):
        candidate = "\n".join(lines[index:])
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ValueError("Could not parse JSON object from subprocess stdout.")


def run_json_command(
    args: list[str],
    *,
    cwd: Path,
    allow_empty_json: bool = False,
    timeout: int | None = None,
) -> tuple[dict[str, Any], str]:
    completed = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True,
        timeout=timeout,
    )
    stdout = completed.stdout.strip()
    if not stdout and allow_empty_json:
        return {}, stdout
    return extract_last_json_object(stdout), stdout


def load_training_targets(root: Path) -> list[dict[str, Any]]:
    manifest = read_json(root / "mystic_data" / "metadata" / "manifests" / "training_manifest.json")
    targets = manifest.get("targets", [])
    if not isinstance(targets, list):
        raise ValueError("training_manifest.json is missing a valid 'targets' list.")
    return sorted(targets, key=lambda item: int(item.get("priority", 9999)))


def default_hf_slugs() -> list[str]:
    return [source["slug"] for source in INGESTION_SOURCES if source.get("source_type") == "public_dataset"]


def collect_data_status(base_dir: Path) -> dict[str, Any]:
    raw_root = base_dir / "raw"
    processed_root = base_dir / "processed" / "internal_mystic_data"
    train_ready_root = base_dir / "train_ready"
    eval_root = base_dir / "eval_holdout"
    return {
        "numina_rows": count_jsonl_rows(raw_root / "numina_math_cot_100.jsonl"),
        "raven_critiques_rows": count_jsonl_rows(base_dir / "internal" / "raven_critiques.jsonl"),
        "failed_proofs_rows": count_jsonl_rows(base_dir / "internal" / "failed_proofs.jsonl"),
        "internal_processed_rows": {
            path.stem: count_jsonl_rows(path)
            for path in sorted(processed_root.glob("*.jsonl"))
        },
        "train_ready_rows": {
            path.name: count_jsonl_rows(path)
            for path in sorted(train_ready_root.glob("*.jsonl"))
        },
        "eval_rows": {
            path.name: count_jsonl_rows(path)
            for path in sorted(eval_root.glob("*.jsonl"))
        },
    }


def run_workflow(args: argparse.Namespace) -> int:
    verify_project_root(ROOT)
    base_dir = Path(args.base_dir).resolve()
    wf_dir = workflow_dir(base_dir, args.workflow_id)
    wf_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "timestamp": now_iso(),
        "workflow_id": args.workflow_id,
        "project_root": str(ROOT),
        "base_dir": str(base_dir),
        "python": sys.executable,
        "options": {
            "seed_internal": args.seed_internal,
            "max_hf_rows": args.max_hf_rows,
            "numina_limit": args.numina_limit,
            "raven_prepare_limit": args.raven_prepare_limit,
            "train_limit": args.train_limit,
            "eval_limit": args.eval_limit,
            "run_cycle_prepare": args.run_cycle_prepare,
            "training_backend": args.training_backend,
            "execute_training": args.execute_training,
            "step_timeout_seconds": args.step_timeout_seconds,
            "continue_on_error": args.continue_on_error,
        },
    }

    summary.setdefault("stdout", {})
    summary["steps"] = []

    def execute_step(
        name: str,
        command: list[str],
        *,
        allow_empty_json: bool = False,
    ) -> dict[str, Any]:
        step_record: dict[str, Any] = {"name": name, "command": command}
        try:
            payload, stdout = run_json_command(
                command,
                cwd=ROOT,
                allow_empty_json=allow_empty_json,
                timeout=args.step_timeout_seconds,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError) as exc:
            step_record["ok"] = False
            step_record["error"] = repr(exc)
            summary[name] = {"error": repr(exc)}
            summary["stdout"][name] = ""
            summary["steps"].append(step_record)
            if not args.continue_on_error:
                write_json(workflow_summary_path(base_dir, args.workflow_id), summary)
                raise
            return summary[name]

        step_record["ok"] = True
        step_record["payload"] = payload
        summary[name] = payload
        summary["stdout"][name] = stdout
        summary["steps"].append(step_record)
        return payload

    execute_step("init_internal_mystic_data", [sys.executable, "scripts/init_internal_mystic_data.py"])

    if args.seed_internal:
        execute_step(
            "seed_internal_examples",
            [sys.executable, "scripts/seed_internal_examples.py"],
            allow_empty_json=True,
        )

    execute_step("resolve_hf_datasets", [sys.executable, "scripts/resolve_hf_datasets.py"])

    hf_args = [sys.executable, "scripts/download_hf_samples.py", "--max-rows", str(args.max_hf_rows)]
    slugs = args.hf_slugs or default_hf_slugs()
    if slugs:
        hf_args.extend(["--slugs", *slugs])
    execute_step("download_hf_samples", hf_args)

    execute_step(
        "download_numina_sample",
        [sys.executable, "scripts/download_numina_sample.py", "--limit", str(args.numina_limit)],
    )

    execute_step("export_raven_lora", [sys.executable, "scripts/export_raven_lora.py"])

    prepare_raven_args = [
        sys.executable,
        "scripts/prepare_raven_training_data.py",
        "--limit",
        str(args.raven_prepare_limit),
        "--eval-ratio",
        str(args.eval_limit / max(args.train_limit + args.eval_limit, 1)),
    ]
    execute_step("prepare_raven_training_data", prepare_raven_args)

    execute_step("prepare_train_ready", [sys.executable, "scripts/prepare_train_ready.py"])

    target_results: list[dict[str, Any]] = []
    for target in load_training_targets(ROOT):
        command = [
            sys.executable,
            "scripts/run_specialist_training.py",
            "--agent",
            str(target["agent"]),
            "--backend",
            args.training_backend,
        ]
        if args.execute_training:
            command.append("--execute")
        try:
            payload, stdout = run_json_command(command, cwd=ROOT, timeout=args.step_timeout_seconds)
            target_results.append(
                {
                    "agent": target["agent"],
                    "adapter": target["adapter"],
                    "priority": target["priority"],
                    "payload": payload,
                    "stdout": stdout,
                }
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError) as exc:
            error_payload = {
                "agent": target["agent"],
                "adapter": target["adapter"],
                "priority": target["priority"],
                "error": repr(exc),
                "stdout": "",
            }
            target_results.append(error_payload)
            if not args.continue_on_error:
                summary["training_targets"] = target_results
                summary["data_status"] = collect_data_status(base_dir)
                write_json(workflow_summary_path(base_dir, args.workflow_id), summary)
                raise
    summary["training_targets"] = target_results

    if args.run_cycle_prepare:
        execute_step("run_mystic_cycle_prepare", [
            sys.executable,
            "scripts/run_mystic_cycle.py",
            "prepare",
            "--cycle-id",
            args.cycle_id,
            "--run-prepare-data",
            "--train-limit",
            str(args.train_limit),
            "--eval-limit",
            str(args.eval_limit),
            "--base-model",
            args.base_model,
            "--adapter-path",
            args.adapter_path,
            "--learning-rate",
            str(args.learning_rate),
        ])

    summary["data_status"] = collect_data_status(base_dir)
    write_json(workflow_summary_path(base_dir, args.workflow_id), summary)
    print(json.dumps(summary, indent=2))
    return 0


def run_status(args: argparse.Namespace) -> int:
    base_dir = Path(args.base_dir).resolve()
    verify_project_root(ROOT)
    workflows_root = base_dir / "workflows"
    summaries = sorted(workflows_root.glob("*/summary.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    latest = read_json(summaries[0]) if summaries else None
    payload = {
        "timestamp": now_iso(),
        "project_root": str(ROOT),
        "base_dir": str(base_dir),
        "latest_workflow_summary": latest,
        "available_workflows": [str(path.parent.name) for path in summaries[: args.limit]],
        "data_status": collect_data_status(base_dir),
        "training_targets": load_training_targets(ROOT),
    }
    print(json.dumps(payload, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the checklist-derived Mystic data and training workflow.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Collect data, prepare train-ready files, and plan training.")
    run_parser.add_argument("--workflow-id", default="manifest_workflow_v0")
    run_parser.add_argument("--base-dir", default=str(ROOT / "mystic_data"))
    run_parser.add_argument("--seed-internal", action="store_true")
    run_parser.add_argument("--max-hf-rows", type=int, default=3)
    run_parser.add_argument("--hf-slugs", nargs="*", default=[])
    run_parser.add_argument("--numina-limit", type=int, default=1100)
    run_parser.add_argument("--raven-prepare-limit", type=int, default=500)
    run_parser.add_argument("--train-limit", type=int, default=1000)
    run_parser.add_argument("--eval-limit", type=int, default=100)
    run_parser.add_argument("--run-cycle-prepare", action="store_true")
    run_parser.add_argument("--cycle-id", default="cycle_1")
    run_parser.add_argument("--base-model", default=DEFAULT_BASE_MODEL)
    run_parser.add_argument("--adapter-path", default=DEFAULT_ADAPTER_PATH)
    run_parser.add_argument("--learning-rate", type=float, default=0.00015)
    run_parser.add_argument("--training-backend", choices=["manual", "unsloth", "axolotl"], default="manual")
    run_parser.add_argument("--execute-training", action="store_true")
    run_parser.add_argument("--step-timeout-seconds", type=int, default=120)
    run_parser.add_argument("--continue-on-error", action="store_true")
    run_parser.set_defaults(func=run_workflow)

    status_parser = subparsers.add_parser("status", help="Show the latest workflow summary and local data counts.")
    status_parser.add_argument("--base-dir", default=str(ROOT / "mystic_data"))
    status_parser.add_argument("--limit", type=int, default=5)
    status_parser.set_defaults(func=run_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
