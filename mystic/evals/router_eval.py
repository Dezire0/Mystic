"""Router smoke evaluation."""

from __future__ import annotations


def evaluate_router(router) -> dict:
    problem = "For every integer n >= 2, study the congruence structure of 4/n."
    return {"problem": problem, "selected_agents": router.route(problem)}

