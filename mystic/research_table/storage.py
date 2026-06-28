from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ResearchTableStorage:
    def __init__(self, root_path: str | Path) -> None:
        self.root_path = Path(root_path)
        self.base_dir = self.root_path / "mystic_data" / "research_table_sessions"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_session(self, session_id: str, payload: dict[str, Any]) -> dict[str, str]:
        session_dir = self.base_dir / session_id
        return self.save_session_dir(session_dir=session_dir, payload=payload)

    def load_session(self, session_id: str) -> dict[str, Any]:
        session_dir = self.base_dir / session_id
        session_path = session_dir / "session.json"
        if not session_path.exists():
            raise FileNotFoundError(session_path)
        payload = json.loads(session_path.read_text(encoding="utf-8"))
        payload["turns"] = self._load_optional_json(session_dir / "turns.json", payload.get("turns", []))
        payload["discoveries"] = self._load_optional_json(session_dir / "discoveries.json", payload.get("discoveries", []))
        payload["verification_requests"] = self._load_optional_json(
            session_dir / "verification_requests.json",
            payload.get("verification_requests", []),
        )
        payload["final_synthesis_package"] = self._load_optional_json(
            session_dir / "final_synthesis.json",
            payload.get("final_synthesis_package", {}),
        )
        return payload

    def save_session_dir(self, *, session_dir: Path, payload: dict[str, Any]) -> dict[str, str]:
        session_dir.mkdir(parents=True, exist_ok=True)
        session_path = session_dir / "session.json"
        turns_path = session_dir / "turns.json"
        discoveries_path = session_dir / "discoveries.json"
        requests_path = session_dir / "verification_requests.json"
        synthesis_path = session_dir / "final_synthesis.json"

        session_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        turns_path.write_text(json.dumps(payload.get("turns", []), indent=2), encoding="utf-8")
        discoveries_path.write_text(json.dumps(payload.get("discoveries", []), indent=2), encoding="utf-8")
        requests_path.write_text(json.dumps(payload.get("verification_requests", []), indent=2), encoding="utf-8")
        synthesis_path.write_text(json.dumps(payload.get("final_synthesis_package", {}), indent=2), encoding="utf-8")
        return {
            "session": str(session_path),
            "turns": str(turns_path),
            "discoveries": str(discoveries_path),
            "verification_requests": str(requests_path),
            "final_synthesis": str(synthesis_path),
        }

    @staticmethod
    def _load_optional_json(path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return default
