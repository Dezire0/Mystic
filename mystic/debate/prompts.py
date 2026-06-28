from __future__ import annotations


def draft_prompt(task: str, problem: str) -> str:
    return f"Produce an initial draft for the task '{task}'.\n\nProblem:\n{problem}"


def critique_prompt(problem: str, prior_text: str) -> str:
    return (
        "Critique the previous turns. Focus on false claims, unsupported steps, and missing cases.\n\n"
        f"Problem:\n{problem}\n\nPrior turns:\n{prior_text}"
    )


def revision_prompt(problem: str, prior_text: str, evidence_text: str) -> str:
    return (
        "Revise your position after critique and tool evidence. State what you retract and keep.\n\n"
        f"Problem:\n{problem}\n\nCritique:\n{prior_text}\n\nEvidence:\n{evidence_text}"
    )


def final_judge_prompt(problem: str, debate_text: str, evidence_text: str) -> str:
    return (
        "You are the final judge. Deterministic tool evidence overrides model claims.\n\n"
        f"Problem:\n{problem}\n\nDebate:\n{debate_text}\n\nEvidence:\n{evidence_text}"
    )
