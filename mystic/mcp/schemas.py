from __future__ import annotations


SCENE_OBJECT_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "minLength": 1},
        "type": {"type": "string", "minLength": 1},
        "label": {"type": "string", "minLength": 1},
        "position": {"type": "object"},
        "rotation": {"type": "object"},
        "scale": {"type": "object"},
        "geometry": {"type": "object"},
        "material": {"type": "object"},
        "data": {"type": "object"},
        "metadata": {"type": "object"},
    },
    "required": ["id", "type", "label", "position", "rotation", "scale", "geometry", "material", "data", "metadata"],
    "additionalProperties": False,
}


TOOL_SCHEMAS = {
    "mystic_status": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    "health_check": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    "mystic_verify_answer": {
        "type": "object",
        "properties": {
            "problem": {"type": "string", "minLength": 1},
            "candidate_answer": {"type": "string", "minLength": 1},
            "constraints": {"type": "array", "items": {"type": "string"}, "maxItems": 12},
            "bounds": {"type": "object"},
        },
        "required": ["problem", "candidate_answer"],
        "additionalProperties": False,
    },
    "mystic_bruteforce_integer_search": {
        "type": "object",
        "properties": {
            "equation": {"type": "string"},
            "variables": {"type": "array", "items": {"type": "string"}},
            "constraints": {"type": "array", "items": {"type": "string"}},
            "bounds": {"type": "object"},
        },
        "required": ["equation", "variables", "constraints", "bounds"],
        "additionalProperties": False,
    },
    "mystic_run_python_check": {
        "type": "object",
        "properties": {
            "code_or_task": {"type": "string"},
            "mode": {"type": "string", "enum": ["task", "code"]},
            "timeout_seconds": {"type": "integer"},
        },
        "required": ["code_or_task", "mode"],
        "additionalProperties": False,
    },
    "mystic_run_local_agent": {
        "type": "object",
        "properties": {
            "agent": {"type": "string", "enum": ["prime", "forge", "raven", "report"]},
            "model": {"type": "string"},
            "task": {"type": "string"},
            "problem": {"type": "string"},
            "context": {"type": "string"},
            "max_tokens": {"type": "integer"},
            "temperature": {"type": "number"},
        },
        "required": ["agent", "task", "problem"],
        "additionalProperties": False,
    },
    "mystic_call_model": {
        "type": "object",
        "properties": {
            "model_id": {"type": "string", "minLength": 1},
            "role": {"type": "string", "enum": ["draft", "critique", "revise", "judge", "summarize"]},
            "task": {"type": "string", "minLength": 1},
            "problem": {"type": "string", "minLength": 1},
            "context": {"type": "string"},
            "max_tokens": {"type": "integer", "minimum": 1},
            "temperature": {"type": "number"},
        },
        "required": ["model_id", "role", "task", "problem"],
        "additionalProperties": False,
    },
    "mystic_compare_models": {
        "type": "object",
        "properties": {
            "problem": {"type": "string", "minLength": 1},
            "models": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 3},
            "task": {"type": "string", "minLength": 1},
            "include_verifier": {"type": "boolean"},
            "max_output_chars_per_model": {"type": "integer", "minimum": 64},
        },
        "required": ["problem", "models", "task", "include_verifier"],
        "additionalProperties": False,
    },
    "mystic_run_debate": {
        "type": "object",
        "properties": {
            "problem": {"type": "string"},
            "participants": {"type": "array"},
            "rounds": {"type": "integer"},
            "tools": {"type": "array", "items": {"type": "string"}},
            "judge": {"type": "string"},
            "max_turns": {"type": "integer"},
        },
        "required": ["problem", "participants", "rounds", "tools"],
        "additionalProperties": False,
    },
    "mystic_run_research_table": {
        "type": "object",
        "properties": {
            "problem": {"type": "string", "minLength": 1},
            "participants": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 4},
            "mode": {"type": "string", "enum": ["discovery_debate", "discovery_only"]},
            "max_rounds": {"type": "integer", "minimum": 1, "maximum": 6},
            "enable_tools": {"type": "boolean"},
            "tools": {"type": "array", "items": {"type": "string", "enum": ["mystic_verify_answer"]}, "maxItems": 4},
            "controller": {"type": "string"},
        },
        "required": ["problem", "participants", "mode", "max_rounds", "enable_tools", "tools"],
        "additionalProperties": False,
    },
    "lab_session_create": {
        "type": "object",
        "properties": {
            "problem": {"type": "string", "minLength": 1},
            "domain": {
                "type": "string",
                "enum": ["math", "physics", "chemistry", "biology", "engineering", "software", "invention", "ai", "general"],
            },
            "goal": {"type": "string", "minLength": 1},
            "mode": {
                "type": "string",
                "enum": ["cheap", "serious", "proof_critical", "single_session_subagents", "multi_model_debate"],
            },
            "participants": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 4},
        },
        "required": ["problem", "domain", "goal", "mode", "participants"],
        "additionalProperties": False,
    },
    "lab_session_get": {
        "type": "object",
        "properties": {"session_id": {"type": "string", "minLength": 1}},
        "required": ["session_id"],
        "additionalProperties": False,
    },
    "lab_session_advance": {
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "minLength": 1},
            "max_steps": {"type": "integer", "minimum": 1, "maximum": 10},
            "target_phase": {"type": "string"},
            "use_model_arena": {"type": "boolean"},
            "use_verifier": {"type": "boolean"},
        },
        "required": ["session_id"],
        "additionalProperties": False,
    },
    "lab_agent_run": {
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "minLength": 1},
            "agent_role": {
                "type": "string",
                "enum": [
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
                ],
            },
            "provider": {"type": "string", "enum": ["auto", "local", "gemini_cli", "claude_cli"]},
            "task": {"type": "string", "minLength": 1},
            "context_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 16},
        },
        "required": ["session_id", "agent_role", "provider", "task", "context_ids"],
        "additionalProperties": False,
    },
    "lab_referee_review": {
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "minLength": 1},
            "claim_id": {"type": "string"},
            "text": {"type": "string"},
            "strictness": {"type": "string", "enum": ["normal", "hostile"]},
        },
        "required": ["session_id", "text", "strictness"],
        "additionalProperties": False,
    },
    "lab_experiment_create": {
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "minLength": 1},
            "claim_id": {"type": "string", "minLength": 1},
            "question": {"type": "string", "minLength": 1},
            "method": {
                "type": "string",
                "enum": ["python_bruteforce", "symbolic", "simulation", "unit_test", "model_debate", "manual_review"],
            },
            "inputs": {"type": "object"},
        },
        "required": ["session_id", "claim_id", "question", "method", "inputs"],
        "additionalProperties": False,
    },
    "lab_experiment_run": {
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "minLength": 1},
            "experiment_id": {"type": "string", "minLength": 1},
            "dry_run": {"type": "boolean"},
        },
        "required": ["session_id", "experiment_id"],
        "additionalProperties": False,
    },
    "lab_memory_search": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 1},
            "domain": {"type": "string"},
            "status_filter": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    "lab_memory_write": {
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "minLength": 1},
            "kind": {"type": "string", "enum": ["claim", "failure", "experiment", "note", "edge"]},
            "payload": {"type": "object"},
        },
        "required": ["session_id", "kind", "payload"],
        "additionalProperties": False,
    },
    "lab_models_debate": {
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "minLength": 1},
            "question": {"type": "string", "minLength": 1},
            "participants": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 4},
            "rounds": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8},
            "use_existing_research_table": {"type": "boolean"},
        },
        "required": ["session_id", "question", "participants", "rounds", "use_existing_research_table"],
        "additionalProperties": False,
    },
    "lab_report_generate": {
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "minLength": 1},
            "format": {"type": "string", "enum": ["markdown"]},
            "include_failures": {"type": "boolean"},
            "include_next_actions": {"type": "boolean"},
        },
        "required": ["session_id", "format", "include_failures", "include_next_actions"],
        "additionalProperties": False,
    },
    "create_lab_scene": {
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "minLength": 1},
            "title": {"type": "string", "minLength": 1},
            "description": {"type": "string"},
            "units": {"type": "object"},
            "parameters": {"type": "object"},
            "metadata": {"type": "object"},
        },
        "required": ["session_id", "title"],
        "additionalProperties": False,
    },
    "get_lab_scene": {
        "type": "object",
        "properties": {
            "scene_id": {"type": "string", "minLength": 1},
        },
        "required": ["scene_id"],
        "additionalProperties": False,
    },
    "add_lab_object": {
        "type": "object",
        "properties": {
            "scene_id": {"type": "string", "minLength": 1},
            "object": SCENE_OBJECT_SCHEMA,
        },
        "required": ["scene_id", "object"],
        "additionalProperties": False,
    },
    "update_lab_object": {
        "type": "object",
        "properties": {
            "scene_id": {"type": "string", "minLength": 1},
            "object_id": {"type": "string", "minLength": 1},
            "patch": {"type": "object"},
        },
        "required": ["scene_id", "object_id", "patch"],
        "additionalProperties": False,
    },
    "remove_lab_object": {
        "type": "object",
        "properties": {
            "scene_id": {"type": "string", "minLength": 1},
            "object_id": {"type": "string", "minLength": 1},
        },
        "required": ["scene_id", "object_id"],
        "additionalProperties": False,
    },
    "set_lab_parameters": {
        "type": "object",
        "properties": {
            "scene_id": {"type": "string", "minLength": 1},
            "parameters": {"type": "object"},
            "units": {"type": "object"},
            "metadata": {"type": "object"},
        },
        "required": ["scene_id", "parameters"],
        "additionalProperties": False,
    },
    "run_lab_simulation": {
        "type": "object",
        "properties": {
            "scene_id": {"type": "string", "minLength": 1},
            "adapter_id": {
                "type": "string",
                "enum": ["math.sympy", "physics.simple_projectile", "physics.simple_collision"],
            },
            "inputs": {"type": "object"},
        },
        "required": ["scene_id", "adapter_id", "inputs"],
        "additionalProperties": False,
    },
    "attach_simulation_to_scene": {
        "type": "object",
        "properties": {
            "scene_id": {"type": "string", "minLength": 1},
            "simulation_id": {"type": "string", "minLength": 1},
            "object_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 32},
            "evidence_refs": {"type": "array", "items": {"type": "string"}, "maxItems": 32},
            "report_refs": {"type": "array", "items": {"type": "string"}, "maxItems": 32},
            "apply_object_updates": {"type": "boolean"},
        },
        "required": ["scene_id", "simulation_id", "apply_object_updates"],
        "additionalProperties": False,
    },
    "export_lab_snapshot": {
        "type": "object",
        "properties": {
            "scene_id": {"type": "string", "minLength": 1},
            "adapter_id": {"type": "string", "enum": ["scene.three_json"]},
            "include_simulations": {"type": "boolean"},
        },
        "required": ["scene_id", "adapter_id", "include_simulations"],
        "additionalProperties": False,
    },
    "generate_lab_report": {
        "type": "object",
        "properties": {
            "scene_id": {"type": "string", "minLength": 1},
            "format": {"type": "string", "enum": ["markdown"]},
            "include_objects": {"type": "boolean"},
            "include_simulations": {"type": "boolean"},
        },
        "required": ["scene_id", "format", "include_objects", "include_simulations"],
        "additionalProperties": False,
    },
    "provider_list": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    "provider_status": {
        "type": "object",
        "properties": {"provider_id": {"type": "string", "minLength": 1}},
        "required": ["provider_id"],
        "additionalProperties": False,
    },
    "provider_connect_start": {
        "type": "object",
        "properties": {
            "provider_id": {"type": "string", "minLength": 1},
            "auth_method": {"type": "string", "enum": ["api_key", "oauth", "bearer_token", "none/mock"]},
        },
        "required": ["provider_id"],
        "additionalProperties": False,
    },
    "provider_connect_callback_status": {
        "type": "object",
        "properties": {
            "provider_id": {"type": "string", "minLength": 1},
            "flow_id": {"type": "string", "minLength": 1},
        },
        "required": ["provider_id", "flow_id"],
        "additionalProperties": False,
    },
    "provider_configure_secret_instructions": {
        "type": "object",
        "properties": {"provider_id": {"type": "string", "minLength": 1}},
        "required": ["provider_id"],
        "additionalProperties": False,
    },
    "provider_verify": {
        "type": "object",
        "properties": {"provider_id": {"type": "string", "minLength": 1}},
        "required": ["provider_id"],
        "additionalProperties": False,
    },
    "provider_disconnect": {
        "type": "object",
        "properties": {"provider_id": {"type": "string", "minLength": 1}},
        "required": ["provider_id"],
        "additionalProperties": False,
    },
    "provider_model_list": {
        "type": "object",
        "properties": {"provider_id": {"type": "string", "minLength": 1}},
        "required": ["provider_id"],
        "additionalProperties": False,
    },
    "provider_call_test": {
        "type": "object",
        "properties": {
            "provider_id": {"type": "string", "minLength": 1},
            "prompt": {"type": "string", "minLength": 1},
        },
        "required": ["provider_id", "prompt"],
        "additionalProperties": False,
    },
    "mystic_export_teacher_packet": {
        "type": "object",
        "properties": {
            "limit": {"type": "integer"},
            "filter": {"type": "string"},
            "target_agent": {"type": "string"},
        },
        "required": ["limit", "filter"],
        "additionalProperties": False,
    },
    "mystic_import_teacher_label": {
        "type": "object",
        "properties": {
            "packet_id": {"type": "string"},
            "label_json": {"type": "object"},
            "source_model": {"type": "string"},
            "target_agent": {"type": "string", "enum": ["raven", "prime", "forge", "report"]},
        },
        "required": ["packet_id", "label_json", "source_model", "target_agent"],
        "additionalProperties": False,
    },
}


