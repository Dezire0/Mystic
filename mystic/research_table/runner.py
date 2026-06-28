from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import Any, Callable
import uuid

from mystic.final_answer_verifier import extract_candidate_tuples
from mystic.research_table.discovery import DiscoveryItem, VerificationRequest
from mystic.research_table.prompts import (
    cross_critique_prompt,
    discovery_sharing_prompt,
    independent_discovery_prompt,
    revision_after_evidence_prompt,
)
from mystic.research_table.session import ResearchTableSession, ResearchTurn
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
        session = ResearchTableSession(
            session_id=session_id,
            problem=problem,
            participants=participants,
            mode=mode,
            requested_rounds=max_rounds,
            participant_models=self._participant_models(participants),
            controller=self._controller_metadata(controller),
        )
        discovery_index: dict[str, dict[str, Any]] = {}
        discovery_by_claim: dict[str, dict[str, Any]] = {}

        independent_turns = self._run_model_phase(
            session=session,
            discovery_index=discovery_index,
            discovery_by_claim=discovery_by_claim,
            round_index=1,
            phase="independent_discovery",
            participants=participants,
            role="draft",
            task="Independent discovery",
            context_by_participant={model_id: independent_discovery_prompt(problem) for model_id in participants},
            reply_to_by_participant={model_id: [] for model_id in participants},
        )
        shared_discoveries_text = self._discoveries_text(session.discoveries)

        sharing_turns = self._run_model_phase(
            session=session,
            discovery_index=discovery_index,
            discovery_by_claim=discovery_by_claim,
            round_index=2,
            phase="discovery_sharing",
            participants=participants,
            role="critique",
            task="Discovery sharing",
            context_by_participant={model_id: discovery_sharing_prompt(problem, shared_discoveries_text) for model_id in participants},
            reply_to_by_participant={
                model_id: [turn.turn_id for turn in independent_turns if turn.speaker_id != model_id] for model_id in participants
            },
        )
        critique_targets = self._target_turns_by_participant(participants, sharing_turns or independent_turns)
        critique_discoveries_text = self._discoveries_text(session.discoveries)
        cross_critique_turns = self._run_model_phase(
            session=session,
            discovery_index=discovery_index,
            discovery_by_claim=discovery_by_claim,
            round_index=3,
            phase="cross_critique",
            participants=participants,
            role="critique",
            task="Cross critique",
            context_by_participant={
                model_id: cross_critique_prompt(problem, critique_targets[model_id].summary or critique_targets[model_id].content, critique_discoveries_text)
                for model_id in participants
            },
            reply_to_by_participant={model_id: [critique_targets[model_id].turn_id] for model_id in participants},
        )

        tool_turns: list[ResearchTurn] = []
        if enable_tools and "mystic_verify_answer" in tools:
            tool_turns = self._run_tool_verification(
                session=session,
                discovery_index=discovery_index,
                round_index=4,
            )

        evidence_text = self._tool_evidence_text(tool_turns)
        revision_turns = self._run_model_phase(
            session=session,
            discovery_index=discovery_index,
            discovery_by_claim=discovery_by_claim,
            round_index=5,
            phase="revision_after_evidence",
            participants=participants,
            role="revise",
            task="Revision after evidence",
            context_by_participant={model_id: revision_after_evidence_prompt(problem, evidence_text) for model_id in participants},
            reply_to_by_participant={
                model_id: self._revision_reply_targets(
                    model_id=model_id,
                    prior_turns=independent_turns + sharing_turns + cross_critique_turns,
                    tool_turns=tool_turns,
                )
                for model_id in participants
            },
        )

        accepted_discoveries = [item for item in session.discoveries if str(item.get("status", "")).lower() in {"verified", "accepted"}]
        rejected_discoveries = [item for item in session.discoveries if str(item.get("status", "")).lower() in {"refuted", "rejected"}]
        pending_discoveries = [item for item in session.discoveries if item not in accepted_discoveries and item not in rejected_discoveries]

        if tool_turns:
            session.final_decision_source = "deterministic_verifier"
            if rejected_discoveries:
                session.final_status = "INVALID"
            elif accepted_discoveries:
                session.final_status = "VALID"
            else:
                session.final_status = "UNKNOWN"
            session.verification = {
                "verdict": session.final_status,
                "accepted_count": len(accepted_discoveries),
                "rejected_count": len(rejected_discoveries),
                "reasoning": self._session_verification_reasoning(
                    accepted_discoveries=accepted_discoveries,
                    rejected_discoveries=rejected_discoveries,
                ),
            }
        else:
            session.final_status = "MODEL_OUTPUTS_ONLY"
            session.final_decision_source = "model_outputs"
            session.verification = None

        final_synthesis_package = {
            "controller": controller,
            "accepted_discoveries": accepted_discoveries,
            "rejected_discoveries": rejected_discoveries,
            "pending_discoveries": pending_discoveries,
            "recommended_next_tool_calls": tools,
            "final_status": session.final_status,
            "final_decision_source": session.final_decision_source,
            "phase_order": [
                "independent_discovery",
                "discovery_sharing",
                "cross_critique",
                "tool_verification",
                "revision_after_evidence",
                "final_synthesis",
            ],
        }
        final_turn = ResearchTurn(
            session_id=session.session_id,
            round_index=6,
            phase="final_synthesis",
            speaker_type="controller",
            speaker_id=controller,
            provider="controller",
            model_name=controller,
            role="judge",
            status=session.final_status,
            content=json.dumps(final_synthesis_package, ensure_ascii=False, indent=2),
            reply_to=[turn.turn_id for turn in revision_turns or tool_turns or cross_critique_turns],
            summary=session.final_status,
            claims=[item["claim"] for item in accepted_discoveries[:3]],
        )
        session.turns.append(final_turn.to_dict())
        session.accepted_discoveries = accepted_discoveries
        session.rejected_discoveries = rejected_discoveries
        session.final_synthesis_package = final_synthesis_package

        payload = session.to_dict()
        saved_paths = self.storage.save_session(session_id, payload)
        payload["saved_artifact_path"] = saved_paths["session"]
        payload["saved_artifacts"] = saved_paths
        return payload

    def _participant_models(self, participants: list[str]) -> list[dict[str, Any]]:
        snapshot = self.router.status_snapshot() if hasattr(self.router, "status_snapshot") else {}
        models: list[dict[str, Any]] = []
        for model_id in participants:
            status = snapshot.get(model_id)
            if status is None:
                models.append(
                    {
                        "model_id": model_id,
                        "provider": "unknown",
                        "model_name": model_id,
                        "role_defaults": [],
                    }
                )
                continue
            models.append(
                {
                    "model_id": model_id,
                    "provider": status.get("provider", ""),
                    "model_name": status.get("model_name", model_id),
                    "role_defaults": status.get("role_defaults", []),
                }
            )
        return models

    @staticmethod
    def _controller_metadata(controller: str) -> dict[str, Any]:
        return {
            "model_id": controller,
            "provider": "controller",
            "model_name": "GPT Controller" if controller == "gpt_controller" else controller,
            "role": "judge",
        }

    @staticmethod
    def _extract_discoveries(turn: ResearchTurn) -> list[dict[str, Any]]:
        discoveries = []
        seen_claims: set[str] = set()
        for candidate in turn.candidate_answers:
            claim = f"Candidate answer {candidate}"
            seen_claims.add(claim)
            item = DiscoveryItem(
                claim=claim,
                rationale=f"Extracted from {turn.speaker_id} during {turn.phase}.",
                confidence="medium",
                needs_verification=True,
                source_turn_id=turn.turn_id,
                type="candidate_answer",
            )
            discoveries.append(item.to_dict())
        for segment in ResearchTableRunner._meaningful_segments(turn.content):
            if segment in seen_claims:
                continue
            item = DiscoveryItem(
                claim=segment,
                rationale=f"Extracted from {turn.speaker_id} during {turn.phase}.",
                confidence="low",
                needs_verification=True,
                source_turn_id=turn.turn_id,
                type=ResearchTableRunner._discovery_type(segment),
            )
            discoveries.append(item.to_dict())
            seen_claims.add(segment)
            if len(discoveries) >= 3:
                break
        return discoveries

    @staticmethod
    def _make_verification_requests(turn: ResearchTurn, discoveries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        requests = []
        for discovery in discoveries[:2]:
            request = VerificationRequest(
                target_discovery_id=discovery["discovery_id"],
                target_turn_id=turn.turn_id,
                target_candidate_answer=discovery["claim"] if discovery.get("type") == "candidate_answer" else "",
                tool="python" if "counterexample" in discovery["claim"].lower() else "brute_force",
                question=f"Check discovery: {discovery['claim']}",
            )
            requests.append(request.to_dict())
        return requests

    def _run_model_phase(
        self,
        *,
        session: ResearchTableSession,
        discovery_index: dict[str, dict[str, Any]],
        discovery_by_claim: dict[str, dict[str, Any]],
        round_index: int,
        phase: str,
        participants: list[str],
        role: str,
        task: str,
        context_by_participant: dict[str, str],
        reply_to_by_participant: dict[str, list[str]],
    ) -> list[ResearchTurn]:
        turns: list[ResearchTurn] = []
        for model_id in participants:
            result = self.router.call_model(
                model_id=model_id,
                role=role,
                task=task,
                problem=session.problem,
                context=context_by_participant[model_id],
                session_id=session.session_id,
            )
            turn = ResearchTurn(
                session_id=session.session_id,
                round_index=round_index,
                phase=phase,
                speaker_type="model",
                speaker_id=result["model_id"],
                provider=result["provider"],
                model_name=result["model_name"],
                role=self._turn_role_for_phase(phase),
                status=result["status"],
                content=result["content"],
                reply_to=reply_to_by_participant.get(model_id, []),
                summary=result["content"][:240],
                claims=self._claims_from_content(result["content"]),
                candidate_answers=self._candidate_answers_from_content(result["content"]),
                latency_sec=result["latency_sec"],
                artifact_path=result["artifact_path"],
            )
            turn.discoveries = self._extract_discoveries(turn)
            turn.discoveries = self._merge_discoveries(turn.discoveries, discovery_index=discovery_index, discovery_by_claim=discovery_by_claim)
            turn.verification_requests = self._make_verification_requests(turn, turn.discoveries)
            turns.append(turn)
            session.turns.append(turn.to_dict())
            for discovery in turn.discoveries:
                if discovery not in session.discoveries:
                    session.discoveries.append(discovery)
            session.verification_requests.extend(turn.verification_requests)
            for discovery in turn.discoveries:
                discovery_index[discovery["discovery_id"]] = discovery
        return turns

    @staticmethod
    def _merge_discoveries(
        discoveries: list[dict[str, Any]],
        *,
        discovery_index: dict[str, dict[str, Any]],
        discovery_by_claim: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        for discovery in discoveries:
            claim = str(discovery.get("claim", "")).strip()
            existing = discovery_by_claim.get(claim)
            if existing is not None:
                existing["needs_verification"] = existing.get("needs_verification", False) or discovery.get("needs_verification", False)
                merged.append(existing)
                continue
            discovery_by_claim[claim] = discovery
            discovery_index[discovery["discovery_id"]] = discovery
            merged.append(discovery)
        return merged

    def _run_tool_verification(
        self,
        *,
        session: ResearchTableSession,
        discovery_index: dict[str, dict[str, Any]],
        round_index: int,
    ) -> list[ResearchTurn]:
        tool_turns: list[ResearchTurn] = []
        for request in session.verification_requests:
            discovery = discovery_index.get(str(request.get("target_discovery_id")))
            if discovery is None:
                continue
            candidate_answer = str(request.get("target_candidate_answer") or discovery.get("claim", "")).strip()
            verification = self.verify_answer(problem=session.problem, candidate_answer=candidate_answer)
            verdict = str(verification.get("verdict", "UNKNOWN")).upper()
            mapped_status = self._discovery_status_from_verdict(verdict)
            if mapped_status is not None:
                discovery["status"] = mapped_status
                discovery["needs_verification"] = False
            request["status"] = mapped_status or "pending"
            request["result_verdict"] = verdict
            request["result_reasoning"] = str(verification.get("reasoning", ""))
            tool_turn = ResearchTurn(
                session_id=session.session_id,
                round_index=round_index,
                phase="tool_verification",
                speaker_type="tool",
                speaker_id="mystic_verify_answer",
                provider="tool",
                model_name="deterministic_verifier",
                role="verifier",
                status="VERIFICATION_RESULT",
                content=str(verification.get("reasoning", "")),
                reply_to=[str(request.get("target_turn_id", ""))] if request.get("target_turn_id") else [],
                summary=verdict,
                claims=[verdict],
                artifact_path=str(verification.get("saved_artifact_path", "")),
                target_discovery_id=str(request.get("target_discovery_id") or ""),
                verification_request_id=str(request.get("request_id", "")),
            )
            request["tool_turn_id"] = tool_turn.turn_id
            tool_turns.append(tool_turn)
            session.turns.append(tool_turn.to_dict())
        return tool_turns

    @staticmethod
    def _target_turns_by_participant(participants: list[str], turns: list[ResearchTurn]) -> dict[str, ResearchTurn]:
        by_speaker = {turn.speaker_id: turn for turn in turns}
        targets: dict[str, ResearchTurn] = {}
        for index, model_id in enumerate(participants):
            target_model = participants[(index + 1) % len(participants)] if len(participants) > 1 else model_id
            targets[model_id] = by_speaker.get(target_model, turns[0])
        return targets

    @staticmethod
    def _revision_reply_targets(
        *,
        model_id: str,
        prior_turns: list[ResearchTurn],
        tool_turns: list[ResearchTurn],
    ) -> list[str]:
        relevant = [turn.turn_id for turn in prior_turns if turn.speaker_id == model_id]
        relevant.extend(turn.turn_id for turn in tool_turns)
        return relevant

    @staticmethod
    def _discoveries_text(discoveries: list[dict[str, Any]]) -> str:
        return "\n".join(f"- {item['claim']} [{item.get('status', 'proposed')}]" for item in discoveries[-12:])

    @staticmethod
    def _tool_evidence_text(tool_turns: list[ResearchTurn]) -> str:
        if not tool_turns:
            return "No deterministic evidence was produced."
        return "\n".join(
            f"- {turn.summary}: {turn.content}" for turn in tool_turns
        )

    @staticmethod
    def _candidate_answers_from_content(content: str) -> list[str]:
        tuples = extract_candidate_tuples(content)
        seen: set[str] = set()
        values: list[str] = []
        for item in tuples:
            label = str(tuple(item))
            if label in seen:
                continue
            seen.add(label)
            values.append(label)
        return values

    @staticmethod
    def _claims_from_content(content: str) -> list[str]:
        claims = ResearchTableRunner._meaningful_segments(content)
        return claims[:2] or [content[:120]]

    @staticmethod
    def _meaningful_segments(content: str) -> list[str]:
        lines = [line.strip(" -*\t") for line in content.splitlines()]
        filtered = [
            line for line in lines
            if line
            and not line.startswith("[")
            and line.lower() not in {"problem:", "context:"}
            and not line.lower().startswith("role:")
            and not line.lower().startswith("task:")
        ]
        explicit = [
            line for line in filtered
            if line.lower().startswith(("discovery:", "claim:", "observation:", "hypothesis:", "revision:", "critique:"))
        ]
        if explicit:
            return [line.split(":", 1)[1].strip() or line for line in explicit[:3]]
        if filtered:
            return filtered[:2]
        fallback = content.strip()
        return [fallback[:180]] if fallback else []

    @staticmethod
    def _discovery_type(claim: str) -> str:
        lowered = claim.lower()
        if "counterexample" in lowered:
            return "counterexample"
        if "candidate" in lowered or "(" in claim and ")" in claim:
            return "candidate_answer"
        if "invariant" in lowered:
            return "invariant"
        if "lemma" in lowered:
            return "lemma"
        return "strategy"

    @staticmethod
    def _discovery_status_from_verdict(verdict: str) -> str | None:
        if verdict == "VALID":
            return "verified"
        if verdict == "INVALID":
            return "refuted"
        return None

    @staticmethod
    def _session_verification_reasoning(
        *,
        accepted_discoveries: list[dict[str, Any]],
        rejected_discoveries: list[dict[str, Any]],
    ) -> str:
        if rejected_discoveries:
            claims = ", ".join(item["claim"] for item in rejected_discoveries[:3])
            return f"Deterministic verifier refuted discoveries: {claims}"
        if accepted_discoveries:
            claims = ", ".join(item["claim"] for item in accepted_discoveries[:3])
            return f"Deterministic verifier supported discoveries: {claims}"
        return "Deterministic verifier did not confirm or refute extracted discoveries."

    @staticmethod
    def _turn_role_for_phase(phase: str) -> str:
        return {
            "independent_discovery": "solver",
            "discovery_sharing": "critic",
            "cross_critique": "critic",
            "revision_after_evidence": "reviser",
        }.get(phase, "solver")
