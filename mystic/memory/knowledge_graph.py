"""Simple local knowledge graph placeholder for v0.1."""

from __future__ import annotations

import json
from pathlib import Path


class KnowledgeGraphStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(json.dumps({"nodes": [], "edges": []}, indent=2), encoding="utf-8")

    def load(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

