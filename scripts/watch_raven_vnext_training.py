from __future__ import annotations

import argparse
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_mystic_cycle import (
    cycle_dir,
    ensure_kaggle_ready,
    FAILURE_KAGGLE_GPU_QUOTA_EXCEEDED,
    is_kaggle_gpu_quota_error,
    kaggle_command_prefix,
    kaggle_download_summary_path,
    kaggle_output_dir,
    kaggle_poll_summary_path,
    kaggle_runtime_env,
    kaggle_submit_summary_path,
    load_submit_summary,
    locate_cycle_signal_file,
    now_iso,
    parse_kaggle_status_output,
    probe_kernel_output_signal,
    read_json,
    run_download,
    run_raw_command,
    write_json,
)
from scripts.run_raven_vnext_eval import vnext_report_paths


STATUS_TRAINING_RUNNING = "TRAINING_RUNNING"
STATUS_TRAINING_SUCCEEDED = "TRAINING_SUCCEEDED"
STATUS_TRAINING_FAILED = "TRAINING_FAILED"
STATUS_TRAINING_TIMEOUT = "TRAINING_TIMEOUT"
STATUS_DOWNLOAD_RUNNING = "DOWNLOAD_RUNNING"
STATUS_DOWNLOAD_COMPLETED = "DOWNLOAD_COMPLETED"
STATUS_ADAPTER_FOUND_NOT_EVALUATED = "ADAPTER_FOUND_NOT_EVALUATED"
STATUS_ADAPTER_INVALID = "ADAPTER_INVALID"
STATUS_EVAL_RUNNING = "EVAL_RUNNING"
STATUS_EVAL_COMPLETED = "EVAL_COMPLETED"
STATUS_EVAL_COMPLETED_WITH_LIMITATIONS = "EVAL_COMPLETED_WITH_LIMITATIONS"
STATUS_BLOCKED = "BLOCKED_NEEDS_USER_ACTION"
STATUS_UNKNOWN = "UNKNOWN"

