from __future__ import annotations

from mystic.lab.session import MemoryEdge


def make_edge(*, session_id: str, from_id: str, to_id: str, relation: str, evidence: str) -> MemoryEdge:
    return MemoryEdge(
        session_id=session_id,
        from_id=from_id,
        to_id=to_id,
        relation=relation,
        evidence=evidence,
    )

