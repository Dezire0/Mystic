from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mystic.lab.session import Claim, Experiment, Failure, LabSession, LabSessionBundle, LabTurn, MemoryEdge
from mystic.lab.schema import PHASE_TO_ROOM


class LabStorage:
    def __init__(self, root_path: str | Path) -> None:
        self.root_path = Path(root_path)
        self.base_dir = self.root_path / "mystic_data" / "lab_sessions"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def session_dir(self, session_id: str) -> Path:
        return self.base_dir / session_id

    def save_bundle(self, bundle: LabSessionBundle) -> dict[str, str]:
        session_dir = self.session_dir(bundle.session.session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "artifacts").mkdir(exist_ok=True)
        (session_dir / "summaries").mkdir(exist_ok=True)

        paths = {
            "session": session_dir / "session.json",
            "turns": session_dir / "turns.json",
            "claims": session_dir / "claims.json",
            "experiments": session_dir / "experiments.json",
            "failures": session_dir / "failures.json",
            "memory_edges": session_dir / "memory_edges.json",
            "notebook": session_dir / "notebook.md",
            "report": session_dir / "report.md",
        }
        bundle.session.artifact_paths = {name: str(path) for name, path in paths.items()}
        bundle.session.active_room = PHASE_TO_ROOM.get(bundle.session.current_phase, bundle.session.active_room)

        paths["session"].write_text(json.dumps(bundle.session.to_dict(), indent=2), encoding="utf-8")
        paths["turns"].write_text(json.dumps([item.to_dict() for item in bundle.turns], indent=2), encoding="utf-8")
        paths["claims"].write_text(json.dumps([item.to_dict() for item in bundle.claims], indent=2), encoding="utf-8")
        paths["experiments"].write_text(
            json.dumps([item.to_dict() for item in bundle.experiments], indent=2), encoding="utf-8"
        )
        paths["failures"].write_text(json.dumps([item.to_dict() for item in bundle.failures], indent=2), encoding="utf-8")
        paths["memory_edges"].write_text(
            json.dumps([item.to_dict() for item in bundle.memory_edges], indent=2), encoding="utf-8"
        )
        paths["notebook"].write_text(bundle.notebook_markdown or "", encoding="utf-8")
        paths["report"].write_text(bundle.report_markdown or "", encoding="utf-8")
        return {name: str(path) for name, path in paths.items()}

    def load_bundle(self, session_id: str) -> LabSessionBundle:
        session_dir = self.session_dir(session_id)
        session_payload = self._load_json(session_dir / "session.json")
        if not isinstance(session_payload, dict):
            raise FileNotFoundError(session_dir / "session.json")
        bundle = LabSessionBundle(
            session=LabSession(**session_payload),
            turns=[LabTurn(**payload) for payload in self._load_json(session_dir / "turns.json", [])],
            claims=[Claim(**payload) for payload in self._load_json(session_dir / "claims.json", [])],
            experiments=[Experiment(**payload) for payload in self._load_json(session_dir / "experiments.json", [])],
            failures=[Failure(**payload) for payload in self._load_json(session_dir / "failures.json", [])],
            memory_edges=[MemoryEdge(**payload) for payload in self._load_json(session_dir / "memory_edges.json", [])],
            notebook_markdown=(session_dir / "notebook.md").read_text(encoding="utf-8")
            if (session_dir / "notebook.md").exists()
            else "",
            report_markdown=(session_dir / "report.md").read_text(encoding="utf-8")
            if (session_dir / "report.md").exists()
            else "",
        )
        return bundle

    @staticmethod
    def _load_json(path: Path, default: Any | None = None) -> Any:
        if not path.exists():
            return [] if default is None else default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return [] if default is None else default

