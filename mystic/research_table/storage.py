from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ResearchTableStorage:
    def __init__(self, root_path: str | Path) -> None:
        self.root_path = Path(root_path)
        self.base_dir = self.root_path / "mystic_data" / "research_table_sessions"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_session(self, session_id: str, payload: dict[str, Any]) -> Path:
        session_dir = self.base_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        path = session_dir / "session.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path