DEFAULT_OAUTH_SECURITY_SCHEMES = [
    {
        "type": "oauth2",
        "scopes": ["tools:read", "tools:execute"],
    }
]


def _tool_definition(
    name: str,
    description: str,
    *,
    title: str,
    read_only: bool = False,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": name,
        "title": title,
        "description": description,
        "inputSchema": TOOL_SCHEMAS[name],
        "securitySchemes": DEFAULT_OAUTH_SECURITY_SCHEMES,
    }
    if read_only:
        payload["annotations"] = {"readOnlyHint": True}
    return payload


TOOL_DEFINITIONS = [
    _tool_definition(
        "mystic_status",
        "Return current Mystic model, dataset, adapter, and tool availability status.",
        title="Mystic Status",
        read_only=True,
    ),
    _tool_definition(
        "health_check",
        "Return a minimal local Mystic health summary without depending on external model providers.",
        title="Health Check",
        read_only=True,
    ),
    _tool_definition(
        "mystic_verify_answer",
        "Deterministically verify candidate answers when direct substitution or bounded search is possible.",
        title="Verify Answer",
        read_only=True,
    ),
    _tool_definition(
        "mystic_bruteforce_integer_search",
        "Search bounded integer domains for solutions to a symbolic equation under constraints.",
        title="Bruteforce Integer Search",
        read_only=True,
    ),
    _tool_definition(
        "mystic_run_python_check",
        "Run constrained Python checks inside Mystic's safe local sandbox.",
        title="Run Python Check",
    ),
    _tool_definition(
        "mystic_run_local_agent",
        "Run a local Mystic agent in draft, critique, or summary mode.",
        title="Run Local Agent",
    ),
    _tool_definition(
        "mystic_call_model",
        "Call any registered Mystic model through the unified ModelRouter.",
        title="Call Model",
    ),
    _tool_definition(
        "mystic_compare_models",
        "Call multiple models and optionally append deterministic verifier output.",
        title="Compare Models",
    ),
    _tool_definition(
        "mystic_run_debate",
        "Run a threaded multi-model debate with critique, tool evidence, revision, and final judgment.",
        title="Run Debate",
    ),
    _tool_definition(
        "mystic_run_research_table",
        "Run the Research Table discovery workflow with structured discoveries and verification requests.",
        title="Run Research Table",
    ),
    _tool_definition(
        "lab_session_create",
        "Create a structured Mystic Lab session using the active storage backend.",
        title="Create Lab Session",
    ),
    _tool_definition(
        "lab_session_get",
        "Load the current lab session state, recent turns, claims, experiments, and failures from the active storage backend.",
        title="Get Lab Session",
        read_only=True,
    ),
    _tool_definition(
        "lab_session_advance",
        "Advance a lab session through structured research phases and persist new artifacts.",
        title="Advance Lab Session",
    ),
    _tool_definition(
        "lab_agent_run",
        "Run a specific virtual lab role against a session and store a structured LabTurn.",
        title="Run Lab Agent",
    ),
    _tool_definition(
        "lab_referee_review",
        "Run a deterministic referee review against a claim or text and archive failures when found.",
        title="Referee Review",
    ),
    _tool_definition(
        "lab_experiment_create",
        "Create a lab experiment linked to a claim.",
        title="Create Experiment",
    ),
    _tool_definition(
        "lab_experiment_run",
        "Run a saved lab experiment and update linked claim evidence.",
        title="Run Experiment",
    ),
    _tool_definition(
        "lab_memory_search",
        "Search across saved lab session memory, claims, failures, and experiments.",
        title="Search Lab Memory",
        read_only=True,
    ),
    _tool_definition(
        "lab_memory_write",
        "Write structured claim, failure, experiment, note, or edge data into a lab session.",
        title="Write Lab Memory",
    ),
    _tool_definition(
        "lab_models_debate",
        "Run the existing Research Table as the Model Arena and import its outputs into a lab session.",
        title="Run Model Arena Debate",
    ),
    _tool_definition(
        "lab_report_generate",
        "Generate a markdown lab report from structured session state and persist it through the active storage backend.",
        title="Generate Lab Report",
    ),
    _tool_definition(
        "create_lab_scene",
        "Create a persisted Mystic LAB scene linked to an existing session.",
        title="Create Lab Scene",
    ),
    _tool_definition(
        "get_lab_scene",
        "Load a persisted Mystic LAB scene, including its objects and stored simulations.",
        title="Get Lab Scene",
        read_only=True,
    ),
    _tool_definition(
        "add_lab_object",
        "Add a structured object to a persisted Mystic LAB scene.",
        title="Add Lab Object",
    ),
    _tool_definition(
        "update_lab_object",
        "Update a structured object inside a persisted Mystic LAB scene.",
        title="Update Lab Object",
    ),
    _tool_definition(
        "remove_lab_object",
        "Remove a structured object from a persisted Mystic LAB scene.",
        title="Remove Lab Object",
    ),
    _tool_definition(
        "set_lab_parameters",
        "Set or update scene-level parameters, units, and metadata for a persisted Mystic LAB scene.",
        title="Set Lab Parameters",
    ),
    _tool_definition(
        "run_lab_simulation",
        "Run a deterministic Phase 1 scene simulation adapter or return a structured engine-required result.",
        title="Run Lab Simulation",
    ),
    _tool_definition(
        "attach_simulation_to_scene",
        "Attach a stored simulation result to a scene and optionally apply its object updates.",
        title="Attach Simulation To Scene",
    ),
    _tool_definition(
        "export_lab_snapshot",
        "Export a persisted scene through the scene.three_json Phase 1 adapter.",
        title="Export Lab Snapshot",
        read_only=True,
    ),
    _tool_definition(
        "generate_lab_report",
        "Generate a markdown scene report that links objects, simulations, and archive references.",
        title="Generate Scene Report",
    ),
    _tool_definition(
        "provider_list",
        "List known external model providers and their current Provider Connect status without exposing secrets.",
        title="List Providers",
        read_only=True,
    ),
    _tool_definition(
        "provider_status",
        "Inspect one Provider Connect record and its current safe configuration status.",
        title="Provider Status",
        read_only=True,
    ),
    _tool_definition(
        "provider_connect_start",
        "Record a provider setup intent and start the safe Provider Connect foundation flow for API key or OAuth metadata.",
        title="Start Provider Connect",
    ),
    _tool_definition(
        "provider_connect_callback_status",
        "Check the stored status of a provider OAuth metadata flow without exposing tokens or callback codes.",
        title="Provider Callback Status",
        read_only=True,
    ),
    _tool_definition(
        "provider_configure_secret_instructions",
        "Return safe Cloudflare secret setup instructions for a provider without printing secret values.",
        title="Provider Secret Instructions",
        read_only=True,
    ),
    _tool_definition(
        "provider_verify",
        "Verify whether a provider appears configured while keeping secrets server-side.",
        title="Verify Provider",
        read_only=True,
    ),
    _tool_definition(
        "provider_disconnect",
        "Mark a provider disconnected without deleting any existing Cloudflare secrets.",
        title="Disconnect Provider",
    ),
    _tool_definition(
        "provider_model_list",
        "Return a provider model list when configuration is present, or a structured required-status response otherwise.",
        title="Provider Model List",
        read_only=True,
    ),
    _tool_definition(
        "provider_call_test",
        "Run a Provider Connect foundation test. Real provider calls stay disabled here unless a mock provider is explicitly used in tests.",
        title="Provider Call Test",
    ),
    _tool_definition(
        "mystic_export_teacher_packet",
        "Export recent uncertain or failing cases for teacher labeling.",
        title="Export Teacher Packet",
    ),
    _tool_definition(
        "mystic_import_teacher_label",
        "Import teacher labels for local agents and persist them under mystic_data.",
        title="Import Teacher Label",
    ),
]


PUBLIC_TOOL_NAMES = [
    "mystic_status",
    "health_check",
    "mystic_verify_answer",
    "mystic_call_model",
    "mystic_compare_models",
    "mystic_run_research_table",
    "lab_session_create",
    "lab_session_get",
    "lab_session_advance",
    "lab_agent_run",
    "lab_referee_review",
    "lab_experiment_create",
    "lab_experiment_run",
    "lab_memory_search",
    "lab_memory_write",
    "lab_models_debate",
    "lab_report_generate",
    "create_lab_scene",
    "get_lab_scene",
    "add_lab_object",
    "update_lab_object",
    "remove_lab_object",
    "set_lab_parameters",
    "run_lab_simulation",
    "attach_simulation_to_scene",
    "export_lab_snapshot",
    "generate_lab_report",
    "provider_list",
    "provider_status",
    "provider_connect_start",
    "provider_connect_callback_status",
    "provider_configure_secret_instructions",
    "provider_verify",
    "provider_disconnect",
    "provider_model_list",
    "provider_call_test",
]


PUBLIC_TOOL_DEFINITIONS = [tool for tool in TOOL_DEFINITIONS if tool["name"] in PUBLIC_TOOL_NAMES]
