from __future__ import annotations

from mystic.lab.session import LabReport, LabSessionBundle


def render_report(bundle: LabSessionBundle) -> LabReport:
    surviving_claims = [claim.to_dict() for claim in bundle.claims if claim.status in {"PROVED", "TESTED", "HEURISTIC"}]
    failed_claims = [claim.to_dict() for claim in bundle.claims if claim.status in {"FAILED", "REFUTED", "NEEDS_MORE_DETAIL"}]
    key_lessons = [failure.lesson for failure in bundle.failures[-5:]]
    surviving_lines = [f"- {claim['text']} [{claim['status']}]" for claim in surviving_claims] or ["- None"]
    failed_lines = [f"- {claim['text']} [{claim['status']}]" for claim in failed_claims] or ["- None"]
    experiment_lines = [f"- {experiment.question} => {experiment.verdict}" for experiment in bundle.experiments] or ["- None"]
    lesson_lines = [f"- {lesson}" for lesson in key_lessons] or ["- None"]
    next_action_lines = [f"- {item}" for item in bundle.session.next_actions] or ["- None"]
    markdown = "\n".join(
        [
            f"# Mystic Lab Report: {bundle.session.session_id}",
            "",
            f"Problem: {bundle.session.problem}",
            f"Domain: {bundle.session.domain}",
            "",
            "## Surviving Claims",
            *surviving_lines,
            "",
            "## Failed Claims",
            *failed_lines,
            "",
            "## Experiments",
            *experiment_lines,
            "",
            "## Key Lessons",
            *lesson_lines,
            "",
            "## Next Actions",
            *next_action_lines,
            "",
        ]
    )
    return LabReport(
        session_id=bundle.session.session_id,
        title=f"Mystic Lab Report {bundle.session.session_id}",
        problem=bundle.session.problem,
        domain=bundle.session.domain,
        surviving_claims=surviving_claims,
        failed_claims=failed_claims,
        experiments=[item.to_dict() for item in bundle.experiments],
        key_lessons=key_lessons,
        next_actions=list(bundle.session.next_actions),
        markdown=markdown,
    )