REQUIRED_TAR_FILES = ["adapter_config.json", "adapter_model.safetensors"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Watch the submitted Raven vNext Kaggle cycle and finish the local handoff.")
    parser.add_argument("--root-path", default=str(ROOT), help="Mystic repository root.")
    parser.add_argument("--cycle-id", default="raven_vnext_adversarial")
    parser.add_argument("--expected-tar-name", default="raven_lora_vnext_adversarial.tar.gz")
    parser.add_argument("--poll-interval-seconds", type=int, default=60)
    parser.add_argument("--max-wait-minutes", type=int, default=180)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument("--eval-only", action="store_true")
    parser.add_argument("--adapter-tar", default="")
    parser.add_argument("--force-eval", action="store_true")
    parser.add_argument("--kaggle-username", default="")
    parser.add_argument("--no-download", action="store_true")
    parser.add_argument("--no-eval", action="store_true")
    return parser


def current_status_path(root_path: Path) -> Path:
    return root_path / "mystic_data" / "training" / "raven" / "current_automation_status.json"


def downloads_dir() -> Path:
    return Path.home() / "Downloads"


def normalize_status_payload(payload: dict[str, Any]) -> dict[str, Any]:
    defaults = {
        "status": STATUS_UNKNOWN,
        "checked_at": now_iso(),
        "cycle_id": "",
        "kaggle_dataset": "",
        "kaggle_kernel": "",
        "package_path": "",
        "submit_summary_path": "",
        "poll_summary_path": "",
        "download_summary_path": "",
        "adapter_candidates": [],
        "selected_adapter_path": "",
        "adapter_valid": None,
        "adapter_missing_files": [],
        "eval_report_path": "",
        "failure_category": None,
        "training_started": None,
        "next_action": "",
        "warnings": [],
        "last_error": None,
    }
    defaults.update(payload)
    return defaults


def write_current_status(root_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_status_payload(payload)
    normalized["checked_at"] = now_iso()
    write_json(current_status_path(root_path), normalized)
    return normalized


def find_adapter_candidates(*, root_path: Path, base_dir: Path, cycle_id: str, expected_tar_name: str) -> list[str]:
    cycle_root = cycle_dir(base_dir, cycle_id)
    cycle_output = kaggle_output_dir(base_dir, cycle_id)
    search_roots = [
        cycle_output,
        cycle_root,
        downloads_dir(),
        root_path,
        root_path / "mystic_data",
    ]

    cycle_matches: list[Path] = []
    other_matches: list[Path] = []
    for search_root in search_roots:
        if not search_root.exists():
            continue
        for path in search_root.rglob(expected_tar_name):
            resolved = path.resolve()
            if cycle_output in resolved.parents or resolved == cycle_output / expected_tar_name:
                cycle_matches.append(resolved)
            else:
                other_matches.append(resolved)

    unique_cycle = sorted({path for path in cycle_matches}, key=lambda item: item.stat().st_mtime, reverse=True)
    unique_other = sorted({path for path in other_matches}, key=lambda item: item.stat().st_mtime, reverse=True)
    return [str(path) for path in [*unique_cycle, *unique_other]]


def validate_adapter_tar_contents(tar_path: Path) -> dict[str, Any]:
    try:
        with tarfile.open(tar_path, "r:gz") as archive:
            names = [member.name for member in archive.getmembers() if member.isfile()]
    except (tarfile.TarError, OSError) as exc:
        return {
            "valid": False,
            "missing_files": list(REQUIRED_TAR_FILES),
            "error": f"Could not read tar archive: {exc}",
            "members": [],
        }

    basenames = {Path(name).name for name in names}
    missing = [filename for filename in REQUIRED_TAR_FILES if filename not in basenames]
    return {
        "valid": not missing,
        "missing_files": missing,
        "error": None,
        "members": names,
    }


def classify_failure_category(error_text: str, failure_output: dict[str, Any] | None = None) -> str | None:
    fragments = [error_text]
    if failure_output:
        try:
            fragments.append(str(failure_output.get("signal_file", "")))
            signal_payload = failure_output.get("signal_payload", {})
            if isinstance(signal_payload, dict):
                fragments.append(str(signal_payload.get("error", "")))
                fragments.append(str(signal_payload.get("traceback", "")))
            else:
                fragments.append(str(signal_payload))
        except Exception:
            fragments.append(repr(failure_output))
    lowered = "\n".join(fragment for fragment in fragments if fragment).lower()
    if is_kaggle_gpu_quota_error(lowered):
        return FAILURE_KAGGLE_GPU_QUOTA_EXCEEDED
    if "package tarball not found" in lowered or "package not found" in lowered:
        return "PACKAGE_NOT_FOUND"
    if ("train_mystic_raven.py" in lowered and "keyerror" in lowered) or (
        "keyerror" in lowered and "searched_roots" in lowered
    ):
        return "KERNEL_SCRIPT_ERROR"
    if any(token in lowered for token in ["traceback", "runtimeerror", "valueerror", "typeerror", "keyerror", "cycle_error"]):
        return "TRAINING_RUNTIME_ERROR"
    return None


def classify_submit_failure(submit_summary: dict[str, Any]) -> str | None:
    declared = str(submit_summary.get("failure_category", "")).strip()
    if declared:
        return declared
    text_fragments = [
        str(submit_summary.get("kernel_stdout", "")),
        str(submit_summary.get("kernel_stderr", "")),
        str(submit_summary.get("kaggle_error", "")),
    ]
    joined = "\n".join(fragment for fragment in text_fragments if fragment)
    if is_kaggle_gpu_quota_error(joined):
        return FAILURE_KAGGLE_GPU_QUOTA_EXCEEDED
    return None


def poll_kaggle_once(
    *,
    root_path: Path,
    base_dir: Path,
    cycle_id: str,
    kernel_ref: str,
    checks: list[dict[str, Any]],
) -> dict[str, Any]:
    ensure_kaggle_ready()
    kaggle_cmd = kaggle_command_prefix()
    with kaggle_runtime_env() as kaggle_env:
        try:
            result = run_raw_command([*kaggle_cmd, "kernels", "status", kernel_ref], cwd=root_path, env=kaggle_env)
            stdout = result.stdout.strip() or result.stderr.strip()
            status = parse_kaggle_status_output(stdout)
        except subprocess.CalledProcessError as exc:
            stdout = (exc.stdout or "").strip() or (exc.stderr or "").strip()
            lowered = stdout.lower()
            if "permission 'kernels.get'" in lowered or "cannot access kernel" in lowered:
                status = "running"
            else:
                raise RuntimeError(f"Kaggle kernel status failed: {stdout}") from exc

        snapshot = {"timestamp": now_iso(), "status": status, "raw": stdout}
        checks.append(snapshot)

        signal_probe = probe_kernel_output_signal(
            kaggle_cmd=kaggle_cmd,
            kernel_ref=kernel_ref,
            output_dir=kaggle_output_dir(base_dir, cycle_id) / "probe",
            env=kaggle_env,
        )
        if signal_probe is not None:
            signal_payload = signal_probe.get("signal_payload", {}) if isinstance(signal_probe, dict) else {}
            signal_status = str(signal_payload.get("status", "")).lower()
            if signal_status == "cycle_done":
                payload = {
                    "timestamp": now_iso(),
                    "command": "poll",
                    "cycle_id": cycle_id,
                    "kernel_ref": kernel_ref,
                    "final_status": "complete",
                    "checks": checks,
                    "signal_probe": signal_probe,
                }
                write_json(kaggle_poll_summary_path(base_dir, cycle_id), payload)
                return {"kaggle_status": "succeeded", "poll_summary": payload, "last_error": None}
            if signal_status == "cycle_error":
                payload = {
                    "timestamp": now_iso(),
                    "command": "poll",
                    "cycle_id": cycle_id,
                    "kernel_ref": kernel_ref,
                    "final_status": "failed",
                    "checks": checks,
                    "failure_output": signal_probe,
                }
                write_json(kaggle_poll_summary_path(base_dir, cycle_id), payload)
                return {"kaggle_status": "failed", "poll_summary": payload, "last_error": repr(signal_payload.get("error", signal_payload))}

    final_status = "running" if status == "running" else "unknown"
    payload = {
        "timestamp": now_iso(),
        "command": "poll",
        "cycle_id": cycle_id,
        "kernel_ref": kernel_ref,
        "final_status": final_status,
        "checks": checks,
    }
    if status == "failed":
        payload["final_status"] = "failed"
        write_json(kaggle_poll_summary_path(base_dir, cycle_id), payload)
        return {"kaggle_status": "failed", "poll_summary": payload, "last_error": stdout}
    if status == "complete":
        payload["final_status"] = "complete"
        write_json(kaggle_poll_summary_path(base_dir, cycle_id), payload)
        return {"kaggle_status": "succeeded", "poll_summary": payload, "last_error": None}
    write_json(kaggle_poll_summary_path(base_dir, cycle_id), payload)
    return {"kaggle_status": "running" if status == "running" else "unknown", "poll_summary": payload, "last_error": None}


def default_download_runner(
    *,
    root_path: Path,
    base_dir: Path,
    cycle_id: str,
    kernel_ref: str,
    expected_tar_name: str,
) -> dict[str, Any]:
    args = argparse.Namespace(
        cycle_id=cycle_id,
        base_dir=str(base_dir),
        kernel_ref=kernel_ref,
        output_tar_name=expected_tar_name,
    )
    run_download(args)
    return read_json(kaggle_download_summary_path(base_dir, cycle_id))


def default_eval_runner(*, root_path: Path, adapter_tar: Path) -> dict[str, Any]:
    command = [
        sys.executable,
        str(root_path / "scripts" / "run_raven_vnext_eval.py"),
        "--root-path",
        str(root_path),
        "--adapter-tar",
        str(adapter_tar),
    ]
    completed = subprocess.run(command, cwd=root_path, text=True, capture_output=True, check=True)
    report_path = vnext_report_paths(root_path)["json"]
    report = read_json(report_path) if report_path.exists() else {}
    return {
        "command": command,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "report": report,
    }


def classify_vnext_decision(report: dict[str, Any]) -> str:
    if not report:
        return "unknown"
    if bool(report.get("after_metrics_unavailable", True)):
        return "smoke-only"
    comparison = report.get("quality_comparison", {})

    def before_after(field: str) -> tuple[Any, Any]:
        payload = comparison.get(field, {}) if isinstance(comparison, dict) else {}
        return payload.get("before"), payload.get("after")

    degrading_positive_fields = [
        "bad_candidate_refutation_rate",
        "first_fatal_error_coverage",
        "deterministic_override_alignment",
        "missing_candidate_detection_rate",
    ]
    for field in degrading_positive_fields:
        before, after = before_after(field)
        if isinstance(before, (int, float)) and isinstance(after, (int, float)) and after < before:
            return "reject"

    before_overaccept, after_overaccept = before_after("valid_overaccept_rate")
    if isinstance(before_overaccept, (int, float)) and isinstance(after_overaccept, (int, float)) and after_overaccept > before_overaccept:
        return "reject"

    minimum_fields = degrading_positive_fields + ["valid_overaccept_rate"]
    if all(before_after(field)[1] is not None for field in minimum_fields):
        return "accept"
    return "smoke-only"


def eval_report_status(report: dict[str, Any]) -> str:
    if bool(report.get("after_metrics_unavailable", True)):
        return STATUS_EVAL_COMPLETED_WITH_LIMITATIONS
    return STATUS_EVAL_COMPLETED


def build_final_result(
    *,
    status_payload: dict[str, Any],
    kaggle_status: str,
    adapter_found: bool,
    adapter_valid: bool | None,
    report: dict[str, Any] | None,
) -> dict[str, Any]:
    report = report or {}
    comparison = report.get("quality_comparison", {}) if isinstance(report, dict) else {}

    def after_metric(field: str) -> Any:
        payload = comparison.get(field, {}) if isinstance(comparison, dict) else {}
        return payload.get("after")

    return {
        "status_payload": status_payload,
        "kaggle_status": kaggle_status,
        "adapter_found": adapter_found,
        "adapter_valid": adapter_valid,
        "report_path": status_payload.get("eval_report_path", ""),
        "after_metrics_unavailable": report.get("after_metrics_unavailable") if report else None,
        "bad_candidate_refutation_rate": after_metric("bad_candidate_refutation_rate"),
        "first_fatal_error_coverage": after_metric("first_fatal_error_coverage"),
        "valid_overaccept_rate": after_metric("valid_overaccept_rate"),
        "deterministic_override_alignment": after_metric("deterministic_override_alignment"),
        "vnext_decision": classify_vnext_decision(report),
    }


def render_summary(result: dict[str, Any]) -> str:
    payload = result["status_payload"]
    lines = [
        "1. Current status:",
        "",
        str(payload.get("status", STATUS_UNKNOWN)),
        "",
        "2. Kaggle status:",
        f"    {result.get('kaggle_status', 'unknown')}",
        "3. Adapter:",
        f"* found: {'yes' if result.get('adapter_found') else 'no'}",
        f"* path: {payload.get('selected_adapter_path', '')}",
        f"* valid: {('yes' if result.get('adapter_valid') is True else 'no' if result.get('adapter_valid') is False else 'unknown')}",
        "",
        "4. Eval:",
        f"* ran: {'yes' if str(payload.get('status', '')).startswith('EVAL_COMPLETED') else 'no'}",
        f"* report path: {result.get('report_path', '')}",
        f"* after_metrics_unavailable: {result.get('after_metrics_unavailable')}",
        f"* bad_candidate_refutation_rate: {result.get('bad_candidate_refutation_rate')}",
        f"* first_fatal_error_coverage: {result.get('first_fatal_error_coverage')}",
        f"* valid_overaccept_rate: {result.get('valid_overaccept_rate')}",
        f"* deterministic_override_alignment: {result.get('deterministic_override_alignment')}",
        f"* vnext decision: {result.get('vnext_decision')}",
        "",
        "5. Next action:",
        str(payload.get("next_action", "")),
    ]
    return "\n".join(lines)


def watch_raven_vnext_training(
    *,
    root_path: str | Path,
    cycle_id: str,
    expected_tar_name: str,
    poll_interval_seconds: int = 60,
    max_wait_minutes: int = 180,
    once: bool = False,
    download_only: bool = False,
    eval_only: bool = False,
    adapter_tar: str = "",
    force_eval: bool = False,
    kaggle_username: str = "",
    no_download: bool = False,
    no_eval: bool = False,
    poller: Callable[..., dict[str, Any]] = poll_kaggle_once,
    download_runner: Callable[..., dict[str, Any]] = default_download_runner,
    eval_runner: Callable[..., dict[str, Any]] = default_eval_runner,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    root = Path(root_path).resolve()
    base_dir = root / "mystic_data"
    submit_path = kaggle_submit_summary_path(base_dir, cycle_id)
    poll_path = kaggle_poll_summary_path(base_dir, cycle_id)
    download_path = kaggle_download_summary_path(base_dir, cycle_id)
    eval_report_path = vnext_report_paths(root)["json"]
    base_payload = {
        "cycle_id": cycle_id,
        "submit_summary_path": str(submit_path),
        "poll_summary_path": str(poll_path),
        "download_summary_path": str(download_path),
        "eval_report_path": str(eval_report_path),
    }

    if not submit_path.exists():
        payload = write_current_status(
            root,
            {
                **base_payload,
                "status": STATUS_BLOCKED,
                "next_action": f"Submit summary is missing. Confirm that {submit_path} exists for the already-submitted cycle.",
                "warnings": [],
                "last_error": f"Missing submit summary: {submit_path}",
            },
        )
        return build_final_result(
            status_payload=payload,
            kaggle_status="unknown",
            adapter_found=False,
            adapter_valid=None,
            report=read_json(eval_report_path) if eval_report_path.exists() else {},
        )

    submit_summary = load_submit_summary(base_dir, cycle_id)
    kernel_ref = str(submit_summary.get("kernel_ref", "")).strip()
    dataset_ref = str(submit_summary.get("dataset_ref", "")).strip()
    package_path = str(submit_summary.get("package_path", "")).strip()
    resolved_kaggle_username = kaggle_username or str(submit_summary.get("kaggle_username", "")).strip()
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []

    skip_download = no_download or eval_only
    skip_eval = no_eval or download_only

    common_payload = {
        **base_payload,
        "kaggle_dataset": dataset_ref,
        "kaggle_kernel": kernel_ref,
        "package_path": package_path,
        "warnings": warnings,
    }

    submit_failure_category = classify_submit_failure(submit_summary)
    training_started = submit_summary.get("training_started")
    if submit_failure_category == FAILURE_KAGGLE_GPU_QUOTA_EXCEEDED and training_started is not True:
        warnings.extend(
            [
                "Latest submit did not start a new Kaggle run because GPU quota was exhausted.",
                "Existing poll summary may refer to an older failed run.",
            ]
        )
        payload = write_current_status(
            root,
            {
                **common_payload,
                "status": STATUS_BLOCKED,
                "failure_category": FAILURE_KAGGLE_GPU_QUOTA_EXCEEDED,
                "training_started": False,
                "adapter_candidates": [],
                "selected_adapter_path": "",
                "adapter_valid": None,
                "adapter_missing_files": [],
                "next_action": "Wait for Kaggle GPU quota reset or use an environment with available GPU quota, then intentionally rerun submit with the same prepared package.",
                "last_error": submit_summary.get("kaggle_error")
                or submit_summary.get("kernel_stdout")
                or submit_summary.get("kernel_stderr")
                or None,
            },
        )
        return build_final_result(
            status_payload=payload,
            kaggle_status="not started due to quota",
            adapter_found=False,
            adapter_valid=None,
            report=read_json(eval_report_path) if eval_report_path.exists() else {},
        )

    try:
        kaggle_status = "unknown"
        poll_summary: dict[str, Any] = {}
        if not eval_only:
            started_at = time.monotonic()
            while True:
                poll_result = poller(
                    root_path=root,
                    base_dir=base_dir,
                    cycle_id=cycle_id,
                    kernel_ref=kernel_ref,
                    checks=checks,
                )
                kaggle_status = str(poll_result.get("kaggle_status", "unknown"))
                poll_summary = poll_result.get("poll_summary", {})
                if kaggle_status == "failed":
                    failure_output = poll_summary.get("failure_output", {}) if isinstance(poll_summary, dict) else {}
                    failure_category = classify_failure_category(
                        str(poll_result.get("last_error", "")),
                        failure_output if isinstance(failure_output, dict) else None,
                    )
                    next_action = "Inspect kaggle_poll_summary.json and Kaggle kernel logs before retrying anything."
                    if failure_category == "PACKAGE_NOT_FOUND":
                        next_action = "Fix Kaggle package discovery and intentionally resubmit the cycle."
                    elif failure_category == "KERNEL_SCRIPT_ERROR":
                        next_action = "Fix generated Kaggle kernel script formatting bug and intentionally resubmit the cycle."
                    elif failure_category == "TRAINING_RUNTIME_ERROR":
                        next_action = "Inspect kaggle_poll_summary.json and Kaggle kernel traceback, fix the runtime failure, and intentionally resubmit the cycle."
                    payload = write_current_status(
                        root,
                        {
                            **common_payload,
                            "status": STATUS_TRAINING_FAILED,
                            "failure_category": failure_category,
                            "next_action": next_action,
                            "last_error": poll_result.get("last_error"),
                        },
                    )
                    return build_final_result(
                        status_payload=payload,
                        kaggle_status=kaggle_status,
                        adapter_found=False,
                        adapter_valid=None,
                        report=read_json(eval_report_path) if eval_report_path.exists() else {},
                    )
                if kaggle_status == "succeeded":
                    break
                if once:
                    payload = write_current_status(
                        root,
                        {
                            **common_payload,
                            "status": STATUS_TRAINING_RUNNING,
                            "next_action": "Training still running. Re-run this watcher later.",
                            "last_error": None,
                        },
                    )
                    return build_final_result(
                        status_payload=payload,
                        kaggle_status=kaggle_status,
                        adapter_found=False,
                        adapter_valid=None,
                        report=read_json(eval_report_path) if eval_report_path.exists() else {},
                    )
                elapsed_minutes = (time.monotonic() - started_at) / 60.0
                if elapsed_minutes >= max_wait_minutes:
                    payload = write_current_status(
                        root,
                        {
                            **common_payload,
                            "status": STATUS_TRAINING_TIMEOUT,
                            "next_action": "Training did not finish before max wait. Re-run the watcher later or inspect Kaggle manually.",
                            "last_error": f"Timed out after {max_wait_minutes} minutes; last Kaggle status={kaggle_status}",
                        },
                    )
                    return build_final_result(
                        status_payload=payload,
                        kaggle_status=kaggle_status,
                        adapter_found=False,
                        adapter_valid=None,
                        report=read_json(eval_report_path) if eval_report_path.exists() else {},
                    )
                sleeper(poll_interval_seconds)
        else:
            kaggle_status = "unknown"

        selected_adapter = Path(adapter_tar).expanduser().resolve() if adapter_tar else None
        adapter_candidates: list[str] = []
        download_summary: dict[str, Any] = {}

        if not selected_adapter and not skip_download and not eval_only:
            write_current_status(
                root,
                {
                    **common_payload,
                    "status": STATUS_DOWNLOAD_RUNNING,
                    "next_action": "Downloading Kaggle output for adapter validation.",
                    "last_error": None,
                },
            )
            download_summary = download_runner(
                root_path=root,
                base_dir=base_dir,
                cycle_id=cycle_id,
                kernel_ref=kernel_ref,
                expected_tar_name=expected_tar_name,
            )
            if str(download_summary.get("adapter_tar", "")).strip():
                selected_adapter = Path(str(download_summary["adapter_tar"])).expanduser().resolve()

        adapter_candidates = find_adapter_candidates(
            root_path=root,
            base_dir=base_dir,
            cycle_id=cycle_id,
            expected_tar_name=expected_tar_name,
        )
        if not selected_adapter and adapter_candidates:
            selected_adapter = Path(adapter_candidates[0]).expanduser().resolve()

        if not selected_adapter or not selected_adapter.exists():
            status = STATUS_TRAINING_SUCCEEDED if kaggle_status == "succeeded" else STATUS_BLOCKED
            payload = write_current_status(
                root,
                {
                    **common_payload,
                    "status": status if skip_download else STATUS_BLOCKED,
                    "adapter_candidates": adapter_candidates,
                    "selected_adapter_path": "",
                    "adapter_valid": None,
                    "adapter_missing_files": [],
                    "next_action": f"Training succeeded but {expected_tar_name} was not found. Check Kaggle output and download it under {downloads_dir()}.",
                    "last_error": None,
                },
            )
            return build_final_result(
                status_payload=payload,
                kaggle_status=kaggle_status,
                adapter_found=False,
                adapter_valid=None,
                report=read_json(eval_report_path) if eval_report_path.exists() else {},
            )

        write_current_status(
            root,
            {
                **common_payload,
                "status": STATUS_DOWNLOAD_COMPLETED,
                "adapter_candidates": adapter_candidates,
                "selected_adapter_path": str(selected_adapter),
                "adapter_valid": None,
                "adapter_missing_files": [],
                "next_action": "Validating adapter tar contents.",
                "last_error": None,
            },
        )
        validation = validate_adapter_tar_contents(selected_adapter)
        if not validation["valid"]:
            if validation.get("error"):
                warnings.append(str(validation["error"]))
            payload = write_current_status(
                root,
                {
                    **common_payload,
                    "status": STATUS_ADAPTER_INVALID,
                    "adapter_candidates": adapter_candidates,
                    "selected_adapter_path": str(selected_adapter),
                    "adapter_valid": False,
                    "adapter_missing_files": list(validation["missing_files"]),
                    "next_action": "Adapter invalid. Inspect or re-download the tarball before running eval.",
                    "last_error": validation.get("error"),
                },
            )
            return build_final_result(
                status_payload=payload,
                kaggle_status=kaggle_status,
                adapter_found=True,
                adapter_valid=False,
                report=read_json(eval_report_path) if eval_report_path.exists() else {},
            )

        if skip_eval:
            payload = write_current_status(
                root,
                {
                    **common_payload,
                    "status": STATUS_ADAPTER_FOUND_NOT_EVALUATED,
                    "adapter_candidates": adapter_candidates,
                    "selected_adapter_path": str(selected_adapter),
                    "adapter_valid": True,
                    "adapter_missing_files": [],
                    "next_action": f"Adapter valid. Run eval when ready: python scripts/run_raven_vnext_eval.py --root-path {root} --adapter-tar {selected_adapter}",
                    "last_error": None,
                },
            )
            return build_final_result(
                status_payload=payload,
                kaggle_status=kaggle_status,
                adapter_found=True,
                adapter_valid=True,
                report=read_json(eval_report_path) if eval_report_path.exists() else {},
            )

        if eval_report_path.exists() and eval_report_path.stat().st_mtime >= selected_adapter.stat().st_mtime and not force_eval:
            report = read_json(eval_report_path)
            payload = write_current_status(
                root,
                {
                    **common_payload,
                    "status": eval_report_status(report),
                    "adapter_candidates": adapter_candidates,
                    "selected_adapter_path": str(selected_adapter),
                    "adapter_valid": True,
                    "adapter_missing_files": [],
                    "next_action": "Eval report is newer than the adapter tar. Review vnext_eval_report.md unless you need --force-eval.",
                    "last_error": None,
                },
            )
            return build_final_result(
                status_payload=payload,
                kaggle_status=kaggle_status,
                adapter_found=True,
                adapter_valid=True,
                report=report,
            )

        write_current_status(
            root,
            {
                **common_payload,
                "status": STATUS_EVAL_RUNNING,
                "adapter_candidates": adapter_candidates,
                "selected_adapter_path": str(selected_adapter),
                "adapter_valid": True,
                "adapter_missing_files": [],
                "next_action": "Running Raven vNext eval.",
                "last_error": None,
            },
        )
        eval_result = eval_runner(root_path=root, adapter_tar=selected_adapter)
        report = eval_result.get("report", {})
        if not report and eval_report_path.exists():
            report = read_json(eval_report_path)
        final_status = eval_report_status(report)
        next_action = "Review mystic_data/training/raven/vnext_eval_report.md."
        if final_status == STATUS_EVAL_COMPLETED_WITH_LIMITATIONS:
            warnings.append("Eval completed but after metrics remain unavailable.")
            next_action = "Review vnext_eval_report.md; Raven vNext should remain smoke-only until after metrics are available."
        payload = write_current_status(
            root,
            {
                **common_payload,
                "status": final_status,
                "adapter_candidates": adapter_candidates,
                "selected_adapter_path": str(selected_adapter),
                "adapter_valid": True,
                "adapter_missing_files": [],
                "next_action": next_action,
                "last_error": None,
            },
        )
        return build_final_result(
            status_payload=payload,
            kaggle_status=kaggle_status,
            adapter_found=True,
            adapter_valid=True,
            report=report,
        )
    except Exception as exc:
        payload = write_current_status(
            root,
            {
                **common_payload,
                "status": STATUS_BLOCKED,
                "next_action": "Inspect current_automation_status.json and the cycle summaries before retrying.",
                "last_error": repr(exc),
            },
        )
        return build_final_result(
            status_payload=payload,
            kaggle_status="unknown",
            adapter_found=False,
            adapter_valid=None,
            report=read_json(eval_report_path) if eval_report_path.exists() else {},
        )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = watch_raven_vnext_training(
        root_path=args.root_path,
        cycle_id=args.cycle_id,
        expected_tar_name=args.expected_tar_name,
        poll_interval_seconds=args.poll_interval_seconds,
        max_wait_minutes=args.max_wait_minutes,
        once=args.once,
        download_only=args.download_only,
        eval_only=args.eval_only,
        adapter_tar=args.adapter_tar,
        force_eval=args.force_eval,
        kaggle_username=args.kaggle_username,
        no_download=args.no_download,
        no_eval=args.no_eval,
    )
    print(render_summary(result))
    status = str(result["status_payload"].get("status", STATUS_UNKNOWN))
    if status in {STATUS_TRAINING_FAILED, STATUS_TRAINING_TIMEOUT, STATUS_ADAPTER_INVALID, STATUS_BLOCKED, STATUS_UNKNOWN}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
