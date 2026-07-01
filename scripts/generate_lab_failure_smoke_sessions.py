from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.lab.memory_graph import make_edge
from mystic.lab.reports import render_report
from mystic.lab.session import Claim, Experiment, Failure, LabSession, LabSessionBundle, LabTurn
from mystic.lab.storage import LabStorage
from mystic.lab.training_export import export_lab_failures_for_raven
from mystic.raven_training import load_jsonl


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def default_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate deterministic reusable Lab failure smoke sessions.")
    parser.add_argument("--root-path", default=str(ROOT), help="Mystic repository root.")
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--allow-overwrite", action="store_true")
    parser.add_argument("--allow-empty", action="store_true")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--output-summary", default="")
    parser.add_argument("--domain", default="math")
    parser.add_argument("--include-unit-fraction-smoke", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include-code-logic-smoke", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include-proof-gap-smoke", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--verify-export", action="store_true")
    return parser


def build_bad_model_turn(
    *,
    session_id: str,
    input_summary: str,
    output: str,
    turn_id: str,
) -> LabTurn:
    return LabTurn(
        session_id=session_id,
        phase="referee_review",
        room="Referee Court",
        agent_role="Referee",
        provider="local",
        model_name="local_prime",
        input_summary=input_summary,
        output=output,
        status="completed",
        turn_id=turn_id,
    )


def build_bundle_from_scenario(
    *,
    scenario: dict[str, Any],
    domain: str,
    run_id: str,
) -> LabSessionBundle:
    session_id = f"lab-failure-smoke-{run_id}-{scenario['slug']}"
    claim_id = f"{session_id}-claim"
    turn_id = f"{session_id}-turn"
    failure_id = f"{session_id}-failure"
    experiment_id = f"{session_id}-experiment"

    session = LabSession(
        session_id=session_id,
        problem=scenario["problem"],
        domain=domain,
        goal=scenario["goal"],
        mode="proof_critical",
        status="completed",
        current_phase="failure_archive",
        next_actions=["Export the failure as Raven training data.", "Repair the false claim before reusing the result."],
        warnings=["Synthetic smoke data for deterministic Failure Museum coverage."],
    )
    turn = build_bad_model_turn(
        session_id=session_id,
        input_summary=scenario["input_summary"],
        output=scenario["bad_claim"],
        turn_id=turn_id,
    )
    claim = Claim(
        session_id=session_id,
        text=scenario["claim_text"],
        claim_type=scenario["claim_type"],
        status=scenario["claim_status"],
        confidence="high",
        source_turn_id=turn.turn_id,
        supporting_evidence=[],
        refuting_evidence=[scenario["refuting_evidence"]],
        related_experiments=[experiment_id],
        related_failures=[failure_id],
        claim_id=claim_id,
    )
    experiment = Experiment(
        session_id=session_id,
        claim_id=claim.claim_id,
        question=scenario["experiment_question"],
        method=scenario["experiment_method"],
        inputs=scenario["experiment_inputs"],
        outputs=scenario["experiment_outputs"],
        verdict=scenario["experiment_verdict"],
        evidence_summary=scenario["refuting_evidence"],
        experiment_id=experiment_id,
    )
    failure = Failure(
        session_id=session_id,
        claim_id=claim.claim_id,
        source_turn_id=turn.turn_id,
        first_fatal_error=scenario["first_fatal_error"],
        failure_type=scenario["failure_type"],
        lesson=scenario["lesson"],
        reusable_as_training_data=True,
        failure_id=failure_id,
    )
    edges = [
        make_edge(
            session_id=session_id,
            from_id=claim.claim_id,
            to_id=experiment.experiment_id,
            relation="generated_experiment",
            evidence=scenario["experiment_question"],
        ),
        make_edge(
            session_id=session_id,
            from_id=claim.claim_id,
            to_id=failure.failure_id,
            relation="caused_failure",
            evidence=scenario["first_fatal_error"],
        ),
    ]
    notebook_markdown = "\n".join(
        [
            f"# Lab Failure Smoke {session_id}",
            "",
            f"Problem: {scenario['problem']}",
            "",
            "## Bad Claim",
            scenario["bad_claim"],
            "",
            "## Failure",
            scenario["first_fatal_error"],
            "",
        ]
    )
    bundle = LabSessionBundle(
        session=session,
        turns=[turn],
        claims=[claim],
        experiments=[experiment],
        failures=[failure],
        memory_edges=edges,
        notebook_markdown=notebook_markdown,
    )
    report = render_report(bundle)
    bundle.report_markdown = report.markdown
    return bundle


def available_scenarios() -> list[dict[str, Any]]:
    return [
        {
            "slug": "unit-fraction-false-candidate",
            "problem": "Find all positive integer triples x <= y <= z such that 1/x + 1/y + 1/z = 1.",
            "goal": "Reject false candidate triples.",
            "input_summary": "Review candidate triple (2, 4, 8).",
            "bad_claim": "Claim: (2, 4, 8) is a valid solution because the reciprocals sum to 1.",
            "claim_text": "(2, 4, 8) is a valid solution of 1/x + 1/y + 1/z = 1.",
            "claim_type": "result",
            "claim_status": "REFUTED",
            "failure_type": "arithmetic",
            "first_fatal_error": "1/2 + 1/4 + 1/8 = 7/8, not 1.",
            "lesson": "Check the exact reciprocal sum before accepting a candidate triple.",
            "refuting_evidence": "Deterministic arithmetic check shows 1/2 + 1/4 + 1/8 = 7/8.",
            "experiment_question": "Does the candidate triple (2, 4, 8) satisfy the unit fraction equation?",
            "experiment_method": "python_bruteforce",
            "experiment_inputs": {"candidate": [2, 4, 8]},
            "experiment_outputs": {"sum": "7/8", "is_valid": False},
            "experiment_verdict": "refutes",
            "group": "unit_fraction",
        },
        {
            "slug": "missing-solution-classification",
            "problem": "Classify positive integer triples x <= y <= z satisfying 1/x + 1/y + 1/z = 1.",
            "goal": "Detect omitted valid solutions in a claimed classification.",
            "input_summary": "Review the claimed complete solution set.",
            "bad_claim": "Claim: The only solutions are (2, 3, 6) and (3, 3, 3).",
            "claim_text": "The full solution set is exactly {(2, 3, 6), (3, 3, 3)}.",
            "claim_type": "result",
            "claim_status": "FAILED",
            "failure_type": "missing_case",
            "first_fatal_error": "The valid solution (2, 4, 4) is omitted.",
            "lesson": "A complete classification must account for every valid case, including (2, 4, 4).",
            "refuting_evidence": "Deterministic search recovers (2, 4, 4) as a valid triple.",
            "experiment_question": "Does the claimed classification omit any valid triples?",
            "experiment_method": "python_bruteforce",
            "experiment_inputs": {"range_limit": 20},
            "experiment_outputs": {"missing_valid_triples": [[2, 4, 4]]},
            "experiment_verdict": "refutes",
            "group": "unit_fraction",
        },
        {
            "slug": "proof-gap-bruteforce-bound",
            "problem": "Prove the full solution set for 1/x + 1/y + 1/z = 1.",
            "goal": "Reject unsupported global conclusions from bounded search alone.",
            "input_summary": "Review a proof that only checks triples up to 20.",
            "bad_claim": "Claim: Checking triples up to 20 proves there are no larger solutions.",
            "claim_text": "Finite brute force up to 20 proves the full solution set.",
            "claim_type": "theorem",
            "claim_status": "NEEDS_MORE_DETAIL",
            "failure_type": "insufficient_detail",
            "first_fatal_error": "Finite brute force up to 20 alone does not prove no larger solutions exist without a bound argument.",
            "lesson": "A bounded search needs a separate argument showing why larger triples are impossible.",
            "refuting_evidence": "The proof provides no bound argument linking the finite search to the full infinite domain.",
            "experiment_question": "Does the claimed proof include a valid bound argument beyond brute force?",
            "experiment_method": "manual_review",
            "experiment_inputs": {"search_limit": 20},
            "experiment_outputs": {"bound_argument_present": False},
            "experiment_verdict": "inconclusive",
            "group": "proof_gap",
        },
        {
            "slug": "code-logic-ordering-bug",
            "problem": "Determine if a candidate checker correctly validates triples under x <= y <= z.",
            "goal": "Find ordering logic bugs in the checker.",
            "input_summary": "Review a checker that enforces only x <= y.",
            "bad_claim": "Claim: The checker is correct if it tests only x <= y.",
            "claim_text": "A checker that verifies only x <= y still correctly validates ordered triples.",
            "claim_type": "design",
            "claim_status": "FAILED",
            "failure_type": "logic_gap",
            "first_fatal_error": "The ordering condition x <= y <= z is not fully checked.",
            "lesson": "Validation logic must enforce the full ordering constraint, not a partial prefix of it.",
            "refuting_evidence": "A checker that ignores y <= z can accept tuples that violate the required ordering.",
            "experiment_question": "Does the checker enforce the complete ordering x <= y <= z?",
            "experiment_method": "unit_test",
            "experiment_inputs": {"checker_rule": "x <= y only"},
            "experiment_outputs": {"checks_y_le_z": False},
            "experiment_verdict": "refutes",
            "group": "code_logic",
        },
    ]


def selected_scenarios(args: argparse.Namespace) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for scenario in available_scenarios():
        group = scenario["group"]
        if group == "unit_fraction" and not args.include_unit_fraction_smoke:
            continue
        if group == "code_logic" and not args.include_code_logic_smoke:
            continue
        if group == "proof_gap" and not args.include_proof_gap_smoke:
            continue
        selected.append(scenario)
    if args.count > 0:
        selected = selected[: args.count]
    return selected


def validate_export_rows(rows: list[dict[str, Any]], expected_reusable_failures: int) -> dict[str, Any]:
    if len(rows) < expected_reusable_failures:
        raise ValueError(
            f"Exported lab failure rows {len(rows)} are fewer than expected reusable failures {expected_reusable_failures}."
        )
    verdicts: Counter[str] = Counter()
    for row in rows:
        if str(row.get("agent", "")).strip() != "raven":
            raise ValueError("Exported lab failure row has unsupported agent.")
        source = row.get("source")
        output = row.get("output")
        if not isinstance(source, dict) or str(source.get("source_type", "")).strip() != "lab_failure":
            raise ValueError("Exported row is missing source.source_type = lab_failure.")
        if not isinstance(output, dict):
            raise ValueError("Exported row is missing output payload.")
        verdict = str(output.get("verdict", "")).strip().upper()
        verdicts[verdict] += 1
    if not (verdicts.get("INVALID", 0) or verdicts.get("NEEDS_MORE_DETAIL", 0)):
        raise ValueError("Exported lab failure rows do not include INVALID or NEEDS_MORE_DETAIL verdicts.")
    return {"rows_written": len(rows), "verdict_distribution": dict(sorted(verdicts.items()))}


def generate_lab_failure_smoke_sessions(
    *,
    root_path: str | Path,
    count: int = 3,
    allow_overwrite: bool = False,
    allow_empty: bool = False,
    run_id: str = "",
    output_summary: str | Path | None = None,
    domain: str = "math",
    include_unit_fraction_smoke: bool = True,
    include_code_logic_smoke: bool = True,
    include_proof_gap_smoke: bool = True,
    verify_export: bool = False,
) -> dict[str, Any]:
    root = Path(root_path)
    storage = LabStorage(root)
    args = argparse.Namespace(
        count=count,
        include_unit_fraction_smoke=include_unit_fraction_smoke,
        include_code_logic_smoke=include_code_logic_smoke,
        include_proof_gap_smoke=include_proof_gap_smoke,
    )
    scenarios = selected_scenarios(args)
    run_id = run_id or default_run_id()
    summary_path = Path(output_summary) if output_summary else (
        root / "mystic_data" / "e2e" / "lab_failure_smoke" / "summary.json"
    )

    bundles: list[LabSessionBundle] = []
    warnings: list[str] = []
    for scenario in scenarios:
        bundle = build_bundle_from_scenario(scenario=scenario, domain=domain, run_id=run_id)
        session_dir = storage.session_dir(bundle.session.session_id)
        if session_dir.exists() and not allow_overwrite:
            raise FileExistsError(
                f"Smoke lab session already exists: {session_dir}. Use --allow-overwrite to replace it."
            )
        if session_dir.exists() and allow_overwrite:
            shutil.rmtree(session_dir)
        storage.save_bundle(bundle)
        bundles.append(bundle)

    failure_type_distribution: Counter[str] = Counter()
    claim_count = 0
    failure_count = 0
    reusable_failures = 0
    session_ids: list[str] = []
    for bundle in bundles:
        session_ids.append(bundle.session.session_id)
        claim_count += len(bundle.claims)
        failure_count += len(bundle.failures)
        for failure in bundle.failures:
            failure_type_distribution[failure.failure_type] += 1
            if failure.reusable_as_training_data:
                reusable_failures += 1

    if reusable_failures <= 0 and not allow_empty:
        raise ValueError("No reusable failures were created. Use --allow-empty to allow an empty smoke run.")

    summary: dict[str, Any] = {
        "run_id": run_id,
        "created_at": now_iso(),
        "sessions_created": len(bundles),
        "claims_created": claim_count,
        "failures_created": failure_count,
        "reusable_failures": reusable_failures,
        "failure_type_distribution": dict(sorted(failure_type_distribution.items())),
        "expected_export_rows": reusable_failures,
        "session_ids": session_ids,
        "warnings": warnings,
    }

    if verify_export:
        export_path = root / "mystic_data" / "datasets" / "lab" / "raven_lab_failures.jsonl"
        export_summary = export_lab_failures_for_raven(root, export_path, allow_empty=allow_empty)
        export_rows = load_jsonl(export_path)
        summary["export_verification"] = validate_export_rows(export_rows, reusable_failures)
        summary["export_summary"] = export_summary

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = generate_lab_failure_smoke_sessions(
            root_path=args.root_path,
            count=args.count,
            allow_overwrite=args.allow_overwrite,
            allow_empty=args.allow_empty,
            run_id=args.run_id,
            output_summary=args.output_summary,
            domain=args.domain,
            include_unit_fraction_smoke=args.include_unit_fraction_smoke,
            include_code_logic_smoke=args.include_code_logic_smoke,
            include_proof_gap_smoke=args.include_proof_gap_smoke,
            verify_export=args.verify_export,
        )
    except (FileExistsError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
