"""Checklist-derived data and training blueprints."""

from __future__ import annotations

from pathlib import Path
import json


INTERNAL_DATASETS = [
    "failed_proofs",
    "raven_critiques",
    "counterexamples",
    "forge_experiments",
    "lean_attempts",
    "proof_repairs",
    "attack_maps",
    "routing_logs",
]


TRAINING_TARGETS = [
    {
        "adapter": "raven_lora_v0",
        "agent": "raven",
        "label": "Raven-LoRA",
        "base_model": "qwen3-14b",
        "priority": 1,
        "datasets": ["failed_proofs", "raven_critiques", "proof_repairs"],
    },
    {
        "adapter": "forge_lora_v0",
        "agent": "forge",
        "label": "Forge-LoRA",
        "base_model": "qwen3-coder",
        "priority": 2,
        "datasets": ["forge_experiments", "counterexamples", "OpenCodeInstruct", "SciCode"],
    },
    {
        "adapter": "prime_lora_v0",
        "agent": "prime",
        "label": "Prime-LoRA",
        "base_model": "deepseek-r1-distill-14b",
        "priority": 3,
        "datasets": ["NuminaMath-CoT", "OpenMathInstruct-2", "OpenR1", "raven_critiques"],
    },
    {
        "adapter": "lean_lora_v0",
        "agent": "lean",
        "label": "Lean-LoRA",
        "base_model": "qwen3-14b",
        "priority": 4,
        "datasets": ["LeanDojo", "LEAN-GitHub", "ProofNet", "lean_attempts"],
    },
    {
        "adapter": "core_router_lora_v0",
        "agent": "core",
        "label": "Core-Router-LoRA",
        "base_model": "qwen3-14b",
        "priority": 5,
        "datasets": ["routing_logs", "attack_maps", "Internal Mystic Data"],
    },
    {
        "adapter": "pattern_lora_v0",
        "agent": "pattern",
        "label": "Pattern-LoRA",
        "base_model": "qwen3-14b",
        "priority": 6,
        "datasets": ["counterexamples", "forge_experiments", "OpenWebMath"],
    },
    {
        "adapter": "physics_lora_v0",
        "agent": "physics",
        "label": "Physics-LoRA",
        "base_model": "qwen3-14b",
        "priority": 7,
        "datasets": ["GPQA Diamond", "SciBench", "SciCode"],
    },
    {
        "adapter": "chem_lora_v0",
        "agent": "chem",
        "label": "Chem-LoRA",
        "base_model": "qwen3-14b",
        "priority": 8,
        "datasets": ["GPQA Diamond", "SciCode", "MSQA"],
    },
    {
        "adapter": "biomath_lora_v0",
        "agent": "biomath",
        "label": "BioMath-LoRA",
        "base_model": "qwen3-14b",
        "priority": 9,
        "datasets": ["LAB-Bench", "GPQA Diamond", "SciCode"],
    },
    {
        "adapter": "report_lora_v0",
        "agent": "report",
        "label": "Report-LoRA",
        "base_model": "qwen3-14b",
        "priority": 10,
        "datasets": ["final_reports", "structured_summaries", "raven_critiques"],
    },
]


