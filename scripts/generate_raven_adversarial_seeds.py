from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
import json
from pathlib import Path
import random
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.raven_training import write_jsonl


UNIT_FRACTION_PROBLEM = (
    "Find all positive integer triples x <= y <= z such that "
    "1/x + 1/y + 1/z = 1."
)


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _seed_row(
    *,
    seed_id: str,
    case_type: str,
    problem: str,
    model_output: str,
    claim: str,
    tool_evidence: str,
    verdict: str,
    first_fatal_error: str,
    critique: str,
    recommended_next_action: str,
    verifier_derived: bool,
) -> dict[str, Any]:
    return {
        "agent": "raven",
        "input": {
            "problem": problem,
            "model_output": model_output,
            "discovery_or_claim": claim,
            "tool_evidence": tool_evidence,
            "context": (
                "Adversarial referee seed. Judge the claim strictly; deterministic evidence "
                "overrides the model output, and completeness is required for VALID."
            ),
        },
        "output": {
            "verdict": verdict,
            "first_fatal_error": first_fatal_error,
            "critique": critique,
            "recommended_next_action": recommended_next_action,
        },
        "source": {
            "source_type": "adversarial_seed",
            "seed_id": seed_id,
            "case_type": case_type,
            "session_id": None,
            "turn_id": None,
            "discovery_id": None,
            "label_id": None,
            "verifier_derived": verifier_derived,
        },
    }


