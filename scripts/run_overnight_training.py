from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.execution_history import write_execution_history_outputs
from mystic.training.continuous import continuous_progress_path


DEFAULT_SLUGS = [
    "openmathinstruct_1",
    "openmathinstruct_2",
    "openr1_mixture_of_thoughts",
    "openthoughts",
    "proofnet",
]

RAW_SAMPLE_PATHS = {
    "openmathinstruct_1": "raw/openmathinstruct_1/sample.jsonl",
    "openmathinstruct_2": "raw/openmathinstruct_2/sample.jsonl",
    "openr1_mixture_of_thoughts": "raw/openr1_mixture_of_thoughts/sample.jsonl",
    "openthoughts": "raw/openthoughts/sample.jsonl",
    "proofnet": "raw/proofnet/sample.jsonl",
    "leandojo": "raw/leandojo/sample.jsonl",
}


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run repeated overnight real-data specialist training batches.")
    parser.add_argument("--run-id", default=f"overnight_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}")
    parser.add_argument("--base-dir", default=str(ROOT / "mystic_data"))
    parser.add_argument("--iterations", type=int, default=4)
    parser.add_argument("--sleep-seconds", type=int, default=30)
    parser.add_argument("--hf-max-rows", type=int, default=200)
    parser.add_argument("--hf-slugs", nargs="*", default=DEFAULT_SLUGS)
    parser.add_argument("--numina-limit", type=int, default=3000)
    parser.add_argument("--public-max-rows-per-agent", type=int, default=300)
    parser.add_argument("--backend", choices=["manual", "unsloth", "axolotl"], default="manual")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--max-steps", type=int, default=20)
    parser.add_argument("--learning-rate", type=float, default=0.00015)
    parser.add_argument("--sequence-length", type=int, default=512)
    parser.add_argument("--step-timeout-seconds", type=int, default=1800)
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument(
        "--run-label",
        default="",
        help="Optional label propagated into append-only specialist training history.",
    )
    return parser


