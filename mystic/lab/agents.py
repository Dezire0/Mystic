from __future__ import annotations

from mystic.lab.schema import PHASE_TO_ROOM


PHASE_ROLE_ORDER = {
    "problem_intake": "Director",
    "background_scan": "Theorist",
    "hypothesis_generation": "HypothesisGenerator",
    "experiment_design": "ExperimentDesigner",
    "simulation_or_execution": "Simulator",
    "referee_review": "Referee",
    "failure_archive": "Archivist",
    "knowledge_update": "Synthesizer",
    "next_experiment_planning": "Director",
    "report_generation": "PaperWriter",
}

AGENT_ROLE_TO_MODEL_ROLE = {
    "Director": "judge",
    "Theorist": "draft",
    "HypothesisGenerator": "draft",
    "ExperimentDesigner": "draft",
    "Simulator": "revise",
    "ProofForger": "draft",
    "Referee": "critique",
    "Archivist": "summarize",
    "Synthesizer": "summarize",
    "PaperWriter": "summarize",
    "ModelArena": "judge",
    "CodeRunner": "revise",
}


def room_for_phase(phase: str) -> str:
    return PHASE_TO_ROOM.get(phase, "Main Lab Room")


def role_for_phase(phase: str) -> str:
    return PHASE_ROLE_ORDER.get(phase, "Director")


def model_role_for_agent(agent_role: str) -> str:
    return AGENT_ROLE_TO_MODEL_ROLE.get(agent_role, "draft")


def build_role_task(*, phase: str, agent_role: str, problem: str, goal: str, context: str) -> str:
    return "\n".join(
        [
            f"Role: {agent_role}",
            f"Phase: {phase}",
            f"Problem: {problem}",
            f"Goal: {goal}",
            "Requirements:",
            "- Produce structured research output, not decorative narration.",
            "- Separate heuristic claims from verified findings.",
            "- State gaps directly.",
            "",
            "Context:",
            context or "No additional context.",
        ]
    )

