from __future__ import annotations

import argparse
import contextlib
from datetime import UTC, datetime
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.raven_training import split_train_eval, write_jsonl

PYTHON_BIN = sys.executable
FAILURE_KAGGLE_GPU_QUOTA_EXCEEDED = "KAGGLE_GPU_QUOTA_EXCEEDED"


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower())
    slug = slug.strip("-")
    if not slug:
        raise ValueError(f"Could not derive slug from: {text!r}")
    return slug


def default_output_tar_name(adapter_path: str) -> str:
    adapter_name = Path(adapter_path).name or "raven_lora"
    return f"{adapter_name}_qwen.tar.gz"


def is_kaggle_gpu_quota_error(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered
        for token in [
            "maximum weekly gpu quota",
            "gpu quota",
            "quota of 30.00 hours reached",
            "quota reached",
        ]
    )


def resolve_prepare_targets(*, limit: int, train_limit: int, eval_limit: int) -> dict[str, float | int]:
    total_limit = int(limit)
    eval_ratio = 0.1
    if train_limit > 0 and eval_limit > 0:
        total_limit = train_limit + eval_limit
        eval_ratio = eval_limit / total_limit
    elif total_limit > 0 and eval_limit > 0:
        eval_ratio = eval_limit / total_limit
    return {
        "total_limit": total_limit,
        "train_limit": train_limit,
        "eval_limit": eval_limit,
        "eval_ratio": eval_ratio,
    }


def verify_project_root(root: Path) -> None:
    required = [
        root / "scripts" / "mystic_loop.py",
        root / "scripts" / "compare_raven_models.py",
        root / "scripts" / "register_model.py",
        root / "scripts" / "train_raven_lora.py",
        root / "scripts" / "evaluate_raven_lora.py",
        root / "configs" / "models.json",
        root / "mystic_data",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Project root validation failed. Missing: {missing}")


def cycle_dir(base_dir: Path, cycle_id: str) -> Path:
    return base_dir / "cycles" / cycle_id


def prepare_summary_path(base_dir: Path, cycle_id: str) -> Path:
    return cycle_dir(base_dir, cycle_id) / "prepare_summary.json"


def cycle_summary_path(base_dir: Path, cycle_id: str) -> Path:
    return cycle_dir(base_dir, cycle_id) / "summary.json"


def kaggle_commands_path(base_dir: Path, cycle_id: str) -> Path:
    return cycle_dir(base_dir, cycle_id) / "kaggle_commands.md"


def kaggle_submit_summary_path(base_dir: Path, cycle_id: str) -> Path:
    return cycle_dir(base_dir, cycle_id) / "kaggle_submit_summary.json"


def kaggle_poll_summary_path(base_dir: Path, cycle_id: str) -> Path:
    return cycle_dir(base_dir, cycle_id) / "kaggle_poll_summary.json"


def kaggle_download_summary_path(base_dir: Path, cycle_id: str) -> Path:
    return cycle_dir(base_dir, cycle_id) / "kaggle_download_summary.json"


def kaggle_dataset_dir(base_dir: Path, cycle_id: str) -> Path:
    return cycle_dir(base_dir, cycle_id) / "kaggle_dataset"


def kaggle_kernel_dir(base_dir: Path, cycle_id: str) -> Path:
    return cycle_dir(base_dir, cycle_id) / "kaggle_kernel"


def kaggle_output_dir(base_dir: Path, cycle_id: str) -> Path:
    return cycle_dir(base_dir, cycle_id) / "kaggle_output"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def processed_ids_count(path: Path) -> int:
    return len(read_jsonl(path))


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


def run_raw_command(
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )


def run_command(args: list[str], *, cwd: Path) -> tuple[dict[str, Any], str]:
    completed = run_raw_command(args, cwd=cwd)
    stdout = completed.stdout.strip()
    payload = extract_last_json_object(stdout)
    return payload, stdout


def verify_training_eval_files(base_dir: Path) -> dict[str, str]:
    train_file = base_dir / "train_ready" / "raven_train.jsonl"
    eval_file = base_dir / "eval_holdout" / "raven_eval.jsonl"
    missing = [str(path) for path in [train_file, eval_file] if not path.exists() or path.stat().st_size == 0]
    if missing:
        raise FileNotFoundError(f"Training/eval files missing or empty: {missing}")
    return {
        "train_file": str(train_file),
        "eval_file": str(eval_file),
    }


def verify_export_file(base_dir: Path) -> Path:
    export_file = base_dir / "train_ready" / "raven_lora.jsonl"
    if not export_file.exists() or export_file.stat().st_size == 0:
        raise FileNotFoundError(f"Export file missing or empty: {export_file}")
    return export_file


def verify_prepared_dataset_file(path: Path) -> Path:
    if not path.exists() or path.stat().st_size == 0:
        raise FileNotFoundError(f"Prepared dataset missing or empty: {path}")
    return path


def materialize_prepared_training_split(
    *,
    prepared_path: Path,
    train_path: Path,
    eval_path: Path,
    eval_ratio: float,
) -> dict[str, Any]:
    rows = read_jsonl(prepared_path)
    train_rows, eval_rows = split_train_eval(rows, eval_ratio)
    write_jsonl(train_path, train_rows)
    write_jsonl(eval_path, eval_rows)
    return {
        "prepared_rows": len(rows),
        "train_rows": len(train_rows),
        "eval_rows": len(eval_rows),
        "prepared_path": str(prepared_path),
        "train_path": str(train_path),
        "eval_path": str(eval_path),
    }


def create_kaggle_package(root_dir: Path, output_tar: Path) -> Path:
    include_paths = [
        root_dir / "scripts",
        root_dir / "mystic",
        root_dir / "configs",
        root_dir / "README.md",
        root_dir / "requirements-training.txt",
        root_dir / "requirements-unsloth.txt",
        root_dir / "requirements-axolotl.txt",
        root_dir / "mystic_data" / "train_ready",
        root_dir / "mystic_data" / "eval_holdout",
        root_dir / "mystic_data" / "metadata",
        root_dir / "mystic_data" / "training" / "raven" / "manifest.json",
        root_dir / "mystic_data" / "training" / "raven" / "package_manifest.json",
    ]
    skip_tokens = [
        "__pycache__",
        ".git",
        ".DS_Store",
        "._",
        "mystic_data/adapters/raven_lora_tiny_gpt2_smoke",
        "mystic_data/models",
        "mystic_data/cycles",
    ]
    output_tar.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output_tar, "w:gz") as archive:
        for path in include_paths:
            if not path.exists():
                continue
            if path.is_dir():
                for item in path.rglob("*"):
                    rel = item.relative_to(root_dir).as_posix()
                    if any(token in rel for token in skip_tokens):
                        continue
                    if item.is_file():
                        archive.add(item, arcname=rel)
            elif path.is_file():
                archive.add(path, arcname=path.relative_to(root_dir).as_posix())
    return output_tar


def build_kaggle_commands_md(
    *,
    cycle_id: str,
    package_path: Path,
    base_model: str = "Qwen/Qwen2.5-0.5B-Instruct",
    adapter_path: str = "mystic_data/adapters/raven_lora_v0",
    output_tar_name: str = "raven_lora_v0_qwen.tar.gz",
    learning_rate: float = 0.0002,
    epochs: int = 1,
    batch_size: int = 1,
    max_length: int = 2048,
) -> str:
    adapter_name = Path(adapter_path).name
    return "\n".join(
        [
            f"# Kaggle Commands for {cycle_id}",
            "",
            "Manual Kaggle fallback commands:",
            "",
            "```bash",
            f"tar -xzf {package_path.name}",
            "python -m pip install -U pip",
            "python -m pip install -r requirements-training.txt",
            "python -m pip install bitsandbytes peft accelerate datasets safetensors",
            "python scripts/train_raven_lora.py \\",
            f"  --base-model {base_model} \\",
            "  --train-file mystic_data/train_ready/raven_train.jsonl \\",
            "  --eval-file mystic_data/eval_holdout/raven_eval.jsonl \\",
            f"  --output-dir {adapter_path} \\",
            f"  --epochs {epochs} \\",
            f"  --batch-size {batch_size} \\",
            f"  --learning-rate {learning_rate} \\",
            f"  --max-length {max_length} \\",
            "  --qlora",
            "python scripts/evaluate_raven_lora.py \\",
            f"  --base-model {base_model} \\",
            f"  --adapter-path {adapter_path} \\",
            "  --eval-file mystic_data/eval_holdout/raven_eval.jsonl \\",
            "  --limit 10",
            f"tar -czf {output_tar_name} mystic_data/adapters/{adapter_name} mystic_data/logs",
            "```",
            "",
            "For full automation use:",
            "",
            "```bash",
            f"python scripts/run_mystic_cycle.py full --cycle-id {cycle_id} --run-prepare-data --base-model {base_model} --adapter-path {adapter_path} --model-id {adapter_name}_auto",
            "```",
            "",
        ]
    )


def current_adapter_status(base_dir: Path) -> dict[str, Any]:
    registry_path = base_dir / "metadata" / "model_versions.json"
    registry = read_json(registry_path) if registry_path.exists() else {"models": []}
    models = list(registry.get("models", []))
    latest_model = models[-1] if models else None
    adapter_path = None
    adapter_exists = False
    adapter_base_model = None
    if latest_model:
        adapter_path = str(latest_model.get("adapter_path", "")).strip() or None
        if adapter_path:
            resolved = Path(adapter_path)
            if not resolved.is_absolute():
                resolved = (ROOT / resolved).resolve()
            adapter_exists = resolved.exists()
            config_path = resolved / "adapter_config.json"
            if config_path.exists():
                adapter_base_model = read_json(config_path).get("base_model_name_or_path")
    return {
        "latest_model": latest_model,
        "adapter_exists": adapter_exists,
        "adapter_base_model": adapter_base_model,
    }


def read_adapter_base_model(adapter_path: Path) -> str:
    config_path = adapter_path / "adapter_config.json"
    payload = read_json(config_path)
    base_model = str(payload.get("base_model_name_or_path", "")).strip()
    if not base_model:
        raise ValueError(f"adapter_config.json missing base_model_name_or_path: {config_path}")
    return base_model


