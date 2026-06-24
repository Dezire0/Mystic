from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import html
import json
from pathlib import Path
import re
from typing import Any

from mystic.jsonl_loop import ensure_data_dirs, read_jsonl
from mystic.training.continuous import continuous_state_path, read_json, specialist_history_log_path
from mystic.training.remote_cycle import remote_cycle_state_path


@dataclass(slots=True)
class ExecutionRecord:
    record_id: str
    timestamp: str
    part: str
    model_name: str
    success: bool
    duration_seconds: float | None
    source: str
    status: str
    details: dict[str, Any]


def parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def iso_or_empty(value: str | None) -> str:
    return value or ""


def infer_part(*values: str) -> str:
    haystack = " ".join(value.lower() for value in values if value).strip()
    mapping = [
        ("biomath", "biomath"),
        ("physics", "physics"),
        ("complexity", "complexity"),
        ("pattern", "pattern"),
        ("report", "report"),
        ("forge", "forge"),
        ("conjecture", "conjecture"),
        ("prime", "prime"),
        ("logic", "logic"),
        ("algebra", "algebra"),
        ("analysis", "analysis"),
        ("probability", "probability"),
        ("geo", "geo"),
        ("chem", "chem"),
        ("lean", "lean"),
        ("raven", "raven"),
        ("simulator", "simulator"),
        ("core", "core"),
        ("archive", "archive"),
        ("knowledge_graph", "knowledge_graph"),
        ("evolution", "evolution"),
        ("adapter", "raven"),
        ("qwen", "raven"),
    ]
    for needle, label in mapping:
        if needle in haystack:
            return label
    return "unknown"


