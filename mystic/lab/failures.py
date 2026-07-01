from __future__ import annotations

from mystic.lab.session import Failure


def make_failure(
    *,
    session_id: str,
    claim_id: str,
    source_turn_id: str,
    first_fatal_error: str,
    failure_type: str,
    lesson: str,
    reusable_as_training_data: bool = True,
) -> Failure:
    return Failure(
        session_id=session_id,
        claim_id=claim_id,
        source_turn_id=source_turn_id,
        first_fatal_error=first_fatal_error,
        failure_type=failure_type,
        lesson=lesson,
        reusable_as_training_data=reusable_as_training_data,
    )