CHECKLIST_DATASETS = [
    {"rank": 1, "name": "Internal Mystic Data", "priority": "critical", "data": INTERNAL_DATASETS},
    {"rank": 2, "name": "NuminaMath-CoT", "priority": "critical", "data": ["math problems", "cot solutions"]},
    {"rank": 3, "name": "OpenMathInstruct-2", "priority": "critical", "data": ["math instruction", "problem-solution", "code-interpreter traces"]},
    {"rank": 4, "name": "OpenMathInstruct-1", "priority": "critical", "data": ["problem-solution pairs"]},
    {"rank": 5, "name": "OpenThoughts3 / OpenThoughts2", "priority": "critical", "data": ["math/code/science reasoning traces"]},
    {"rank": 6, "name": "OpenR1 / Mixture-of-Thoughts", "priority": "critical", "data": ["verified reasoning traces"]},
    {"rank": 7, "name": "AM-DeepSeek-R1-Distilled", "priority": "critical", "data": ["distilled reasoning traces"]},
    {"rank": 8, "name": "LeanDojo", "priority": "critical", "data": ["Lean proof states", "tactics", "premises"]},
    {"rank": 9, "name": "LEAN-GitHub", "priority": "critical", "data": ["Lean theorem and tactic corpus"]},
    {"rank": 10, "name": "ProofNet", "priority": "high", "data": ["natural language proof", "Lean statement"]},
    {"rank": 11, "name": "miniF2F", "priority": "high", "data": ["formal olympiad theorem proving"]},
    {"rank": 12, "name": "PutnamBench", "priority": "high", "data": ["formal theorem proving"]},
    {"rank": 13, "name": "Proof-Pile / Proof-Pile-2", "priority": "very_high", "data": ["formal math and theorem corpus"]},
    {"rank": 14, "name": "The Stack v2 Python subset", "priority": "very_high", "data": ["Python source code"]},
    {"rank": 15, "name": "The Stack v2 Lean subset", "priority": "very_high", "data": ["Lean and mathlib code"]},
    {"rank": 16, "name": "The Stack v2 Sage/SymPy subset", "priority": "very_high", "data": ["SageMath and SymPy code"]},
    {"rank": 17, "name": "OpenCodeInstruct", "priority": "very_high", "data": ["code instruction", "tests", "feedback"]},
    {"rank": 18, "name": "CodeContests", "priority": "very_high", "data": ["programming problems", "solutions", "tests"]},
    {"rank": 19, "name": "APPS", "priority": "high", "data": ["coding problems and Python solutions"]},
    {"rank": 20, "name": "TACO", "priority": "high", "data": ["algorithmic code generation and tests"]},
    {"rank": 21, "name": "Codehacks", "priority": "high", "data": ["adversarial tests", "counterexamples"]},
    {"rank": 22, "name": "SciCode", "priority": "critical", "data": ["scientific coding tasks"]},
    {"rank": 23, "name": "OpenWebMath", "priority": "critical", "data": ["math web text", "latex"]},
    {"rank": 24, "name": "Nemotron-CC-Math", "priority": "critical", "data": ["math/science pretraining corpus"]},
    {"rank": 25, "name": "MegaMath", "priority": "very_high", "data": ["math text", "math code", "synthetic qa"]},
    {"rank": 26, "name": "FineMath", "priority": "high", "data": ["filtered math web corpus"]},
    {"rank": 27, "name": "DeepSeekMath-style Corpus", "priority": "critical", "data": ["filtered math web corpus"]},
    {"rank": 28, "name": "MetaMathQA", "priority": "high", "data": ["rephrased math qa"]},
    {"rank": 29, "name": "MathInstruct / MAmmoTH", "priority": "very_high", "data": ["cot and pot math instruction"]},
    {"rank": 30, "name": "MATH / MATH-500", "priority": "high", "data": ["competition math solutions"]},
]


