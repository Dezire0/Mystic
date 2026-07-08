from __future__ import annotations

from datetime import UTC, datetime


LAB_DOMAINS = {
    "math",
    "physics",
    "chemistry",
    "biology",
    "engineering",
    "software",
    "invention",
    "ai",
    "general",
}

LAB_SESSION_STATUSES = {
    "created",
    "running",
    "waiting_for_user",
    "blocked",
    "completed",
    "failed",
}

LAB_SESSION_MODES = {
    "single_session_subagents",
    "multi_model_debate",
    "proof_critical",
    "cheap",
    "serious",
}

LAB_PHASES = [
    "problem_intake",
    "background_scan",
    "hypothesis_generation",
    "experiment_design",
    "simulation_or_execution",
    "referee_review",
    "failure_archive",
    "knowledge_update",
    "next_experiment_planning",
    "report_generation",
    "completed",
]

LAB_AGENT_ROLES = {
    "Director",
    "Theorist",
    "HypothesisGenerator",
    "ExperimentDesigner",
    "Simulator",
    "ProofForger",
    "Referee",
    "Archivist",
    "Synthesizer",
    "PaperWriter",
    "ModelArena",
    "CodeRunner",
}

LAB_CLAIM_TYPES = {
    "theorem",
    "lemma",
    "hypothesis",
    "observation",
    "design",
    "bug",
    "result",
    "question",
    "assumption",
}

LAB_CLAIM_STATUSES = {
    "PROVED",
    "TESTED",
    "HEURISTIC",
    "FAILED",
    "UNKNOWN",
    "NEEDS_MORE_DETAIL",
    "REFUTED",
}

LAB_EXPERIMENT_METHODS = {
    "python_bruteforce",
    "symbolic",
    "simulation",
    "unit_test",
    "model_debate",
    "manual_review",
    "literature_scan_placeholder",
}

LAB_EXPERIMENT_VERDICTS = {
    "supports",
    "refutes",
    "inconclusive",
    "error",
}

LAB_ENGINE_ADAPTERS = {
    "math.sympy",
    "physics.simple_projectile",
    "physics.simple_collision",
    "scene.three_json",
}

LAB_PROVIDER_TYPES = {
    "openai_compatible",
    "gemini",
    "google_vertex_ai",
    "anthropic",
    "future/custom",
}

LAB_PROVIDER_AUTH_METHODS = {
    "api_key",
    "oauth",
    "bearer_token",
    "none/mock",
}

LAB_PROVIDER_STATUSES = {
    "not_configured",
    "provider_required",
    "api_key_required",
    "oauth_required",
    "connected",
    "auth_failed",
    "rate_limited",
    "provider_unavailable",
    "disconnected",
}

LAB_PROVIDER_AUTH_FLOW_STATUSES = {
    "pending",
    "oauth_required",
    "callback_received",
    "failed",
    "completed",
    "disconnected",
}

LAB_SIMULATION_STATUSES = {
    "completed",
    "engine_required",
    "unsupported_expression",
    "deferred",
    "error",
}

LAB_FAILURE_TYPES = {
    "arithmetic",
    "logic_gap",
    "invalid_assumption",
    "missing_case",
    "counterexample",
    "unsupported_generalization",
    "hallucination",
    "tool_error",
    "runtime_error",
    "insufficient_detail",
    "contradiction",
}

LAB_MEMORY_RELATIONS = {
    "supports",
    "refutes",
    "depends_on",
    "generalizes",
    "specializes",
    "contradicts",
    "caused_failure",
    "generated_experiment",
    "generated_training_data",
}

LAB_TURN_STATUSES = {
    "created",
    "running",
    "completed",
    "blocked",
    "failed",
    "AUTH_REQUIRED",
    "ERROR",
}

PHASE_TO_ROOM = {
    "problem_intake": "Main Lab Room",
    "background_scan": "Theory Room",
    "hypothesis_generation": "Hypothesis Chamber",
    "experiment_design": "Experiment Room",
    "simulation_or_execution": "Simulation Tank",
    "referee_review": "Referee Court",
    "failure_archive": "Failure Museum",
    "knowledge_update": "Research Memory Graph",
    "next_experiment_planning": "Control Panel",
    "report_generation": "Paper Room",
    "completed": "Main Lab Room",
}


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def validate_choice(field_name: str, value: str, allowed: set[str]) -> None:
    if value not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise ValueError(f"{field_name} must be one of [{allowed_text}]")