def format_duration(duration_seconds: float | None) -> str:
    if duration_seconds is None:
        return "-"
    if duration_seconds < 1:
        return f"{duration_seconds:.2f}s"
    if duration_seconds < 60:
        return f"{duration_seconds:.1f}s"
    minutes = int(duration_seconds // 60)
    seconds = duration_seconds % 60
    return f"{minutes}m {seconds:.0f}s"


def kaggle_kernel_url(ref: str | None) -> str:
    value = str(ref or "").strip()
    if not value or "/" not in value:
        return ""
    return f"https://www.kaggle.com/code/{value}"


def kaggle_dataset_url(ref: str | None) -> str:
    value = str(ref or "").strip()
    if not value or "/" not in value:
        return ""
    return f"https://www.kaggle.com/datasets/{value}"


def _normalize_model_name(value: str | None) -> str:
    if not value:
        return "-"
    text = str(value)
    if "/" in text:
        return text
    path = Path(text)
    if len(path.parts) > 1 or path.suffix:
        return path.name or text
    return text


def _build_record(
    *,
    record_id: str,
    timestamp: str,
    part: str,
    model_name: str,
    success: bool,
    duration_seconds: float | None,
    source: str,
    status: str,
    details: dict[str, Any] | None = None,
) -> ExecutionRecord:
    return ExecutionRecord(
        record_id=record_id,
        timestamp=timestamp,
        part=part,
        model_name=_normalize_model_name(model_name),
        success=success,
        duration_seconds=duration_seconds,
        source=source,
        status=status,
        details=details or {},
    )


def extract_last_json_object(text: str) -> dict[str, Any]:
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    for index in range(len(lines)):
        candidate = "\n".join(lines[index:])
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def collect_training_records(base_dir: str | Path) -> list[ExecutionRecord]:
    paths = ensure_data_dirs(base_dir)
    records: list[ExecutionRecord] = []
    for row in read_jsonl(paths.training_log_file):
        metrics = row.get("metrics", {})
        duration = metrics.get("train_runtime")
        output_dir = str(row.get("output_dir", ""))
        part = infer_part(output_dir, str(row.get("base_model", "")))
        status = str(row.get("status", "UNKNOWN"))
        records.append(
            _build_record(
                record_id=f"training:{row.get('event_id', row.get('run_id', ''))}",
                timestamp=str(row.get("timestamp", "")),
                part=part,
                model_name=str(row.get("base_model", "")),
                success=status in {"TRAIN_OK", "DRY_RUN_OK"},
                duration_seconds=float(duration) if duration is not None else None,
                source="training_log",
                status=status,
                details=row,
            )
        )
    return records


def collect_eval_records(base_dir: str | Path) -> list[ExecutionRecord]:
    paths = ensure_data_dirs(base_dir)
    records: list[ExecutionRecord] = []
    for row in read_jsonl(paths.raven_eval_results_file):
        metrics = row.get("metrics", {})
        success = float(metrics.get("invalid_json_rate", 1.0)) == 0.0 and int(metrics.get("simple_failure_count", 1)) == 0
        records.append(
            _build_record(
                record_id=f"eval:{row.get('event_id', row.get('run_id', ''))}",
                timestamp=str(row.get("timestamp", "")),
                part="raven",
                model_name=str(row.get("base_model", "")),
                success=success,
                duration_seconds=None,
                source="raven_eval_results",
                status="EVAL_OK" if success else "EVAL_WARN",
                details=row,
            )
        )
    return records


def collect_compare_records(base_dir: str | Path) -> list[ExecutionRecord]:
    paths = ensure_data_dirs(base_dir)
    records: list[ExecutionRecord] = []
    for row in read_jsonl(paths.raven_comparison_results_file):
        if row.get("kind") != "summary":
            continue
        metrics = row.get("metrics", {})
        success = metrics.get("adapter_better_or_equal_rate") is not None
        total = int(metrics.get("total", 0) or 0)
        avg_latency = (
            metrics.get("adapter", {}).get("average_latency")
            if isinstance(metrics.get("adapter"), dict)
            else None
        )
        duration = float(avg_latency) * total if avg_latency is not None and total > 0 else None
        records.append(
            _build_record(
                record_id=f"compare:{row.get('event_id', row.get('run_id', ''))}",
                timestamp=str(row.get("timestamp", "")),
                part="raven",
                model_name=str(row.get("base_model", "")),
                success=success,
                duration_seconds=duration,
                source="raven_comparison_results",
                status="COMPARE_OK" if success else "COMPARE_ERROR",
                details=row,
            )
        )
    return records


def collect_loop_records(base_dir: str | Path) -> list[ExecutionRecord]:
    paths = ensure_data_dirs(base_dir)
    rows = read_jsonl(paths.run_log_file)
    if not rows:
        return []

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        run_id = str(row.get("run_id", ""))
        if not run_id:
            continue
        grouped.setdefault(run_id, []).append(row)

    records: list[ExecutionRecord] = []
    for run_id, group_rows in grouped.items():
        ordered = sorted(group_rows, key=lambda item: parse_timestamp(str(item.get("timestamp", ""))))
        first = ordered[0]
        last = ordered[-1]
        started_at = parse_timestamp(str(first.get("timestamp", "")))
        finished_at = parse_timestamp(str(last.get("timestamp", "")))
        duration = max((finished_at - started_at).total_seconds(), 0.0)
        statuses = [str(item.get("status", "")) for item in ordered]
        success = any(status in {"VALID", "INVALID", "GAP", "NEEDS_MORE_DETAIL", "COMPARE_OK", "COMPARE_BASE_BETTER"} for status in statuses)
        model_name = str(last.get("raven_model", "") or last.get("generator_model", ""))
        records.append(
            _build_record(
                record_id=f"loop:{run_id}",
                timestamp=str(first.get("timestamp", "")),
                part=infer_part(model_name, run_id),
                model_name=model_name,
                success=success,
                duration_seconds=duration if duration > 0 else None,
                source="run_log",
                status="LOOP_OK" if success else "LOOP_ERROR",
                details={
                    "run_id": run_id,
                    "statuses": statuses,
                    "processed_events": len(group_rows),
                },
            )
        )
    return records


def collect_cycle_records(base_dir: str | Path) -> list[ExecutionRecord]:
    base = Path(base_dir)
    cycle_root = base / "cycles"
    if not cycle_root.exists():
        return []

    specs = [
        ("prepare_summary.json", "cycle_prepare", "PREPARE_OK"),
        ("kaggle_submit_summary.json", "cycle_submit", "SUBMIT_OK"),
        ("kaggle_poll_summary.json", "cycle_poll", "POLL_OK"),
        ("kaggle_download_summary.json", "cycle_download", "DOWNLOAD_OK"),
        ("summary.json", "cycle_finish", "FINISH_OK"),
    ]
    records: list[ExecutionRecord] = []
    for cycle_dir in sorted(cycle_root.glob("*")):
        if not cycle_dir.is_dir():
            continue
        prepare_payload: dict[str, Any] = {}
        prepare_path = cycle_dir / "prepare_summary.json"
        if prepare_path.exists():
            prepare_payload = json.loads(prepare_path.read_text(encoding="utf-8"))
        for filename, source, success_status in specs:
            path = cycle_dir / filename
            if not path.exists():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            status = success_status
            success = True
            duration: float | None = None
            if filename == "kaggle_poll_summary.json":
                final_status = str(payload.get("final_status", "")).lower()
                success = final_status == "complete"
                status = "POLL_OK" if success else "POLL_FAIL"
                checks = payload.get("checks", [])
                if isinstance(checks, list) and len(checks) >= 2:
                    started_at = parse_timestamp(str(checks[0]["timestamp"]))
                    finished_at = parse_timestamp(str(checks[-1]["timestamp"]))
                    duration = max((finished_at - started_at).total_seconds(), 0.0)
            if filename == "summary.json":
                processed_count = int(payload.get("processed_count", 0) or 0)
                success = processed_count > 0
                status = "FINISH_OK" if success else "FINISH_FAIL"

            model_name = str(
                payload.get("base_model", "")
                or payload.get("loop_payload", {}).get("base_model", "")
                or prepare_payload.get("base_model", "")
                or "-"
            )
            adapter_hint = str(payload.get("adapter_path", "") or prepare_payload.get("adapter_path", ""))
            records.append(
                _build_record(
                    record_id=f"{source}:{cycle_dir.name}",
                    timestamp=str(payload.get("timestamp", "")),
                    part=infer_part(adapter_hint, model_name, cycle_dir.name),
                    model_name=model_name,
                    success=success,
                    duration_seconds=duration,
                    source=source,
                    status=status,
                    details=payload,
                )
            )
    return records


def collect_batch_training_records(base_dir: str | Path) -> list[ExecutionRecord]:
    base = Path(base_dir)
    specialist_history_path = specialist_history_log_path(base)
    if specialist_history_path.exists():
        records: list[ExecutionRecord] = []
        for index, row in enumerate(read_jsonl(specialist_history_path)):
            timestamp = str(row.get("timestamp", ""))
            if not timestamp:
                continue
            duration_value = row.get("duration_seconds")
            returncode_value = row.get("returncode", 1)
            returncode = 1 if returncode_value is None else int(returncode_value)
            success = bool(row.get("success", returncode == 0))
            agent = str(row.get("agent", "") or f"specialist-{index}")
            model_name = str(row.get("model_name", "") or row.get("base_model", "") or "-")
            status = str(row.get("status", "TRAIN_OK" if success else "TRAIN_ERROR"))
            records.append(
                _build_record(
                    record_id=str(row.get("event_id", f"specialist_training_history:{agent}:{index}")),
                    timestamp=timestamp,
                    part=infer_part(agent, model_name, str(row.get("division", ""))),
                    model_name=model_name,
                    success=success,
                    duration_seconds=float(duration_value) if duration_value is not None else None,
                    source="specialist_training_history",
                    status=status,
                    details=row,
                )
            )
        return records

    summary_path = base / "reports" / "specialist_training_batch_run.json"
    if not summary_path.exists():
        return []

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    records: list[ExecutionRecord] = []
    for index, row in enumerate(payload):
        stdout = str(row.get("stdout", "") or "")
        parsed = extract_last_json_object(stdout)
        nested = extract_last_json_object(str(parsed.get("stdout", "") or "")) if isinstance(parsed, dict) else {}
        local_training = {}
        if isinstance(parsed.get("local_training"), dict):
            local_training = parsed["local_training"]
        elif isinstance(nested.get("local_training"), dict):
            local_training = nested["local_training"]
        plan = local_training.get("plan", {}) if isinstance(local_training, dict) else {}
        result = local_training.get("result", {}) if isinstance(local_training, dict) else {}
        metrics = result.get("metrics", {}) if isinstance(result, dict) else {}
        top_level_plan = parsed.get("plan", {}) if isinstance(parsed, dict) else {}
        nested_top_plan = nested.get("plan", {}) if isinstance(nested, dict) else {}
        job_manifest = str(parsed.get("job_manifest", "") or "")
        manifest_path = Path(job_manifest) if job_manifest else None
        timestamp = ""
        if manifest_path and manifest_path.exists():
            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            timestamp = str(manifest_payload.get("created_at", ""))
            if timestamp and len(timestamp) == 16 and "T" in timestamp and timestamp.endswith("Z"):
                timestamp = timestamp[:4] + "-" + timestamp[4:6] + "-" + timestamp[6:8] + "T" + timestamp[9:11] + ":" + timestamp[11:13] + ":" + timestamp[13:15] + "+00:00"
        if not timestamp:
            timestamp = datetime.now(UTC).isoformat()

        agent = str(row.get("agent", "") or plan.get("agent", "") or f"batch-{index}")
        model_name = str(
            plan.get("model_name", "")
            or top_level_plan.get("smoke_model", "")
            or top_level_plan.get("base_model", "")
            or nested_top_plan.get("base_model", "")
            or plan.get("base_model", "")
            or "-"
        )
        duration_value = metrics.get("train_runtime")
        if duration_value is None and stdout:
            match = re.search(r"'train_runtime': '([0-9.]+)'", stdout)
            if match:
                duration_value = float(match.group(1))
        records.append(
            _build_record(
                record_id=f"batch_training:{agent}:{index}",
                timestamp=timestamp,
                part=infer_part(agent, model_name),
                model_name=model_name,
                success=int(row.get("returncode", 1)) == 0,
                duration_seconds=float(duration_value) if duration_value is not None else None,
                source="specialist_training_batch",
                status="TRAIN_OK" if int(row.get("returncode", 1)) == 0 else "TRAIN_ERROR",
                details=row,
            )
        )
    return records


def collect_execution_records(base_dir: str | Path) -> list[ExecutionRecord]:
    records = []
    records.extend(collect_batch_training_records(base_dir))
    records.extend(collect_training_records(base_dir))
    records.extend(collect_eval_records(base_dir))
    records.extend(collect_compare_records(base_dir))
    records.extend(collect_loop_records(base_dir))
    records.extend(collect_cycle_records(base_dir))
    return sorted(records, key=lambda item: parse_timestamp(item.timestamp), reverse=True)


def load_continuous_status(base_dir: str | Path) -> dict[str, Any]:
    path = continuous_state_path(base_dir)
    if not path.exists():
        return {}
    return read_json(path)


def load_remote_cycle_status(base_dir: str | Path) -> dict[str, Any]:
    path = remote_cycle_state_path(base_dir)
    if not path.exists():
        return {}
    return read_json(path)


def display_stream(record: ExecutionRecord) -> str:
    mapping = {
        "specialist_training_history": "Local Smoke",
        "specialist_training_batch": "Local Batch",
        "training_log": "Raven Train",
        "raven_eval_results": "Raven Eval",
        "raven_comparison_results": "Raven Compare",
        "run_log": "Research Loop",
        "cycle_prepare": "Remote Prepare",
        "cycle_submit": "Remote Submit",
        "cycle_poll": "Remote Poll",
        "cycle_download": "Remote Download",
        "cycle_finish": "Remote Finish",
    }
    return mapping.get(record.source, record.source.replace("_", " ").title())


def display_context(record: ExecutionRecord) -> str:
    details = record.details
    if "run_label" in details:
        return str(details["run_label"])
    if "run_id" in details:
        return str(details["run_id"])
    if "cycle_id" in details:
        return str(details["cycle_id"])
    if record.source.startswith("cycle_") and ":" in record.record_id:
        return record.record_id.split(":", 1)[1]
    if "kernel_ref" in details:
        return str(details["kernel_ref"])
    return record.source


def display_context_lines(record: ExecutionRecord) -> list[tuple[str, str]]:
    details = record.details
    lines: list[tuple[str, str]] = []
    context = display_context(record)
    if context and context != record.source:
        lines.append(("text", context))
    kernel_ref = str(details.get("kernel_ref", "") or "")
    dataset_ref = str(details.get("dataset_ref", "") or "")
    stdout_log = str(details.get("stdout_log", "") or "")
    stderr_log = str(details.get("stderr_log", "") or "")
    if kernel_ref:
        lines.append(("url", kaggle_kernel_url(kernel_ref)))
    if dataset_ref:
        lines.append(("url", kaggle_dataset_url(dataset_ref)))
    if stdout_log:
        lines.append(("text", Path(stdout_log).name))
    if stderr_log and stderr_log != stdout_log:
        lines.append(("text", Path(stderr_log).name))
    return lines[:4]


def status_label(status: str) -> str:
    mapping = {
        "TRAIN_OK": "학습 완료",
        "DRY_RUN_OK": "드라이런 완료",
        "TRAIN_ERROR": "학습 실패",
        "EVAL_OK": "평가 완료",
        "EVAL_WARN": "평가 경고",
        "COMPARE_OK": "비교 완료",
        "COMPARE_ERROR": "비교 실패",
        "LOOP_OK": "루프 완료",
        "LOOP_ERROR": "루프 실패",
        "PREPARE_OK": "준비 완료",
        "SUBMIT_OK": "업로드 완료",
        "POLL_OK": "원격 학습 완료",
        "POLL_FAIL": "원격 학습 실패",
        "DOWNLOAD_OK": "다운로드 완료",
        "FINISH_OK": "재투입 완료",
        "FINISH_FAIL": "재투입 실패",
    }
    return mapping.get(status, status)


def summarize_records(records: list[ExecutionRecord]) -> dict[str, Any]:
    total = len(records)
    success_count = sum(1 for record in records if record.success)
    failure_count = total - success_count
    recent = records[:20]
    recent_success_rate = 0.0
    if recent:
        recent_success_rate = (sum(1 for record in recent if record.success) / len(recent)) * 100.0
    latest_success = next((record for record in records if record.success), None)
    latest_failure = next((record for record in records if not record.success), None)
    return {
        "total": total,
        "success_count": success_count,
        "failure_count": failure_count,
        "recent_success_rate": recent_success_rate,
        "latest_success": latest_success,
        "latest_failure": latest_failure,
    }


def write_execution_history_outputs(base_dir: str | Path) -> dict[str, str | int]:
    base = Path(base_dir)
    reports_dir = base / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    output_html = reports_dir / "execution_history.html"
    output_json = reports_dir / "execution_history.json"
    records = collect_execution_records(base)
    continuous_status = load_continuous_status(base)
    remote_cycle_status = load_remote_cycle_status(base)
    stats = summarize_records(records)
    generated_at = datetime.now(UTC).isoformat()
    output_html.write_text(
        render_execution_history_html(
            records,
            generated_at=generated_at,
            continuous_status=continuous_status,
            remote_cycle_status=remote_cycle_status,
        )
        + "\n",
        encoding="utf-8",
    )
    output_json.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "continuous_status": continuous_status,
                "remote_cycle_status": remote_cycle_status,
                "stats": {
                    "total": stats["total"],
                    "success_count": stats["success_count"],
                    "failure_count": stats["failure_count"],
                    "recent_success_rate": stats["recent_success_rate"],
                },
                "record_count": len(records),
                "records": [
                    {
                        "record_id": record.record_id,
                        "timestamp": record.timestamp,
                        "part": record.part,
                        "model_name": record.model_name,
                        "success": record.success,
                        "duration_seconds": record.duration_seconds,
                        "source": record.source,
                        "status": record.status,
                    }
                    for record in records
                ],
            },
            indent=2,
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "generated_at": generated_at,
        "record_count": len(records),
        "output_html": str(output_html),
        "output_json": str(output_json),
    }


