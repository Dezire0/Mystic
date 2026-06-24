from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
from typing import Any

from mystic.training.blueprints import AGENT_DIVISIONS, ARCHITECTURE_TRAINING_TARGETS


TRAINABLE_AGENTS = [
    target for target in ARCHITECTURE_TRAINING_TARGETS if target.get("adapter")
]


def bootstrap_architecture_train_ready(base_dir: str | Path, *, force: bool = False, rows_per_agent: int = 3) -> dict[str, Any]:
    root = Path(base_dir)
    train_ready_root = root / "train_ready"
    train_ready_root.mkdir(parents=True, exist_ok=True)

    examples = _load_seed_examples(root, limit=max(rows_per_agent, 3))
    if not examples:
        raise ValueError("No seed examples available for architecture bootstrap.")

    written: dict[str, int] = {}
    skipped: dict[str, str] = {}
    for target in TRAINABLE_AGENTS:
        agent = str(target["agent"])
        target_path = train_ready_root / f"{agent}_train_ready.jsonl"
        existing_rows = _count_jsonl_rows(target_path)
        if existing_rows > 0 and not force:
            skipped[agent] = f"kept existing rows ({existing_rows})"
            continue

        rows = _build_agent_rows(target, examples[:rows_per_agent])
        _write_jsonl(target_path, rows)
        written[agent] = len(rows)

    return {
        "written": written,
        "skipped": skipped,
        "seed_example_count": len(examples),
    }


def _load_seed_examples(root: Path, *, limit: int) -> list[dict[str, str]]:
    examples: list[dict[str, str]] = []
    numina = root / "raw" / "numina_math_cot_100.jsonl"
    if numina.exists():
        for line in numina.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            examples.append(
                {
                    "problem": str(row.get("problem", "")),
                    "reference_solution": str(row.get("solution", "")),
                    "source": "numina_math_cot_100",
                }
            )
            if len(examples) >= limit:
                return examples

    for path in sorted((root / "raw").glob("**/sample.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            examples.append(
                {
                    "problem": str(_first_nonempty(row, ["problem", "instruction", "input"]) or ""),
                    "reference_solution": str(_first_nonempty(row, ["solution", "output", "response"]) or ""),
                    "source": path.parent.name,
                }
            )
            if len(examples) >= limit:
                return examples
    return examples


def _first_nonempty(row: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value
    messages = row.get("messages")
    if isinstance(messages, list):
        for item in messages:
            if isinstance(item, dict):
                content = item.get("content")
                if isinstance(content, str) and content.strip():
                    return content
    return None


def _build_agent_rows(target: dict[str, Any], examples: list[dict[str, str]]) -> list[dict[str, Any]]:
    agent = str(target["agent"])
    rows: list[dict[str, Any]] = []
    for index, example in enumerate(examples):
        rows.append(
            {
                "agent": agent,
                "division": AGENT_DIVISIONS.get(agent, "unknown"),
                "instruction": _instruction_for_target(target),
                "input": (
                    f"Architecture target: {target['name']}\n"
                    f"Seed problem: {example['problem']}\n\n"
                    f"Reference material:\n{example['reference_solution']}\n\n"
                    f"Checklist datasets: {', '.join(target.get('datasets', []))}"
                ),
                "output": _output_for_target(target, example, index),
                "status": "BOOTSTRAP_SYNTHETIC",
                "metadata": {
                    "dataset": "bootstrap_synthetic",
                    "split": "train",
                    "source": example["source"],
                    "target_agent": agent,
                    "base_model": target["model"],
                    "bootstrap": True,
                    "bootstrap_index": index,
                },
            }
        )
    return rows


def _instruction_for_target(target: dict[str, Any]) -> str:
    agent = str(target["agent"])
    return {
        "algebra": "Solve the problem with explicit algebraic transformations and preserve symbolic invariants.",
        "geo": "Produce a geometry-focused reasoning trace with constructions, angle relations, and explicit claims.",
        "analysis": "Reason like an analysis specialist and state the limiting argument or inequality structure clearly.",
        "probability": "Explain the probabilistic structure, random variables, and conditioning steps conservatively.",
        "logic": "Check proof structure, assumptions, and inference validity with logic-specialist discipline.",
        "complexity": "Translate the task into a complexity or algorithmic reasoning sketch with failure-aware commentary.",
        "biomath": "Frame the task as quantitative biomath reasoning grounded in structured assumptions.",
        "chem": "Frame the task as chemistry-oriented symbolic reasoning with conservative derivation steps.",
        "physics": "Frame the task as mathematical physics reasoning with units, laws, or conserved quantities when relevant.",
        "conjecture": "Propose a useful conjecture, lemma, or reformulation instead of a final polished proof.",
        "simulator": "Write a simulator-oriented plan or pseudocode sketch that could test the claim computationally.",
    }.get(agent, f"Produce a bootstrap specialist response for {target['name']}.")


def _output_for_target(target: dict[str, Any], example: dict[str, str], index: int) -> str:
    agent = str(target["agent"])
    base = example["reference_solution"] or example["problem"]
    snippets = {
        "algebra": f"Algebra bootstrap {index + 1}: isolate symbolic quantities, simplify carefully, and verify each transformation against the seed reference.\n\nSeed reference:\n{base}",
        "geo": f"Geometry bootstrap {index + 1}: identify the diagram entities, list the relation claims, and note which step still needs a formal proof.\n\nSeed reference:\n{base}",
        "analysis": f"Analysis bootstrap {index + 1}: expose the limiting or inequality argument, mark any unstated continuity assumptions, and keep the derivation cautious.\n\nSeed reference:\n{base}",
        "probability": f"Probability bootstrap {index + 1}: define the random objects, spell out conditioning, and separate exact facts from heuristic intuition.\n\nSeed reference:\n{base}",
        "logic": f"Logic bootstrap {index + 1}: enumerate premises, infer the next valid consequence, and reject leaps that are not justified by the seed reasoning.\n\nSeed reference:\n{base}",
        "complexity": f"Complexity bootstrap {index + 1}: restate the computational core, sketch an algorithm or reduction, and call out missing proof obligations.\n\nSeed reference:\n{base}",
        "biomath": f"BioMath bootstrap {index + 1}: convert the task into quantitative assumptions, variables, and a conservative interpretation grounded in the seed reasoning.\n\nSeed reference:\n{base}",
        "chem": f"Chem bootstrap {index + 1}: identify symbolic chemical quantities or transformation rules and keep unsupported claims explicitly flagged.\n\nSeed reference:\n{base}",
        "physics": f"Physics bootstrap {index + 1}: map the problem to mathematical physics structure, note governing quantities, and state where derivation evidence is still missing.\n\nSeed reference:\n{base}",
        "conjecture": f"Conjecture bootstrap {index + 1}: propose a candidate lemma or reformulation suggested by the seed problem and explain why it may help.\n\nSeed reference:\n{base}",
        "simulator": f"Simulator bootstrap {index + 1}: sketch a small computational experiment or pseudocode procedure that could test the seed claim.\n\nSeed reference:\n{base}",
    }
    return snippets.get(agent, f"Bootstrap output for {target['name']}:\n\n{base}")


def _count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    payload = "\n".join(json.dumps(row, ensure_ascii=True) for row in rows)
    if payload:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")