def run_json_command(command: list[str], *, timeout: int) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return {
        "command": command,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


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
    return {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_progress(base_dir: Path, payload: dict[str, Any]) -> None:
    path = continuous_progress_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def decode_process_stream(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value or "")


def count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def has_cached_numina_rows(base_dir: Path, requested_rows: int) -> bool:
    return count_jsonl_rows(base_dir / "raw" / "numina_math_cot_100.jsonl") >= requested_rows


def has_cached_hf_rows(base_dir: Path, slug: str) -> bool:
    relative = RAW_SAMPLE_PATHS.get(slug)
    if relative and count_jsonl_rows(base_dir / relative) > 0:
        return True
    snapshot_manifest = base_dir / "raw" / slug / "snapshot_manifest.json"
    return snapshot_manifest.exists()


def step_label(command: list[str]) -> str:
    if any("download_numina_sample.py" in part for part in command):
        return "Numina 샘플 다운로드"
    if any("download_hf_samples.py" in part for part in command):
        slug = ""
        if "--slugs" in command:
            slug_index = command.index("--slugs") + 1
            if slug_index < len(command):
                slug = str(command[slug_index])
        return f"Hugging Face 샘플 다운로드 · {slug}" if slug else "Hugging Face 샘플 다운로드"
    if any("prepare_public_train_ready.py" in part for part in command):
        return "공개 train_ready 생성"
    if any("run_all_specialists.py" in part for part in command):
        return "전문가 학습 배치 실행"
    return "학습 단계 실행"


def build_progress_payload(
    *,
    run_id: str,
    run_label: str,
    iteration: int,
    iterations_total: int,
    total_steps: int,
    completed_steps: int,
    current_step_index: int,
    current_step_label: str,
    status: str,
    started_at: str,
    effective_numina_limit: int,
    effective_hf_rows: int,
    effective_public_rows: int,
    last_error: str = "",
    current_step_started_at: str = "",
) -> dict[str, Any]:
    progress_percent = 100 if total_steps <= 0 else int(round((completed_steps / total_steps) * 100))
    return {
        "run_id": run_id,
        "run_label": run_label,
        "status": status,
        "started_at": started_at,
        "updated_at": now_iso(),
        "iteration": iteration,
        "iterations_total": iterations_total,
        "total_steps": total_steps,
        "completed_steps": completed_steps,
        "current_step_index": current_step_index,
        "current_step_label": current_step_label,
        "current_step_started_at": current_step_started_at,
        "progress_percent": progress_percent,
        "effective_numina_limit": effective_numina_limit,
        "effective_hf_rows": effective_hf_rows,
        "effective_public_max_rows_per_agent": effective_public_rows,
        "last_error": last_error,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_dir = Path(args.base_dir)
    run_dir = base_dir / "overnight_runs" / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "run_id": args.run_id,
        "run_label": args.run_label or args.run_id,
        "started_at": now_iso(),
        "options": {
            "iterations": args.iterations,
            "sleep_seconds": args.sleep_seconds,
            "hf_max_rows": args.hf_max_rows,
            "hf_slugs": args.hf_slugs,
            "numina_limit": args.numina_limit,
            "public_max_rows_per_agent": args.public_max_rows_per_agent,
            "backend": args.backend,
            "epochs": args.epochs,
            "max_steps": args.max_steps,
            "learning_rate": args.learning_rate,
            "sequence_length": args.sequence_length,
            "step_timeout_seconds": args.step_timeout_seconds,
            "continue_on_error": args.continue_on_error,
            "run_label": args.run_label or args.run_id,
        },
        "iterations": [],
    }

    for iteration in range(1, args.iterations + 1):
        started_at = now_iso()
        effective_numina_limit = args.numina_limit * iteration
        effective_hf_rows = args.hf_max_rows * iteration
        effective_public_rows = args.public_max_rows_per_agent * iteration
        iteration_payload: dict[str, Any] = {
            "iteration": iteration,
            "started_at": started_at,
            "effective_numina_limit": effective_numina_limit,
            "effective_hf_rows": effective_hf_rows,
            "effective_public_max_rows_per_agent": effective_public_rows,
            "steps": [],
            "skipped_steps": [],
        }

        commands: list[list[str]] = []
        if has_cached_numina_rows(base_dir, effective_numina_limit):
            iteration_payload["skipped_steps"].append(
                {
                    "command": "download_numina_sample.py",
                    "reason": "cached_rows_sufficient",
                    "cached_rows": count_jsonl_rows(base_dir / "raw" / "numina_math_cot_100.jsonl"),
                }
            )
        else:
            commands.append(
                [
                    sys.executable,
                    "scripts/download_numina_sample.py",
                    "--limit",
                    str(effective_numina_limit),
                ]
            )
        for slug in args.hf_slugs:
            if has_cached_hf_rows(base_dir, slug):
                iteration_payload["skipped_steps"].append(
                    {
                        "command": "download_hf_samples.py",
                        "slug": slug,
                        "reason": "cached_rows_present",
                        "cached_rows": count_jsonl_rows(base_dir / RAW_SAMPLE_PATHS[slug]),
                    }
                )
                continue
            commands.append(
                [
                    sys.executable,
                    "scripts/download_hf_samples.py",
                    "--max-rows",
                    str(effective_hf_rows),
                    "--slugs",
                    slug,
                ]
            )
        commands.extend(
            [
                [
                    sys.executable,
                    "scripts/prepare_public_train_ready.py",
                    "--max-rows-per-agent",
                    str(effective_public_rows),
                    "--overwrite",
                ],
                [
                    sys.executable,
                    "scripts/run_all_specialists.py",
                    "--backend",
                    args.backend,
                    "--skip-bootstrap",
                    "--epochs",
                    str(args.epochs),
                    "--max-steps",
                    str(args.max_steps),
                    "--learning-rate",
                    str(args.learning_rate),
                    "--sequence-length",
                    str(args.sequence_length),
                    "--run-label",
                    args.run_label or args.run_id,
                ],
            ]
        )

        total_steps = len(iteration_payload["skipped_steps"]) + len(commands)
        completed_steps = len(iteration_payload["skipped_steps"])
        write_progress(
            base_dir,
            build_progress_payload(
                run_id=args.run_id,
                run_label=args.run_label or args.run_id,
                iteration=iteration,
                iterations_total=args.iterations,
                total_steps=total_steps,
                completed_steps=completed_steps,
                current_step_index=completed_steps + 1 if completed_steps < total_steps else total_steps,
                current_step_label="대기 중" if total_steps else "실행할 단계 없음",
                status="running",
                started_at=started_at,
                effective_numina_limit=effective_numina_limit,
                effective_hf_rows=effective_hf_rows,
                effective_public_rows=effective_public_rows,
            ),
        )

        for step_index, command in enumerate(commands, start=1):
            step_started_at = now_iso()
            current_step_index = len(iteration_payload["skipped_steps"]) + step_index
            write_progress(
                base_dir,
                build_progress_payload(
                    run_id=args.run_id,
                    run_label=args.run_label or args.run_id,
                    iteration=iteration,
                    iterations_total=args.iterations,
                    total_steps=total_steps,
                    completed_steps=completed_steps,
                    current_step_index=current_step_index,
                    current_step_label=step_label(command),
                    status="running",
                    started_at=started_at,
                    effective_numina_limit=effective_numina_limit,
                    effective_hf_rows=effective_hf_rows,
                    effective_public_rows=effective_public_rows,
                    current_step_started_at=step_started_at,
                ),
            )
            stdout_log = run_dir / "logs" / f"iteration_{iteration:03d}_step_{step_index:02d}.stdout.log"
            stderr_log = run_dir / "logs" / f"iteration_{iteration:03d}_step_{step_index:02d}.stderr.log"
            try:
                result = run_json_command(command, timeout=args.step_timeout_seconds)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                stdout = decode_process_stream(getattr(exc, "stdout", "") or "")
                stderr = decode_process_stream(getattr(exc, "stderr", "") or "")
                write_text(stdout_log, stdout)
                write_text(stderr_log, stderr)
                step_payload = {
                    "command": command,
                    "ok": False,
                    "error": repr(exc),
                    "error_type": type(exc).__name__,
                    "stdout_log": str(stdout_log),
                    "stderr_log": str(stderr_log),
                    "parsed": extract_last_json_object(stdout),
                }
                iteration_payload["steps"].append(step_payload)
                write_json(run_dir / f"iteration_{iteration:03d}.json", iteration_payload)
                write_progress(
                    base_dir,
                    build_progress_payload(
                        run_id=args.run_id,
                        run_label=args.run_label or args.run_id,
                        iteration=iteration,
                        iterations_total=args.iterations,
                        total_steps=total_steps,
                        completed_steps=completed_steps,
                        current_step_index=current_step_index,
                        current_step_label=step_label(command),
                        status="error",
                        started_at=started_at,
                        effective_numina_limit=effective_numina_limit,
                        effective_hf_rows=effective_hf_rows,
                        effective_public_rows=effective_public_rows,
                        last_error=repr(exc),
                        current_step_started_at=step_started_at,
                    ),
                )
                if not args.continue_on_error:
                    summary["iterations"].append(iteration_payload)
                    summary["aborted_at"] = now_iso()
                    summary["history_outputs"] = write_execution_history_outputs(base_dir)
                    write_json(run_dir / "summary.json", summary)
                    print(json.dumps(summary, indent=2))
                    return 1
                continue

            write_text(stdout_log, result["stdout"])
            write_text(stderr_log, result["stderr"])
            step_payload = {
                "command": command,
                "ok": True,
                "stdout_log": str(stdout_log),
                "stderr_log": str(stderr_log),
                "parsed": extract_last_json_object(result["stdout"]),
            }
            iteration_payload["steps"].append(step_payload)
            write_json(run_dir / f"iteration_{iteration:03d}.json", iteration_payload)
            completed_steps += 1
            write_progress(
                base_dir,
                build_progress_payload(
                    run_id=args.run_id,
                    run_label=args.run_label or args.run_id,
                    iteration=iteration,
                    iterations_total=args.iterations,
                    total_steps=total_steps,
                    completed_steps=completed_steps,
                    current_step_index=min(completed_steps + 1, total_steps),
                    current_step_label=step_label(command),
                    status="running" if completed_steps < total_steps else "complete",
                    started_at=started_at,
                    effective_numina_limit=effective_numina_limit,
                    effective_hf_rows=effective_hf_rows,
                    effective_public_rows=effective_public_rows,
                    current_step_started_at=step_started_at,
                ),
            )

        iteration_payload["finished_at"] = now_iso()
        summary["iterations"].append(iteration_payload)
        summary["history_outputs"] = write_execution_history_outputs(base_dir)
        write_json(run_dir / "summary.json", summary)
        write_progress(
            base_dir,
            build_progress_payload(
                run_id=args.run_id,
                run_label=args.run_label or args.run_id,
                iteration=iteration,
                iterations_total=args.iterations,
                total_steps=total_steps,
                completed_steps=total_steps,
                current_step_index=total_steps,
                current_step_label="반복 완료",
                status="complete",
                started_at=started_at,
                effective_numina_limit=effective_numina_limit,
                effective_hf_rows=effective_hf_rows,
                effective_public_rows=effective_public_rows,
            ),
        )

        if iteration < args.iterations and args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

    summary["finished_at"] = now_iso()
    summary["history_outputs"] = write_execution_history_outputs(base_dir)
    write_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