def validate_adapter_files(adapter_path: Path, base_model: str) -> dict[str, str]:
    config_path = adapter_path / "adapter_config.json"
    weights_path = adapter_path / "adapter_model.safetensors"
    missing = [str(path) for path in [config_path, weights_path] if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Adapter files missing: {missing}")
    actual_base_model = read_adapter_base_model(adapter_path)
    if actual_base_model != base_model:
        raise ValueError(
            "Adapter/base model mismatch: "
            f"adapter was trained on '{actual_base_model}' but --base-model is '{base_model}'."
        )
    return {
        "adapter_config": str(config_path),
        "adapter_weights": str(weights_path),
        "base_model_name_or_path": actual_base_model,
    }


def backup_and_clear_processed_ids(base_dir: Path, cycle_id: str) -> dict[str, Any]:
    processed_file = base_dir / "state" / "processed_ids.jsonl"
    backup_dir = base_dir / "state" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    processed_file.parent.mkdir(parents=True, exist_ok=True)
    processed_file.touch(exist_ok=True)
    rows = read_jsonl(processed_file)
    backup_path = backup_dir / f"processed_ids_{cycle_id}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.jsonl"
    shutil.copy2(processed_file, backup_path)
    processed_file.write_text("", encoding="utf-8")
    return {
        "processed_ids_file": str(processed_file),
        "backup_path": str(backup_path),
        "backed_up_count": len(rows),
        "cleared_count": 0,
    }


def safe_extract_adapter_tar(tar_path: Path, destination: Path) -> list[str]:
    extracted: list[str] = []
    destination_resolved = destination.resolve()
    with tarfile.open(tar_path, "r:gz") as archive:
        members = []
        for member in archive.getmembers():
            name = member.name
            parts = Path(name).parts
            if any(part.startswith("._") for part in parts):
                continue
            if "__MACOSX" in parts:
                continue
            member_path = (destination / name).resolve()
            if not str(member_path).startswith(str(destination_resolved)):
                raise ValueError(f"Unsafe tar member path detected: {name}")
            members.append(member)
            extracted.append(name)
        archive.extractall(destination, members=members)
    return extracted


def latest_cycle_summaries(base_dir: Path, limit: int = 5) -> list[dict[str, Any]]:
    cycles_root = base_dir / "cycles"
    if not cycles_root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for pattern in ["*/prepare_summary.json", "*/kaggle_submit_summary.json", "*/kaggle_poll_summary.json", "*/kaggle_download_summary.json", "*/summary.json"]:
        for summary_path in sorted(cycles_root.glob(pattern)):
            rows.append(read_json(summary_path))
    rows.sort(key=lambda row: str(row.get("timestamp", "")))
    return rows[-limit:]


def require_kaggle_cli() -> str:
    python_candidates: list[list[str]] = []
    seen_python: set[str] = set()
    for candidate in [
        PYTHON_BIN,
        shutil.which("python"),
        shutil.which("python3"),
        "/opt/homebrew/bin/python3",
        "/opt/homebrew/Caskroom/miniforge/base/bin/python",
        "/opt/homebrew/Caskroom/miniforge/base/bin/python3",
        "/usr/local/bin/python3",
    ]:
        if not candidate:
            continue
        resolved = str(Path(candidate).expanduser())
        if resolved in seen_python or not Path(resolved).exists():
            continue
        seen_python.add(resolved)
        python_candidates.append([resolved, "-m", "kaggle"])

    for candidate in python_candidates:
        try:
            subprocess.run(
                [*candidate, "--version"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            return " ".join(candidate)
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue

    kaggle_candidates = [
        shutil.which("kaggle"),
        "/opt/homebrew/bin/kaggle",
        "/opt/homebrew/Caskroom/miniforge/base/bin/kaggle",
        "/usr/local/bin/kaggle",
    ]
    seen_kaggle: set[str] = set()
    for kaggle_path in kaggle_candidates:
        if not kaggle_path:
            continue
        resolved = str(Path(kaggle_path).expanduser())
        if resolved in seen_kaggle or not Path(resolved).exists():
            continue
        seen_kaggle.add(resolved)
        try:
            subprocess.run(
                [resolved, "--version"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            return resolved
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    raise FileNotFoundError(
        "Kaggle CLI not found. Install it first, for example: "
        "`python -m pip install kaggle`, then place credentials in ~/.kaggle/kaggle.json."
    )


@contextlib.contextmanager
def kaggle_runtime_env() -> Any:
    """Prefer OAuth credentials when both legacy kaggle.json and OAuth files exist.

    Recent Kaggle CLI builds can read legacy keys for some read-only operations but still
    require OAuth/access-token config for dataset uploads. A temporary KAGGLE_CONFIG_DIR
    avoids mutating the user's ~/.kaggle directory.
    """
    base_env = os.environ.copy()
    config_dir = Path.home() / ".kaggle"
    access_token = config_dir / "access_token"
    credentials = config_dir / "credentials.json"
    if access_token.exists() and credentials.exists() and not os.getenv("MYSTIC_DISABLE_KAGGLE_OAUTH_SHIM"):
        with tempfile.TemporaryDirectory(prefix="mystic_kaggle_oauth_") as temp_dir:
            temp_path = Path(temp_dir)
            for source in [access_token, credentials]:
                target = temp_path / source.name
                shutil.copy2(source, target)
                target.chmod(0o600)
            env = dict(base_env)
            env["KAGGLE_CONFIG_DIR"] = str(temp_path)
            yield env
            return
    yield base_env


def kaggle_command_prefix() -> list[str]:
    mode = require_kaggle_cli()
    if mode.startswith(PYTHON_BIN) or mode.endswith("-m kaggle") or " -m kaggle" in mode:
        return mode.split(" ")
    return ["kaggle"]


def detect_kaggle_username() -> str:
    username = os.getenv("KAGGLE_USERNAME", "").strip()
    if username:
        return username
    credentials_path = Path.home() / ".kaggle" / "credentials.json"
    if credentials_path.exists():
        payload = json.loads(credentials_path.read_text(encoding="utf-8"))
        username = str(payload.get("username", "")).strip()
        if username:
            return username
    credential_path = Path.home() / ".kaggle" / "kaggle.json"
    if credential_path.exists():
        payload = json.loads(credential_path.read_text(encoding="utf-8"))
        username = str(payload.get("username", "")).strip()
        if username:
            return username
    raise FileNotFoundError(
        "Kaggle credentials not found. Set KAGGLE_USERNAME/KAGGLE_KEY or create ~/.kaggle/kaggle.json."
    )


def ensure_kaggle_ready() -> str:
    kaggle_cmd = kaggle_command_prefix()
    username = detect_kaggle_username()
    with kaggle_runtime_env() as env:
        try:
            run_raw_command([*kaggle_cmd, "datasets", "list", "--mine", "-p", "1"], cwd=ROOT, env=env)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                "Kaggle authentication failed. Run `kaggle auth login` or refresh "
                "~/.kaggle/access_token before starting remote cycles. "
                f"stdout={exc.stdout.strip()!r} stderr={exc.stderr.strip()!r}"
            ) from exc
    return username


def parse_kaggle_status_output(stdout: str) -> str:
    text = stdout.lower()
    if any(token in text for token in ["complete", "completed", "success"]):
        return "complete"
    if any(token in text for token in ["failed", "error", "cancel"]):
        return "failed"
    if any(token in text for token in ["running", "queued", "pending", "starting"]):
        return "running"
    return "unknown"


def parse_kaggle_dataset_status_output(stdout: str) -> str:
    text = stdout.strip().lower()
    if "ready" in text:
        return "ready"
    if any(token in text for token in ["running", "queued", "pending", "creating", "uploading"]):
        return "running"
    if any(token in text for token in ["failed", "error"]):
        return "failed"
    return "unknown"


def kaggle_dataset_create_needs_version(stdout: str, stderr: str) -> bool:
    combined = f"{stdout}\n{stderr}".lower()
    duplicate_markers = [
        "already in use",
        "already exists",
        "requested title",
        "dataset creation error",
    ]
    return any(marker in combined for marker in duplicate_markers) and any(
        marker in combined for marker in ["already in use", "already exists", "requested title"]
    )


def locate_downloaded_adapter_tar(output_dir: Path, expected_name: str) -> Path:
    exact = output_dir / expected_name
    if exact.exists():
        return exact
    tarballs = sorted(output_dir.rglob("*.tar.gz"))
    if not tarballs:
        raise FileNotFoundError(f"No .tar.gz artifacts found under {output_dir}")
    return tarballs[0]


def locate_cycle_signal_file(output_dir: Path) -> Path | None:
    exact = output_dir / "mystic_cycle_signal.json"
    if exact.exists():
        return exact
    matches = sorted(output_dir.rglob("mystic_cycle_signal.json"))
    return matches[0] if matches else None


def package_discovery_keywords(package_filename: str) -> list[str]:
    keywords = ["mystic", "raven", "vnext", "adversarial"]
    lowered = package_filename.lower()
    return [keyword for keyword in keywords if keyword in lowered or keyword in {"mystic", "raven"}]


def limited_directory_listing(root: Path, *, max_depth: int = 2, max_entries: int = 40) -> list[str]:
    if not root.exists():
        return []
    entries: list[str] = []
    for current_root, dirnames, filenames in os.walk(root):
        current_path = Path(current_root)
        try:
            relative = current_path.relative_to(root)
            depth = len(relative.parts)
        except ValueError:
            depth = 0
        if depth > max_depth:
            dirnames[:] = []
            continue
        names = sorted(dirnames) + sorted(filenames)
        for name in names:
            entry_path = current_path / name
            try:
                rel = entry_path.relative_to(root).as_posix()
            except ValueError:
                rel = str(entry_path)
            suffix = "/" if entry_path.is_dir() else ""
            entries.append(f"{root.name}/{rel}{suffix}")
            if len(entries) >= max_entries:
                return entries
    return entries


def iter_files_limited(root: Path, *, max_depth: int = 2) -> list[Path]:
    if not root.exists():
        return []
    files: list[Path] = []
    for current_root, dirnames, filenames in os.walk(root):
        current_path = Path(current_root)
        try:
            relative = current_path.relative_to(root)
            depth = len(relative.parts)
        except ValueError:
            depth = 0
        if depth > max_depth:
            dirnames[:] = []
            continue
        for filename in filenames:
            files.append(current_path / filename)
    return files


def discover_package_tar(
    search_roots: list[Path],
    *,
    expected_filename: str,
    dataset_slug: str,
    keywords: list[str] | None = None,
    max_depth: int = 2,
) -> tuple[Path, dict[str, Any]]:
    normalized_roots: list[Path] = []
    seen_roots: set[Path] = set()
    for root in search_roots:
        resolved = root.resolve() if root.exists() else root
        if resolved in seen_roots:
            continue
        seen_roots.add(resolved)
        normalized_roots.append(root)

    input_root = next((root for root in normalized_roots if str(root) == "/kaggle/input"), None)
    effective_keywords = [keyword.lower() for keyword in (keywords or package_discovery_keywords(expected_filename))]
    candidate_rows: list[dict[str, Any]] = []
    exact_candidates: list[dict[str, Any]] = []
    fallback_candidates: list[dict[str, Any]] = []
    seen_files: set[Path] = set()

    for root in normalized_roots:
        for path in iter_files_limited(root, max_depth=max_depth):
            resolved = path.resolve()
            if resolved in seen_files or path.suffixes[-2:] != [".tar", ".gz"]:
                continue
            seen_files.add(resolved)
            lowered_name = path.name.lower()
            row = {
                "path": path,
                "path_str": str(path),
                "name": path.name,
                "size": path.stat().st_size,
                "mtime": path.stat().st_mtime,
                "dataset_match": dataset_slug in str(path),
                "exact_match": path.name == expected_filename,
            }
            if row["exact_match"]:
                exact_candidates.append(row)
                candidate_rows.append(row)
                continue
            if any(keyword in lowered_name for keyword in effective_keywords):
                fallback_candidates.append(row)
                candidate_rows.append(row)

    def sort_key(row: dict[str, Any]) -> tuple[int, int, int, int, str]:
        return (
            0 if row["exact_match"] else 1,
            0 if row["dataset_match"] else 1,
            -int(row["size"]),
            -int(row["mtime"]),
            row["path_str"],
        )

    candidate_rows.sort(key=sort_key)
    diagnostics = {
        "expected_filename": expected_filename,
        "dataset_slug": dataset_slug,
        "searched_roots": [str(root) for root in normalized_roots],
        "input_listing": limited_directory_listing(input_root, max_depth=1) if input_root else [],
        "candidate_count": len(candidate_rows),
        "candidates": [
            {
                "path": row["path_str"],
                "exact_match": row["exact_match"],
                "dataset_match": row["dataset_match"],
                "size": row["size"],
            }
            for row in candidate_rows
        ],
        "keywords": effective_keywords,
    }
    if candidate_rows:
        return Path(candidate_rows[0]["path"]), diagnostics
    raise FileNotFoundError(
        "Package tarball not found. "
        + json.dumps(diagnostics, ensure_ascii=True, sort_keys=True)
    )


def validate_generated_kaggle_submit_artifacts(
    *,
    package_path: Path,
    dataset_dir: Path,
    kernel_dir: Path,
    dataset_ref: str,
    dataset_slug: str,
    package_filename: str,
    training_script_path: Path,
    output_tar_name: str,
    adapter_path: str,
) -> dict[str, Any]:
    if not package_path.exists():
        raise FileNotFoundError(f"Cycle package not found: {package_path}")
    copied_package = dataset_dir / package_filename
    if not copied_package.exists():
        raise FileNotFoundError(f"Copied package missing from dataset staging dir: {copied_package}")

    metadata_path = dataset_dir / "dataset-metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Dataset metadata missing: {metadata_path}")
    metadata = read_json(metadata_path)
    if str(metadata.get("id", "")).strip() != dataset_ref:
        raise ValueError(f"Dataset metadata id mismatch: expected {dataset_ref!r} got {metadata.get('id')!r}")

    if not training_script_path.exists():
        raise FileNotFoundError(f"Generated Kaggle kernel missing: {training_script_path}")
    kernel_text = training_script_path.read_text(encoding="utf-8")
    required_snippets = [
        package_filename,
        "def find_package(",
        "PACKAGE_KEYWORDS",
        "limited_directory_listing(",
        "discover_package_candidates(",
    ]
    missing_snippets = [snippet for snippet in required_snippets if snippet not in kernel_text]
    if missing_snippets:
        raise ValueError(f"Generated Kaggle kernel is missing expected discovery content: {missing_snippets}")
    unresolved_placeholders = [
        placeholder
        for placeholder in [
            "$EXPECTED_PACKAGE_FILENAME",
            "$OUTPUT_TAR_NAME",
            "{searched_roots}",
            '"\'searched_roots\'"',
        ]
        if placeholder in kernel_text
    ]
    if unresolved_placeholders:
        raise ValueError(
            "Generated Kaggle kernel contains unresolved placeholder content: "
            f"{unresolved_placeholders}"
        )
    try:
        compile(kernel_text, str(training_script_path), "exec")
    except SyntaxError as exc:
        raise ValueError(
            f"Generated Kaggle kernel failed to compile: {training_script_path}: {exc}"
        ) from exc

    if output_tar_name not in kernel_text:
        raise ValueError(f"Generated Kaggle kernel missing output tar name {output_tar_name!r}")
    if adapter_path not in kernel_text:
        raise ValueError(f"Generated Kaggle kernel missing adapter path {adapter_path!r}")

    return {
        "package_filename": package_filename,
        "dataset_slug": dataset_slug,
        "dataset_ref": dataset_ref,
        "dataset_metadata_path": str(metadata_path),
        "generated_kernel_path": str(training_script_path),
        "copied_package_path": str(copied_package),
        "kernel_contains_discovery_helper": True,
        "kernel_contains_expected_package_filename": True,
    }


def probe_kernel_output_signal(
    *,
    kaggle_cmd: list[str],
    kernel_ref: str,
    output_dir: Path,
    env: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        run_raw_command([*kaggle_cmd, "kernels", "output", kernel_ref, "-p", str(output_dir), "-o"], cwd=ROOT, env=env)
    except subprocess.CalledProcessError:
        return None
    signal_file = locate_cycle_signal_file(output_dir)
    if signal_file is None:
        return None
    return {
        "signal_file": str(signal_file),
        "signal_payload": read_json(signal_file),
    }


def load_prepare_summary(base_dir: Path, cycle_id: str) -> dict[str, Any]:
    summary_path = prepare_summary_path(base_dir, cycle_id)
    if not summary_path.exists():
        raise FileNotFoundError(f"Prepare summary not found: {summary_path}")
    return read_json(summary_path)


def load_submit_summary(base_dir: Path, cycle_id: str) -> dict[str, Any]:
    summary_path = kaggle_submit_summary_path(base_dir, cycle_id)
    if not summary_path.exists():
        raise FileNotFoundError(f"Kaggle submit summary not found: {summary_path}")
    return read_json(summary_path)


def build_kaggle_training_script(
    *,
    cycle_id: str,
    dataset_slug: str,
    package_filename: str,
    base_model: str,
    adapter_path: str,
    adapter_dirname: str,
    output_tar_name: str,
    learning_rate: float,
    epochs: int,
    batch_size: int,
    max_length: int,
) -> str:
    package_keywords = package_discovery_keywords(package_filename)
    return "\n".join(
        [
            "from __future__ import annotations",
            "",
            "from datetime import UTC, datetime",
            "import json",
            "import os",
            "from pathlib import Path",
            "import subprocess",
            "import sys",
            "import tarfile",
            "import time",
            "import traceback",
            "",
            f'CYCLE_ID = "{cycle_id}"',
            f'DATASET_SLUG = "{dataset_slug}"',
            f'PACKAGE_FILENAME = "{package_filename}"',
            f'BASE_MODEL = "{base_model}"',
            f'ADAPTER_PATH = "{adapter_path}"',
            f'ADAPTER_DIRNAME = "{adapter_dirname}"',
            f'OUTPUT_TAR_NAME = "{output_tar_name}"',
            f"PACKAGE_KEYWORDS = {package_keywords!r}",
            "EXPECTED_KAGGLE_INPUT_DIR = Path('/kaggle/input') / DATASET_SLUG",
            "",
            "SIGNAL_PATH = Path('/kaggle/working') / 'mystic_cycle_signal.json'",
            "",
            "class PackageDiscoveryError(RuntimeError):",
            "    pass",
            "",
            "def run(args: list[str]) -> None:",
            '    print("+", " ".join(args), flush=True)',
            "    subprocess.run(args, check=True)",
            "",
            "def now_iso() -> str:",
            "    return datetime.now(UTC).isoformat()",
            "",
            "def write_signal(status: str, **extra: object) -> None:",
            "    payload = {'timestamp': now_iso(), 'status': status}",
            "    payload.update(extra)",
            "    SIGNAL_PATH.write_text(json.dumps(payload, indent=2) + '\\n', encoding='utf-8')",
            "    print(f'[signal] {status}', flush=True)",
            "",
            "def limited_directory_listing(root: Path, max_depth: int = 2, max_entries: int = 40) -> list[str]:",
            "    if not root.exists():",
            "        return []",
            "    entries: list[str] = []",
            "    stack = [(root, 0)]",
            "    while stack and len(entries) < max_entries:",
            "        current, depth = stack.pop(0)",
            "        try:",
            "            children = sorted(current.iterdir(), key=lambda item: item.name)",
            "        except Exception:",
            "            continue",
            "        for child in children:",
            "            try:",
            "                rel = child.relative_to(root).as_posix()",
            "            except Exception:",
            "                rel = child.name",
            "            entries.append(f'{root.name}/{rel}' + ('/' if child.is_dir() else ''))",
            "            if len(entries) >= max_entries:",
            "                break",
            "            if child.is_dir() and depth < max_depth:",
            "                stack.append((child, depth + 1))",
            "    return entries",
            "",
            "def discover_package_candidates(search_roots: list[Path], max_depth: int = 2) -> tuple[list[dict[str, object]], dict[str, object]]:",
            "    candidates: list[dict[str, object]] = []",
            "    seen_paths: set[Path] = set()",
            "    searched_roots: list[str] = []",
            "    likely_dirs: list[str] = []",
            "    input_root = Path('/kaggle/input')",
            "    if input_root.exists():",
            "        for child in sorted(input_root.iterdir(), key=lambda item: item.name):",
            "            if child.is_dir():",
            "                likely_dirs.append(str(child))",
            "    for root in search_roots:",
            "        searched_roots.append(str(root))",
            "        if not root.exists():",
            "            continue",
            "        stack = [(root, 0)]",
            "        while stack:",
            "            current, depth = stack.pop(0)",
            "            try:",
            "                children = sorted(current.iterdir(), key=lambda item: item.name)",
            "            except Exception:",
            "                continue",
            "            for child in children:",
            "                if child.is_dir():",
            "                    if depth < max_depth:",
            "                        stack.append((child, depth + 1))",
            "                    continue",
            "                if not child.name.endswith('.tar.gz'):",
            "                    continue",
            "                resolved = child.resolve()",
            "                if resolved in seen_paths:",
            "                    continue",
            "                seen_paths.add(resolved)",
            "                lowered_name = child.name.lower()",
            "                exact_match = child.name == PACKAGE_FILENAME",
            "                fuzzy_match = any(keyword in lowered_name for keyword in PACKAGE_KEYWORDS)",
            "                if not exact_match and not fuzzy_match:",
            "                    continue",
            "                candidates.append({",
            "                    'path': str(child),",
            "                    'name': child.name,",
            "                    'exact_match': exact_match,",
            "                    'dataset_match': DATASET_SLUG in str(child),",
            "                    'size': child.stat().st_size,",
            "                    'mtime': child.stat().st_mtime,",
            "                })",
            "    diagnostics = {",
            "        'cycle_id': CYCLE_ID,",
            "        'dataset_slug': DATASET_SLUG,",
            "        'expected_package_filename': PACKAGE_FILENAME,",
            "        'expected_kaggle_input_dir': str(EXPECTED_KAGGLE_INPUT_DIR),",
            "        'searched_roots': searched_roots,",
            "        'input_listing': limited_directory_listing(input_root, max_depth=1),",
            "        'likely_dataset_directories': likely_dirs[:10],",
            "        'likely_directory_listings': {path: limited_directory_listing(Path(path), max_depth=1) for path in likely_dirs[:10]},",
            "        'keywords': PACKAGE_KEYWORDS,",
            "    }",
            "    candidates.sort(key=lambda row: (0 if row['exact_match'] else 1, 0 if row['dataset_match'] else 1, -int(row['size']), -int(row['mtime']), str(row['path'])))",
            "    diagnostics['candidates'] = candidates",
            "    return candidates, diagnostics",
            "",
            "def find_package(",
            "    search_roots: list[Path] | None = None,",
            "    local_candidates: list[Path] | None = None,",
            ") -> tuple[Path, dict[str, object]]:",
            "    if local_candidates is None:",
            "        local_candidates = [",
            "        Path(__file__).resolve().parent / PACKAGE_FILENAME,",
            "        Path.cwd() / PACKAGE_FILENAME,",
            "        Path('/kaggle/working') / PACKAGE_FILENAME,",
            "        Path('/kaggle/src') / PACKAGE_FILENAME,",
            "        ]",
            "    for candidate in local_candidates:",
            "        if candidate.exists():",
            "            return candidate, {'found_via': 'local_exact', 'path': str(candidate)}",
            "    if search_roots is None:",
            "        search_roots = [",
            "        Path(__file__).resolve().parent,",
            "        Path.cwd(),",
            "        Path('/kaggle/working'),",
            "        Path('/kaggle/src'),",
            "        Path('/kaggle/input'),",
            "        EXPECTED_KAGGLE_INPUT_DIR,",
            "        ]",
            "    candidates, diagnostics = discover_package_candidates(search_roots, max_depth=2)",
            "    print('Package discovery diagnostics:', json.dumps(diagnostics, indent=2), flush=True)",
            "    if candidates:",
            "        selected = Path(str(candidates[0]['path']))",
            "        diagnostics['selected_candidate'] = str(selected)",
            "        return selected, diagnostics",
            "    searched_roots = list(diagnostics.get('searched_roots', []))",
            "    input_listing = list(diagnostics.get('input_listing', []))",
            "    likely_dataset_directories = list(diagnostics.get('likely_dataset_directories', []))",
            "    candidate_paths = [str(row.get('path', '')) for row in candidates]",
            "    print(f'Package discovery failed: expected_package_filename={PACKAGE_FILENAME!r}', flush=True)",
            "    print(f'Package discovery searched_roots={searched_roots!r}', flush=True)",
            "    print(f'Package discovery candidate_tarballs={candidate_paths!r}', flush=True)",
            "    print(f'Package discovery input_listing={input_listing!r}', flush=True)",
            "    raise PackageDiscoveryError(",
            "        'Could not find training package tar. '",
            "        f'expected_package_filename={PACKAGE_FILENAME!r}; '",
            "        f'dataset_slug={DATASET_SLUG!r}; '",
            "        f'searched_roots={searched_roots!r}; '",
            "        f'candidates={candidate_paths!r}; '",
            "        f'input_listing={input_listing!r}; '",
            "        f'likely_dataset_directories={likely_dataset_directories!r}'",
            "    )",
            "",
            "write_signal('starting', dataset_slug=DATASET_SLUG, base_model=BASE_MODEL, adapter_dirname=ADAPTER_DIRNAME)",
            "try:",
            "    package_path = None",
            "    package_diagnostics = {}",
            "    last_error = None",
            "    for attempt in range(60):",
            "        try:",
            "            package_path, package_diagnostics = find_package()",
            "            print(f'Found package on attempt {attempt + 1}: {package_path}', flush=True)",
            "            write_signal('package_found', package_path=str(package_path), attempt=attempt + 1, diagnostics=package_diagnostics)",
            "            break",
            "        except PackageDiscoveryError as exc:",
            "            last_error = exc",
            "            print(f'Waiting for Kaggle dataset mount ({attempt + 1}/60)...', flush=True)",
            "            time.sleep(10)",
            "    if package_path is None:",
            "        raise last_error or PackageDiscoveryError('Could not find training package tar.')",
            "    workdir = Path('/kaggle/working/mystic_cycle')",
            "    workdir.mkdir(parents=True, exist_ok=True)",
            "    with tarfile.open(package_path, 'r:gz') as archive:",
            "        archive.extractall(workdir)",
            "    write_signal('package_extracted', workdir=str(workdir))",
            "    os.chdir(workdir)",
            "    run([sys.executable, '-m', 'pip', 'install', '-U', 'pip'])",
            "    if Path('requirements-training.txt').exists():",
            "        run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements-training.txt'])",
            "    run([sys.executable, '-m', 'pip', 'install', 'bitsandbytes', 'peft', 'accelerate', 'datasets', 'safetensors'])",
            "    write_signal('training_started')",
            "    run([",
            "        sys.executable,",
            "        'scripts/train_raven_lora.py',",
            "        '--base-model', BASE_MODEL,",
            "        '--train-file', 'mystic_data/train_ready/raven_train.jsonl',",
            "        '--eval-file', 'mystic_data/eval_holdout/raven_eval.jsonl',",
            "        '--output-dir', ADAPTER_PATH,",
            f"        '--epochs', '{epochs}',",
            f"        '--batch-size', '{batch_size}',",
            f"        '--learning-rate', '{learning_rate}',",
            f"        '--max-length', '{max_length}',",
            "        '--qlora',",
            "    ])",
            "    write_signal('training_complete')",
            "    run([",
            "        sys.executable,",
            "        'scripts/evaluate_raven_lora.py',",
            "        '--base-model', BASE_MODEL,",
            "        '--adapter-path', ADAPTER_PATH,",
            "        '--eval-file', 'mystic_data/eval_holdout/raven_eval.jsonl',",
            "        '--limit', '10',",
            "    ])",
            "    write_signal('evaluation_complete')",
            "    output_tar = Path('/kaggle/working') / OUTPUT_TAR_NAME",
            "    with tarfile.open(output_tar, 'w:gz') as archive:",
            "        archive.add(workdir / ADAPTER_PATH, arcname=ADAPTER_PATH)",
            "        archive.add(workdir / 'mystic_data' / 'logs', arcname='mystic_data/logs')",
            "    write_signal('cycle_done', output_tar=str(output_tar))",
            "    print(output_tar)",
            "except Exception as exc:",
            "    write_signal('cycle_error', error=repr(exc), traceback=traceback.format_exc())",
            "    raise",
            "",
        ]
    )


def write_kaggle_dataset_metadata(dataset_dir: Path, *, dataset_ref: str, title: str) -> Path:
    payload = {
        "title": title,
        "id": dataset_ref,
        "licenses": [{"name": "CC0-1.0"}],
    }
    metadata_path = dataset_dir / "dataset-metadata.json"
    write_json(metadata_path, payload)
    write_json(dataset_dir / "datasets-metadata.json", payload)
    return metadata_path


def write_kaggle_kernel_metadata(
    kernel_dir: Path,
    *,
    kernel_ref: str,
    title: str,
    dataset_ref: str,
) -> Path:
    metadata_path = kernel_dir / "kernel-metadata.json"
    payload = {
        "id": kernel_ref,
        "title": title,
        "code_file": "train_mystic_raven.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": True,
        "dataset_data_sources": [dataset_ref],
        "dataset_sources": [dataset_ref],
        "competition_sources": [],
        "kernel_sources": [],
        "model_sources": [],
    }
    write_json(metadata_path, payload)
    return metadata_path


def wait_for_kaggle_dataset_ready(
    *,
    kaggle_cmd: list[str],
    dataset_ref: str,
    cwd: Path,
    env: dict[str, str] | None = None,
    poll_seconds: int = 10,
    timeout_minutes: int = 10,
) -> dict[str, Any]:
    started_at = time.monotonic()
    checks: list[dict[str, Any]] = []
    while True:
        try:
            result = run_raw_command([*kaggle_cmd, "datasets", "status", dataset_ref], cwd=cwd, env=env)
            stdout = result.stdout.strip() or result.stderr.strip()
            status = parse_kaggle_dataset_status_output(stdout)
        except subprocess.CalledProcessError as exc:
            stdout = (exc.stdout or "").strip() or (exc.stderr or "").strip()
            lowered = stdout.lower()
            if "authentication required" in lowered:
                raise RuntimeError(f"Kaggle authentication failed while polling dataset: {stdout}") from exc
            status = "running"
        snapshot = {"timestamp": now_iso(), "status": status, "raw": stdout}
        checks.append(snapshot)
        if status == "ready":
            return {"final_status": status, "checks": checks}
        if status == "failed":
            raise RuntimeError(f"Kaggle dataset failed: {stdout}")
        elapsed_minutes = (time.monotonic() - started_at) / 60.0
        if elapsed_minutes > timeout_minutes:
            raise TimeoutError(f"Kaggle dataset polling timed out after {timeout_minutes} minutes.")
        time.sleep(poll_seconds)


def wait_for_dataset_visibility_stabilization(seconds: int = 180) -> None:
    if seconds > 0:
        time.sleep(seconds)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local and Kaggle-backed Mystic cycle helper.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Verify files, optionally rebuild train/eval data, and create a Kaggle tarball.")
    prepare.add_argument("--cycle-id", required=True)
    prepare.add_argument("--base-dir", default=str(ROOT / "mystic_data"))
    prepare.add_argument("--package-out", default="")
    prepare.add_argument("--run-prepare-data", action="store_true", help="Run prepare_raven_training_data.py before packaging.")
    prepare.add_argument("--dataset-source", default="default", choices=["default", "research_table"])
    prepare.add_argument("--target", default="raven", choices=["raven"])
    prepare.add_argument("--include-adversarial-seeds", action="store_true")
    prepare.add_argument("--adversarial-path", default="")
    prepare.add_argument("--include-lab-failures", action="store_true")
    prepare.add_argument("--lab-failures-path", default="")
    prepare.add_argument("--max-lab-failure-rows", type=int, default=0)
    prepare.add_argument("--lab-failure-weight", type=int, default=1)
    prepare.add_argument("--min-invalid-rows", type=int, default=0)
    prepare.add_argument("--allow-low-invalid", action="store_true")
    prepare.add_argument("--limit", type=int, default=0, help="Optional total row limit for prepare_raven_training_data.py.")
    prepare.add_argument("--train-limit", type=int, default=0, help="Requested train row target for larger cycles.")
    prepare.add_argument("--eval-limit", type=int, default=0, help="Requested eval row target for larger cycles.")
    prepare.add_argument("--base-model", default="Qwen/Qwen2.5-0.5B-Instruct")
    prepare.add_argument("--adapter-path", default="mystic_data/adapters/raven_lora_v0")
    prepare.add_argument("--learning-rate", type=float, default=0.0002)
    prepare.add_argument("--epochs", type=int, default=1)
    prepare.add_argument("--batch-size", type=int, default=1)
    prepare.add_argument("--max-length", type=int, default=2048)

    submit = subparsers.add_parser("submit", help="Upload the cycle package to Kaggle and push a GPU kernel.")
    submit.add_argument("--cycle-id", required=True)
    submit.add_argument("--base-dir", default=str(ROOT / "mystic_data"))
    submit.add_argument("--kaggle-username", default="")
    submit.add_argument("--dataset-slug", default="")
    submit.add_argument("--kernel-slug", default="")
    submit.add_argument("--package-path", default="")
    submit.add_argument("--base-model", default="Qwen/Qwen2.5-0.5B-Instruct")
    submit.add_argument("--adapter-path", default="mystic_data/adapters/raven_lora_v0")
    submit.add_argument("--output-tar-name", default="")
    submit.add_argument("--learning-rate", type=float, default=0.0002)
    submit.add_argument("--epochs", type=int, default=1)
    submit.add_argument("--batch-size", type=int, default=1)
    submit.add_argument("--max-length", type=int, default=2048)

    poll = subparsers.add_parser("poll", help="Poll Kaggle kernel status until completion or failure.")
    poll.add_argument("--cycle-id", required=True)
    poll.add_argument("--base-dir", default=str(ROOT / "mystic_data"))
    poll.add_argument("--kernel-ref", default="")
    poll.add_argument("--poll-seconds", type=int, default=60)
    poll.add_argument("--timeout-minutes", type=int, default=240)

    download = subparsers.add_parser("download", help="Download Kaggle kernel outputs for a cycle.")
    download.add_argument("--cycle-id", required=True)
    download.add_argument("--base-dir", default=str(ROOT / "mystic_data"))
    download.add_argument("--kernel-ref", default="")
    download.add_argument("--output-tar-name", default="raven_lora_v0_qwen.tar.gz")

    finish = subparsers.add_parser("finish", help="Restore adapter, validate it, run reinjection, compare, and register.")
    finish.add_argument("--adapter-tar", required=True)
    finish.add_argument("--adapter-path", required=True)
    finish.add_argument("--base-model", required=True)
    finish.add_argument("--cycle-id", required=True)
    finish.add_argument("--run-limit", type=int, default=20)
    finish.add_argument("--compare-limit", type=int, default=100)
    finish.add_argument("--model-id", required=True)
    finish.add_argument("--base-dir", default=str(ROOT / "mystic_data"))
    finish.add_argument("--run-id", default="")
    finish.add_argument("--notes", default="")

    full = subparsers.add_parser("full", help="Run prepare -> Kaggle submit -> poll -> download -> finish automatically.")
    full.add_argument("--cycle-id", required=True)
    full.add_argument("--base-dir", default=str(ROOT / "mystic_data"))
    full.add_argument("--run-prepare-data", action="store_true")
    full.add_argument("--dataset-source", default="default", choices=["default", "research_table"])
    full.add_argument("--target", default="raven", choices=["raven"])
    full.add_argument("--include-adversarial-seeds", action="store_true")
    full.add_argument("--adversarial-path", default="")
    full.add_argument("--min-invalid-rows", type=int, default=0)
    full.add_argument("--allow-low-invalid", action="store_true")
    full.add_argument("--limit", type=int, default=0)
    full.add_argument("--train-limit", type=int, default=0)
    full.add_argument("--eval-limit", type=int, default=0)
    full.add_argument("--package-out", default="")
    full.add_argument("--kaggle-username", default="")
    full.add_argument("--dataset-slug", default="")
    full.add_argument("--kernel-slug", default="")
    full.add_argument("--base-model", default="Qwen/Qwen2.5-0.5B-Instruct")
    full.add_argument("--adapter-path", default="mystic_data/adapters/raven_lora_v0")
    full.add_argument("--model-id", default="raven_lora_v0_qwen_auto")
    full.add_argument("--output-tar-name", default="")
    full.add_argument("--learning-rate", type=float, default=0.0002)
    full.add_argument("--epochs", type=int, default=1)
    full.add_argument("--batch-size", type=int, default=1)
    full.add_argument("--max-length", type=int, default=2048)
    full.add_argument("--run-limit", type=int, default=20)
    full.add_argument("--compare-limit", type=int, default=100)
    full.add_argument("--poll-seconds", type=int, default=60)
    full.add_argument("--timeout-minutes", type=int, default=240)
    full.add_argument("--notes", default="")

    status = subparsers.add_parser("status", help="Print recent cycle summaries, model versions, adapter files, and recent run logs.")
    status.add_argument("--base-dir", default=str(ROOT / "mystic_data"))
    status.add_argument("--limit", type=int, default=5)

    return parser


def run_prepare(args: argparse.Namespace) -> int:
    verify_project_root(ROOT)
    base_dir = Path(args.base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    cycle_root = cycle_dir(base_dir, args.cycle_id)
    cycle_root.mkdir(parents=True, exist_ok=True)
    targets = resolve_prepare_targets(limit=args.limit, train_limit=args.train_limit, eval_limit=args.eval_limit)
    dataset_source = str(getattr(args, "dataset_source", "default") or "default")
    target_agent = str(getattr(args, "target", "raven") or "raven")
    include_adversarial_seeds = bool(getattr(args, "include_adversarial_seeds", False))
    adversarial_path_value = str(getattr(args, "adversarial_path", "") or "")
    adversarial_path = (
        Path(adversarial_path_value)
        if adversarial_path_value
        else base_dir / "datasets" / "raven" / "adversarial_seed_raven.jsonl"
    )
    include_lab_failures = bool(getattr(args, "include_lab_failures", False))
    lab_failures_path_value = str(getattr(args, "lab_failures_path", "") or "")
    lab_failures_path = (
        Path(lab_failures_path_value)
        if lab_failures_path_value
        else base_dir / "datasets" / "lab" / "raven_lab_failures.jsonl"
    )
    max_lab_failure_rows = int(getattr(args, "max_lab_failure_rows", 0) or 0)
    lab_failure_weight = int(getattr(args, "lab_failure_weight", 1) or 1)
    min_invalid_rows = int(getattr(args, "min_invalid_rows", 0) or 0)
    allow_low_invalid = bool(getattr(args, "allow_low_invalid", False))

    export_payload: dict[str, Any] | None = None
    export_stdout = ""
    prepared_dataset_path: Path | None = None
    split_payload: dict[str, Any] | None = None

    if dataset_source == "research_table":
        if target_agent != "raven":
            raise ValueError(f"Unsupported target for research_table dataset source: {target_agent}")
        if args.run_prepare_data or include_adversarial_seeds or include_lab_failures:
            command = [
                PYTHON_BIN,
                "scripts/prepare_research_table_training.py",
                "--target",
                target_agent,
                "--input",
                str(base_dir / "datasets" / "raven" / "research_table_raven.jsonl"),
                "--output",
                str(base_dir / "training" / "raven" / "research_table_train.jsonl"),
            ]
            if include_adversarial_seeds:
                command.extend(
                    [
                        "--include-adversarial-seeds",
                        "--adversarial-path",
                        str(adversarial_path),
                    ]
                )
            if include_lab_failures:
                command.extend(
                    [
                        "--include-lab-failures",
                        "--lab-failures-path",
                        str(lab_failures_path),
                        "--lab-failure-weight",
                        str(lab_failure_weight),
                    ]
                )
                if max_lab_failure_rows > 0:
                    command.extend(["--max-lab-failure-rows", str(max_lab_failure_rows)])
            if min_invalid_rows > 0:
                command.extend(["--min-invalid-rows", str(min_invalid_rows)])
            if allow_low_invalid:
                command.append("--allow-low-invalid")
            if int(targets["total_limit"]) > 0:
                command.extend(["--max-rows", str(int(targets["total_limit"]))])
            export_payload, export_stdout = run_command(command, cwd=ROOT)
        prepared_dataset_path = verify_prepared_dataset_file(base_dir / "training" / "raven" / "research_table_train.jsonl")
        split_payload = materialize_prepared_training_split(
            prepared_path=prepared_dataset_path,
            train_path=base_dir / "train_ready" / "raven_train.jsonl",
            eval_path=base_dir / "eval_holdout" / "raven_eval.jsonl",
            eval_ratio=float(targets["eval_ratio"]),
        )
    else:
        export_command = [PYTHON_BIN, "scripts/export_raven_lora.py", "--base-dir", str(base_dir)]
        if int(targets["total_limit"]) > 0:
            export_command.extend(["--target-rows", str(int(targets["total_limit"]))])
        export_payload, export_stdout = run_command(export_command, cwd=ROOT)
        prepared_dataset_path = verify_export_file(base_dir)

    prepare_payload: dict[str, Any] | None = None
    prepare_stdout = ""
    if args.run_prepare_data and dataset_source == "default":
        command = [
            PYTHON_BIN,
            "scripts/prepare_raven_training_data.py",
            "--input",
            str(base_dir / "train_ready" / "raven_lora.jsonl"),
            "--train-out",
            str(base_dir / "train_ready" / "raven_train.jsonl"),
            "--eval-out",
            str(base_dir / "eval_holdout" / "raven_eval.jsonl"),
            "--eval-ratio",
            str(targets["eval_ratio"]),
        ]
        if int(targets["total_limit"]) > 0:
            command.extend(["--limit", str(int(targets["total_limit"]))])
        prepare_payload, prepare_stdout = run_command(command, cwd=ROOT)

    training_files = verify_training_eval_files(base_dir)
    training_manifest_path = base_dir / "training" / "raven" / "manifest.json"
    training_manifest = read_json(training_manifest_path) if training_manifest_path.exists() else {}
    train_rows_count = len(read_jsonl(Path(training_files["train_file"])))
    eval_rows_count = len(read_jsonl(Path(training_files["eval_file"])))
    package_manifest = {
        "created_at": now_iso(),
        "cycle_id": args.cycle_id,
        "dataset_source": dataset_source,
        "target_agent": target_agent,
        "include_adversarial_seeds": include_adversarial_seeds,
        "adversarial_path": str(adversarial_path) if include_adversarial_seeds else "",
        "include_lab_failures": include_lab_failures,
        "lab_failures_path": str(lab_failures_path) if include_lab_failures else "",
        "lab_failure_weight": lab_failure_weight if include_lab_failures else 0,
        "research_table_rows": int(
            training_manifest.get("research_table_rows", (export_payload or {}).get("research_table_rows", 0))
        ),
        "adversarial_seed_rows": int(
            training_manifest.get("adversarial_seed_rows", (export_payload or {}).get("adversarial_seed_rows", 0))
        ),
        "lab_failure_rows": int(
            training_manifest.get("lab_failure_rows", (export_payload or {}).get("lab_failure_rows", 0))
        ),
        "combined_rows": int(
            training_manifest.get("combined_rows", (export_payload or {}).get("combined_rows", 0))
        ),
        "invalid_rows_count": int(
            training_manifest.get("invalid_rows_count", 0)
        ),
        "train_rows": train_rows_count,
        "eval_rows": eval_rows_count,
        "train_file": training_files["train_file"],
        "eval_file": training_files["eval_file"],
        "training_manifest_path": str(training_manifest_path) if training_manifest else "",
    }
    archived_package_manifest_path = base_dir / "training" / "raven" / "package_manifest.json"
    write_json(archived_package_manifest_path, package_manifest)
    cycle_package_manifest_path = cycle_root / "package_manifest.json"
    write_json(cycle_package_manifest_path, package_manifest)
    package_out = Path(args.package_out) if args.package_out else ROOT / f"mystic_gpu_train_package_{args.cycle_id}.tar.gz"
    package_path = create_kaggle_package(ROOT, package_out)
    kaggle_commands = build_kaggle_commands_md(
        cycle_id=args.cycle_id,
        package_path=package_path,
        base_model=args.base_model,
        adapter_path=args.adapter_path,
        output_tar_name=default_output_tar_name(args.adapter_path),
        learning_rate=args.learning_rate,
        epochs=args.epochs,
        batch_size=args.batch_size,
        max_length=args.max_length,
    )
    write_text(kaggle_commands_path(base_dir, args.cycle_id), kaggle_commands)

    payload = {
        "timestamp": now_iso(),
        "command": "prepare",
        "cycle_id": args.cycle_id,
        "project_root": str(ROOT),
        "base_dir": str(base_dir),
        "dataset_source": dataset_source,
        "target_agent": target_agent,
        "base_model": args.base_model,
        "adapter_path": args.adapter_path,
        "requested_split": targets,
        "prepared_dataset_file": str(prepared_dataset_path) if prepared_dataset_path else "",
        "training_files": training_files,
        "training_manifest_path": str(training_manifest_path) if training_manifest else "",
        "training_manifest": training_manifest,
        "package_manifest_path": str(cycle_package_manifest_path),
        "package_manifest": package_manifest,
        "package_path": str(package_path),
        "kaggle_commands_path": str(kaggle_commands_path(base_dir, args.cycle_id)),
        "package_size_bytes": package_path.stat().st_size,
        "ran_prepare_training_data": args.run_prepare_data or include_adversarial_seeds or include_lab_failures,
        "export_payload": export_payload,
        "prepare_payload": prepare_payload,
        "training_split_payload": split_payload,
        "stdout": {
            "dataset_prepare": export_stdout,
            "prepare_raven_training_data": prepare_stdout,
        },
    }
    write_json(prepare_summary_path(base_dir, args.cycle_id), payload)
    print(json.dumps(payload, indent=2))
    return 0


def run_submit(args: argparse.Namespace) -> int:
    verify_project_root(ROOT)
    username = args.kaggle_username or ensure_kaggle_ready()
    base_dir = Path(args.base_dir)
    cycle_root = cycle_dir(base_dir, args.cycle_id)
    cycle_root.mkdir(parents=True, exist_ok=True)
    prepare_summary = load_prepare_summary(base_dir, args.cycle_id)

    package_path = Path(args.package_path) if args.package_path else Path(str(prepare_summary["package_path"]))
    if not package_path.is_absolute():
        package_path = (ROOT / package_path).resolve()
    if not package_path.exists():
        raise FileNotFoundError(f"Cycle package not found: {package_path}")

    dataset_slug = args.dataset_slug or slugify(f"mystic-cycle-{args.cycle_id}")
    kernel_slug = args.kernel_slug or slugify(f"mystic-raven-{args.cycle_id}")
    dataset_ref = f"{username}/{dataset_slug}"
    kernel_ref = f"{username}/{kernel_slug}"
    adapter_dirname = Path(args.adapter_path).name
    kaggle_cmd = kaggle_command_prefix()
    output_tar_name = args.output_tar_name or default_output_tar_name(args.adapter_path)

    dataset_dir = kaggle_dataset_dir(base_dir, args.cycle_id)
    kernel_dir = kaggle_kernel_dir(base_dir, args.cycle_id)
    shutil.rmtree(dataset_dir, ignore_errors=True)
    shutil.rmtree(kernel_dir, ignore_errors=True)
    dataset_dir.mkdir(parents=True, exist_ok=True)
    kernel_dir.mkdir(parents=True, exist_ok=True)

    copied_package = dataset_dir / package_path.name
    shutil.copy2(package_path, copied_package)
    write_kaggle_dataset_metadata(
        dataset_dir,
        dataset_ref=dataset_ref,
        title=f"Mystic Cycle {args.cycle_id}",
    )
    bundled_kernel_package = kernel_dir / package_path.name
    shutil.copy2(package_path, bundled_kernel_package)

    training_script_path = kernel_dir / "train_mystic_raven.py"
    write_text(
        training_script_path,
        build_kaggle_training_script(
            cycle_id=args.cycle_id,
            dataset_slug=dataset_slug,
            package_filename=package_path.name,
            base_model=args.base_model,
            adapter_path=args.adapter_path,
            adapter_dirname=adapter_dirname,
            output_tar_name=output_tar_name,
            learning_rate=args.learning_rate,
            epochs=args.epochs,
            batch_size=args.batch_size,
            max_length=args.max_length,
        ),
    )
    write_kaggle_kernel_metadata(
        kernel_dir,
        kernel_ref=kernel_ref,
        title=f"Mystic Raven {args.cycle_id}",
        dataset_ref=dataset_ref,
    )
    submit_validation = validate_generated_kaggle_submit_artifacts(
        package_path=package_path,
        dataset_dir=dataset_dir,
        kernel_dir=kernel_dir,
        dataset_ref=dataset_ref,
        dataset_slug=dataset_slug,
        package_filename=package_path.name,
        training_script_path=training_script_path,
        output_tar_name=output_tar_name,
        adapter_path=args.adapter_path,
    )

    with kaggle_runtime_env() as kaggle_env:
        try:
            dataset_result = run_raw_command(
                [*kaggle_cmd, "datasets", "create", "-p", str(dataset_dir)],
                cwd=ROOT,
                env=kaggle_env,
            )
            if kaggle_dataset_create_needs_version(dataset_result.stdout, dataset_result.stderr):
                dataset_result = run_raw_command(
                    [*kaggle_cmd, "datasets", "version", "-p", str(dataset_dir), "-m", f"Mystic cycle {args.cycle_id} package update"],
                    cwd=ROOT,
                    env=kaggle_env,
                )
                dataset_action = "version"
            else:
                dataset_action = "create"
        except subprocess.CalledProcessError as exc:
            if not kaggle_dataset_create_needs_version(exc.stdout or "", exc.stderr or ""):
                payload = {
                    "timestamp": now_iso(),
                    "command": "submit",
                    "cycle_id": args.cycle_id,
                    "kaggle_username": username,
                    "dataset_slug": dataset_slug,
                    "dataset_ref": dataset_ref,
                    "kernel_ref": kernel_ref,
                    "package_path": str(package_path),
                    "package_filename": package_path.name,
                    "dataset_dir": str(dataset_dir),
                    "kernel_dir": str(kernel_dir),
                    "expected_kaggle_input_dir": f"/kaggle/input/{dataset_slug}",
                    "generated_kernel_path": str(training_script_path),
                    "output_tar_name": output_tar_name,
                    "adapter_path": args.adapter_path,
                    "dataset_action": "create_failed",
                    "dataset_stdout": (exc.stdout or "").strip(),
                    "dataset_stderr": (exc.stderr or "").strip(),
                    "dataset_returncode": exc.returncode,
                    "submit_validation": submit_validation,
                    "status": "SUBMIT_ERROR",
                }
                write_json(kaggle_submit_summary_path(base_dir, args.cycle_id), payload)
                raise RuntimeError(
                    "Kaggle dataset create failed. "
                    f"stdout={(exc.stdout or '').strip()!r} stderr={(exc.stderr or '').strip()!r}"
                ) from exc
            dataset_result = run_raw_command(
                [*kaggle_cmd, "datasets", "version", "-p", str(dataset_dir), "-m", f"Mystic cycle {args.cycle_id} package update"],
                cwd=ROOT,
                env=kaggle_env,
            )
            dataset_action = "version"
        dataset_status = wait_for_kaggle_dataset_ready(
            kaggle_cmd=kaggle_cmd,
            dataset_ref=dataset_ref,
            cwd=ROOT,
            env=kaggle_env,
        )
        wait_for_dataset_visibility_stabilization(60)
        try:
            kernel_result = run_raw_command([*kaggle_cmd, "kernels", "push", "-p", str(kernel_dir)], cwd=ROOT, env=kaggle_env)
        except subprocess.CalledProcessError as exc:
            kernel_stdout = (exc.stdout or "").strip()
            kernel_stderr = (exc.stderr or "").strip()
            kaggle_error = kernel_stdout or kernel_stderr
            failure_category = FAILURE_KAGGLE_GPU_QUOTA_EXCEEDED if is_kaggle_gpu_quota_error(kaggle_error) else "KAGGLE_KERNEL_PUSH_FAILED"
            payload = {
                "timestamp": now_iso(),
                "command": "submit",
                "cycle_id": args.cycle_id,
                "kaggle_username": username,
                "dataset_slug": dataset_slug,
                "dataset_ref": dataset_ref,
                "kernel_ref": kernel_ref,
                "package_path": str(package_path),
                "package_filename": package_path.name,
                "dataset_dir": str(dataset_dir),
                "kernel_dir": str(kernel_dir),
                "expected_kaggle_input_dir": f"/kaggle/input/{dataset_slug}",
                "generated_kernel_path": str(training_script_path),
                "output_tar_name": output_tar_name,
                "adapter_path": args.adapter_path,
                "dataset_action": dataset_action,
                "dataset_stdout": dataset_result.stdout.strip(),
                "dataset_status": dataset_status,
                "kernel_stdout": kernel_stdout,
                "kernel_stderr": kernel_stderr,
                "kernel_push_succeeded": False,
                "submit_succeeded": False,
                "training_started": False,
                "failure_category": failure_category,
                "kaggle_error": kaggle_error,
                "next_action": "Wait for Kaggle GPU quota reset or use an environment with available GPU quota, then intentionally rerun submit with the same prepared package."
                if failure_category == FAILURE_KAGGLE_GPU_QUOTA_EXCEEDED
                else "Inspect the Kaggle kernel push error and intentionally rerun submit once the submission problem is resolved.",
                "submit_validation": submit_validation,
            }
            write_json(kaggle_submit_summary_path(base_dir, args.cycle_id), payload)
            if failure_category == FAILURE_KAGGLE_GPU_QUOTA_EXCEEDED:
                print(json.dumps(payload, indent=2))
                return 1
            raise RuntimeError(
                "Kaggle kernel push failed. "
                f"stdout={kernel_stdout!r} stderr={kernel_stderr!r}"
            ) from exc

    kernel_stdout = kernel_result.stdout.strip()
    kernel_stderr = kernel_result.stderr.strip()
    kaggle_error = kernel_stdout or kernel_stderr
    if is_kaggle_gpu_quota_error(kaggle_error):
        payload = {
            "timestamp": now_iso(),
            "command": "submit",
            "cycle_id": args.cycle_id,
            "kaggle_username": username,
            "dataset_slug": dataset_slug,
            "dataset_ref": dataset_ref,
            "kernel_ref": kernel_ref,
            "package_path": str(package_path),
            "package_filename": package_path.name,
            "dataset_dir": str(dataset_dir),
            "kernel_dir": str(kernel_dir),
            "expected_kaggle_input_dir": f"/kaggle/input/{dataset_slug}",
            "generated_kernel_path": str(training_script_path),
            "output_tar_name": output_tar_name,
            "adapter_path": args.adapter_path,
            "dataset_action": dataset_action,
            "dataset_stdout": dataset_result.stdout.strip(),
            "dataset_status": dataset_status,
            "kernel_stdout": kernel_stdout,
            "kernel_stderr": kernel_stderr,
            "kernel_push_succeeded": False,
            "submit_succeeded": False,
            "training_started": False,
            "failure_category": FAILURE_KAGGLE_GPU_QUOTA_EXCEEDED,
            "kaggle_error": kaggle_error,
            "next_action": "Wait for Kaggle GPU quota reset or use an environment with available GPU quota, then intentionally rerun submit with the same prepared package.",
            "submit_validation": submit_validation,
        }
        write_json(kaggle_submit_summary_path(base_dir, args.cycle_id), payload)
        print(json.dumps(payload, indent=2))
        return 1

    payload = {
        "timestamp": now_iso(),
        "command": "submit",
        "cycle_id": args.cycle_id,
        "kaggle_username": username,
        "dataset_slug": dataset_slug,
        "dataset_ref": dataset_ref,
        "kernel_ref": kernel_ref,
        "package_path": str(package_path),
        "package_filename": package_path.name,
        "dataset_dir": str(dataset_dir),
        "kernel_dir": str(kernel_dir),
        "expected_kaggle_input_dir": f"/kaggle/input/{dataset_slug}",
        "generated_kernel_path": str(training_script_path),
        "output_tar_name": output_tar_name,
        "adapter_path": args.adapter_path,
        "dataset_action": dataset_action,
        "dataset_stdout": dataset_result.stdout.strip(),
        "dataset_status": dataset_status,
        "kernel_stdout": kernel_stdout,
        "kernel_stderr": kernel_stderr,
        "kernel_push_succeeded": True,
        "submit_succeeded": True,
        "training_started": True,
        "submit_validation": submit_validation,
    }
    write_json(kaggle_submit_summary_path(base_dir, args.cycle_id), payload)
    print(json.dumps(payload, indent=2))
    return 0


def run_poll(args: argparse.Namespace) -> int:
    verify_project_root(ROOT)
    ensure_kaggle_ready()
    base_dir = Path(args.base_dir)
    submit_summary = load_submit_summary(base_dir, args.cycle_id)
    kernel_ref = args.kernel_ref or str(submit_summary["kernel_ref"])
    kaggle_cmd = kaggle_command_prefix()
    started_at = time.monotonic()
    statuses: list[dict[str, Any]] = []

    with kaggle_runtime_env() as kaggle_env:
        while True:
            try:
                result = run_raw_command([*kaggle_cmd, "kernels", "status", kernel_ref], cwd=ROOT, env=kaggle_env)
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
            statuses.append(snapshot)

            probe_dir = kaggle_output_dir(base_dir, args.cycle_id) / "probe"
            signal_probe = probe_kernel_output_signal(
                kaggle_cmd=kaggle_cmd,
                kernel_ref=kernel_ref,
                output_dir=probe_dir,
                env=kaggle_env,
            )
            if signal_probe is not None:
                signal_payload = signal_probe.get("signal_payload", {})
                signal_status = str(signal_payload.get("status", "")).lower()
                if signal_status == "cycle_done":
                    payload = {
                        "timestamp": now_iso(),
                        "command": "poll",
                        "cycle_id": args.cycle_id,
                        "kernel_ref": kernel_ref,
                        "final_status": "complete",
                        "checks": statuses,
                        "signal_probe": signal_probe,
                    }
                    write_json(kaggle_poll_summary_path(base_dir, args.cycle_id), payload)
                    print(json.dumps(payload, indent=2))
                    return 0
                if signal_status == "cycle_error":
                    write_json(
                        kaggle_poll_summary_path(base_dir, args.cycle_id),
                        {
                            "timestamp": now_iso(),
                            "command": "poll",
                            "cycle_id": args.cycle_id,
                            "kernel_ref": kernel_ref,
                            "final_status": "failed",
                            "checks": statuses,
                            "failure_output": signal_probe,
                        },
                    )
                    raise RuntimeError(f"Kaggle kernel failed via signal: {signal_payload}")

            if status == "complete":
                break
            if status == "failed":
                failure_output_payload: dict[str, Any] = {}
                failure_output_dir = kaggle_output_dir(base_dir, args.cycle_id) / "failure"
                failure_output_dir.mkdir(parents=True, exist_ok=True)
                try:
                    output_result = run_raw_command(
                        [*kaggle_cmd, "kernels", "output", kernel_ref, "-p", str(failure_output_dir), "-o"],
                        cwd=ROOT,
                        env=kaggle_env,
                    )
                    signal_file = locate_cycle_signal_file(failure_output_dir)
                    failure_output_payload = {
                        "output_dir": str(failure_output_dir),
                        "stdout": output_result.stdout.strip(),
                        "signal_file": str(signal_file) if signal_file is not None else None,
                        "signal_payload": read_json(signal_file) if signal_file is not None else None,
                    }
                except Exception as output_exc:  # pragma: no cover - depends on Kaggle availability
                    failure_output_payload = {"output_dir": str(failure_output_dir), "error": repr(output_exc)}
                write_json(
                    kaggle_poll_summary_path(base_dir, args.cycle_id),
                    {
                        "timestamp": now_iso(),
                        "command": "poll",
                        "cycle_id": args.cycle_id,
                        "kernel_ref": kernel_ref,
                        "final_status": status,
                        "checks": statuses,
                        "failure_output": failure_output_payload,
                    },
                )
                raise RuntimeError(f"Kaggle kernel failed: {stdout}")
            elapsed_minutes = (time.monotonic() - started_at) / 60.0
            if elapsed_minutes > args.timeout_minutes:
                raise TimeoutError(f"Kaggle kernel polling timed out after {args.timeout_minutes} minutes.")
            time.sleep(args.poll_seconds)

    payload = {
        "timestamp": now_iso(),
        "command": "poll",
        "cycle_id": args.cycle_id,
        "kernel_ref": kernel_ref,
        "final_status": "complete",
        "checks": statuses,
    }
    write_json(kaggle_poll_summary_path(base_dir, args.cycle_id), payload)
    print(json.dumps(payload, indent=2))
    return 0


def run_download(args: argparse.Namespace) -> int:
    verify_project_root(ROOT)
    ensure_kaggle_ready()
    base_dir = Path(args.base_dir)
    submit_summary = load_submit_summary(base_dir, args.cycle_id)
    kernel_ref = args.kernel_ref or str(submit_summary["kernel_ref"])
    kaggle_cmd = kaggle_command_prefix()
    output_dir = kaggle_output_dir(base_dir, args.cycle_id)
    shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    expected_tar_name = args.output_tar_name or str(submit_summary.get("output_tar_name", "")).strip() or default_output_tar_name("mystic_data/adapters/raven_lora_v0")
    with kaggle_runtime_env() as kaggle_env:
        result = run_raw_command([*kaggle_cmd, "kernels", "output", kernel_ref, "-p", str(output_dir)], cwd=ROOT, env=kaggle_env)
    adapter_tar = locate_downloaded_adapter_tar(output_dir, expected_tar_name)
    signal_file = locate_cycle_signal_file(output_dir)
    signal_payload = read_json(signal_file) if signal_file is not None else None
    payload = {
        "timestamp": now_iso(),
        "command": "download",
        "cycle_id": args.cycle_id,
        "kernel_ref": kernel_ref,
        "output_dir": str(output_dir),
        "adapter_tar": str(adapter_tar),
        "output_tar_name": expected_tar_name,
        "signal_file": str(signal_file) if signal_file is not None else None,
        "signal_payload": signal_payload,
        "stdout": result.stdout.strip(),
    }
    write_json(kaggle_download_summary_path(base_dir, args.cycle_id), payload)
    print(json.dumps(payload, indent=2))
    return 0


def run_finish(args: argparse.Namespace) -> int:
    verify_project_root(ROOT)
    base_dir = Path(args.base_dir)
    cycle_root = cycle_dir(base_dir, args.cycle_id)
    cycle_root.mkdir(parents=True, exist_ok=True)

    adapter_tar = Path(args.adapter_tar).expanduser().resolve()
    if not adapter_tar.exists():
        raise FileNotFoundError(f"Adapter tar not found: {adapter_tar}")

    adapter_path = Path(args.adapter_path)
    if not adapter_path.is_absolute():
        adapter_path = (ROOT / adapter_path).resolve()

    extracted_files = safe_extract_adapter_tar(adapter_tar, ROOT)
    validation = validate_adapter_files(adapter_path, args.base_model)
    processed_backup = backup_and_clear_processed_ids(base_dir, args.cycle_id)
    run_id = args.run_id or f"{args.cycle_id}_reinjection"

    loop_payload, loop_stdout = run_command(
        [
            PYTHON_BIN,
            "scripts/mystic_loop.py",
            "--base-dir",
            str(base_dir),
            "--limit",
            str(args.run_limit),
            "--backend",
            "adapter",
            "--base-model",
            args.base_model,
            "--adapter-path",
            str(adapter_path),
            "--run-id",
            run_id,
        ],
        cwd=ROOT,
    )
    processed_count = int(loop_payload.get("processed_count", 0))
    if processed_count <= 0:
        raise ValueError("mystic_loop.py completed but processed_count <= 0.")

    compare_payload, compare_stdout = run_command(
        [
            PYTHON_BIN,
            "scripts/compare_raven_models.py",
            "--base-model",
            args.base_model,
            "--adapter-path",
            str(adapter_path),
            "--eval-file",
            str(base_dir / "eval_holdout" / "raven_eval.jsonl"),
            "--limit",
            str(args.compare_limit),
        ],
        cwd=ROOT,
    )
    metrics = compare_payload.get("metrics", {})
    adapter_better_or_equal_rate = metrics.get("adapter_better_or_equal_rate")
    if adapter_better_or_equal_rate is None:
        raise ValueError("compare_raven_models.py output missing adapter_better_or_equal_rate.")

    register_payload, register_stdout = run_command(
        [
            PYTHON_BIN,
            "scripts/register_model.py",
            "--model-id",
            args.model_id,
            "--base-model",
            args.base_model,
            "--adapter-path",
            str(adapter_path),
            "--metrics",
            json.dumps(metrics),
            "--notes",
            args.notes or f"Registered by run_mystic_cycle finish for {args.cycle_id}",
        ],
        cwd=ROOT,
    )

    payload = {
        "timestamp": now_iso(),
        "command": "finish",
        "cycle_id": args.cycle_id,
        "adapter_tar": str(adapter_tar),
        "adapter_path": str(adapter_path),
        "base_model": args.base_model,
        "model_id": args.model_id,
        "run_id": run_id,
        "extracted_files_count": len(extracted_files),
        "validation": validation,
        "processed_backup": processed_backup,
        "processed_count": processed_count,
        "adapter_better_or_equal_rate": adapter_better_or_equal_rate,
        "loop_payload": loop_payload,
        "compare_payload": compare_payload,
        "register_payload": register_payload,
        "stdout": {
            "mystic_loop": loop_stdout,
            "compare_raven_models": compare_stdout,
            "register_model": register_stdout,
        },
    }
    write_json(cycle_summary_path(base_dir, args.cycle_id), payload)
    print(json.dumps(payload, indent=2))
    return 0


def run_full(args: argparse.Namespace) -> int:
    prepare_args = argparse.Namespace(
        cycle_id=args.cycle_id,
        base_dir=args.base_dir,
        package_out=args.package_out,
        run_prepare_data=args.run_prepare_data,
        dataset_source=args.dataset_source,
        target=args.target,
        include_adversarial_seeds=getattr(args, "include_adversarial_seeds", False),
        adversarial_path=getattr(args, "adversarial_path", ""),
        min_invalid_rows=getattr(args, "min_invalid_rows", 0),
        allow_low_invalid=getattr(args, "allow_low_invalid", False),
        limit=args.limit,
        train_limit=args.train_limit,
        eval_limit=args.eval_limit,
        base_model=args.base_model,
        adapter_path=args.adapter_path,
        learning_rate=args.learning_rate,
        epochs=args.epochs,
        batch_size=args.batch_size,
        max_length=args.max_length,
    )
    run_prepare(prepare_args)

    submit_args = argparse.Namespace(
        cycle_id=args.cycle_id,
        base_dir=args.base_dir,
        kaggle_username=args.kaggle_username,
        dataset_slug=args.dataset_slug,
        kernel_slug=args.kernel_slug,
        package_path=args.package_out,
        base_model=args.base_model,
        adapter_path=args.adapter_path,
        output_tar_name=args.output_tar_name,
        learning_rate=args.learning_rate,
        epochs=args.epochs,
        batch_size=args.batch_size,
        max_length=args.max_length,
    )
    run_submit(submit_args)

    poll_args = argparse.Namespace(
        cycle_id=args.cycle_id,
        base_dir=args.base_dir,
        kernel_ref="",
        poll_seconds=args.poll_seconds,
        timeout_minutes=args.timeout_minutes,
    )
    run_poll(poll_args)

    download_args = argparse.Namespace(
        cycle_id=args.cycle_id,
        base_dir=args.base_dir,
        kernel_ref="",
        output_tar_name=args.output_tar_name or default_output_tar_name(args.adapter_path),
    )
    run_download(download_args)
    download_summary = read_json(kaggle_download_summary_path(Path(args.base_dir), args.cycle_id))

    finish_args = argparse.Namespace(
        adapter_tar=str(download_summary["adapter_tar"]),
        adapter_path=args.adapter_path,
        base_model=args.base_model,
        cycle_id=args.cycle_id,
        run_limit=args.run_limit,
        compare_limit=args.compare_limit,
        model_id=args.model_id,
        base_dir=args.base_dir,
        run_id=f"{args.cycle_id}_reinjection",
        notes=args.notes,
    )
    return run_finish(finish_args)


def run_status(args: argparse.Namespace) -> int:
    verify_project_root(ROOT)
    base_dir = Path(args.base_dir)
    registry_path = base_dir / "metadata" / "model_versions.json"
    run_log_path = base_dir / "logs" / "run_log.jsonl"
    adapter_root = base_dir / "adapters"

    summaries = latest_cycle_summaries(base_dir, limit=args.limit)
    registry = read_json(registry_path) if registry_path.exists() else {"models": []}
    adapter_files = sorted(str(path) for path in adapter_root.glob("*") if path.exists())
    recent_run_logs = read_jsonl(run_log_path)[-args.limit:]
    adapter_status = current_adapter_status(base_dir)

    payload = {
        "timestamp": now_iso(),
        "command": "status",
        "project_root": str(ROOT),
        "recent_cycle_summaries": summaries,
        "registered_model_versions": registry.get("models", []),
        "current_adapter_status": adapter_status,
        "adapter_files": adapter_files,
        "recent_run_logs": recent_run_logs,
        "processed_ids_count": processed_ids_count(base_dir / "state" / "processed_ids.jsonl"),
    }
    print(json.dumps(payload, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "prepare":
        return run_prepare(args)
    if args.command == "submit":
        return run_submit(args)
    if args.command == "poll":
        return run_poll(args)
    if args.command == "download":
        return run_download(args)
    if args.command == "finish":
        return run_finish(args)
    if args.command == "full":
        return run_full(args)
    if args.command == "status":
        return run_status(args)
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
