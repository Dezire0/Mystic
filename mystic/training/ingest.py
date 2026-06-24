"""Dataset ingestion scaffolds aligned to the checklist."""

from __future__ import annotations

from pathlib import Path
import json

from mystic.training.blueprints import INGESTION_SOURCES, write_json


def build_ingestion_registry(base_dir: str | Path) -> dict[str, object]:
    root = Path(base_dir)
    metadata_root = root / "metadata" / "ingestion"
    raw_root = root / "raw"
    processed_root = root / "processed" / "public_datasets"
    metadata_root.mkdir(parents=True, exist_ok=True)
    processed_root.mkdir(parents=True, exist_ok=True)

    registry = {"sources": []}
    created: list[str] = []

    for source in INGESTION_SOURCES:
        source_slug = source["slug"]
        raw_dir = raw_root / source_slug
        processed_dir = processed_root / source_slug
        raw_dir.mkdir(parents=True, exist_ok=True)
        processed_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            **source,
            "raw_dir": str(raw_dir),
            "processed_dir": str(processed_dir),
            "raw_readme": str(raw_dir / "README.md"),
            "processed_manifest": str(processed_dir / "manifest.json"),
        }
        _write_if_missing(
            raw_dir / "README.md",
            _raw_readme_text(source["name"], source_slug, source["recommended_target_agents"]),
        )
        write_json(processed_dir / "manifest.json", manifest)
        write_json(metadata_root / f"{source_slug}.json", manifest)
        registry["sources"].append(manifest)
        created.append(str(metadata_root / f"{source_slug}.json"))

    write_json(metadata_root / "registry.json", registry)
    created.append(str(metadata_root / "registry.json"))
    return {"registry_path": str(metadata_root / "registry.json"), "manifests": created}


def _raw_readme_text(name: str, slug: str, agents: list[str]) -> str:
    return (
        f"# {name}\n\n"
        f"Slug: `{slug}`\n\n"
        "Place original downloaded files for this dataset here.\n\n"
        f"Recommended target agents: {', '.join(agents)}\n"
    )


def _write_if_missing(path: Path, text: str) -> None:
    if not path.exists():
        path.write_text(text, encoding="utf-8")
