from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from mystic.execution_history import (
    collect_execution_records,
    dataset_label_for_record,
    dataset_label_from_slug,
    format_duration,
    load_continuous_status,
    load_remote_cycle_status,
    parse_timestamp,
    source_agents_by_slug,
)
from mystic.training.blueprints import ARCHITECTURE_TRAINING_TARGETS


PAGE_SIZE = 8
GREEN = "green"
YELLOW = "yellow"
RED = "red"

STATUS_EMOJI = {
    GREEN: "🟢",
    YELLOW: "🟡",
    RED: "🔴",
}

STATUS_COLOR = {
    GREEN: 0x2ECC71,
    YELLOW: 0xF1C40F,
    RED: 0xE74C3C,
}

REMOTE_PHASE_PROGRESS = {
    "starting": 10,
    "prepared": 25,
    "submitted": 50,
    "polling": 75,
    "poll_complete": 85,
    "download_complete": 95,
    "finish_complete": 100,
}

PHASE_LABELS = {
    "starting": "시작 중",
    "prepared": "준비 완료",
    "submitted": "제출 완료",
    "polling": "실행 확인 중",
    "poll_complete": "실행 완료",
    "download_complete": "결과 다운로드 완료",
    "finish_complete": "반영 완료",
}


@dataclass(slots=True)
class ExpertSnapshot:
    agent: str
    name: str
    division: str
    model: str
    adapter: str
    dataset: str
    train_ready_rows: int
    progress_percent: int
    status_text: str
    status_kind: str
    status_emoji: str
    status_color: int
    is_active: bool
    is_trainable: bool
    latest_timestamp: str
    success_count: int
    failure_count: int
    eta_text: str
    error_excerpt: str
    stage: str
    dataset_progress_text: str
    status_detail: str
    progress_reason: str


def subscribers_path(base_dir: str | Path) -> Path:
    return Path(base_dir) / "state" / "discord_dm_subscribers.json"


