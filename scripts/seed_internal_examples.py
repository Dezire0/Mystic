from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.training.blueprints import INTERNAL_DATASETS
from mystic.training.bootstrap import init_internal_data_files


EXAMPLES = {
    "failed_proofs": {
        "record_type": "failed_proofs",
        "instruction": "Audit a claimed proof and isolate the first invalid inference.",
        "input": "Claim: every tested value satisfied the conjecture, therefore the theorem is proved.",
        "output": "Finite testing does not prove the universal claim.",
        "status": "INVALID",
    },
    "raven_critiques": {
        "record_type": "raven_critiques",
        "instruction": "Referee the proof aggressively.",
        "input": "The argument assumes a residue class split but does not prove coverage.",
        "output": "Missing full residue-class coverage; claim remains unproven.",
        "status": "GAP",
    },
    "counterexamples": {
        "record_type": "counterexamples",
        "instruction": "Record a concrete failure case for the current heuristic.",
        "input": "Heuristic predicted all parameter pairs satisfy the invariant.",
        "output": "Found parameter tuple (3, 5, 8) violating the proposed invariant.",
        "status": "REFUTED",
    },
    "forge_experiments": {
        "record_type": "forge_experiments",
        "instruction": "Design a bounded computational search.",
        "input": "Search for Erdos-Straus decompositions up to n=20.",
        "output": "Checked up to 20 with no missing decomposition in the tested bound.",
        "status": "HEURISTIC",
    },
    "lean_attempts": {
        "record_type": "lean_attempts",
        "instruction": "Draft a Lean theorem statement and note blockers.",
        "input": "Formalize existence of positive integer decomposition placeholders.",
        "output": "Statement drafted, but key arithmetic lemmas are still missing.",
        "status": "GAP",
    },
    "proof_repairs": {
        "record_type": "proof_repairs",
        "instruction": "Rewrite the broken step into an explicit lemma obligation.",
        "input": "Original proof jumped from empirical evidence to existence.",
        "output": "Introduce a lemma proving the construction for each residue class separately.",
        "status": "PROMISING",
    },
    "attack_maps": {
        "record_type": "attack_maps",
        "instruction": "Map the research attack surface.",
        "input": "Problem involves arithmetic decomposition with verification and search components.",
        "output": "Route to Prime, Forge, Raven, Lean, Pattern, and Conjecture.",
        "status": "PROMISING",
    },
    "routing_logs": {
        "record_type": "routing_logs",
        "instruction": "Record a router decision with rationale.",
        "input": "Keywords matched: integer, conjecture, fraction, prove.",
        "output": "Selected prime, forge, raven, lean, pattern, conjecture.",
        "status": "FORMALIZED",
    },
}


def main() -> None:
    base_dir = ROOT / "mystic_data"
    init_internal_data_files(base_dir)
    internal_root = base_dir / "processed" / "internal_mystic_data"
    timestamp = datetime.now(UTC).isoformat()

    for dataset_name in INTERNAL_DATASETS:
        example = dict(EXAMPLES[dataset_name])
        example["metadata"] = {
            "source": "seed_internal_examples",
            "created_at": timestamp,
            "session_id": None,
            "agent": None,
            "model": None,
            "adapter": None,
        }
        path = internal_root / f"{dataset_name}.jsonl"
        path.write_text(json.dumps(example, ensure_ascii=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

