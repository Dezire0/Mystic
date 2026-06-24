"""Session access helpers."""

from __future__ import annotations

from mystic.memory.archive import ArchiveStore


class SessionService:
    def __init__(self, archive: ArchiveStore) -> None:
        self.archive = archive

    def list_sessions(self) -> list[dict]:
        return self.archive.list_sessions()

    def get_session(self, session_id: str) -> dict:
        return self.archive.get_session(session_id)

