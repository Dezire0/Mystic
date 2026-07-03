from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import json
import logging
import uuid

from mystic.lab.agents import AGENT_ROLE_TO_MODEL_ROLE, build_role_task, model_role_for_agent, role_for_phase, room_for_phase
from mystic.lab.claims import claims_from_turn
from mystic.lab.experiments import summarize_experiment
from mystic.lab.failures import make_failure
from mystic.lab.memory_graph import make_edge
from mystic.lab.reality_anchor import normalize_claim_status
from mystic.lab.reports import render_report
from mystic.lab.schema import LAB_PHASES, PHASE_TO_ROOM
from mystic.lab.session import Claim, Experiment, LabSession, LabSessionBundle, LabTurn, MemoryEdge
from mystic.lab.storage import LabStorage

logger = logging.getLogger(__name__)


class LabRunner:
    def __init__(
        self,
        *,
        root_path: str | Path,
        router: Any,
        verify_answer: Any,
        research_table_runner: Any,
    ) -> None:
        self.root_path = Path(root_path)
        self.router = router
        self.verify_answer = verify_answer
        self.research_table_runner = research_table_runner
        self.storage = LabStorage(self.root_path)

    def create_session(
        self,
        *,
        problem: str,
        domain: str,
        goal: str,
        mode: str,
        participants: list[str],
    ) -> dict[str, Any]:
        session_id = f"lab-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
        session = LabSession(
            session_id=session_id,
            problem=problem,
            domain=domain,
            goal=goal,
            mode=mode,
            controller={
                "model_id": "gpt_controller",
                "provider": "controller",
                "model_name": "GPT Controller",
                "role": "judge",
            },
            participants=self._participant_models(participants),
            next_actions=["Run lab_session_advance to begin structured research."],
        )
        bundle = LabSessionBundle(
            session=session,
            notebook_markdown=f"# Lab Notebook {session_id}\n\nProblem: {problem}\n\n",
        )
        paths = self.storage.save_bundle(bundle)
        return {
            "session_id": session_id,
            "status": session.status,
            "current_phase": session.current_phase,
            "paths": paths,
        }

    def get_session(self, *, session_id: str) -> dict[str, Any]:
        bundle = self.storage.load_bundle(session_id)
        return {
            "session": bundle.session.to_dict(),
            "session_id": bundle.session.session_id,
            "latest_turns": [item.to_dict() for item in bundle.turns[-10:]],
            "turns": [item.to_dict() for item in bundle.turns],
            "claims": [item.to_dict() for item in bundle.claims],
            "experiments": [item.to_dict() for item in bundle.experiments],
            "failures": [item.to_dict() for item in bundle.failures],
            "memory_edges": [item.to_dict() for item in bundle.memory_edges],
            "next_actions": list(bundle.session.next_actions),
            "notebook_path": bundle.session.artifact_paths.get("notebook", ""),
            "report_path": bundle.session.artifact_paths.get("report", ""),
            "notebook_markdown": bundle.notebook_markdown,
            "report_markdown": bundle.report_markdown,
        }

    def advance_session(
        self,
        *,
        session_id: str,
        max_steps: int = 1,
        target_phase: str | None = None,
        use_model_arena: bool = False,
        use_verifier: bool = True,
    ) -> dict[str, Any]:
        bundle = self.storage.load_bundle(session_id)
        new_turns: list[LabTurn] = []
        new_claims: list[Claim] = []
        new_experiments: list[Experiment] = []
        new_failures: list[Any] = []

        if bundle.session.current_phase == "completed":
            return {
                "updated_session": bundle.session.to_dict(),
                "new_turns": [],
                "new_claims": [],
                "new_experiments": [],
                "new_failures": [],
                "next_actions": list(bundle.session.next_actions),
            }

        bundle.session.status = "running"
        for _ in range(max(1, max_steps)):
            phase = bundle.session.current_phase
            generated = self._advance_phase(
                bundle=bundle,
                phase=phase,
                use_model_arena=use_model_arena,
                use_verifier=use_verifier,
            )
            new_turns.extend(generated["turns"])
            new_claims.extend(generated["claims"])
            new_experiments.extend(generated["experiments"])
            new_failures.extend(generated["failures"])
            if target_phase and bundle.session.current_phase == target_phase:
                break
            if phase == "completed" or bundle.session.current_phase == "completed":
                break

        bundle.session.touch()
        paths = self.storage.save_bundle(bundle)
        return {
            "updated_session": bundle.session.to_dict(),
            "new_turns": [item.to_dict() for item in new_turns],
            "new_claims": [item.to_dict() for item in new_claims],
            "new_experiments": [item.to_dict() for item in new_experiments],
            "new_failures": [item.to_dict() for item in new_failures],
            "next_actions": list(bundle.session.next_actions),
            "paths": paths,
        }

    def run_agent(
        self,
        *,
        session_id: str,
        agent_role: str,
        provider: str,
        task: str,
        context_ids: list[str],
    ) -> dict[str, Any]:
        bundle = self.storage.load_bundle(session_id)
        context = self._context_from_ids(bundle, context_ids)
        turn = self._run_role_turn(
            bundle=bundle,
            phase=bundle.session.current_phase,
            agent_role=agent_role,
            task=task,
            provider_preference=provider,
            context=context,
            requested_tools=[],
        )
        new_claims = claims_from_turn(bundle.session.session_id, turn)
        bundle.turns.append(turn)
        bundle.claims.extend(new_claims)
        bundle.session.next_actions = [f"Review turn {turn.turn_id}.", "Decide whether to advance the lab session."]
        bundle.session.touch()
        self.storage.save_bundle(bundle)
        return {
            "turn_id": turn.turn_id,
            "status": turn.status,
            "output": turn.output,
            "extracted_claims": [item.to_dict() for item in new_claims],
            "next_actions": list(bundle.session.next_actions),
        }

    def referee_review(
        self,
        *,
        session_id: str,
        claim_id: str | None,
        text: str,
        strictness: str,
    ) -> dict[str, Any]:
        bundle = self.storage.load_bundle(session_id)
        result = self._referee_review_in_bundle(bundle=bundle, claim_id=claim_id, text=text, strictness=strictness)
        bundle.session.next_actions = ["Review referee verdict.", "Archive any failed claims."]
        bundle.session.touch()
        self.storage.save_bundle(bundle)
        return result

    def create_experiment(
        self,
        *,
        session_id: str,
        claim_id: str,
        question: str,
        method: str,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        bundle = self.storage.load_bundle(session_id)
        experiment = Experiment(
            session_id=session_id,
            claim_id=claim_id,
            question=question,
            method=method,
            inputs=inputs,
            tool_name="deterministic_verifier" if method == "python_bruteforce" else method,
        )
        bundle.experiments.append(experiment)
        bundle.memory_edges.append(
            make_edge(
                session_id=session_id,
                from_id=claim_id,
                to_id=experiment.experiment_id,
                relation="generated_experiment",
                evidence=question,
            )
        )
        bundle.session.next_actions = [f"Run experiment {experiment.experiment_id}."]
        bundle.session.touch()
        self.storage.save_bundle(bundle)
        return {"experiment_id": experiment.experiment_id, "status": experiment.verdict}

    def run_experiment(self, *, session_id: str, experiment_id: str, dry_run: bool) -> dict[str, Any]:
        bundle = self.storage.load_bundle(session_id)
        experiment = self._experiment_by_id(bundle, experiment_id)
        claim = self._claim_by_id(bundle, experiment.claim_id)
        if dry_run:
            return {
                "experiment_id": experiment.experiment_id,
                "verdict": experiment.verdict,
                "outputs": experiment.outputs,
                "evidence_summary": summarize_experiment(experiment),
                "updated_claim_status": claim.status if claim is not None else "UNKNOWN",
            }
        result = self._run_experiment_in_bundle(bundle=bundle, experiment=experiment)
        bundle.session.next_actions = ["Review experiment evidence.", "Continue to referee review if needed."]
        bundle.session.touch()
        self.storage.save_bundle(bundle)
        return result

    def memory_search(
        self,
        *,
        query: str,
        domain: str | None,
        status_filter: str | None,
        limit: int,
    ) -> dict[str, Any]:
        query_text = query.lower()
        matching_sessions = []
        claims = []
        failures = []
        experiments = []
        edges = []
        for session_dir in sorted(self.storage.base_dir.iterdir(), reverse=True):
            if not session_dir.is_dir():
                continue
            try:
                bundle = self.storage.load_bundle(session_dir.name)
            except Exception:
                continue
            if domain and bundle.session.domain != domain:
                continue
            if query_text in json.dumps(bundle.session.to_dict(), ensure_ascii=False).lower():
                matching_sessions.append(bundle.session.to_dict())
            for claim in bundle.claims:
                if status_filter and claim.status != status_filter:
                    continue
                if query_text in claim.text.lower():
                    claims.append(claim.to_dict())
            for failure in bundle.failures:
                if query_text in json.dumps(failure.to_dict(), ensure_ascii=False).lower():
                    failures.append(failure.to_dict())
            for experiment in bundle.experiments:
                if query_text in json.dumps(experiment.to_dict(), ensure_ascii=False).lower():
                    experiments.append(experiment.to_dict())
            for edge in bundle.memory_edges:
                if query_text in json.dumps(edge.to_dict(), ensure_ascii=False).lower():
                    edges.append(edge.to_dict())
        return {
            "matching_sessions": matching_sessions[:limit],
            "claims": claims[:limit],
            "failures": failures[:limit],
            "experiments": experiments[:limit],
            "memory_edges": edges[:limit],
        }

    def memory_write(self, *, session_id: str, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        bundle = self.storage.load_bundle(session_id)
        if kind == "claim":
            item = Claim(session_id=session_id, **payload)
            bundle.claims.append(item)
            written_id = item.claim_id
        elif kind == "failure":
            item = make_failure(session_id=session_id, **payload)
            bundle.failures.append(item)
            written_id = item.failure_id
        elif kind == "experiment":
            item = Experiment(session_id=session_id, **payload)
            bundle.experiments.append(item)
            written_id = item.experiment_id
        elif kind == "edge":
            item = MemoryEdge(session_id=session_id, **payload)
            bundle.memory_edges.append(item)
            written_id = item.edge_id
        elif kind == "note":
            note = str(payload.get("text", "")).strip()
            bundle.notebook_markdown += f"\n- {note}\n"
            written_id = "note"
        else:
            raise ValueError(f"Unsupported memory kind: {kind}")
        bundle.session.touch()
        paths = self.storage.save_bundle(bundle)
        path_key = {
            "note": "notebook",
            "claim": "claims",
            "failure": "failures",
            "experiment": "experiments",
            "edge": "memory_edges",
        }[kind]
        return {"written_object_id": written_id, "path": paths.get(path_key, paths["session"])}

    def models_debate(
        self,
        *,
        session_id: str,
        question: str,
        participants: list[str],
        rounds: list[str],
        use_existing_research_table: bool,
    ) -> dict[str, Any]:
        if not use_existing_research_table:
            raise ValueError("Model Arena currently requires use_existing_research_table=true")
        bundle = self.storage.load_bundle(session_id)
        selected = participants or [item["model_id"] for item in bundle.session.participants[:2] if item.get("model_id")]
        result, imported_claims, imported_failures, imported_experiments = self._run_model_arena_in_bundle(
            bundle=bundle,
            question=question,
            participants=selected,
            rounds=rounds,
        )
        bundle.session.next_actions = ["Review imported Model Arena claims.", "Run referee review on disputed claims."]
        bundle.session.touch()
        self.storage.save_bundle(bundle)
        return {
            "research_table_session_id": result["session_id"],
            "imported_claims": imported_claims,
            "imported_failures": imported_failures,
            "summary": f"Imported {imported_claims} claims, {imported_failures} failures, and {imported_experiments} experiments.",
        }

    def report_generate(
        self,
        *,
        session_id: str,
        format: str,
        include_failures: bool,
        include_next_actions: bool,
    ) -> dict[str, Any]:
        if format != "markdown":
            raise ValueError("Only markdown report generation is supported.")
        bundle = self.storage.load_bundle(session_id)
        report = render_report(bundle)
        bundle.report_markdown = report.markdown
        if not include_failures:
            report.failed_claims = []
        if not include_next_actions:
            report.next_actions = []
        bundle.session.current_phase = "completed"
        bundle.session.status = "completed"
        bundle.session.next_actions = []
        bundle.session.touch()
        paths = self.storage.save_bundle(bundle)
        return {
            "report_path": paths["report"],
            "markdown": report.markdown,
            "summary": {
                "surviving_claims": len(report.surviving_claims),
                "failed_claims": len(report.failed_claims),
                "next_actions": len(report.next_actions),
            },
        }

    def _advance_phase(
        self,
        *,
        bundle: LabSessionBundle,
        phase: str,
        use_model_arena: bool,
        use_verifier: bool,
    ) -> dict[str, list[Any]]:
        turns: list[LabTurn] = []
        claims: list[Claim] = []
        experiments: list[Experiment] = []
        failures: list[Any] = []
        role = role_for_phase(phase)
        context = self._phase_context(bundle, phase)
        turn = self._run_role_turn(
            bundle=bundle,
            phase=phase,
            agent_role=role,
            task=build_role_task(
                phase=phase,
                agent_role=role,
                problem=bundle.session.problem,
                goal=bundle.session.goal,
                context=context,
            ),
            provider_preference="auto",
            context=context,
            requested_tools=["mystic_verify_answer"] if phase in {"simulation_or_execution", "referee_review"} else [],
        )
        bundle.turns.append(turn)
        turns.append(turn)

        extracted_claims = claims_from_turn(bundle.session.session_id, turn)
        if phase in {"background_scan", "hypothesis_generation", "knowledge_update"}:
            bundle.claims.extend(extracted_claims)
            claims.extend(extracted_claims)
        if phase == "experiment_design":
            target_claim = bundle.claims[-1] if bundle.claims else None
            if target_claim is not None:
                experiment = Experiment(
                    session_id=bundle.session.session_id,
                    claim_id=target_claim.claim_id,
                    question=f"Test claim: {target_claim.text}",
                    method="python_bruteforce" if use_verifier else "manual_review",
                    inputs={"candidate_answer": target_claim.text},
                    tool_name="mystic_verify_answer" if use_verifier else "manual_review",
                )
                bundle.experiments.append(experiment)
                bundle.memory_edges.append(
                    make_edge(
                        session_id=bundle.session.session_id,
                        from_id=target_claim.claim_id,
                        to_id=experiment.experiment_id,
                        relation="generated_experiment",
                        evidence=experiment.question,
                    )
                )
                experiments.append(experiment)
        if phase == "simulation_or_execution":
            if use_model_arena or bundle.session.mode in {"serious", "proof_critical", "multi_model_debate"}:
                result, imported_claims, imported_failures, imported_experiments = self._run_model_arena_in_bundle(
                    bundle=bundle,
                    question=bundle.session.problem,
                    participants=[item["model_id"] for item in bundle.session.participants if item.get("model_id")][:3],
                    rounds=["independent_discovery", "cross_critique", "revision_after_evidence", "final_synthesis"],
                )
                bundle.notebook_markdown += (
                    f"\n## Model Arena\n\nImported {imported_claims} claims, {imported_failures} failures, "
                    f"and {imported_experiments} experiments from Research Table {result['session_id']}.\n"
                )
                if imported_claims:
                    claims.extend(bundle.claims[-imported_claims:])
                if imported_failures:
                    failures.extend(bundle.failures[-imported_failures:])
                if imported_experiments:
                    experiments.extend(bundle.experiments[-imported_experiments:])
            elif bundle.experiments:
                updated_experiment = bundle.experiments[-1]
                result = self._run_experiment_in_bundle(bundle=bundle, experiment=updated_experiment)
                experiments.append(updated_experiment)
                bundle.notebook_markdown += f"\n## Simulation\n\n{result['evidence_summary']}\n"
        if phase == "referee_review":
            target_claim = bundle.claims[-1] if bundle.claims else None
            if target_claim is not None:
                review = self._referee_review_in_bundle(
                    bundle=bundle,
                    claim_id=target_claim.claim_id,
                    text=target_claim.text,
                    strictness="hostile",
                )
                if review["failures"]:
                    failures.extend(bundle.failures[-len(review["failures"]) :])
        if phase == "failure_archive" and bundle.failures:
            latest_failure = bundle.failures[-1]
            if bundle.claims:
                bundle.memory_edges.append(
                    make_edge(
                        session_id=bundle.session.session_id,
                        from_id=bundle.claims[-1].claim_id,
                        to_id=latest_failure.failure_id,
                        relation="caused_failure",
                        evidence=latest_failure.first_fatal_error,
                    )
                )
        if phase == "report_generation":
            report = render_report(bundle)
            bundle.report_markdown = report.markdown

        bundle.session.current_phase = self._next_phase(phase)
        bundle.session.active_room = PHASE_TO_ROOM.get(bundle.session.current_phase, bundle.session.active_room)
        bundle.session.next_actions = self._next_actions_for_phase(bundle.session.current_phase)
        if bundle.session.current_phase == "completed":
            bundle.session.status = "completed"
        bundle.session.touch()
        bundle.notebook_markdown += f"\n## {phase}\n\n{turn.output[:500]}\n"
        return {
            "turns": turns,
            "claims": claims,
            "experiments": experiments,
            "failures": failures,
        }

    def _participant_models(self, participants: list[str]) -> list[dict[str, Any]]:
        snapshot = self.router.status_snapshot() if hasattr(self.router, "status_snapshot") else {}
        models = []
        for requested_participant in participants:
            model_id, item = self._resolve_participant(requested_participant, snapshot)
            status = item.get("status", {})
            models.append(
                {
                    "requested_participant": requested_participant,
                    "model_id": model_id,
                    "provider": item.get("provider", "unknown"),
                    "model_name": item.get("model_name", model_id),
                    "status": {
                        "state": status.get("state", "unknown"),
                        "available": bool(status.get("available", False)),
                        "authenticated": bool(status.get("authenticated", False)),
                        "message": status.get("message", ""),
                    },
                }
            )
        return models

    def _resolve_participant(
        self,
        requested_participant: str,
        snapshot: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        if requested_participant in snapshot:
            return requested_participant, snapshot[requested_participant]
        desired_role = model_role_for_agent(requested_participant) if requested_participant in AGENT_ROLE_TO_MODEL_ROLE else ""
        if desired_role:
            candidates: list[tuple[str, dict[str, Any]]] = []
            for model_id, item in snapshot.items():
                role_defaults = item.get("role_defaults", [])
                if desired_role in role_defaults:
                    candidates.append((model_id, item))
            if candidates:
                for model_id, item in candidates:
                    status = item.get("status", {})
                    if status.get("available") and status.get("authenticated"):
                        return model_id, item
                return candidates[0]
        logger.info(
            "lab_participant_unresolved requested_participant=%s",
            requested_participant,
        )
        return requested_participant, snapshot.get(requested_participant, {})

    def _run_role_turn(
        self,
        *,
        bundle: LabSessionBundle,
        phase: str,
        agent_role: str,
        task: str,
        provider_preference: str,
        context: str,
        requested_tools: list[str],
    ) -> LabTurn:
        participant = self._select_participant(bundle, provider_preference)
        if participant is None:
            return LabTurn(
                session_id=bundle.session.session_id,
                phase=phase,
                room=room_for_phase(phase),
                agent_role=agent_role,
                provider="none",
                model_name="unavailable",
                input_summary=task[:200],
                output="No configured participant is available for this role.",
                requested_tools=requested_tools,
                status="blocked",
            )
        model_id = str(participant.get("model_id", ""))
        provider = str(participant.get("provider", "unknown"))
        result = self.router.call_model(
            model_id=model_id,
            role=model_role_for_agent(agent_role),
            task=task,
            problem=bundle.session.problem,
            context=context,
            session_id=bundle.session.session_id,
        )
        status = result["status"] if result["status"] in {"AUTH_REQUIRED", "ERROR"} else "completed"
        output = result["content"]
        if result["status"] == "AUTH_REQUIRED" and result.get("auth_message"):
            output = result["auth_message"]
        turn = LabTurn(
            session_id=bundle.session.session_id,
            phase=phase,
            room=room_for_phase(phase),
            agent_role=agent_role,
            provider=provider,
            model_name=result["model_name"],
            input_summary=task[:200],
            output=output,
            extracted_claims=self._extract_claim_payloads(output, phase=phase),
            requested_tools=requested_tools,
            status=status,
            error="" if result["status"] != "ERROR" else "Model call failed.",
        )
        return turn

    @staticmethod
    def _extract_claim_payloads(text: str, *, phase: str) -> list[dict[str, Any]]:
        claims = []
        for raw in text.splitlines():
            line = raw.strip("- *\t ")
            if len(line) < 18:
                continue
            claims.append(
                {
                    "text": line[:400],
                    "claim_type": "observation" if phase == "background_scan" else "hypothesis",
                    "confidence": "medium" if phase == "knowledge_update" else "low",
                }
            )
            if len(claims) >= 5:
                break
        return claims

    @staticmethod
    def _next_phase(current_phase: str) -> str:
        index = LAB_PHASES.index(current_phase)
        if index >= len(LAB_PHASES) - 1:
            return "completed"
        return LAB_PHASES[index + 1]

    @staticmethod
    def _next_actions_for_phase(phase: str) -> list[str]:
        if phase == "completed":
            return []
        room = PHASE_TO_ROOM.get(phase, "Main Lab Room")
        return [f"Advance to {phase} in {room}.", "Inspect newly saved artifacts and claims."]

    def _select_participant(self, bundle: LabSessionBundle, provider_preference: str) -> dict[str, Any] | None:
        participants = bundle.session.participants
        if provider_preference not in {"", "auto"}:
            for participant in participants:
                provider = str(participant.get("provider", ""))
                model_id = str(participant.get("model_id", ""))
                if provider_preference == "local" and provider not in {"cli", "api"}:
                    return participant
                if provider == provider_preference or model_id == provider_preference:
                    return participant
        for participant in participants:
            status = participant.get("status", {})
            if status.get("available") and status.get("authenticated"):
                return participant
        return participants[0] if participants else None

    @staticmethod
    def _context_from_ids(bundle: LabSessionBundle, context_ids: list[str]) -> str:
        if not context_ids:
            return bundle.notebook_markdown[-2000:]
        parts: list[str] = []
        for item in bundle.turns:
            if item.turn_id in context_ids:
                parts.append(item.output)
        for item in bundle.claims:
            if item.claim_id in context_ids:
                parts.append(item.text)
        return "\n\n".join(parts)

    @staticmethod
    def _phase_context(bundle: LabSessionBundle, phase: str) -> str:
        sections = [
            f"Current phase: {phase}",
            f"Known claims: {len(bundle.claims)}",
            f"Known experiments: {len(bundle.experiments)}",
            f"Known failures: {len(bundle.failures)}",
        ]
        if bundle.claims:
            sections.append("Latest claim: " + bundle.claims[-1].text[:400])
        if bundle.experiments:
            sections.append("Latest experiment: " + bundle.experiments[-1].question[:400])
        if bundle.failures:
            sections.append("Latest failure: " + bundle.failures[-1].first_fatal_error[:400])
        return "\n".join(sections)

    @staticmethod
    def _claim_by_id(bundle: LabSessionBundle, claim_id: str | None) -> Claim | None:
        if not claim_id:
            return None
        for item in bundle.claims:
            if item.claim_id == claim_id:
                return item
        return None

    @staticmethod
    def _experiment_by_id(bundle: LabSessionBundle, experiment_id: str) -> Experiment:
        for item in bundle.experiments:
            if item.experiment_id == experiment_id:
                return item
        raise KeyError(f"Unknown experiment_id: {experiment_id}")

    def _run_experiment_in_bundle(self, *, bundle: LabSessionBundle, experiment: Experiment) -> dict[str, Any]:
        claim = self._claim_by_id(bundle, experiment.claim_id)
        if experiment.method == "model_debate":
            result, imported_claims, imported_failures, imported_experiments = self._run_model_arena_in_bundle(
                bundle=bundle,
                question=experiment.question,
                participants=[item["model_id"] for item in bundle.session.participants[:3] if item.get("model_id")],
                rounds=["independent_discovery", "cross_critique", "revision_after_evidence", "final_synthesis"],
            )
            experiment.outputs = result
            experiment.verdict = "supports" if imported_claims else "inconclusive"
            experiment.evidence_summary = (
                f"Imported {imported_claims} claims, {imported_failures} failures, and {imported_experiments} experiments."
            )
            return {
                "experiment_id": experiment.experiment_id,
                "verdict": experiment.verdict,
                "outputs": experiment.outputs,
                "evidence_summary": experiment.evidence_summary,
                "updated_claim_status": claim.status if claim is not None else "UNKNOWN",
            }
        candidate_answer = str(experiment.inputs.get("candidate_answer") or (claim.text if claim is not None else ""))
        verification = self.verify_answer(problem=bundle.session.problem, candidate_answer=candidate_answer)
        verdict = str(verification.get("verdict", "UNKNOWN")).upper()
        experiment.outputs = verification
        experiment.tool_name = "mystic_verify_answer"
        experiment.verdict = "supports" if verdict == "VALID" else "refutes" if verdict == "INVALID" else "inconclusive"
        experiment.evidence_summary = verification.get("reasoning", "")
        if claim is not None:
            claim.status = normalize_claim_status(
                verifier_verdict=verdict,
                method=experiment.method,
                incomplete_proof=verdict == "UNKNOWN",
            )
            claim.related_experiments.append(experiment.experiment_id)
            if verdict == "VALID":
                claim.supporting_evidence.append(verification.get("saved_artifact_path", ""))
            elif verdict == "INVALID":
                claim.refuting_evidence.append(verification.get("saved_artifact_path", ""))
            claim.touch()
        return {
            "experiment_id": experiment.experiment_id,
            "verdict": experiment.verdict,
            "outputs": experiment.outputs,
            "evidence_summary": experiment.evidence_summary,
            "updated_claim_status": claim.status if claim is not None else "UNKNOWN",
        }

    def _referee_review_in_bundle(
        self,
        *,
        bundle: LabSessionBundle,
        claim_id: str | None,
        text: str,
        strictness: str,
    ) -> dict[str, Any]:
        claim = self._claim_by_id(bundle, claim_id) if claim_id else None
        target_text = text.strip() or (claim.text if claim is not None else "")
        verification = self.verify_answer(problem=bundle.session.problem, candidate_answer=target_text)
        verdict = str(verification.get("verdict", "UNKNOWN")).upper()
        first_fatal_error = verification.get("reasoning", "") if verdict == "INVALID" else ""
        critique = first_fatal_error or "No deterministic fatal error was found."
        status = normalize_claim_status(
            verifier_verdict=verdict,
            referee_fatal_error=bool(first_fatal_error and strictness == "hostile"),
            incomplete_proof=verdict == "UNKNOWN",
        )
        updated_claims: list[Claim] = []
        failures = []
        if claim is not None:
            claim.status = status
            if verdict == "VALID":
                claim.supporting_evidence.append(verification.get("saved_artifact_path", ""))
            elif verdict == "INVALID":
                claim.refuting_evidence.append(verification.get("saved_artifact_path", ""))
            claim.touch()
            updated_claims.append(claim)
            if first_fatal_error:
                failure = make_failure(
                    session_id=bundle.session.session_id,
                    claim_id=claim.claim_id,
                    source_turn_id="",
                    first_fatal_error=first_fatal_error,
                    failure_type="logic_gap",
                    lesson="Referee identified a deterministic failure.",
                )
                bundle.failures.append(failure)
                claim.related_failures.append(failure.failure_id)
                failures.append(failure)
        turn = LabTurn(
            session_id=bundle.session.session_id,
            phase="referee_review",
            room=room_for_phase("referee_review"),
            agent_role="Referee",
            provider="tool",
            model_name="deterministic_verifier",
            input_summary=target_text[:200],
            output=json.dumps(verification, ensure_ascii=False, indent=2),
            requested_tools=["mystic_verify_answer"],
            tool_results=[verification],
            status="completed",
        )
        bundle.turns.append(turn)
        return {
            "verdict": verdict,
            "first_fatal_error": first_fatal_error,
            "critique": critique,
            "recommended_next_action": "Review referee verdict.",
            "updated_claims": [item.to_dict() for item in updated_claims],
            "failures": [item.to_dict() for item in failures],
        }

    def _run_model_arena_in_bundle(
        self,
        *,
        bundle: LabSessionBundle,
        question: str,
        participants: list[str],
        rounds: list[str],
    ) -> tuple[dict[str, Any], int, int, int]:
        result = self.research_table_runner.run(
            problem=question or bundle.session.problem,
            participants=participants[:3],
            mode="discovery_debate",
            max_rounds=max(1, len(rounds)),
            enable_tools=True,
            tools=["mystic_verify_answer"],
            controller="gpt_controller",
        )
        imported_claims, imported_failures, imported_experiments = self._import_research_table(
            bundle=bundle,
            research_payload=result,
        )
        arena_turn = LabTurn(
            session_id=bundle.session.session_id,
            phase="simulation_or_execution",
            room="Model Arena",
            agent_role="ModelArena",
            provider="research_table",
            model_name="Research Table",
            input_summary=question or bundle.session.problem,
            output=result.get("final_synthesis_package", {}).get("final_status", "UNKNOWN"),
            requested_tools=["mystic_run_research_table", "mystic_verify_answer"],
            tool_results=[{"research_table_session_id": result["session_id"]}],
            status="completed",
        )
        bundle.turns.append(arena_turn)
        return result, imported_claims, imported_failures, imported_experiments

    def _import_research_table(
        self,
        *,
        bundle: LabSessionBundle,
        research_payload: dict[str, Any],
    ) -> tuple[int, int, int]:
        imported_claims = 0
        imported_failures = 0
        imported_experiments = 0
        source_session_id = research_payload.get("session_id", "")
        verifier_used = research_payload.get("final_decision_source") == "deterministic_verifier"
        for item in research_payload.get("accepted_discoveries", []):
            claim = Claim(
                session_id=bundle.session.session_id,
                text=str(item.get("claim", "")),
                claim_type="result",
                status="TESTED" if verifier_used else "HEURISTIC",
                confidence=str(item.get("confidence", "medium")),
                source_turn_id=str(item.get("source_turn_id", "")),
                supporting_evidence=[source_session_id],
            )
            bundle.claims.append(claim)
            imported_claims += 1
        for item in research_payload.get("rejected_discoveries", []):
            claim = Claim(
                session_id=bundle.session.session_id,
                text=str(item.get("claim", "")),
                claim_type="result",
                status="REFUTED" if verifier_used else "FAILED",
                confidence=str(item.get("confidence", "medium")),
                source_turn_id=str(item.get("source_turn_id", "")),
                refuting_evidence=[source_session_id],
            )
            bundle.claims.append(claim)
            imported_claims += 1
            failure = make_failure(
                session_id=bundle.session.session_id,
                claim_id=claim.claim_id,
                source_turn_id=claim.source_turn_id,
                first_fatal_error=str(item.get("rationale", "Research Table refuted this discovery.")),
                failure_type="contradiction",
                lesson="Model Arena rejected the discovery after verification.",
            )
            bundle.failures.append(failure)
            claim.related_failures.append(failure.failure_id)
            imported_failures += 1
            bundle.memory_edges.append(
                make_edge(
                    session_id=bundle.session.session_id,
                    from_id=claim.claim_id,
                    to_id=failure.failure_id,
                    relation="caused_failure",
                    evidence=failure.first_fatal_error,
                )
            )
        for request in research_payload.get("verification_requests", []):
            experiment = Experiment(
                session_id=bundle.session.session_id,
                claim_id=str(request.get("target_discovery_id") or ""),
                question=str(request.get("question", "Verification request")),
                method="model_debate",
                inputs=request,
                tool_name=str(request.get("tool", "mystic_verify_answer")),
            )
            bundle.experiments.append(experiment)
            imported_experiments += 1
        return imported_claims, imported_failures, imported_experiments


__all__ = ["LabRunner"]
