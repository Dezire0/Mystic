from __future__ import annotations

from typing import Any, Callable

from mystic.debate.prompts import critique_prompt, draft_prompt, final_judge_prompt, revision_prompt
from mystic.debate.session import DebateSession
from mystic.debate.storage import DebateStorage
from mystic.debate.turn import DebateTurn


VerifyCallable = Callable[..., dict[str, Any]]


class DebateRunner:
    def __init__(
        self,
        *,
        root_path: str,
        router: Any,
        verify_answer: VerifyCallable,
    ) -> None:
        self.root_path = root_path
        self.router = router
        self.verify_answer = verify_answer
        self.storage = DebateStorage(root_path)

    def run(
        self,
        *,
        problem: str,
        participants: list[dict[str, Any]],
        rounds: int,
        tools: list[str],
        judge: str,
        max_turns: int,
    ) -> dict[str, Any]:
        session = DebateSession(
            problem=problem,
            participants=participants,
            rounds=rounds,
            tools=tools,
            judge=judge,
            max_turns=max_turns,
        )
        turns: list[DebateTurn] = []

        draft_turns: list[DebateTurn] = []
        for participant in participants:
            if len(turns) >= max_turns:
                break
            role = str(participant.get("role", "solver"))
            if role not in {"solver", "reviser", "critic", "judge"}:
                role = "solver"
            result = self.router.call_model(
                model_id=str(participant["model_id"]),
                role="draft",
                task="Independent draft",
                problem=problem,
                context=draft_prompt("Independent draft", problem),
                session_id=session.session_id,
            )
            turn = DebateTurn(
                session_id=session.session_id,
                round_index=1,
                phase="parallel_draft",
                speaker_type="model",
                speaker_id=result["model_id"],
                provider=result["provider"],
                model_name=result["model_name"],
                role=role,
                status=result["status"],
                content=result["content"],
                summary=result["content"][:240],
                claims=[result["content"][:120]],
                candidate_answers=[candidate for candidate in self._extract_candidate_snippets(result["content"])],
                latency_sec=result["latency_sec"],
                artifact_path=result["artifact_path"],
            )
            turns.append(turn)
            draft_turns.append(turn)

        critique_turns: list[DebateTurn] = []
        critique_targets = [turn.turn_id for turn in draft_turns]
        critique_source_text = "\n\n".join(turn.content for turn in draft_turns)
        for participant in participants:
            if len(turns) >= max_turns:
                break
            if str(participant.get("role", "solver")) not in {"critic", "solver"}:
                continue
            result = self.router.call_model(
                model_id=str(participant["model_id"]),
                role="critique",
                task="Cross critique",
                problem=problem,
                context=critique_prompt(problem, critique_source_text),
                session_id=session.session_id,
            )
            turn = DebateTurn(
                session_id=session.session_id,
                round_index=min(rounds, 2),
                phase="cross_critique",
                speaker_type="model",
                speaker_id=result["model_id"],
                provider=result["provider"],
                model_name=result["model_name"],
                role="critic",
                status=result["status"],
                content=result["content"],
                reply_to=critique_targets,
                summary=result["content"][:240],
                claims=[result["content"][:120]],
                latency_sec=result["latency_sec"],
                artifact_path=result["artifact_path"],
            )
            turns.append(turn)
            critique_turns.append(turn)

        evidence_turn: DebateTurn | None = None
        if len(turns) < max_turns and "mystic_verify_answer" in tools:
            verification = self.verify_answer(
                problem=problem,
                candidate_answer="\n\n".join(turn.content for turn in draft_turns),
            )
            evidence_turn = DebateTurn(
                session_id=session.session_id,
                round_index=min(rounds, 3),
                phase="tool_verification",
                speaker_type="tool",
                speaker_id="mystic_verify_answer",
                provider="tool",
                model_name="deterministic_verifier",
                role="verifier",
                status="VERIFICATION_RESULT",
                content=verification["reasoning"],
                reply_to=[turn.turn_id for turn in draft_turns + critique_turns],
                summary=verification["verdict"],
                claims=[verification["verdict"]],
                candidate_answers=verification.get("failed_candidates", []) + verification.get("passed_candidates", []),
                latency_sec=0.0,
                artifact_path=str(verification.get("saved_artifact_path", "")),
            )
            turns.append(evidence_turn)

        revision_turns: list[DebateTurn] = []
        revision_reply_to = [turn.turn_id for turn in critique_turns]
        if evidence_turn is not None:
            revision_reply_to.append(evidence_turn.turn_id)
        evidence_text = evidence_turn.content if evidence_turn is not None else ""
        for participant in participants:
            if len(turns) >= max_turns:
                break
            if str(participant.get("role", "solver")) not in {"reviser", "solver"}:
                continue
            result = self.router.call_model(
                model_id=str(participant["model_id"]),
                role="revise",
                task="Revision after critique and tool evidence",
                problem=problem,
                context=revision_prompt(problem, critique_source_text, evidence_text),
                session_id=session.session_id,
            )
            turn = DebateTurn(
                session_id=session.session_id,
                round_index=min(rounds, 4),
                phase="revision",
                speaker_type="model",
                speaker_id=result["model_id"],
                provider=result["provider"],
                model_name=result["model_name"],
                role="reviser",
                status=result["status"],
                content=result["content"],
                reply_to=revision_reply_to,
                summary=result["content"][:240],
                claims=[result["content"][:120]],
                latency_sec=result["latency_sec"],
                artifact_path=result["artifact_path"],
            )
            turns.append(turn)
            revision_turns.append(turn)

        final_package = self._final_package(problem, turns, evidence_turn)
        if len(turns) < max_turns:
            final_turn = DebateTurn(
                session_id=session.session_id,
                round_index=min(rounds, 5),
                phase="final_judgment",
                speaker_type="judge",
                speaker_id=judge,
                provider="controller",
                model_name="GPT Controller",
                role="judge",
                status="FINAL_JUDGE",
                content=final_package,
                reply_to=[turn.turn_id for turn in turns[-3:]],
                summary=final_package[:240],
            )
            turns.append(final_turn)

        payload = {
            "session_id": session.session_id,
            "problem": problem,
            "participants": participants,
            "rounds": rounds,
            "turns": [turn.to_dict() for turn in turns],
            "final_package": final_package,
        }
        saved_path = self.storage.save_session(session.session_id, payload)
        payload["saved_artifact_path"] = str(saved_path)
        return payload

    @staticmethod
    def _extract_candidate_snippets(content: str) -> list[str]:
        return [line.strip() for line in content.splitlines() if "(" in line and ")" in line][:5]

    @staticmethod
    def _final_package(problem: str, turns: list[DebateTurn], evidence_turn: DebateTurn | None) -> str:
        debate_text = "\n".join(f"{turn.speaker_id}: {turn.summary}" for turn in turns[-6:])
        evidence_text = evidence_turn.content if evidence_turn is not None else "No deterministic evidence was produced."
        return final_judge_prompt(problem, debate_text, evidence_text)