def render_execution_history_html(
    records: list[ExecutionRecord],
    *,
    generated_at: str,
    continuous_status: dict[str, Any] | None = None,
    remote_cycle_status: dict[str, Any] | None = None,
) -> str:
    status_payload = continuous_status or {}
    remote_status = remote_cycle_status or {}
    stats = summarize_records(records)
    rows: list[str] = []
    for index, record in enumerate(records, start=1):
        timestamp = html.escape(record.timestamp)
        part = html.escape(record.part)
        model_name = html.escape(record.model_name)
        success_text = "성공" if record.success else "실패"
        duration = html.escape(format_duration(record.duration_seconds))
        stream = html.escape(display_stream(record))
        context_lines = display_context_lines(record)
        context_html = "".join(
            (
                f'<div class="subtle"><a href="{html.escape(value)}" target="_blank" rel="noreferrer">{html.escape(value)}</a></div>'
                if kind == "url"
                else f'<div class="subtle">{html.escape(value)}</div>'
            )
            for kind, value in context_lines
        )
        status = html.escape(status_label(record.status))
        rows.append(
            f"<tr class=\"{'row-ok' if record.success else 'row-fail'}\">"
            f"<td>{index}</td>"
            f"<td>{timestamp}</td>"
            f"<td><div class=\"stream-chip\">{stream}</div>{context_html}</td>"
            f"<td>{part}</td>"
            f"<td>{model_name}</td>"
            f"<td><span class=\"result {'ok' if record.success else 'fail'}\">{success_text}</span></td>"
            f"<td><span class=\"status-pill\">{status}</span></td>"
            f"<td>{duration}</td>"
            "</tr>"
        )

    body_rows = "\n".join(rows) if rows else "<tr><td colspan=\"8\">기록이 없습니다.</td></tr>"
    status_value = html.escape(str(status_payload.get("status", "inactive")))
    current_cycle = html.escape(str(status_payload.get("current_cycle", "-")))
    active_slug = html.escape(str(status_payload.get("active_slug", "-")))
    next_slug = html.escape(str(status_payload.get("next_slug", "-")))
    completed_cycles = html.escape(str(status_payload.get("completed_cycles", "-")))
    last_heartbeat = html.escape(str(status_payload.get("last_heartbeat", "-")))
    last_error = html.escape(str(status_payload.get("last_error", "")))
    remote_status_value = html.escape(str(remote_status.get("status", "inactive")))
    remote_cycle_id = html.escape(str(remote_status.get("active_cycle_id", "-")))
    remote_phase = html.escape(str(remote_status.get("current_phase", "-")))
    remote_kernel_ref = html.escape(str(remote_status.get("current_kernel_ref", "-")))
    remote_dataset_ref = html.escape(str(remote_status.get("current_dataset_ref", "-")))
    remote_kernel_url = kaggle_kernel_url(remote_status.get("current_kernel_ref"))
    remote_dataset_url = kaggle_dataset_url(remote_status.get("current_dataset_ref"))
    remote_completed = html.escape(str(remote_status.get("completed_cycles", "-")))
    remote_adapter = html.escape(str(remote_status.get("active_adapter_path", "-")))
    remote_kernel_html = (
        f'<a href="{html.escape(remote_kernel_url)}" target="_blank" rel="noreferrer">{remote_kernel_ref}</a>'
        if remote_kernel_url
        else remote_kernel_ref
    )
    remote_dataset_html = (
        f'<a href="{html.escape(remote_dataset_url)}" target="_blank" rel="noreferrer">{remote_dataset_ref}</a>'
        if remote_dataset_url
        else remote_dataset_ref
    )
    latest_success = stats["latest_success"]
    latest_failure = stats["latest_failure"]
    latest_success_text = "-"
    if latest_success is not None:
        latest_success_text = (
            f"{display_stream(latest_success)} / {latest_success.part} / "
            f"{status_label(latest_success.status)} / {latest_success.timestamp}"
        )
    latest_failure_text = "-"
    if latest_failure is not None:
        latest_failure_text = (
            f"{display_stream(latest_failure)} / {latest_failure.part} / "
            f"{status_label(latest_failure.status)} / {latest_failure.timestamp}"
        )
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="5">
  <title>Mystic Execution History</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f1ea;
      --panel: #fffdf8;
      --line: #d8cfbf;
      --text: #1f1b16;
      --muted: #6f6458;
      --ok: #155724;
      --fail: #8b1e2d;
      --accent: #b85c38;
    }}
    body {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
      background:
        radial-gradient(circle at top left, rgba(184, 92, 56, 0.12), transparent 28%),
        linear-gradient(180deg, #f7f3eb 0%, var(--bg) 100%);
      color: var(--text);
    }}
    .wrap {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 34px;
      letter-spacing: 0.02em;
    }}
    .meta {{
      color: var(--muted);
      margin-bottom: 20px;
    }}
    .status-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 12px;
      margin-bottom: 20px;
    }}
    .status-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px 18px;
      box-shadow: 0 10px 30px rgba(42, 29, 18, 0.08);
    }}
    .status-card h2 {{
      margin: 0 0 8px;
      font-size: 18px;
    }}
    .status-card p {{
      margin: 6px 0;
      font-size: 14px;
    }}
    .status-card a {{
      color: var(--accent);
      text-decoration: none;
    }}
    .status-card a:hover {{
      text-decoration: underline;
    }}
    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-bottom: 20px;
    }}
    .stat-card {{
      background: rgba(255, 253, 248, 0.92);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 14px 16px;
    }}
    .stat-card .label {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .stat-card .value {{
      font-size: 28px;
      font-weight: 700;
      margin-top: 6px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      overflow: hidden;
      box-shadow: 0 10px 30px rgba(42, 29, 18, 0.08);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    thead {{
      background: linear-gradient(90deg, rgba(184, 92, 56, 0.12), rgba(184, 92, 56, 0.04));
    }}
    th, td {{
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    th {{
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
    }}
    tbody tr:hover {{
      background: rgba(184, 92, 56, 0.05);
    }}
    .row-ok {{
      background: rgba(21, 87, 36, 0.02);
    }}
    .row-fail {{
      background: rgba(139, 30, 45, 0.02);
    }}
    .ok {{
      color: var(--ok);
      font-weight: 700;
    }}
    .fail {{
      color: var(--fail);
      font-weight: 700;
    }}
    .result {{
      display: inline-block;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 13px;
      background: rgba(0, 0, 0, 0.04);
    }}
    .status-pill {{
      display: inline-block;
      padding: 4px 10px;
      border-radius: 999px;
      background: rgba(184, 92, 56, 0.08);
      font-size: 12px;
      color: var(--muted);
      letter-spacing: 0.04em;
    }}
    .subtle {{
      color: var(--muted);
      font-size: 12px;
      margin-top: 4px;
      word-break: break-word;
    }}
    .subtle a {{
      color: var(--muted);
      text-decoration: none;
    }}
    .subtle a:hover {{
      text-decoration: underline;
    }}
    .stream-chip {{
      display: inline-block;
      padding: 4px 10px;
      border-radius: 999px;
      background: rgba(31, 27, 22, 0.06);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.03em;
    }}
    .caption {{
      padding: 14px;
      color: var(--muted);
      font-size: 13px;
      border-top: 1px solid var(--line);
      background: rgba(184, 92, 56, 0.04);
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Mystic Execution History</h1>
    <div class="meta">생성 시각: {html.escape(generated_at)} · 총 {len(records)}개 실행 기록</div>
    <div class="stats-grid">
      <div class="stat-card">
        <div class="label">총 기록</div>
        <div class="value">{stats['total']}</div>
      </div>
      <div class="stat-card">
        <div class="label">성공</div>
        <div class="value">{stats['success_count']}</div>
      </div>
      <div class="stat-card">
        <div class="label">실패</div>
        <div class="value">{stats['failure_count']}</div>
      </div>
      <div class="stat-card">
        <div class="label">최근 20개 성공률</div>
        <div class="value">{stats['recent_success_rate']:.0f}%</div>
      </div>
    </div>
    <div class="status-grid">
      <div class="status-card">
        <h2>로컬 연속 학습</h2>
        <p>상태: {status_value}</p>
        <p>현재 사이클: {current_cycle}</p>
        <p>완료 사이클: {completed_cycles}</p>
        <p>현재 데이터셋: {active_slug}</p>
        <p>다음 데이터셋: {next_slug}</p>
        <p>마지막 heartbeat: {last_heartbeat}</p>
        <p>마지막 오류: {last_error or "-"}</p>
      </div>
      <div class="status-card">
        <h2>원격 Kaggle 사이클</h2>
        <p>상태: {remote_status_value}</p>
        <p>현재 사이클: {remote_cycle_id}</p>
        <p>현재 단계: {remote_phase}</p>
        <p>완료 사이클: {remote_completed}</p>
        <p>어댑터 경로: {remote_adapter}</p>
        <p>커널: {remote_kernel_html}</p>
        <p>데이터셋: {remote_dataset_html}</p>
      </div>
      <div class="status-card">
        <h2>최근 성공</h2>
        <p>{html.escape(latest_success_text)}</p>
      </div>
      <div class="status-card">
        <h2>최근 실패</h2>
        <p>{html.escape(latest_failure_text)}</p>
      </div>
    </div>
    <div class="panel">
      <table>
        <thead>
          <tr>
            <th>번호</th>
            <th>시각</th>
            <th>스트림</th>
            <th>파트</th>
            <th>모델명</th>
            <th>결과</th>
            <th>상태</th>
            <th>걸린 시간</th>
          </tr>
        </thead>
        <tbody>
          {body_rows}
        </tbody>
      </table>
      <div class="caption">이 페이지는 append-only JSONL 로그, cycle summary, 로컬 연속 학습 상태, 원격 Kaggle 사이클 상태를 합쳐서 생성됩니다.</div>
    </div>
  </div>
</body>
</html>
"""
