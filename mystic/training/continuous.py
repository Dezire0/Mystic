"""Helpers for persistent continuous training state and status outputs."""

from __future__ import annotations

from datetime import UTC, datetime
import html
import json
from pathlib import Path
from typing import Any

from mystic.training.blueprints import INGESTION_SOURCES


LAUNCHD_LABEL = "com.mystic.continuous-training"


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def continuous_state_path(base_dir: str | Path) -> Path:
    return Path(base_dir) / "state" / "continuous_training_state.json"


def continuous_cycle_log_path(base_dir: str | Path) -> Path:
    return Path(base_dir) / "logs" / "continuous_training_cycles.jsonl"


def continuous_cycle_details_dir(base_dir: str | Path) -> Path:
    return Path(base_dir) / "logs" / "continuous_cycle_details"


def continuous_status_json_path(base_dir: str | Path) -> Path:
    return Path(base_dir) / "reports" / "continuous_training_status.json"


def continuous_status_html_path(base_dir: str | Path) -> Path:
    return Path(base_dir) / "reports" / "continuous_training_status.html"


def continuous_progress_path(base_dir: str | Path) -> Path:
    return Path(base_dir) / "state" / "continuous_training_progress.json"


def specialist_history_log_path(base_dir: str | Path) -> Path:
    return Path(base_dir) / "logs" / "specialist_training_history.jsonl"


def default_rotation_slugs() -> list[str]:
    slugs: list[str] = []
    for source in INGESTION_SOURCES:
        if source.get("source_type") != "public_dataset":
            continue
        slug = str(source["slug"])
        if slug == "numinamath_cot":
            continue
        if source.get("preferred_repo_id"):
            slugs.append(slug)
    preferred_order = [
        "openmathinstruct_2",
        "openr1_mixture_of_thoughts",
        "openthoughts",
        "openmathinstruct_1",
    ]
    ordered = [slug for slug in preferred_order if slug in slugs]
    remaining = [slug for slug in slugs if slug not in ordered]
    return ordered + remaining


def normalize_rotation_slugs(base_dir: str | Path, requested_slugs: list[str]) -> list[str]:
    root = Path(base_dir) / "raw"
    normalized: list[str] = []
    deferred: list[str] = []
    seen: set[str] = set()
    for slug in requested_slugs:
        if slug in seen:
            continue
        seen.add(slug)
        sample_path = root / slug / "sample.jsonl"
        snapshot_manifest = root / slug / "snapshot_manifest.json"
        if sample_path.exists():
            normalized.append(slug)
            continue
        if snapshot_manifest.exists():
            deferred.append(slug)
            continue
        normalized.append(slug)
    return normalized + deferred


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return read_json(path)


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def load_recent_cycle_rows(base_dir: str | Path, limit: int = 10) -> list[dict[str, Any]]:
    path = continuous_cycle_log_path(base_dir)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows[-limit:]


def write_continuous_status_outputs(base_dir: str | Path, state: dict[str, Any]) -> dict[str, str]:
    base = Path(base_dir)
    payload = {
        "generated_at": now_iso(),
        "state": state,
        "recent_cycles": load_recent_cycle_rows(base, limit=10),
    }
    json_path = continuous_status_json_path(base)
    html_path = continuous_status_html_path(base)
    write_json(json_path, payload)
    html_path.write_text(render_continuous_status_html(payload) + "\n", encoding="utf-8")
    return {
        "output_json": str(json_path),
        "output_html": str(html_path),
    }


def render_continuous_status_html(payload: dict[str, Any]) -> str:
    state = payload.get("state", {})
    recent_cycles = payload.get("recent_cycles", [])
    rows = []
    for row in reversed(recent_cycles):
        status = html.escape(str(row.get("status", "-")))
        cycle_number = html.escape(str(row.get("cycle_number", "-")))
        slug = html.escape(str(row.get("active_slug", "-")))
        success_text = "성공" if bool(row.get("success")) else "실패"
        rows.append(
            "<tr>"
            f"<td>{cycle_number}</td>"
            f"<td>{html.escape(str(row.get('finished_at', row.get('started_at', '-'))))}</td>"
            f"<td>{slug}</td>"
            f"<td>{status}</td>"
            f"<td>{success_text}</td>"
            "</tr>"
        )
    body_rows = "\n".join(rows) if rows else "<tr><td colspan=\"5\">기록이 없습니다.</td></tr>"
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="5">
  <title>Mystic Continuous Training Status</title>
  <style>
    body {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", serif;
      background: #f7f3eb;
      color: #1f1b16;
    }}
    .wrap {{
      max-width: 1080px;
      margin: 0 auto;
      padding: 28px 20px 44px;
    }}
    .panel {{
      background: #fffdf8;
      border: 1px solid #d8cfbf;
      border-radius: 18px;
      padding: 18px 20px;
      box-shadow: 0 10px 30px rgba(42, 29, 18, 0.08);
      margin-bottom: 20px;
    }}
    .meta {{
      color: #6f6458;
      margin-top: 4px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: #fffdf8;
      border: 1px solid #d8cfbf;
      border-radius: 18px;
      overflow: hidden;
    }}
    th, td {{
      padding: 12px 14px;
      border-bottom: 1px solid #d8cfbf;
      text-align: left;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="panel">
      <h1>Mystic Continuous Training</h1>
      <div class="meta">generated_at: {html.escape(str(payload.get("generated_at", "-")))}</div>
      <div class="meta">status: {html.escape(str(state.get("status", "-")))}</div>
      <div class="meta">current_cycle: {html.escape(str(state.get("current_cycle", "-")))}</div>
      <div class="meta">active_slug: {html.escape(str(state.get("active_slug", "-")))}</div>
      <div class="meta">next_slug: {html.escape(str(state.get("next_slug", "-")))}</div>
      <div class="meta">completed_cycles: {html.escape(str(state.get("completed_cycles", "-")))}</div>
      <div class="meta">last_heartbeat: {html.escape(str(state.get("last_heartbeat", "-")))}</div>
      <div class="meta">last_error: {html.escape(str(state.get("last_error", "")))}</div>
    </div>
    <table>
      <thead>
        <tr>
          <th>Cycle</th>
          <th>시각</th>
          <th>Dataset</th>
          <th>Status</th>
          <th>성공 여부</th>
        </tr>
      </thead>
      <tbody>
        {body_rows}
      </tbody>
    </table>
  </div>
</body>
</html>"""
