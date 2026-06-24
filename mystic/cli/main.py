"""Command line entrypoint for Mystic."""

from __future__ import annotations

import argparse
import json
import sys

from mystic.core.orchestrator import MysticOrchestrator
from mystic.evals.fake_proof_eval import run_fake_proof_eval


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mystic")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init")

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("problem")

    subparsers.add_parser("sessions")

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("session_id")

    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("kind", choices=["raven", "forge", "all", "prime", "algebra", "analysis", "lean", "core"])

    eval_parser = subparsers.add_parser("eval")
    eval_parser.add_argument("suite", choices=["fake-proofs"])

    subparsers.add_parser("agents")
    subparsers.add_parser("config")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    orchestrator = MysticOrchestrator()

    if args.command == "init":
        print(orchestrator.init_workspace())
        return 0
    if args.command == "run":
        result = orchestrator.run_problem(args.problem)
        print(result.report_text)
        return 0
    if args.command == "sessions":
        print(json.dumps(orchestrator.list_sessions(), indent=2))
        return 0
    if args.command == "show":
        print(json.dumps(orchestrator.get_session(args.session_id), indent=2))
        return 0
    if args.command == "export":
        print(json.dumps(orchestrator.export_dataset(args.kind), indent=2))
        return 0
    if args.command == "eval":
        print(json.dumps(run_fake_proof_eval(orchestrator), indent=2))
        return 0
    if args.command == "agents":
        print(json.dumps(orchestrator.available_agents(), indent=2))
        return 0
    if args.command == "config":
        print(json.dumps(orchestrator.config_snapshot(), indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