def unit_fraction_rows() -> list[dict[str, Any]]:
    return [
        _seed_row(
            seed_id="unit-fraction-wrong-candidate",
            case_type="wrong_candidate_tuple",
            problem=UNIT_FRACTION_PROBLEM,
            model_output="The solutions are (2,3,6), (2,4,8), and (3,3,3).",
            claim="(2,4,8) is a solution and the displayed list is complete.",
            tool_evidence="1/2 + 1/4 + 1/8 = 7/8, not 1. The valid tuple (2,4,4) is also missing.",
            verdict="INVALID",
            first_fatal_error="The candidate (2,4,8) does not satisfy the equation.",
            critique="The answer contains a false candidate and omits a genuine solution.",
            recommended_next_action="Run exact substitution checking and bounded integer enumeration.",
            verifier_derived=True,
        ),
        _seed_row(
            seed_id="unit-fraction-missing-solution",
            case_type="missing_solution",
            problem=UNIT_FRACTION_PROBLEM,
            model_output="The only solutions are (2,3,6) and (3,3,3).",
            claim="The two listed triples form the complete solution set.",
            tool_evidence="(2,4,4) satisfies 1/2 + 1/4 + 1/4 = 1.",
            verdict="INVALID",
            first_fatal_error="The solution set is incomplete because it omits (2,4,4).",
            critique="A complete classification cannot omit a directly verified solution.",
            recommended_next_action="Enumerate the bounded x=2 and x=3 cases and verify every tuple exactly.",
            verifier_derived=True,
        ),
        _seed_row(
            seed_id="unit-fraction-ordering-violation",
            case_type="ordering_violation",
            problem=UNIT_FRACTION_PROBLEM,
            model_output="The solution (3,6,4) works.",
            claim="(3,6,4) obeys all constraints and satisfies the equation.",
            tool_evidence="The constraint fails because 6 <= 4 is false; also 1/3 + 1/6 + 1/4 = 3/4.",
            verdict="INVALID",
            first_fatal_error="The proposed tuple violates the ordering constraint and does not satisfy the equation.",
            critique="Both the domain constraint and direct substitution refute the claim.",
            recommended_next_action="Normalize tuple order and run exact substitution before accepting a candidate.",
            verifier_derived=True,
        ),
        _seed_row(
            seed_id="unit-fraction-arithmetic-failure",
            case_type="arithmetic_substitution_failure",
            problem=UNIT_FRACTION_PROBLEM,
            model_output="(4,5,7) is a solution.",
            claim="The tuple (4,5,7) satisfies the reciprocal equation.",
            tool_evidence="1/4 + 1/5 + 1/7 = 83/140, not 1.",
            verdict="INVALID",
            first_fatal_error="The tuple (4,5,7) fails direct substitution.",
            critique="Exact rational arithmetic immediately rejects the proposed tuple.",
            recommended_next_action="Use exact fractions instead of decimal estimates.",
            verifier_derived=True,
        ),
        _seed_row(
            seed_id="unit-fraction-incomplete-proof",
            case_type="incomplete_proof",
            problem=UNIT_FRACTION_PROBLEM,
            model_output="Testing some values gives (2,3,6), (2,4,4), and (3,3,3), so these are all solutions.",
            claim="Testing several values proves the candidate list is complete.",
            tool_evidence="All three listed tuples pass substitution, but substitution does not exclude other tuples.",
            verdict="NEEDS_MORE_DETAIL",
            first_fatal_error="No completeness argument is provided.",
            critique="The candidates may be correct, but the proof never bounds or exhausts the search space.",
            recommended_next_action="Prove x <= 3, then enumerate x=2 and x=3 rigorously.",
            verifier_derived=True,
        ),
        _seed_row(
            seed_id="unit-fraction-bad-bound",
            case_type="proof_gap_bad_bound",
            problem=UNIT_FRACTION_PROBLEM,
            model_output=(
                "Since x <= y <= z, 1 = 1/x + 1/y + 1/z >= 3/x, so x >= 3. "
                "Therefore only x=3 is possible."
            ),
            claim="The ordering constraint implies x >= 3 and excludes x=2.",
            tool_evidence=(
                "Because 1/x >= 1/y >= 1/z, the correct bound is "
                "1 = 1/x + 1/y + 1/z <= 3/x, hence x <= 3."
            ),
            verdict="INVALID",
            first_fatal_error="The proof reverses the inequality and derives an invalid bound.",
            critique="The incorrect direction removes valid x=2 solutions.",
            recommended_next_action="Rewrite each inequality from x <= y <= z before dividing or summing.",
            verifier_derived=True,
        ),
        _seed_row(
            seed_id="unit-fraction-weak-valid-list",
            case_type="valid_candidates_incomplete_proof",
            problem=UNIT_FRACTION_PROBLEM,
            model_output="The solutions are (2,3,6), (2,4,4), and (3,3,3). This can be checked by substitution.",
            claim="Substitution alone proves that the displayed set contains all solutions.",
            tool_evidence="Each listed tuple sums to 1, but this evidence only proves soundness, not completeness.",
            verdict="NEEDS_MORE_DETAIL",
            first_fatal_error="The proof does not show that no other positive integer triples exist.",
            critique="The candidate set is correct, but a finite bound and exhaustive case split are missing.",
            recommended_next_action="Bound x using the ordering, then solve the remaining two-variable equations.",
            verifier_derived=True,
        ),
        _seed_row(
            seed_id="unit-fraction-complete-proof",
            case_type="valid_complete_proof",
            problem=UNIT_FRACTION_PROBLEM,
            model_output=(
                "Since x <= y <= z, 1 = 1/x + 1/y + 1/z <= 3/x, so x <= 3; x=1 is impossible. "
                "For x=2, 1/y+1/z=1/2 and y<=4, giving (2,3,6) and (2,4,4). "
                "For x=3, y=3 and z=3. Thus these three tuples are all solutions."
            ),
            claim="The bounded case split proves the complete solution set.",
            tool_evidence=(
                "Exact substitution verifies (2,3,6), (2,4,4), and (3,3,3); "
                "the x<=3 bound exhausts all possible x."
            ),
            verdict="VALID_COMPLETE_PROOF",
            first_fatal_error="",
            critique="The proof supplies a finite bound, covers every remaining case, and verifies the candidates.",
            recommended_next_action="Accept the proof.",
            verifier_derived=True,
        ),
    ]


