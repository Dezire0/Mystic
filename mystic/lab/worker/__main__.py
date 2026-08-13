from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys

from mystic.lab.campaign_runtime import CampaignRuntime
from mystic.lab.scientific_job_runtime import ScientificJobRuntime

from .config import ScientificWorkerConfig
from .service import ScientificJobWorkerService
from .status_store import WorkerControlStorage, WorkerStatusStorage


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Trusted Mystic scientific job worker")
    modes = parser.add_mutually_exclusive_group(required=True)
    for name in ("self-test", "once", "run", "status", "reconcile-once", "drain"):
        modes.add_argument(f"--{name}", action="store_true")
    return parser


def _authenticated_config(root_path: Path) -> ScientificWorkerConfig:
    # Credential material is required before any command that mutates durable
    # worker state. It is verified by the deployment bootstrap, never printed,
    # and is not an MCP credential.
    verifier = ScientificWorkerConfig.credential_verifier_from_environment()
    verifier.require(os.environ.get("MYSTIC_SCIENTIFIC_WORKER_CREDENTIAL", ""))
    return ScientificWorkerConfig.from_environment(root_path=root_path)


def _require_explicit_worker_id() -> None:
    """Prevent an operator command from silently addressing a random ID."""
    if not os.environ.get("MYSTIC_SCIENTIFIC_WORKER_ID", "").strip():
        raise ValueError("MYSTIC_SCIENTIFIC_WORKER_ID is required for status and drain")


def _service(root_path: Path, config: ScientificWorkerConfig) -> ScientificJobWorkerService:
    campaigns = CampaignRuntime(root_path)
    runtime = ScientificJobRuntime(root_path, campaign_runtime=campaigns)
    return ScientificJobWorkerService(runtime, config)


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.self_test:
        config = ScientificWorkerConfig.from_environment()
        payload = {
            "ok": True,
            "worker_id": config.worker_id,
            "maximum_concurrency": config.maximum_concurrency,
            "engine_runtime": "allowlisted",
            "credential_material_exposed": False,
        }
        print(json.dumps(payload, sort_keys=True))
        return 0
    root = Path(os.environ.get("MYSTIC_SCIENTIFIC_WORKER_ROOT", Path.cwd()))
    try:
        if arguments.status or arguments.drain:
            _require_explicit_worker_id()
        config = _authenticated_config(root)
    except (ValueError, PermissionError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, sort_keys=True))
        return 2
    if arguments.status:
        try:
            health = WorkerStatusStorage(root).get(config.worker_id)
        except KeyError:
            print(json.dumps({"ok": False, "error": "Scientific worker status was not found."}, sort_keys=True))
            return 3
        print(json.dumps({"ok": True, "health": health}, sort_keys=True))
        return 0
    if arguments.drain:
        request = WorkerControlStorage(root).request_drain(config.worker_id)
        print(json.dumps({"ok": True, "worker_id": request["worker_id"], "action": "drain_requested"}, sort_keys=True))
        return 0
    service = _service(root, config)
    if arguments.reconcile_once:
        print(json.dumps({"ok": True, "reconciliation": service.reconcile_once()}, sort_keys=True))
        service.drain_and_stop()
        return 0
    if arguments.once:
        result = service.poll_once(wait_for_completion=True)
        print(json.dumps({"ok": True, "poll": asdict(result), "health": service.safe_health()}, sort_keys=True))
        service.drain_and_stop()
        return 0
    try:
        service.run_forever()
    except KeyboardInterrupt:
        service.drain_and_stop()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
