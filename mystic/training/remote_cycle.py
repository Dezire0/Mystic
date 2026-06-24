"""Helpers for the persistent Kaggle-backed remote Raven cycle."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from mystic.training.continuous import append_jsonl, now_iso, read_json, write_json


REMOTE_LAUNCHD_LABEL = "com.mystic.remote-cycle"


def remote_cycle_state_path(base_dir: str | Path) -> Path:
    return Path(base_dir) / "state" / "remote_cycle_state.json"


def remote_cycle_log_path(base_dir: str | Path) -> Path:
    return Path(base_dir) / "logs" / "remote_cycle_runs.jsonl"


def remote_cycle_details_dir(base_dir: str | Path) -> Path:
    return Path(base_dir) / "logs" / "remote_cycle_details"


def remote_cycle_status_json_path(base_dir: str | Path) -> Path:
    return Path(base_dir) / "reports" / "remote_cycle_status.json"


def remote_cycle_status_html_path(base_dir: str | Path) -> Path:
    return Path(base_dir) / "reports" / "remote_cycle_status.html"


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


def load_recent_remote_rows(base_dir: str | Path, limit: int = 10) -> list[dict[str, Any]]:
    path = remote_cycle_log_path(base_dir)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(read_json_line(stripped))
    return rows[-limit:]


def read_json_line(text: str) -> dict[str, Any]:
    import json

    return json.loads(text)


def write_remote_status_outputs(base_dir: str | Path, state: dict[str, Any]) -> dict[str, str]:
    base = Path(base_dir)
    payload = {
        "generated_at": now_iso(),
        "state": state,
        "recent_cycles": load_recent_remote_rows(base, limit=10),
    }
    json_path = remote_cycle_status_json_path(base)
    html_path = remote_cycle_status_html_path(base)
    write_json(json_path, payload)
    html_path.write_text(render_remote_status_html(payload) + "\n", encoding="utf-8")
    return {
        "output_json": str(json_path),
        "output_html": str(html_path),
    }


def render_remote_status_html(payload: dict[str, Any]) -> str:
    state = payload.get("state", {})
    recent_cycles = payload.get("recent_cycles", [])
    kernel_ref = str(state.get("current_kernel_ref", "-"))
    dataset_ref = str(state.get("current_dataset_ref", "-"))
    kernel_url = kaggle_kernel_url(kernel_ref)
    dataset_url = kaggle_dataset_url(dataset_ref)
    kernel_html = (
        f'<a href="{html.escape(kernel_url)}" target="_blank" rel="noreferrer">{html.escape(kernel_ref)}</a>'
        if kernel_url
        else html.escape(kernel_ref)
    )
    dataset_html = (
        f'<a href="{html.escape(dataset_url)}" target="_blank" rel="noreferrer">{html.escape(dataset_ref)}</a>'
        if dataset_url
        else html.escape(dataset_ref)
    )
    rows: list[str] = []
    for row in reversed(recent_cycles):
        cycle_id = str(row.get("cycle_id", "-"))
        row_kernel_ref = str(row.get("kernel_ref", "") or "")
        row_dataset_ref = str(row.get("dataset_ref", "") or "")
        detail_bits: list[str] = []
        if row_kernel_ref:
            row_kernel_url = kaggle_kernel_url(row_kernel_ref)
            detail_bits.append(
                f'<a href="{html.escape(row_kernel_url)}" target="_blank" rel="noreferrer">{html.escape(row_kernel_ref)}</a>'
                if row_kernel_url
                else html.escape(row_kernel_ref)
            )
        if row_dataset_ref:
            row_dataset_url = kaggle_dataset_url(row_dataset_ref)
            detail_bits.append(
                f'<a href="{html.escape(row_dataset_url)}" target="_blank" rel="noreferrer">{html.escape(row_dataset_ref)}</a>'
                if row_dataset_url
                else html.escape(row_dataset_ref)
            )
        rows.append(
            "<tr>"
            f"<td><div>{html.escape(cycle_id)}</div><div class=\"subtle\">{'<br>'.join(detail_bits) if detail_bits else '-'}</div></td>"
            f"<td>{html.escape(str(row.get('finished_at', row.get('started_at', '-'))))}</td>"
            f"<td>{html.escape(str(row.get('status', '-')))}</td>"
            f"<td>{'성공' if bool(row.get('success')) else '실패'}</td>"
            "</tr>"
        )
    body_rows = "\n".join(rows) if rows else "<tr><td colspan=\"4\">기록이 없습니다.</td></tr>"
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="10">
  <title>Mystic Remote Cycle Status</title>
  <style>
    body {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", serif;
      background: #f5f1e7;
      color: #1f1b16;
    }}
    .wrap {{
      max-width: 1100px;
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
    a {{
      color: #b85c38;
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    .subtle {{
      color: #6f6458;
      font-size: 12px;
      margin-top: 4px;
      word-break: break-word;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="panel">
      <h1>Mystic Remote Kaggle Cycle</h1>
      <p>generated_at: {html.escape(str(payload.get("generated_at", "-")))}</p>
      <p>status: {html.escape(str(state.get("status", "-")))}</p>
      <p>current_cycle: {html.escape(str(state.get("current_cycle", "-")))}</p>
      <p>active_cycle_id: {html.escape(str(state.get("active_cycle_id", "-")))}</p>
      <p>current_phase: {html.escape(str(state.get("current_phase", "-")))}</p>
      <p>adapter_path: {html.escape(str(state.get("active_adapter_path", "-")))}</p>
      <p>kernel_ref: {kernel_html}</p>
      <p>dataset_ref: {dataset_html}</p>
      <p>last_error: {html.escape(str(state.get("last_error", "")))}</p>
    </div>
    <table>
      <thead>
        <tr>
          <th>Cycle</th>
          <th>시각</th>
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


__all__ = [
    "REMOTE_LAUNCHD_LABEL",
    "append_jsonl",
    "now_iso",
    "read_json",
    "remote_cycle_details_dir",
    "remote_cycle_log_path",
    "remote_cycle_state_path",
    "write_json",
    "write_remote_status_outputs",
]
