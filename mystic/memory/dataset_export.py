"""Dataset export facade."""

from __future__ import annotations

from mystic.memory.archive import ArchiveStore


def export_datasets(archive: ArchiveStore, export_type: str) -> list[str]:
    return archive.export_dataset(export_type)

