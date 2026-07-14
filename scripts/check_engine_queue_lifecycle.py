"""Bounded local lifecycle check for trusted engine queue semantics."""
from __future__ import annotations

import json

from mystic.lab.engines import builtin_registry
from mystic.lab.engines.runtime import EngineJob, EngineRuntime


def main() -> int:
    runtime = EngineRuntime(builtin_registry())
    cancelled = EngineJob("lifecycle-cancelled", "engineering.dc_circuit", {"resistance_top_ohm": 1_000, "resistance_bottom_ohm": 1_000})
    completed = EngineJob("lifecycle-completed", "engineering.dc_circuit", {"source_voltage_v": 5, "resistance_top_ohm": 1_000, "resistance_bottom_ohm": 1_000})
    runtime.queue.create(cancelled)
    runtime.queue.create(completed)
    runtime.queue.request_cancellation(cancelled.job_id)
    result = runtime.execute_next("lifecycle-runner")
    assert cancelled.status == "cancelled"
    assert completed.status == "completed"
    assert result and result["status"] == "completed" and result["engine_id"] == completed.engine_id
    assert runtime.execute_next("lifecycle-runner") is None
    print(json.dumps({"status": "ok", "cancelled_job": cancelled.status, "completed_job": completed.status, "run_id": result["run_id"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