def generic_rows() -> list[dict[str, Any]]:
    return [
        _seed_row(
            seed_id="generic-positive-integer-violation",
            case_type="positive_integer_violation",
            problem="Find all positive integer pairs (x,y) satisfying x + y = 5.",
            model_output="The solutions include (0,5), (1,4), and (2,3).",
            claim="(0,5) is a positive integer solution.",
            tool_evidence="Although 0 + 5 = 5, zero is not a positive integer.",
            verdict="INVALID",
            first_fatal_error="The candidate (0,5) violates the positive integer constraint.",
            critique="Satisfying the equation does not excuse violating the stated domain.",
            recommended_next_action="Filter candidates by every domain constraint before checking the equation.",
            verifier_derived=True,
        ),
        _seed_row(
            seed_id="generic-denominator-zero",
            case_type="denominator_zero",
            problem="Find positive integer triples satisfying 1/x + 1/y + 1/z = 1.",
            model_output="One solution is (0,2,2).",
            claim="The tuple (0,2,2) is valid.",
            tool_evidence="The term 1/0 is undefined, and x=0 is not positive.",
            verdict="INVALID",
            first_fatal_error="The proposed tuple makes a denominator zero.",
            critique="The expression is undefined before any arithmetic equality can be considered.",
            recommended_next_action="Reject zero denominators before substitution.",
            verifier_derived=True,
        ),
        _seed_row(
            seed_id="generic-hidden-division-zero",
            case_type="hidden_division_by_zero",
            problem="Solve a^2 = a over the integers.",
            model_output="Divide both sides by a to get a=1, so 1 is the only solution.",
            claim="Division by a is valid for every integer solution.",
            tool_evidence="a=0 satisfies a^2=a, but division by a is invalid in that case.",
            verdict="INVALID",
            first_fatal_error="The proof divides by a without separating the possible case a=0.",
            critique="An unverified nonzero assumption deletes a genuine solution.",
            recommended_next_action="Factor as a(a-1)=0 or split into a=0 and a!=0 cases.",
            verifier_derived=True,
        ),
        _seed_row(
            seed_id="generic-modular-unsupported",
            case_type="unsupported_modular_claim",
            problem="Determine which integers n make n^2-n divisible by 2.",
            model_output="Tests for n=1 through 10 work, so every integer works.",
            claim="A finite test proves divisibility for all integers.",
            tool_evidence="The tested values are consistent with the claim but do not constitute a universal proof.",
            verdict="NEEDS_MORE_DETAIL",
            first_fatal_error="The universal claim is inferred only from finitely many tests.",
            critique="A parity argument is required: one of consecutive integers n and n-1 is even.",
            recommended_next_action="Prove the claim by parity rather than extrapolating from examples.",
            verifier_derived=False,
        ),
        _seed_row(
            seed_id="generic-overgeneralization",
            case_type="overgeneralization",
            problem="Decide whether n^2+n+41 is prime for every nonnegative integer n.",
            model_output="It is prime for n=0 through 20, therefore it is always prime.",
            claim="Primality on tested inputs proves universal primality.",
            tool_evidence="At n=41, n^2+n+41 = 41*43, which is composite.",
            verdict="INVALID",
            first_fatal_error="The universal claim has the explicit counterexample n=41.",
            critique="Finite successful tests cannot establish a universal statement, and exact evidence refutes it.",
            recommended_next_action="Search for symbolic factors or counterexamples before generalizing.",
            verifier_derived=True,
        ),
        _seed_row(
            seed_id="generic-tool-conflict",
            case_type="verifier_override",
            problem="Determine whether 17 is divisible by 3.",
            model_output="VALID: 17 is divisible by 3 because 3*6=17.",
            claim="17 has zero remainder modulo 3.",
            tool_evidence="17 = 3*5 + 2, so 17 mod 3 = 2.",
            verdict="INVALID",
            first_fatal_error="The arithmetic identity 3*6=17 is false.",
            critique="Deterministic arithmetic evidence overrides the model's confident VALID label.",
            recommended_next_action="Compute the quotient and remainder exactly.",
            verifier_derived=True,
        ),
    ]


