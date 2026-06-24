"""Hugging Face integration for dataset resolution and sampling."""

from __future__ import annotations

import json
from pathlib import Path

from mystic.training.blueprints import INGESTION_SOURCES, write_json


def get_hf_auth_status() -> dict[str, object]:
    try:
        from huggingface_hub import get_token
    except ModuleNotFoundError:
        return {"token_present": False, "available": False}

    token = get_token()
    payload = {"token_present": bool(token), "available": True}
    if token:
        try:
            payload["whoami"] = _make_hf_api(token=token).whoami()
        except Exception as exc:
            payload["whoami_error"] = repr(exc)
    return payload


def resolve_hf_datasets(base_dir: str | Path, limit: int = 5) -> dict[str, object]:
    root = Path(base_dir)
    out_root = root / "metadata" / "huggingface"
    out_root.mkdir(parents=True, exist_ok=True)
    api = _make_hf_api()
    resolutions = []

    for source in INGESTION_SOURCES:
        if source["source_type"] != "public_dataset":
            continue
        query = source.get("hf_search") or source["name"]
        candidates = []
        for dataset in api.list_datasets(search=query, limit=limit):
            candidates.append({"id": dataset.id})
        resolved = {
            "slug": source["slug"],
            "name": source["name"],
            "query": query,
            "preferred_repo_id": source.get("preferred_repo_id"),
            "candidates": candidates,
        }
        write_json(out_root / f"{source['slug']}.json", resolved)
        resolutions.append(resolved)

    registry = {"auth": get_hf_auth_status(), "sources": resolutions}
    write_json(out_root / "registry.json", registry)
    return {"registry_path": str(out_root / "registry.json"), "count": len(resolutions)}


def download_hf_samples(base_dir: str | Path, slugs: list[str] | None = None, max_rows: int = 3) -> dict[str, object]:
    root = Path(base_dir)
    sample_root = root / "raw"
    results = []
    sources = [source for source in INGESTION_SOURCES if source["source_type"] == "public_dataset"]
    if slugs:
        allowed = set(slugs)
        sources = [source for source in sources if source["slug"] in allowed]

    for source in sources:
        repo_id = source.get("preferred_repo_id")
        if not repo_id:
            results.append({"slug": source["slug"], "status": "skipped", "reason": "no_preferred_repo_id"})
            continue
        try:
            sample_info = _download_dataset_sample(sample_root, source["slug"], repo_id, max_rows)
        except Exception as exc:
            fallback = _try_snapshot_fallback(sample_root, source["slug"], repo_id, exc)
            if fallback is not None:
                results.append({"slug": source["slug"], "repo_id": repo_id, "status": "snapshot_fallback", **fallback})
                continue
            results.append({"slug": source["slug"], "repo_id": repo_id, "status": "error", "error": repr(exc)})
            continue
        results.append({"slug": source["slug"], "repo_id": repo_id, "status": "ok", **sample_info})

    registry_path = root / "metadata" / "huggingface" / "sample_downloads.json"
    write_json(registry_path, {"results": results})
    return {"results": results, "registry_path": str(registry_path)}


def _download_dataset_sample(sample_root: Path, slug: str, repo_id: str, max_rows: int) -> dict[str, object]:
    from datasets import load_dataset

    config = _first_config(repo_id)
    split = _first_split(repo_id, config)
    kwargs = {"path": repo_id, "split": split, "streaming": True}
    if config is not None:
        kwargs["name"] = config
    dataset = load_dataset(**kwargs)
    rows = []
    for index, row in enumerate(dataset):
        if index >= max_rows:
            break
        rows.append(row)

    raw_dir = sample_root / slug
    raw_dir.mkdir(parents=True, exist_ok=True)
    sample_path = raw_dir / "sample.jsonl"
    sample_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=True) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )
    manifest = {
        "repo_id": repo_id,
        "config": config,
        "split": split,
        "rows": len(rows),
        "sample_path": str(sample_path),
    }
    write_json(raw_dir / "sample_manifest.json", manifest)
    return manifest


def _first_config(repo_id: str) -> str | None:
    from datasets import get_dataset_config_names

    try:
        configs = get_dataset_config_names(repo_id)
    except Exception:
        return None
    return configs[0] if configs else None


def _first_split(repo_id: str, config: str | None) -> str:
    from datasets import get_dataset_split_names

    kwargs = {"path": repo_id}
    if config is not None:
        kwargs["config_name"] = config
    try:
        splits = get_dataset_split_names(**kwargs)
    except Exception:
        return "train"
    return splits[0] if splits else "train"


def _try_snapshot_fallback(sample_root: Path, slug: str, repo_id: str, exc: Exception) -> dict[str, object] | None:
    if "Dataset scripts are no longer supported" not in repr(exc):
        return None
    from huggingface_hub import snapshot_download

    raw_dir = sample_root / slug / "snapshot"
    raw_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_download(
        repo_id=repo_id,
        repo_type="dataset",
        local_dir=str(raw_dir),
        allow_patterns=["README*", "*.py", "*.json", "*.md", "*.yaml", "*.yml"],
    )
    manifest = {
        "repo_id": repo_id,
        "snapshot_path": str(snapshot_path),
        "reason": "dataset_script_fallback",
    }
    write_json(sample_root / slug / "snapshot_manifest.json", manifest)
    return manifest


def _make_hf_api(token: str | None = None):
    from huggingface_hub import HfApi

    return HfApi(token=token)
