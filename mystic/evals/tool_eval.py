"""Tooling smoke checks."""

from __future__ import annotations


def evaluate_python_runner(runner) -> dict:
    result = runner.run("print({'ok': True})\n")
    return result.to_dict()

