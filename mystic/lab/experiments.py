from __future__ import annotations

from mystic.lab.session import Experiment


def summarize_experiment(experiment: Experiment) -> str:
    if experiment.evidence_summary:
        return experiment.evidence_summary
    if experiment.outputs:
        return f"{experiment.method} => {experiment.verdict}"
    return f"{experiment.method} is pending"