def erdos_straus_rows() -> list[dict[str, Any]]:
    problem = "For n=2, find positive integers x,y,z such that 4/n = 1/x + 1/y + 1/z."
    return [
        _seed_row(
            seed_id="erdos-straus-n2-wrong-witness",
            case_type="erdos_straus_wrong_witness",
            problem=problem,
            model_output="For n=2, the witness is (1,3,7).",
            claim="2 = 1 + 1/3 + 1/7.",
            tool_evidence="1 + 1/3 + 1/7 = 31/21, not 2.",
            verdict="INVALID",
            first_fatal_error="The proposed witness fails exact substitution.",
            critique="The witness is refuted by rational arithmetic.",
            recommended_next_action="Check the identity exactly; (1,2,2) is a valid witness for n=2.",
            verifier_derived=True,
        ),
        _seed_row(
            seed_id="erdos-straus-finite-test-generalization",
            case_type="erdos_straus_overgeneralization",
            problem="Prove that 4/n is a sum of three positive unit fractions for every integer n>=2.",
            model_output="A computer check succeeds for n=2 through 100, so the conjecture is proved.",
            claim="A bounded computation proves the statement for all n>=2.",
            tool_evidence="The computation covers only 99 values and provides no argument for n>100.",
            verdict="NEEDS_MORE_DETAIL",
            first_fatal_error="The claimed universal proof does not cover integers greater than 100.",
            critique="A finite smoke test is evidence, not a proof of the infinite statement.",
            recommended_next_action="State the result as bounded verification or supply a valid general argument.",
            verifier_derived=False,
        ),
    ]


def validate_seed_rows(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        output = row["output"]
        source = row["source"]
        if output["verdict"] == "INVALID" and not str(output["first_fatal_error"]).strip():
            raise ValueError(f"INVALID seed is missing first_fatal_error: {source['seed_id']}")
        if source.get("verifier_derived") and not str(row["input"]["tool_evidence"]).strip():
            raise ValueError(f"Verifier-derived seed is missing tool_evidence: {source['seed_id']}")


def generate_raven_adversarial_seeds(
    *,
    output_path: str | Path,
    count: int = 0,
    seed: int = 0,
    include_erdos_straus_smoke: bool = False,
    include_unit_fraction_triples: bool = True,
    allow_overwrite: bool = False,
) -> dict[str, Any]:
    target = Path(output_path)
    manifest_path = target.parent / "adversarial_seed_manifest.json"
    existing = [path for path in (target, manifest_path) if path.exists()]
    if existing and not allow_overwrite:
        raise FileExistsError(f"Refusing to overwrite existing adversarial seed artifacts: {existing}")

    pool = generic_rows()
    if include_unit_fraction_triples:
        pool = unit_fraction_rows() + pool
    if include_erdos_straus_smoke:
        pool.extend(erdos_straus_rows())
    if count < 0:
        raise ValueError("--count must be zero or positive.")
    if count > len(pool):
        raise ValueError(f"Requested {count} seeds, but only {len(pool)} curated cases are available.")

    rows = list(pool)
    if count > 0:
        rows = random.Random(seed).sample(rows, count)
    validate_seed_rows(rows)
    write_jsonl(target, rows)

    verdicts = Counter(str(row["output"]["verdict"]).strip().upper() for row in rows)
    case_types = Counter(str(row["source"]["case_type"]) for row in rows)
    manifest = {
        "target_agent": "raven",
        "output_path": str(target),
        "rows_written": len(rows),
        "seed": seed,
        "requested_count": count,
        "include_unit_fraction_triples": include_unit_fraction_triples,
        "include_erdos_straus_smoke": include_erdos_straus_smoke,
        "verdict_distribution": dict(sorted(verdicts.items())),
        "case_type_distribution": dict(sorted(case_types.items())),
        "created_at": now_iso(),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return {
        **manifest,
        "manifest_path": str(manifest_path),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate deterministic curated Raven adversarial training seeds.")
    parser.add_argument("--root-path", default=str(ROOT), help="Mystic repository root.")
    parser.add_argument("--output", default="", help="Optional adversarial seed JSONL output path.")
    parser.add_argument("--count", type=int, default=0, help="Optional number of curated rows to select.")
    parser.add_argument("--seed", type=int, default=0, help="Deterministic selection seed used with --count.")
    parser.add_argument("--include-erdos-straus-smoke", action="store_true")
    parser.add_argument(
        "--include-unit-fraction-triples",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root_path)
    output = Path(args.output) if args.output else (
        root / "mystic_data" / "datasets" / "raven" / "adversarial_seed_raven.jsonl"
    )
    try:
        payload = generate_raven_adversarial_seeds(
            output_path=output,
            count=args.count,
            seed=args.seed,
            include_erdos_straus_smoke=args.include_erdos_straus_smoke,
            include_unit_fraction_triples=args.include_unit_fraction_triples,
            allow_overwrite=args.allow_overwrite,
        )
    except (FileExistsError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
