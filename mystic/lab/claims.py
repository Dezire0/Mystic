from __future__ import annotations

from mystic.lab.reality_anchor import normalize_claim_status
from mystic.lab.session import Claim, LabTurn


def claims_from_turn(session_id: str, turn: LabTurn) -> list[Claim]:
    claims: list[Claim] = []
    for item in turn.extracted_claims:
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        claims.append(
            Claim(
                session_id=session_id,
                text=text,
                claim_type=str(item.get("claim_type", "hypothesis")),
                status=normalize_claim_status(model_generated=True),
                confidence=str(item.get("confidence", "low")),
                source_turn_id=turn.turn_id,
            )
        )
    return claims

