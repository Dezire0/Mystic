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
