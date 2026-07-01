from __future__ import annotations


TOOL_SCHEMAS = {
    "mystic_status": {
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
            "target_phase": {"type": ["string", "null"]},
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
            "claim_id": {"type": ["string", "null"]},
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
            "domain": {"type": ["string", "null"]},
            "status_filter": {"type": ["string", "null"]},
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


TOOL_DEFINITIONS = [
    {
        "name": "mystic_status",
        "description": "Return current Mystic model, dataset, adapter, and tool availability status.",
        "inputSchema": TOOL_SCHEMAS["mystic_status"],
    },
    {
        "name": "mystic_verify_answer",
        "description": "Deterministically verify candidate answers when direct substitution or bounded search is possible.",
        "inputSchema": TOOL_SCHEMAS["mystic_verify_answer"],
    },
    {
        "name": "mystic_bruteforce_integer_search",
        "description": "Search bounded integer domains for solutions to a symbolic equation under constraints.",
        "inputSchema": TOOL_SCHEMAS["mystic_bruteforce_integer_search"],
    },
    {
        "name": "mystic_run_python_check",
        "description": "Run constrained Python checks inside Mystic's safe local sandbox.",
        "inputSchema": TOOL_SCHEMAS["mystic_run_python_check"],
    },
    {
        "name": "mystic_run_local_agent",
        "description": "Run a local Mystic agent in draft, critique, or summary mode.",
        "inputSchema": TOOL_SCHEMAS["mystic_run_local_agent"],
    },
    {
        "name": "mystic_call_model",
        "description": "Call any registered Mystic model through the unified ModelRouter.",
        "inputSchema": TOOL_SCHEMAS["mystic_call_model"],
    },
    {
        "name": "mystic_compare_models",
        "description": "Call multiple models and optionally append deterministic verifier output.",
        "inputSchema": TOOL_SCHEMAS["mystic_compare_models"],
    },
    {
        "name": "mystic_run_debate",
        "description": "Run a threaded multi-model debate with critique, tool evidence, revision, and final judgment.",
        "inputSchema": TOOL_SCHEMAS["mystic_run_debate"],
    },
    {
        "name": "mystic_run_research_table",
        "description": "Run the Research Table discovery workflow with structured discoveries and verification requests.",
        "inputSchema": TOOL_SCHEMAS["mystic_run_research_table"],
    },
    {
        "name": "lab_session_create",
        "description": "Create a structured Mystic Lab session under mystic_data/lab_sessions.",
        "inputSchema": TOOL_SCHEMAS["lab_session_create"],
    },
    {
        "name": "lab_session_get",
        "description": "Load the current lab session state, recent turns, claims, experiments, and failures.",
        "inputSchema": TOOL_SCHEMAS["lab_session_get"],
    },
    {
        "name": "lab_session_advance",
        "description": "Advance a lab session through structured research phases and persist new artifacts.",
        "inputSchema": TOOL_SCHEMAS["lab_session_advance"],
    },
    {
        "name": "lab_agent_run",
        "description": "Run a specific virtual lab role against a session and store a structured LabTurn.",
        "inputSchema": TOOL_SCHEMAS["lab_agent_run"],
    },
    {
        "name": "lab_referee_review",
        "description": "Run a deterministic referee review against a claim or text and archive failures when found.",
        "inputSchema": TOOL_SCHEMAS["lab_referee_review"],
    },
    {
        "name": "lab_experiment_create",
        "description": "Create a lab experiment linked to a claim.",
        "inputSchema": TOOL_SCHEMAS["lab_experiment_create"],
    },
    {
        "name": "lab_experiment_run",
        "description": "Run a saved lab experiment and update linked claim evidence.",
        "inputSchema": TOOL_SCHEMAS["lab_experiment_run"],
    },
    {
        "name": "lab_memory_search",
        "description": "Search across saved lab session memory, claims, failures, and experiments.",
        "inputSchema": TOOL_SCHEMAS["lab_memory_search"],
    },
    {
        "name": "lab_memory_write",
        "description": "Write structured claim, failure, experiment, note, or edge data into a lab session.",
        "inputSchema": TOOL_SCHEMAS["lab_memory_write"],
    },
    {
        "name": "lab_models_debate",
        "description": "Run the existing Research Table as the Model Arena and import its outputs into a lab session.",
        "inputSchema": TOOL_SCHEMAS["lab_models_debate"],
    },
    {
        "name": "lab_report_generate",
        "description": "Generate a markdown lab report from structured session state.",
        "inputSchema": TOOL_SCHEMAS["lab_report_generate"],
    },
    {
        "name": "mystic_export_teacher_packet",
        "description": "Export recent uncertain or failing cases for teacher labeling.",
        "inputSchema": TOOL_SCHEMAS["mystic_export_teacher_packet"],
    },
    {
        "name": "mystic_import_teacher_label",
        "description": "Import teacher labels for local agents and persist them under mystic_data.",
        "inputSchema": TOOL_SCHEMAS["mystic_import_teacher_label"],
    },
]


PUBLIC_TOOL_NAMES = [
    "mystic_status",
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
]


PUBLIC_TOOL_DEFINITIONS = [tool for tool in TOOL_DEFINITIONS if tool["name"] in PUBLIC_TOOL_NAMES]