def load_subscribers(base_dir: str | Path) -> dict[str, Any]:
    path = subscribers_path(base_dir)
    if not path.exists():
        return {"subscribers": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_subscriber(base_dir: str | Path, *, user_id: int, username: str) -> dict[str, Any]:
    path = subscribers_path(base_dir)
    payload = load_subscribers(base_dir)
    subscribers = payload.setdefault("subscribers", [])
    key = str(user_id)
    existing = next((row for row in subscribers if str(row.get("user_id")) == key), None)
    now = datetime.now(UTC).isoformat()
    if existing is None:
        subscribers.append({"user_id": key, "username": username, "activated_at": now, "last_used_at": now})
    else:
        existing["username"] = username
        existing["last_used_at"] = now
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return payload


def load_dashboard_snapshot(base_dir: str | Path) -> dict[str, Any]:
    base = Path(base_dir)
    records = collect_execution_records(base)
    continuous_status = load_continuous_status(base)
    remote_status = load_remote_cycle_status(base)
    active_slug = str(continuous_status.get("active_slug", "") or "")
    active_agents = source_agents_by_slug().get(active_slug, set())

    records_by_agent: dict[str, list[Any]] = {}
    for record in records:
        if record.part == "unknown":
            continue
        records_by_agent.setdefault(record.part, []).append(record)

    experts: list[ExpertSnapshot] = []
    for target in ARCHITECTURE_TRAINING_TARGETS:
        agent = str(target["agent"])
        agent_records = records_by_agent.get(agent, [])
        latest = agent_records[0] if agent_records else None
        latest_failure = next((record for record in agent_records if not record.success), None)
        latest_success = next((record for record in agent_records if record.success), None)
        train_ready_rows = count_agent_rows(base, agent)
        dataset_progress = dataset_progress_for_agent(base, agent)
        is_trainable = bool(target.get("adapter")) or agent == "raven"
        is_active = agent in active_agents or (agent == "raven" and str(remote_status.get("status", "")) == "running")
        dataset = infer_dataset(agent, latest=latest, active_slug=active_slug, remote_status=remote_status)
        stage = str(target.get("current_stage", ""))
        status_kind = infer_status_kind(
            agent=agent,
            latest=latest,
            latest_failure=latest_failure,
            is_active=is_active,
            train_ready_rows=train_ready_rows,
            stage=stage,
            dataset_progress=dataset_progress,
        )
        status_text = infer_status_text(status_kind, latest=latest, remote_status=remote_status)
        if status_kind == GREEN and not is_cycle_complete(stage=stage, dataset_progress=dataset_progress):
            status_text = "대기"
        status_detail = infer_status_detail(
            agent=agent,
            status_kind=status_kind,
            is_active=is_active,
            dataset=dataset,
            dataset_progress=dataset_progress,
            stage=stage,
            remote_status=remote_status,
        )
        progress_percent = infer_progress_percent(
            agent=agent,
            stage=stage,
            is_active=is_active,
            latest=latest,
            train_ready_rows=train_ready_rows,
            remote_status=remote_status,
            dataset_progress=dataset_progress,
        )
        experts.append(
            ExpertSnapshot(
                agent=agent,
                name=str(target.get("name", agent)),
                division=str(target.get("division", "unknown")),
                model=str(target.get("model", "-")),
                adapter=str(target.get("adapter") or "-"),
                dataset=dataset,
                train_ready_rows=train_ready_rows,
                progress_percent=progress_percent,
                status_text=status_text,
                status_kind=status_kind,
                status_emoji=STATUS_EMOJI[status_kind],
                status_color=STATUS_COLOR[status_kind],
                is_active=is_active,
                is_trainable=is_trainable,
                latest_timestamp=latest.timestamp if latest else "",
                success_count=sum(1 for record in agent_records if record.success),
                failure_count=sum(1 for record in agent_records if not record.success),
                eta_text=infer_eta_text(
                    agent=agent,
                    is_active=is_active,
                    latest=latest,
                    latest_success=latest_success,
                    records=agent_records,
                    continuous_status=continuous_status,
                    remote_status=remote_status,
                ),
                error_excerpt=extract_error_excerpt(latest_failure),
                stage=stage,
                dataset_progress_text=f"{dataset_progress['covered']}/{dataset_progress['expected']} datasets",
                status_detail=status_detail,
                progress_reason=infer_progress_reason(agent=agent, is_active=is_active),
            )
        )

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "continuous_status": continuous_status,
        "remote_status": remote_status,
        "experts": experts,
        "total_pages": max(1, (len(experts) + PAGE_SIZE - 1) // PAGE_SIZE),
    }


def count_agent_rows(base_dir: Path, agent: str) -> int:
    path = base_dir / "train_ready" / f"{agent}_train_ready.jsonl"
    if not path.exists():
        return 0
    count = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def dataset_progress_for_agent(base_dir: Path, agent: str) -> dict[str, int]:
    train_ready_path = base_dir / "train_ready" / f"{agent}_train_ready.jsonl"
    covered = set()
    if train_ready_path.exists():
        for line in train_ready_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            metadata = row.get("metadata", {})
            dataset_name = str(metadata.get("dataset", "") or "").strip()
            if dataset_name:
                covered.add(dataset_name)
    target = next((item for item in ARCHITECTURE_TRAINING_TARGETS if str(item.get("agent")) == agent), None)
    expected = len(target.get("datasets", [])) if isinstance(target, dict) else 0
    expected = max(expected, len(covered), 1)
    return {
        "covered": len(covered),
        "expected": expected,
    }


def infer_dataset(agent: str, *, latest: Any, active_slug: str, remote_status: dict[str, Any]) -> str:
    if agent == "raven":
        current_dataset = str(remote_status.get("current_dataset_ref", "") or "")
        if current_dataset:
            return current_dataset
    if active_slug and agent in source_agents_by_slug().get(active_slug, set()):
        return dataset_label_from_slug(active_slug)
    if latest is not None:
        return dataset_label_for_record(latest)
    return "-"


def infer_status_kind(
    *,
    agent: str,
    latest: Any,
    latest_failure: Any,
    is_active: bool,
    train_ready_rows: int,
    stage: str,
    dataset_progress: dict[str, int],
) -> str:
    if is_active:
        return YELLOW
    if latest is not None and not latest.success:
        return RED
    return GREEN


def infer_status_text(status_kind: str, *, latest: Any, remote_status: dict[str, Any]) -> str:
    if status_kind == YELLOW:
        return "학습 중"
    if status_kind == RED:
        return "오류"
    if latest is not None and latest.success:
        return "완료"
    return "대기"


def is_cycle_complete(*, stage: str, dataset_progress: dict[str, int]) -> bool:
    if stage == "tool_only":
        return True
    return dataset_progress["covered"] >= dataset_progress["expected"]


def infer_status_detail(
    *,
    agent: str,
    status_kind: str,
    is_active: bool,
    dataset: str,
    dataset_progress: dict[str, int],
    stage: str,
    remote_status: dict[str, Any],
) -> str:
    if status_kind == RED:
        return "최근 실행 실패"
    if is_active and agent == "raven":
        phase = str(remote_status.get("current_phase", "") or "")
        return PHASE_LABELS.get(phase, phase or "원격 실행 중")
    if is_active:
        return dataset or "로컬 학습 실행 중"
    if stage == "tool_only":
        return "도구 준비"
    return f"{dataset_progress['covered']}/{dataset_progress['expected']} 데이터셋"


def infer_progress_percent(
    *,
    agent: str,
    stage: str,
    is_active: bool,
    latest: Any,
    train_ready_rows: int,
    remote_status: dict[str, Any],
    dataset_progress: dict[str, int],
) -> int:
    if stage == "tool_only":
        return 100
    if agent == "raven" and is_active:
        phase = str(remote_status.get("current_phase", "") or "")
        return REMOTE_PHASE_PROGRESS.get(phase, 65)

    row_progress = min(train_ready_rows / 100.0, 1.0)
    dataset_ratio = dataset_progress["covered"] / max(dataset_progress["expected"], 1)
    progress = int(round(max(row_progress * 0.35, dataset_ratio) * 90))
    if latest is not None and latest.success and dataset_progress["covered"] >= dataset_progress["expected"]:
        progress = max(progress, 100)
    elif latest is not None and latest.success:
        progress = max(progress, 60)
    elif is_active:
        progress = max(progress, 72)
    elif latest is not None and not latest.success:
        progress = max(progress, 35 if train_ready_rows > 0 else 10)
    elif train_ready_rows > 0:
        progress = max(progress, 45)
    else:
        progress = max(progress, 5)
    return min(progress, 100)


def infer_progress_reason(*, agent: str, is_active: bool) -> str:
    if is_active and agent == "raven":
        return "원격 사이클 단계 기준"
    if is_active:
        return "현재 로컬 학습 기준"
    return "데이터셋 커버리지 기준"


def infer_eta_text(
    *,
    agent: str,
    is_active: bool,
    latest: Any,
    latest_success: Any,
    records: list[Any],
    continuous_status: dict[str, Any],
    remote_status: dict[str, Any],
) -> str:
    durations = [record.duration_seconds for record in records if record.success and record.duration_seconds]
    average = sum(durations) / len(durations) if durations else None
    if not is_active:
        if latest_success is not None and latest_success.duration_seconds:
            return f"최근 완료 {format_duration(latest_success.duration_seconds)}"
        if average is not None:
            return f"평균 {format_duration(average)}"
        if agent == "raven":
            return "원격 GPU 대기 또는 실행 중"
        return "추정 불가"

    start_value = ""
    if agent == "raven":
        start_value = str(remote_status.get("cycle_started_at", "") or "")
    else:
        start_value = str(continuous_status.get("cycle_started_at", "") or "")
    if not start_value:
        return "진행 중"
    try:
        started_at = parse_timestamp(start_value)
    except Exception:
        return "진행 중"
    elapsed = max((datetime.now(UTC) - started_at).total_seconds(), 0.0)
    if average is None:
        return f"경과 {format_duration(elapsed)}"
    remaining = max(average - elapsed, 0.0)
    if remaining <= 5:
        return "곧 완료 예상"
    return f"약 {format_duration(remaining)} 남음"


def extract_error_excerpt(record: Any | None) -> str:
    if record is None:
        return ""
    details = record.details if hasattr(record, "details") else {}
    candidates = [
        str(details.get("error", "") or ""),
        str(details.get("failure_output", {}).get("signal_payload", {}).get("error", "") or "")
        if isinstance(details.get("failure_output"), dict)
        else "",
        str(details.get("failure_output", {}).get("signal_payload", {}).get("traceback", "") or "")
        if isinstance(details.get("failure_output"), dict)
        else "",
    ]
    for key in ("stderr_log", "stdout_log"):
        path_value = str(details.get(key, "") or "")
        if not path_value:
            continue
        path = Path(path_value)
        if not path.exists():
            continue
        tail = tail_text(path, line_limit=20, char_limit=1800)
        if tail:
            candidates.append(tail)
    for candidate in candidates:
        cleaned = clean_text(candidate)
        if cleaned:
            return cleaned[:1800]
    return ""


def tail_text(path: Path, *, line_limit: int, char_limit: int) -> str:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    tail = "\n".join(lines[-line_limit:])
    return tail[-char_limit:]


def clean_text(value: str) -> str:
    return str(value or "").strip()


def overview_page(snapshot: dict[str, Any], page: int) -> dict[str, Any]:
    experts: list[ExpertSnapshot] = snapshot["experts"]
    total_pages = int(snapshot["total_pages"])
    current_page = max(0, min(page, total_pages - 1))
    start = current_page * PAGE_SIZE
    page_experts = experts[start : start + PAGE_SIZE]
    lines = []
    for expert in page_experts:
        lines.append(
            f"{expert.status_emoji} **{expert.name}** · {expert.status_text}\n"
            f"{expert.status_detail}"
        )
    continuous = snapshot["continuous_status"]
    remote = snapshot["remote_status"]
    description = "\n\n".join(lines) if lines else "표시할 전문가가 없습니다."
    return {
        "title": f"Mystic 학습 개요 ({current_page + 1}/{total_pages})",
        "description": description,
        "color": 0x5865F2,
        "fields": [
            {
                "name": "로컬 학습",
                "value": (
                    f"현재: `{local_status_label(continuous)}`\n"
                    f"사이클: `{continuous.get('current_cycle', '-')}`\n"
                    f"데이터셋: `{continuous.get('active_slug', '-') or '-'}`"
                ),
                "inline": True,
            },
            {
                "name": "원격 Raven",
                "value": (
                    f"현재: `{remote_status_label(remote)}`\n"
                    f"사이클: `{remote.get('active_cycle_id', '-')}`\n"
                    f"단계: `{PHASE_LABELS.get(str(remote.get('current_phase', '') or ''), str(remote.get('current_phase', '-') or '-'))}`"
                ),
                "inline": True,
            },
            {
                "name": "표시 규칙",
                "value": "🟡 학습 중\n🟢 대기/완료\n🔴 실패/오류",
                "inline": True,
            },
        ],
        "footer": f"generated_at: {snapshot['generated_at']}",
        "page_experts": page_experts,
        "page": current_page,
        "total_pages": total_pages,
    }


def expert_detail_page(snapshot: dict[str, Any], agent: str) -> dict[str, Any]:
    experts: list[ExpertSnapshot] = snapshot["experts"]
    expert = next(item for item in experts if item.agent == agent)
    return {
        "author": expert.name,
        "title": f"{expert.status_emoji} {expert.status_text}",
        "description": f"{render_progress_bar(expert.progress_percent)}\n기준: {expert.progress_reason}",
        "color": expert.status_color,
        "fields": [
            {"name": "학습 현황", "value": f"`{expert.status_text}`", "inline": True},
            {"name": "진행률", "value": f"`{expert.progress_percent}%`", "inline": True},
            {"name": "학습 데이터", "value": expert.dataset or "-", "inline": True},
            {"name": "예상 시간", "value": expert.eta_text, "inline": True},
            {"name": "현재 상태", "value": expert.status_detail, "inline": True},
            {"name": "모델", "value": expert.model or "-", "inline": True},
            {"name": "어댑터", "value": expert.adapter or "-", "inline": True},
            {"name": "train_ready rows", "value": str(expert.train_ready_rows), "inline": True},
            {"name": "데이터셋 진행", "value": expert.dataset_progress_text, "inline": True},
            {"name": "성공 / 실패", "value": f"{expert.success_count} / {expert.failure_count}", "inline": True},
            {"name": "스테이지", "value": expert.stage or "-", "inline": True},
            {"name": "최근 업데이트", "value": expert.latest_timestamp or "-", "inline": True},
            {
                "name": "실패 로그",
                "value": expert.error_excerpt if expert.error_excerpt else "최근 실패 로그 없음",
                "inline": False,
            },
        ],
        "footer": f"division: {expert.division} | generated_at: {snapshot['generated_at']}",
        "expert": expert,
    }


def render_progress_bar(percent: int, *, width: int = 20) -> str:
    filled = int(round((max(0, min(percent, 100)) / 100.0) * width))
    return "█" * filled + "░" * (width - filled) + f" {percent}%"


def local_status_label(payload: dict[str, Any]) -> str:
    status = str(payload.get("status", "")).lower()
    if status == "running":
        return "학습 중"
    if status == "error":
        return "오류"
    return "대기"


def remote_status_label(payload: dict[str, Any]) -> str:
    status = str(payload.get("status", "")).lower()
    if status == "running":
        return "학습 중"
    if status == "error":
        return "오류"
    return "대기"
