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
            "problem": {"type": "string"},
            "candidate_answer": {"type": "string"},
            "constraints": {"type": "array", "items": {"type": "string"}},
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
            "model_id": {"type": "string"},
            "role": {"type": "string", "enum": ["draft", "critique", "revise", "judge", "summarize"]},
            "task": {"type": "string"},
            "problem": {"type": "string"},
            "context": {"type": "string"},
            "max_tokens": {"type": "integer"},
            "temperature": {"type": "number"},
        },
        "required": ["model_id", "role", "task", "problem"],
        "additionalProperties": False,
    },
    "mystic_compare_models": {
        "type": "object",
        "properties": {
            "problem": {"type": "string"},
            "models": {"type": "array", "items": {"type": "string"}},
            "task": {"type": "string"},
            "include_verifier": {"type": "boolean"},
            "max_output_chars_per_model": {"type": "integer"},
        },
        "required": ["problem", "models", "task", "include_verifier"],
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
]