INGESTION_SOURCES = [
    {
        "name": "Internal Mystic Data",
        "slug": "internal_mystic_data",
        "priority": 1,
        "source_type": "local",
        "status": "bootstrap_ready",
        "recommended_target_agents": ["raven", "forge", "prime", "lean", "core", "pattern", "report"],
    },
    {
        "name": "NuminaMath-CoT",
        "slug": "numinamath_cot",
        "priority": 2,
        "source_type": "public_dataset",
        "status": "manifest_ready",
        "hf_search": "NuminaMath-CoT",
        "preferred_repo_id": "AI-MO/NuminaMath-CoT",
        "recommended_target_agents": ["prime", "core", "report"],
    },
    {
        "name": "OpenMathInstruct-2",
        "slug": "openmathinstruct_2",
        "priority": 3,
        "source_type": "public_dataset",
        "status": "manifest_ready",
        "hf_search": "OpenMathInstruct-2",
        "preferred_repo_id": "nvidia/OpenMathInstruct-2",
        "recommended_target_agents": ["prime", "core", "report"],
    },
    {
        "name": "OpenMathInstruct-1",
        "slug": "openmathinstruct_1",
        "priority": 4,
        "source_type": "public_dataset",
        "status": "manifest_ready",
        "hf_search": "OpenMathInstruct-1",
        "preferred_repo_id": "nvidia/OpenMathInstruct-1",
        "recommended_target_agents": ["prime", "core"],
    },
    {
        "name": "OpenThoughts3 / OpenThoughts2",
        "slug": "openthoughts",
        "priority": 5,
        "source_type": "public_dataset",
        "status": "manifest_ready",
        "hf_search": "OpenThoughts",
        "preferred_repo_id": "open-thoughts/OpenThoughts-114k",
        "recommended_target_agents": ["prime", "forge", "core", "report"],
    },
    {
        "name": "OpenR1 / Mixture-of-Thoughts",
        "slug": "openr1_mixture_of_thoughts",
        "priority": 6,
        "source_type": "public_dataset",
        "status": "manifest_ready",
        "hf_search": "OpenR1",
        "preferred_repo_id": "open-r1/OpenR1-Math-220k",
        "recommended_target_agents": ["prime", "core", "lean"],
    },
    {
        "name": "AM-DeepSeek-R1-Distilled",
        "slug": "am_deepseek_r1_distilled",
        "priority": 7,
        "source_type": "public_dataset",
        "status": "manifest_ready",
        "hf_search": "AM-DeepSeek-R1-Distilled",
        "recommended_target_agents": ["prime", "core", "report"],
    },
    {
        "name": "LeanDojo",
        "slug": "leandojo",
        "priority": 8,
        "source_type": "public_dataset",
        "status": "manifest_ready",
        "hf_search": "LeanDojo",
        "preferred_repo_id": "tasksource/leandojo",
        "recommended_target_agents": ["lean"],
    },
    {
        "name": "LEAN-GitHub",
        "slug": "lean_github",
        "priority": 9,
        "source_type": "public_dataset",
        "status": "manifest_ready",
        "hf_search": "LEAN-GitHub",
        "recommended_target_agents": ["lean"],
    },
    {
        "name": "ProofNet",
        "slug": "proofnet",
        "priority": 10,
        "source_type": "public_dataset",
        "status": "manifest_ready",
        "hf_search": "ProofNet",
        "preferred_repo_id": "hoskinson-center/proofnet",
        "recommended_target_agents": ["lean", "raven", "report"],
    },
]


SOFTWARE_STACK = [
    "Python 3.11+",
    "Git",
    "Docker",
    "SQLite",
    "Ollama",
    "Transformers",
    "PEFT",
    "Unsloth",
    "Axolotl",
    "TRL",
    "PyTorch",
    "FastAPI",
    "Typer",
    "SQLAlchemy",
    "Pydantic",
    "pytest",
    "SymPy",
    "NumPy",
    "SciPy",
    "SageMath",
    "Lean 4",
    "Z3",
    "Jupyter",
    "DVC",
    "rclone",
    "Weights & Biases",
    "MLflow",
]


AGENT_DIVISIONS = {
    "core": "core",
    "prime": "pure_math",
    "forge": "discovery",
    "lean": "verification",
    "raven": "verification",
    "pattern": "discovery",
    "physics": "science",
    "chem": "science",
    "biomath": "science",
    "report": "report",
}


INTERNAL_RECORD_ROUTING = {
    "failed_proofs": ["raven"],
    "raven_critiques": ["raven", "report", "prime"],
    "counterexamples": ["forge", "pattern"],
    "forge_experiments": ["forge", "pattern"],
    "lean_attempts": ["lean"],
    "proof_repairs": ["raven", "prime"],
    "attack_maps": ["core", "prime"],
    "routing_logs": ["core"],
}


def write_json(path: str | Path, payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
