from __future__ import annotations


def independent_discovery_prompt(problem: str) -> str:
    return (
        "Work independently first. Return a strategy, non-obvious discoveries, lemma candidates, "
        "possible counterexamples, proof gaps, verification requests, and questions for other models.\n\n"
        f"Problem:\n{problem}"
    )


def discovery_sharing_prompt(problem: str, discoveries_text: str) -> str:
    return (
        "You are seeing discoveries from other models. Accept, challenge, extend, or refute them.\n\n"
        f"Problem:\n{problem}\n\nDiscoveries:\n{discoveries_text}"
    )


def cross_critique_prompt(problem: str, target_summary: str, discoveries_text: str) -> str:
    return (
        "Cross-critique another participant. Point out errors, unsupported jumps, hidden assumptions, "
        "or stronger alternatives.\n\n"
        f"Problem:\n{problem}\n\nTarget turn:\n{target_summary}\n\nCurrent discoveries:\n{discoveries_text}"
    )


def revision_after_evidence_prompt(problem: str, evidence_text: str) -> str:
    return (
        "Revise your position after seeing deterministic tool evidence. Preserve only claims still supported, "
        "withdraw refuted claims, and sharpen anything that remains uncertain.\n\n"
        f"Problem:\n{problem}\n\nEvidence:\n{evidence_text}"
    )
