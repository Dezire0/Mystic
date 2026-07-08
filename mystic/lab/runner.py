from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import json
import uuid

from mystic.lab.adapters import apply_simulation_to_scene, execute_adapter, export_scene, render_scene_report
from mystic.lab.agents import build_role_task, model_role_for_agent, role_for_phase, room_for_phase
from mystic.lab.claims import claims_from_turn
from mystic.lab.experiments import summarize_experiment
from mystic.lab.failures import make_failure
from mystic.lab.memory_graph import make_edge
from mystic.lab.provider_connect import ProviderConnectManager, normalize_provider_id
from mystic.lab.provider_router import ProviderRouter, SUPPORTED_PROVIDER_IDS
from mystic.lab.reality_anchor import normalize_claim_status
from mystic.lab.reports import render_report
from mystic.lab.schema import LAB_PHASES, PHASE_TO_ROOM
from mystic.lab.scene import LabScene, LabSceneBundle, LabSceneObject, LabSimulation, normalize_scene_object_payload
from mystic.lab.session import Claim, Experiment, LabSession, LabSessionBundle, LabTurn, MemoryEdge
from mystic.lab.storage import LabStorage


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
        self.provider_connect = ProviderConnectManager(storage=self.storage, runtime_mode="local_backend")
        self.provider_router = ProviderRouter(storage=self.storage, runtime_mode="local_backend")

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
            "provider_result": turn.tool_results[0] if turn.tool_results else {},
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
        provider: str = "",
    ) -> dict[str, Any]:
        bundle = self.storage.load_bundle(session_id)
        result = self._referee_review_in_bundle(
            bundle=bundle,
            claim_id=claim_id,
            text=text,
            strictness=strictness,
            provider=provider,
        )
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
        for session_id in self.storage.list_session_ids():
            try:
                bundle = self.storage.load_bundle(session_id)
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
        if selected and all(self._resolve_provider_alias(item)[0] in SUPPORTED_PROVIDER_IDS for item in selected):
            result = self._run_provider_debate_in_bundle(
                bundle=bundle,
                question=question,
                participants=selected,
                rounds=rounds,
            )
            bundle.session.next_actions = ["Review imported provider-backed debate claims.", "Run referee review on disputed claims."]
            bundle.session.touch()
            self.storage.save_bundle(bundle)
            return result
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

    def create_scene(
        self,
        *,
        session_id: str,
        title: str,
        description: str = "",
        units: dict[str, Any] | None = None,
        parameters: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session_bundle = self.storage.load_bundle(session_id)
        scene_id = f"scene-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
        scene = LabScene(
            scene_id=scene_id,
            session_id=session_id,
            domain=session_bundle.session.domain,
            title=title.strip(),
            description=description,
            units=dict(units or {}),
            parameters=dict(parameters or {}),
            metadata={"scene_adapter": "scene.three_json", **dict(metadata or {})},
        )
        scene_bundle = LabSceneBundle(scene=scene)
        paths = self.storage.save_scene(scene_bundle)
        return {
            "scene_id": scene_id,
            "session_id": session_id,
            "paths": paths,
            "scene": scene.to_dict(),
        }

    def get_scene(self, *, scene_id: str) -> dict[str, Any]:
        scene_bundle = self.storage.load_scene(scene_id)
        return self._scene_payload(scene_bundle)

    def add_object(self, *, scene_id: str, object: dict[str, Any]) -> dict[str, Any]:
        scene_bundle = self.storage.load_scene(scene_id)
        normalized = normalize_scene_object_payload(object, scene_id=scene_id)
        scene_object = LabSceneObject(**normalized)
        scene_bundle.objects.append(scene_object)
        scene_bundle.scene.touch()
        paths = self.storage.save_scene(scene_bundle)
        return {
            "scene_id": scene_id,
            "object_id": scene_object.id,
            "object": scene_object.to_dict(),
            "paths": paths,
        }

    def update_object(self, *, scene_id: str, object_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        scene_bundle = self.storage.load_scene(scene_id)
        target = self._scene_object_by_id(scene_bundle, object_id)
        updated_payload = target.to_dict()
        updated_payload.update({key: value for key, value in patch.items() if key not in {"scene_id", "id", "created_at"}})
        normalized = normalize_scene_object_payload(updated_payload, scene_id=scene_id)
        target.type = normalized["type"]
        target.label = normalized["label"]
        target.position = normalized["position"]
        target.rotation = normalized["rotation"]
        target.scale = normalized["scale"]
        target.geometry = normalized["geometry"]
        target.material = normalized["material"]
        target.data = normalized["data"]
        target.metadata = normalized["metadata"]
        target.touch()
        scene_bundle.scene.touch()
        paths = self.storage.save_scene(scene_bundle)
        return {
            "scene_id": scene_id,
            "object_id": target.id,
            "object": target.to_dict(),
            "paths": paths,
        }

    def remove_object(self, *, scene_id: str, object_id: str) -> dict[str, Any]:
        scene_bundle = self.storage.load_scene(scene_id)
        removed = self._scene_object_by_id(scene_bundle, object_id)
        scene_bundle.objects = [item for item in scene_bundle.objects if item.id != object_id]
        for simulation in scene_bundle.simulations:
            simulation.attached_object_ids = [item for item in simulation.attached_object_ids if item != object_id]
            simulation.touch()
        scene_bundle.scene.touch()
        paths = self.storage.save_scene(scene_bundle)
        return {
            "scene_id": scene_id,
            "removed_object_id": removed.id,
            "paths": paths,
        }

    def set_scene_parameters(
        self,
        *,
        scene_id: str,
        parameters: dict[str, Any],
        units: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        scene_bundle = self.storage.load_scene(scene_id)
        scene_bundle.scene.parameters.update(dict(parameters))
        if units:
            scene_bundle.scene.units.update(dict(units))
        if metadata:
            scene_bundle.scene.metadata.update(dict(metadata))
        scene_bundle.scene.touch()
        paths = self.storage.save_scene(scene_bundle)
        return {
            "scene_id": scene_id,
            "parameters": dict(scene_bundle.scene.parameters),
            "units": dict(scene_bundle.scene.units),
            "paths": paths,
        }

    def run_simulation(self, *, scene_id: str, adapter_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        scene_bundle = self.storage.load_scene(scene_id)
        result = execute_adapter(adapter_id, scene_bundle, dict(inputs))
        simulation = LabSimulation(
            simulation_id=f"sim-{uuid.uuid4().hex[:12]}",
            scene_id=scene_bundle.scene.scene_id,
            session_id=scene_bundle.scene.session_id,
            adapter_id=adapter_id,
            status=str(result["status"]),
            inputs=dict(inputs),
            outputs=dict(result.get("outputs", {})) if isinstance(result.get("outputs"), dict) else {},
            evidence=dict(result.get("evidence", {})) if isinstance(result.get("evidence"), dict) else {},
            warnings=[str(item) for item in result.get("warnings", []) if str(item)],
            errors=[str(item) for item in result.get("errors", []) if str(item)],
            attached_object_ids=[
                str(item).strip()
                for item in inputs.get("object_ids", [])
                if str(item).strip()
            ] or ([str(inputs.get("object_id")).strip()] if str(inputs.get("object_id", "")).strip() else []),
            metadata={
                "engine_status": result["status"],
                "scene_adapter": scene_bundle.scene.metadata.get("scene_adapter", "scene.three_json"),
            },
        )
        scene_bundle.simulations.append(simulation)
        scene_bundle.scene.evidence_refs.append(f"simulation:{simulation.simulation_id}")
        scene_bundle.scene.touch()
        paths = self.storage.save_scene(scene_bundle)
        return {
            "scene_id": scene_id,
            "simulation_id": simulation.simulation_id,
            "status": simulation.status,
            "result": result,
            "paths": paths,
        }

    def attach_simulation_to_scene(
        self,
        *,
        scene_id: str,
        simulation_id: str,
        object_ids: list[str] | None = None,
        evidence_refs: list[str] | None = None,
        report_refs: list[str] | None = None,
        apply_object_updates: bool = True,
    ) -> dict[str, Any]:
        scene_bundle = self.storage.load_scene(scene_id)
        simulation = self._scene_simulation_by_id(scene_bundle, simulation_id)
        selected_object_ids = [str(item).strip() for item in (object_ids or []) if str(item).strip()]
        if not selected_object_ids:
            selected_object_ids = list(simulation.attached_object_ids)
        simulation.attached_object_ids = selected_object_ids
        if simulation_id not in scene_bundle.scene.attached_simulations:
            scene_bundle.scene.attached_simulations.append(simulation_id)
        for ref in evidence_refs or []:
            ref_text = str(ref).strip()
            if ref_text and ref_text not in scene_bundle.scene.evidence_refs:
                scene_bundle.scene.evidence_refs.append(ref_text)
        for ref in report_refs or []:
            ref_text = str(ref).strip()
            if ref_text and ref_text not in scene_bundle.scene.report_refs:
                scene_bundle.scene.report_refs.append(ref_text)
        if apply_object_updates and simulation.status == "completed":
            apply_simulation_to_scene(scene_bundle, simulation, selected_object_ids)
        simulation.touch()
        scene_bundle.scene.touch()
        paths = self.storage.save_scene(scene_bundle)
        return {
            "scene_id": scene_id,
            "simulation_id": simulation_id,
            "attached_object_ids": list(simulation.attached_object_ids),
            "attached_simulations": list(scene_bundle.scene.attached_simulations),
            "paths": paths,
        }

    def export_snapshot(
        self,
        *,
        scene_id: str,
        adapter_id: str,
        include_simulations: bool,
    ) -> dict[str, Any]:
        scene_bundle = self.storage.load_scene(scene_id)
        export_result = export_scene(adapter_id, scene_bundle, include_simulations=include_simulations)
        if export_result["status"] == "completed":
            scene_bundle.scene.exports_json[adapter_id] = export_result["outputs"]["snapshot"]
            scene_bundle.scene.touch()
            paths = self.storage.save_scene(scene_bundle)
        else:
            paths = scene_bundle.scene.artifact_paths
        return {
            "scene_id": scene_id,
            "adapter_id": adapter_id,
            "status": export_result["status"],
            "snapshot": export_result.get("outputs", {}).get("snapshot"),
            "paths": paths,
        }

    def generate_scene_report(
        self,
        *,
        scene_id: str,
        format: str,
        include_objects: bool,
        include_simulations: bool,
    ) -> dict[str, Any]:
        if format != "markdown":
            raise ValueError("Only markdown report generation is supported.")
        scene_bundle = self.storage.load_scene(scene_id)
        scene_bundle.scene.report_markdown = render_scene_report(scene_bundle)
        report_path = scene_bundle.scene.artifact_paths.get("report", "")
        if report_path and report_path not in scene_bundle.scene.report_refs:
            scene_bundle.scene.report_refs.append(report_path)
        for simulation in scene_bundle.simulations:
            refs = simulation.metadata.setdefault("report_refs", [])
            if isinstance(refs, list) and report_path and report_path not in refs:
                refs.append(report_path)
            simulation.touch()
        scene_bundle.scene.touch()
        paths = self.storage.save_scene(scene_bundle)
        object_count = len(scene_bundle.objects) if include_objects else 0
        simulation_count = len(scene_bundle.simulations) if include_simulations else 0
        return {
            "scene_id": scene_id,
            "report_path": paths["report"],
            "markdown": scene_bundle.scene.report_markdown,
            "summary": {
                "objects": object_count,
                "simulations": simulation_count,
                "attached_simulations": len(scene_bundle.scene.attached_simulations),
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
        for model_id in participants:
            provider_key = normalize_provider_id(model_id)
            if provider_key in SUPPORTED_PROVIDER_IDS:
                provider_status = self.provider_connect.provider_status(provider_id=provider_key)
                ready = provider_key == "mock" or provider_status["status"] == "connected"
                model_name = (
                    provider_status.get("model_list", [provider_key])[0]
                    if isinstance(provider_status.get("model_list"), list) and provider_status.get("model_list")
                    else provider_key
                )
                models.append(
                    {
                        "model_id": provider_key,
                        "provider": provider_key,
                        "model_name": model_name,
                        "status": {
                            "state": provider_status["status"],
                            "available": ready,
                            "authenticated": ready,
                            "message": provider_status.get("failure_reason", ""),
                        },
                    }
                )
                continue
            item = snapshot.get(model_id, {})
            status = item.get("status", {})
            models.append(
                {
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
        provider_key = self._provider_key_for_participant(participant)
        if provider_key in SUPPORTED_PROVIDER_IDS:
            return self._run_provider_turn(
                bundle=bundle,
                phase=phase,
                agent_role=agent_role,
                task=task,
                context=context,
                requested_tools=requested_tools,
                provider_id=provider_key,
                requested_model=str(participant.get("model_name", "")),
            )
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

    def _run_provider_turn(
        self,
        *,
        bundle: LabSessionBundle,
        phase: str,
        agent_role: str,
        task: str,
        context: str,
        requested_tools: list[str],
        provider_id: str,
        requested_model: str,
    ) -> LabTurn:
        provider_result = self.provider_router.invoke(
            provider_id=provider_id,
            tool_name="lab_agent_run",
            session_id=bundle.session.session_id,
            agent_role=agent_role,
            model=requested_model,
            system_prompt=f"You are Mystic LAB agent {agent_role} operating in phase {phase}.",
            prompt="\n".join(
                [
                    f"Problem: {bundle.session.problem}",
                    f"Goal: {bundle.session.goal}",
                    f"Task: {task}",
                    "",
                    "Context:",
                    context,
                ]
            ),
            metadata={"phase": phase},
        )
        turn_status = "completed"
        if provider_result["status"] in {"provider_required", "api_key_required", "provider_auth_failed"}:
            turn_status = "AUTH_REQUIRED"
        elif provider_result["status"] != "completed":
            turn_status = "ERROR"
        output = provider_result["output_text"] or provider_result["error_message_safe"] or "Provider returned no output."
        extracted_claims = self._extract_claim_payloads(output, phase=phase) if turn_status == "completed" else []
        return LabTurn(
            session_id=bundle.session.session_id,
            phase=phase,
            room=room_for_phase(phase),
            agent_role=agent_role,
            provider=provider_id,
            model_name=provider_result["model"] or provider_id,
            input_summary=task[:200],
            output=output,
            extracted_claims=extracted_claims,
            requested_tools=requested_tools,
            tool_results=[provider_result],
            status=turn_status,
            error="" if turn_status == "completed" else provider_result["error_message_safe"],
        )

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
        provider: str = "",
    ) -> dict[str, Any]:
        provider_key = normalize_provider_id(provider)
        if provider_key in SUPPORTED_PROVIDER_IDS:
            return self._provider_referee_review_in_bundle(
                bundle=bundle,
                claim_id=claim_id,
                text=text,
                strictness=strictness,
                provider_id=provider_key,
            )
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

    def _provider_referee_review_in_bundle(
        self,
        *,
        bundle: LabSessionBundle,
        claim_id: str | None,
        text: str,
        strictness: str,
        provider_id: str,
    ) -> dict[str, Any]:
        claim = self._claim_by_id(bundle, claim_id) if claim_id else None
        target_text = text.strip() or (claim.text if claim is not None else "")
        provider_result = self.provider_router.invoke(
            provider_id=provider_id,
            tool_name="lab_referee_review",
            session_id=bundle.session.session_id,
            agent_role="Referee",
            system_prompt="You are a strict Mystic LAB referee. Return JSON with keys verdict, critique, first_fatal_error, recommended_next_action.",
            prompt="\n".join(
                [
                    f"Problem: {bundle.session.problem}",
                    f"Strictness: {strictness}",
                    f"Claim text: {target_text}",
                    "If you cannot verify completely, return verdict UNKNOWN and explain the gap.",
                ]
            ),
            metadata={"strictness": strictness, "claim_id": claim_id or ""},
        )
        parsed = self._parse_provider_referee_output(provider_result["output_text"])
        verdict = parsed.get("verdict", "UNKNOWN")
        first_fatal_error = parsed.get("first_fatal_error", "")
        critique = parsed.get("critique", provider_result["error_message_safe"] or provider_result["output_text"])
        recommended_next_action = parsed.get("recommended_next_action", "Review referee verdict.")
        updated_claims: list[Claim] = []
        failures = []
        if provider_result["status"] == "completed" and claim is not None:
            claim.status = normalize_claim_status(
                verifier_verdict=verdict,
                referee_fatal_error=bool(first_fatal_error and strictness == "hostile"),
                incomplete_proof=verdict == "UNKNOWN",
            )
            claim.touch()
            updated_claims.append(claim)
            if first_fatal_error:
                failure = make_failure(
                    session_id=bundle.session.session_id,
                    claim_id=claim.claim_id,
                    source_turn_id="",
                    first_fatal_error=first_fatal_error,
                    failure_type="logic_gap",
                    lesson="Provider-backed referee identified a failure or proof gap.",
                )
                bundle.failures.append(failure)
                claim.related_failures.append(failure.failure_id)
                failures.append(failure)
        turn_status = "completed"
        if provider_result["status"] in {"provider_required", "api_key_required", "provider_auth_failed"}:
            turn_status = "AUTH_REQUIRED"
        elif provider_result["status"] != "completed":
            turn_status = "ERROR"
        turn = LabTurn(
            session_id=bundle.session.session_id,
            phase="referee_review",
            room=room_for_phase("referee_review"),
            agent_role="Referee",
            provider=provider_id,
            model_name=provider_result["model"] or provider_id,
            input_summary=target_text[:200],
            output=provider_result["output_text"] or provider_result["error_message_safe"],
            requested_tools=["lab_referee_review"],
            tool_results=[provider_result],
            status=turn_status,
            error="" if turn_status == "completed" else provider_result["error_message_safe"],
        )
        bundle.turns.append(turn)
        return {
            "verdict": verdict if provider_result["status"] == "completed" else provider_result["status"].upper(),
            "first_fatal_error": first_fatal_error,
            "critique": critique,
            "recommended_next_action": recommended_next_action,
            "updated_claims": [item.to_dict() for item in updated_claims],
            "failures": [item.to_dict() for item in failures],
            "provider_result": provider_result,
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

    def _run_provider_debate_in_bundle(
        self,
        *,
        bundle: LabSessionBundle,
        question: str,
        participants: list[str],
        rounds: list[str],
    ) -> dict[str, Any]:
        resolved = [self._resolve_provider_alias(item) for item in participants[:3]]
        missing = [item for item in resolved if self._provider_readiness(item[0]) != "connected"]
        if missing:
            provider_status = self.provider_connect.provider_status(provider_id=missing[0][0])
            return {
                "debate_session_id": "",
                "research_table_session_id": "",
                "imported_claims": 0,
                "imported_failures": 0,
                "summary": "Provider-backed debate could not start because a participant is not connected.",
                "provider_result": {
                    "status": self.provider_router._status_from_provider_payload(provider_status),
                    "provider_id": provider_status["provider_id"],
                    "model": "",
                    "output_text": "",
                    "raw_usage_safe": {},
                    "latency_ms": 0,
                    "error_type": self.provider_router._status_from_provider_payload(provider_status),
                    "error_message_safe": provider_status.get("setup_instructions", ""),
                    "call_id": "",
                    "storage_ref": "",
                },
                "transcript": [],
                "final_synthesis": "",
            }

        transcript: list[dict[str, Any]] = []
        imported_claims = 0
        for provider_id, requested_model in resolved:
            debate_prompt = "\n".join(
                [
                    "Participate in a Mystic LAB debate.",
                    f"Question: {question or bundle.session.problem}",
                    f"Rounds: {', '.join(rounds)}",
                    "Prior transcript:",
                    json.dumps(transcript, ensure_ascii=False),
                ]
            )
            result = self.provider_router.invoke(
                provider_id=provider_id,
                tool_name="lab_models_debate",
                session_id=bundle.session.session_id,
                agent_role="ModelArena",
                model=requested_model,
                system_prompt="You are one participant in a structured research debate. Be explicit about assumptions and uncertainties.",
                prompt=debate_prompt,
                metadata={"rounds": rounds, "question": question},
            )
            turn_status = "completed" if result["status"] == "completed" else "ERROR"
            output = result["output_text"] or result["error_message_safe"]
            turn = LabTurn(
                session_id=bundle.session.session_id,
                phase="simulation_or_execution",
                room="Model Arena",
                agent_role="ModelArena",
                provider=provider_id,
                model_name=result["model"] or provider_id,
                input_summary=(question or bundle.session.problem)[:200],
                output=output,
                extracted_claims=self._extract_claim_payloads(output, phase="simulation_or_execution") if turn_status == "completed" else [],
                requested_tools=["lab_models_debate"],
                tool_results=[result],
                status=turn_status,
                error="" if turn_status == "completed" else result["error_message_safe"],
            )
            bundle.turns.append(turn)
            claims = claims_from_turn(bundle.session.session_id, turn) if turn_status == "completed" else []
            if claims:
                bundle.claims.extend(claims)
                imported_claims += len(claims)
            transcript.append(
                {
                    "provider_id": provider_id,
                    "model": result["model"],
                    "status": result["status"],
                    "output_text": output,
                    "call_id": result["call_id"],
                }
            )

        synthesis_result = self.provider_router.invoke(
            provider_id=resolved[0][0],
            tool_name="lab_models_debate",
            session_id=bundle.session.session_id,
            agent_role="Synthesizer",
            model=resolved[0][1],
            system_prompt="You are the final synthesizer for a provider-backed Mystic LAB debate. Summarize agreement, disagreements, and next checks.",
            prompt="\n".join(
                [
                    f"Question: {question or bundle.session.problem}",
                    "Transcript:",
                    json.dumps(transcript, ensure_ascii=False),
                ]
            ),
            metadata={"rounds": rounds, "synthesis": True},
        )
        synthesis_turn = LabTurn(
            session_id=bundle.session.session_id,
            phase="simulation_or_execution",
            room="Model Arena",
            agent_role="Synthesizer",
            provider=resolved[0][0],
            model_name=synthesis_result["model"] or resolved[0][0],
            input_summary=(question or bundle.session.problem)[:200],
            output=synthesis_result["output_text"] or synthesis_result["error_message_safe"],
            requested_tools=["lab_models_debate"],
            tool_results=[synthesis_result],
            status="completed" if synthesis_result["status"] == "completed" else "ERROR",
            error="" if synthesis_result["status"] == "completed" else synthesis_result["error_message_safe"],
        )
        bundle.turns.append(synthesis_turn)
        return {
            "debate_session_id": f"debate-{uuid.uuid4().hex[:12]}",
            "research_table_session_id": "",
            "imported_claims": imported_claims,
            "imported_failures": 0,
            "summary": synthesis_turn.output or f"Provider-backed debate completed with {len(transcript)} participants.",
            "transcript": transcript,
            "final_synthesis": synthesis_turn.output,
            "provider_results": [item["call_id"] for item in transcript],
        }

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

    @staticmethod
    def _provider_key_for_participant(participant: dict[str, Any]) -> str:
        provider = normalize_provider_id(str(participant.get("provider", "")))
        if provider in SUPPORTED_PROVIDER_IDS:
            return provider
        model_id = normalize_provider_id(str(participant.get("model_id", "")))
        return model_id if model_id in SUPPORTED_PROVIDER_IDS else ""

    @staticmethod
    def _resolve_provider_alias(value: str) -> tuple[str, str]:
        raw = str(value or "").strip()
        if ":" in raw:
            provider_id, model = raw.split(":", 1)
            return normalize_provider_id(provider_id), model.strip()
        return normalize_provider_id(raw), ""

    def _provider_readiness(self, provider_id: str) -> str:
        if provider_id == "mock":
            return "connected"
        payload = self.provider_connect.provider_status(provider_id=provider_id)
        return self.provider_router._status_from_provider_payload(payload)

    @staticmethod
    def _parse_provider_referee_output(text: str) -> dict[str, str]:
        try:
            payload = json.loads(text)
        except (TypeError, json.JSONDecodeError):
            return {
                "verdict": "UNKNOWN",
                "critique": str(text or "").strip() or "Provider referee did not return parseable JSON.",
                "first_fatal_error": "",
                "recommended_next_action": "Review provider-backed referee output manually.",
            }
        if not isinstance(payload, dict):
            return {
                "verdict": "UNKNOWN",
                "critique": str(text or "").strip() or "Provider referee returned an unexpected payload.",
                "first_fatal_error": "",
                "recommended_next_action": "Review provider-backed referee output manually.",
            }
        verdict = str(payload.get("verdict", "UNKNOWN")).upper()
        if verdict not in {"VALID", "INVALID", "UNKNOWN"}:
            verdict = "UNKNOWN"
        return {
            "verdict": verdict,
            "critique": str(payload.get("critique", "")).strip(),
            "first_fatal_error": str(payload.get("first_fatal_error", "")).strip(),
            "recommended_next_action": str(payload.get("recommended_next_action", "Review referee verdict.")).strip(),
        }

    @staticmethod
    def _scene_object_by_id(scene_bundle: LabSceneBundle, object_id: str) -> LabSceneObject:
        for item in scene_bundle.objects:
            if item.id == object_id:
                return item
        raise KeyError(f"Unknown scene object id: {object_id}")

    @staticmethod
    def _scene_simulation_by_id(scene_bundle: LabSceneBundle, simulation_id: str) -> LabSimulation:
        for item in scene_bundle.simulations:
            if item.simulation_id == simulation_id:
                return item
        raise KeyError(f"Unknown simulation_id: {simulation_id}")

    @staticmethod
    def _scene_payload(scene_bundle: LabSceneBundle) -> dict[str, Any]:
        return {
            "scene": scene_bundle.scene.to_dict(),
            "scene_id": scene_bundle.scene.scene_id,
            "session_id": scene_bundle.scene.session_id,
            "objects": [item.to_dict() for item in scene_bundle.objects],
            "simulations": [item.to_dict() for item in scene_bundle.simulations],
            "attached_simulations": list(scene_bundle.scene.attached_simulations),
            "report_path": scene_bundle.scene.artifact_paths.get("report", ""),
            "snapshot_path": scene_bundle.scene.artifact_paths.get("snapshot", ""),
            "report_markdown": scene_bundle.scene.report_markdown,
            "exports": dict(scene_bundle.scene.exports_json),
        }


__all__ = ["LabRunner"]
