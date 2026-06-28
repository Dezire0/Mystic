from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable
import uuid

from mystic.debate.turn import DebateTurn
from mystic.research_table.discovery import DiscoveryItem, VerificationRequest
from mystic.research_table.prompts import discovery_sharing_prompt, independent_discovery_prompt
from mystic.research_table.storage import ResearchTableStorage


VerifyCallable = Callable[..., dict[str, Any]]


class ResearchTableRunner:
    def __init__(self, *, root_path: str, router: Any, verify_answer: VerifyCallable) -> None:
        self.root_path = root_path
        self.router = router
        self.verify_answer = verify_answer
        self.storage = ResearchTableStorage(root_path)

    def run(
        self,
        *,
        problem: str,
        participants: list[str],
        mode: str,
        max_rounds: int,
        enable_tools: bool,
        tools: list[str],
        controller: str,
    ) -> dict[str, Any]:
        session_id = f"research-{mode}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
        turns: list[DebateTurn] = []
        discoveries: list[dict[str, Any]] = []
        verification_requests: list[dict[str, Any]] = []

        for model_id in participants:
            result = self.router.call_model(
                model_id=model_id,
                role="draft",
                task="Independent discovery",
                problem=problem,
                context=independent_discovery_prompt(problem),
                session_id=session_id,
            )
            turn = DebateTurn(
                session_id=session_id,
                round_index=1,
                phase="independent_discovery",
                speaker_type="model",
                speaker_id=result["model_id"],
                provider=result["provider"],
                model_name=result["model_name"],
                role="solver",
                status=result["status"],
                content=result["content"],
                summary=result["content"][:240],
                claims=[result["content"][:120]],
                latency_sec=result["latency_sec"],
                artifact_path=result["artifact_path"],
            )
            turn.discoveries = self._extract_discoveries(turn)
            turn.verification_requests = self._make_verification_requests(turn.discoveries)
            turns.append(turn)
            discoveries.extend(turn.discoveries)
            verification_requests.extend(turn.verification_requests)

        discoveries_text = "\n".join(item["claim"] for item in discoveries)
        for model_id in participants:
            result = self.router.call_model(
                model_id=model_id,
                role="critique",
                task="Discovery sharing",
                problem=problem,
                context=discovery_sharing_prompt(problem, discoveries_text),
                session_id=session_id,
            )
            turn = DebateTurn(
                session_id=session_id,
                round_index=min(max_rounds, 2),
                phase="discovery_sharing",
                speaker_type="model",
                speaker_id=result["model_id"],
                provider=result["provider"],
                model_name=result["model_name"],
                role="critic",
                status=result["status"],
                content=result["content"],
                reply_to=[prior.turn_id for prior in turns[: len(participants)]],
                summary=result["content"][:240],
                claims=[result["content"][:120]],
                latency_sec=result["latency_sec"],
                artifact_path=result["artifact_path"],
            )
            turn.discoveries = self._extract_discoveries(turn)
            turn.verification_requests = self._make_verification_requests(turn.discoveries)
            turns.append(turn)
            discoveries.extend(turn.discoveries)
            verification_requests.extend(turn.verification_requests)

        accepted_discoveries: list[dict[str, Any]] = []
        rejected_discoveries: list[dict[str, Any]] = []
        verification: dict[str, Any] | None = None
        final_status = "MODEL_OUTPUTS_ONLY"
        final_decision_source = "model_outputs"
        if enable_tools and "mystic_verify_answer" in tools:
            verification = self.verify_answer(
                problem=problem,
                candidate_answer="\n\n".join(turn.content for turn in turns),
            )
            tool_turn = DebateTurn(
                session_id=session_id,
                round_index=min(max_rounds, 3),
                phase="tool_verification",
                speaker_type="tool",
                speaker_id="mystic_verify_answer",
                provider="tool",
                model_name="deterministic_verifier",
                role="verifier",
                status="VERIFICATION_RESULT",
                content=verification["reasoning"],
                reply_to=[turn.turn_id for turn in turns],
                summary=verification["verdict"],
                claims=[verification["verdict"]],
                artifact_path=str(verification.get("saved_artifact_path", "")),
            )
            turns.append(tool_turn)
            if verification["verdict"] == "VALID":
                accepted_discoveries = discoveries[:]
            elif verification["verdict"] == "INVALID":
                rejected_discoveries = discoveries[:]
            final_status = verification["verdict"]
            final_decision_source = "deterministic_verifier"

        final_synthesis_package = {
            "controller": controller,
            "accepted_discoveries": accepted_discoveries,
            "rejected_discoveries": rejected_discoveries,
            "recommended_next_tool_calls": tools,
            "final_status": final_status,
            "final_decision_source": final_decision_source,
        }
        payload = {
            "session_id": session_id,
            "problem": problem,
            "participants": participants,
            "rounds": max_rounds,
            "turns": [turn.to_dict() for turn in turns],
            "discoveries": discoveries,
            "verification_requests": verification_requests,
            "accepted_discoveries": accepted_discoveries,
            "rejected_discoveries": rejected_discoveries,
            "verification": verification,
            "final_status": final_status,
            "final_decision_source": final_decision_source,
            "final_synthesis_package": final_synthesis_package,
        }
        saved_path = self.storage.save_session(session_id, payload)
        payload["saved_artifact_path"] = str(saved_path)
        return payload

    @staticmethod
    def _extract_discoveries(turn: DebateTurn) -> list[dict[str, Any]]:
        sentences = [segment.strip() for segment in turn.content.split(".") if segment.strip()]
        if not sentences:
            sentences = [turn.content.strip() or "No discovery extracted."]
        discoveries = []
        for sentence in sentences[:2]:
            item = DiscoveryItem(
                claim=sentence,
                rationale=f"Extracted from {turn.speaker_id} during {turn.phase}.",
                confidence="low",
                needs_verification=True,
                source_turn_id=turn.turn_id,
                type="computational_observation" if "(" in sentence and ")" in sentence else "strategy",
            )
            discoveries.append(item.to_dict())
        return discoveries

    @staticmethod
    def _make_verification_requests(discoveries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        requests = []
        for discovery in discoveries[:2]:
            request = VerificationRequest(
                target_discovery_id=discovery["discovery_id"],
                tool="python" if "counterexample" in discovery["claim"].lower() else "brute_force",
                question=f"Check discovery: {discovery['claim']}",
            )
            requests.append(request.to_dict())
        return requests
