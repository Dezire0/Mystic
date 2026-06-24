"""Simple fake-proof routing evaluation."""

from __future__ import annotations

from mystic.evals.sample_cases import SAMPLE_CASES


def run_fake_proof_eval(orchestrator) -> dict:
    case = SAMPLE_CASES[0]
    result = orchestrator.run_problem(case)
    return {
        "case": case,
        "selected_agents": result.selected_agents,
        "report_excerpt": result.report_text.splitlines()[:6],
    }

