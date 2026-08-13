#!/usr/bin/env python3
"""Destructive-safe acceptance checks for the Phase 2C.2A job runtime.

This utility intentionally has no default database target.  It will run only
when a direct, protected staging connection is supplied and both the supplied
project ref and database host identify the designated staging project.  It
never prints the connection URL, password, or a lease token.

The worker RPCs return an opaque lease capability.  The capability is held in
this process only long enough to exercise the normal start/complete/fail
paths; the database stores hash verifiers only.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any, Callable
from urllib.parse import unquote, urlsplit
import uuid


STAGING_PROJECT_REF = "pdfvyqxvdrbxamhhngxj"
STAGING_HOST = f"db.{STAGING_PROJECT_REF}.supabase.co"
FIXTURE_PREFIX = "acc2c2a_staging"
ENGINE_ID = "physics.simple_projectile"
ENGINE_VERSION = "2.0.0"
ACCEPTANCE_HELPER_SCHEMA = "private_phase2c2a_acceptance"


class StagingHarnessError(RuntimeError):
    """A safe, credential-free staging harness failure."""


@dataclass(frozen=True, slots=True)
class StagingConfig:
    """Validated direct database configuration; never serialize this object."""

    project_ref: str
    database_url: str
    host: str
    port: int
    database: str
    user: str
    password: str

    @classmethod
    def from_environment(cls) -> "StagingConfig":
        project_ref = os.environ.get("MYSTIC_STAGING_SUPABASE_PROJECT_REF", "")
        if project_ref != STAGING_PROJECT_REF:
            raise StagingHarnessError("staging project ref is missing or does not match the authorized target")
        database_url = os.environ.get("MYSTIC_STAGING_DATABASE_URL", "")
        if not database_url:
            raise StagingHarnessError("MYSTIC_STAGING_DATABASE_URL is required for real-session validation")
        parsed = urlsplit(database_url)
        if parsed.scheme not in {"postgres", "postgresql"}:
            raise StagingHarnessError("staging database URL must use a PostgreSQL scheme")
        if parsed.hostname != STAGING_HOST:
            raise StagingHarnessError("staging database host does not bind to the authorized project ref")
        if not parsed.username or parsed.password is None or not parsed.path or parsed.path == "/":
            raise StagingHarnessError("staging database URL is incomplete")
        return cls(
            project_ref=project_ref,
            database_url=database_url,
            host=parsed.hostname,
            port=parsed.port or 5432,
            database=unquote(parsed.path.lstrip("/")),
            user=unquote(parsed.username),
            password=unquote(parsed.password),
        )

    def safe_metadata(self) -> dict[str, object]:
        return {
            "project_ref": self.project_ref,
            "target": "Mystic staging / destructive-safe concurrency validation",
            "database_host_bound": self.host == STAGING_HOST,
            "direct_session_required": True,
        }


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class PsqlDatabase:
    """A fresh psql process per operation: no Python-side connection pooling."""

    def __init__(self, config: StagingConfig) -> None:
        self.config = config

    def _environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        # The URL is not inherited by child processes; credentials remain in
        # libpq's protected environment rather than process arguments/output.
        environment.pop("MYSTIC_STAGING_DATABASE_URL", None)
        environment.update(
            {
                "PGHOST": self.config.host,
                "PGPORT": str(self.config.port),
                "PGDATABASE": self.config.database,
                "PGUSER": self.config.user,
                "PGPASSWORD": self.config.password,
                "PGSSLMODE": "require",
                "PGAPPNAME": "mystic-phase2c2a-staging-validation",
                "LC_ALL": "C",
            }
        )
        return environment

    def scalar(self, sql: str) -> str:
        completed = subprocess.run(
            ["psql", "-X", "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-c", sql],
            check=False,
            capture_output=True,
            text=True,
            env=self._environment(),
            timeout=30,
        )
        if completed.returncode != 0:
            # stderr can include user-controlled values or SQL fragments.  Do
            # not surface it, and never place a lease token in an exception.
            raise StagingHarnessError("staging database operation was rejected")
        return completed.stdout.strip()

    def json(self, sql: str) -> dict[str, Any]:
        output = self.scalar(sql)
        try:
            value = json.loads(output)
        except json.JSONDecodeError as error:
            raise StagingHarnessError("staging database returned an invalid structured response") from error
        if not isinstance(value, dict):
            raise StagingHarnessError("staging database returned an unexpected structured response")
        return value


@dataclass(frozen=True, slots=True)
class Fixture:
    campaign_id: str
    job_id: str


class ScientificJobStagingHarness:
    def __init__(self, database: PsqlDatabase, *, fixture_prefix: str = FIXTURE_PREFIX) -> None:
        self.database = database
        self.fixture_prefix = fixture_prefix

    def _fixture_id(self, kind: str) -> str:
        return f"{self.fixture_prefix}_{kind}_{uuid.uuid4().hex}"

    def _ensure_no_foreign_active_work(self) -> None:
        payload = self.database.json(
            "select json_build_object('foreign_active_jobs', "
            f"{ACCEPTANCE_HELPER_SCHEMA}.foreign_active_job_count({_quote(self.fixture_prefix)}));"
        )
        if payload.get("foreign_active_jobs") != 0:
            raise StagingHarnessError("refusing to compete with non-fixture staging work")

    def _seed_engine(self) -> None:
        self.database.scalar(
            f"select {ACCEPTANCE_HELPER_SCHEMA}.ensure_fixture_engine();"
        )

    def _create_fixture_campaign(self, campaign_id: str) -> None:
        self.database.scalar(
            f"select {ACCEPTANCE_HELPER_SCHEMA}.create_fixture_campaign({_quote(campaign_id)});"
        )

    @staticmethod
    def _input_payload() -> str:
        return (
            "jsonb_build_object('initial_position',jsonb_build_array(0,0,0),"
            "'initial_velocity',jsonb_build_array(1,4,0),'duration_seconds',1)"
        )

    def create_ready_job(self, *, kind: str, max_attempts: int = 3) -> Fixture:
        self._ensure_no_foreign_active_work()
        self._seed_engine()
        campaign_id = self._fixture_id(f"campaign_{kind}")
        job_id = self._fixture_id(f"job_{kind}")
        input_payload = self._input_payload()
        self._create_fixture_campaign(campaign_id)
        created = self.database.json(
            "select json_build_object('job_id',(public.mystic_create_scientific_job("
            f"{_quote(job_id)},{_quote(campaign_id)},0,'engine_execution',{_quote(ENGINE_ID)},{_quote(ENGINE_VERSION)},"
            f"{input_payload},public.mystic_scientific_job_payload_hash({input_payload}),{max_attempts},"
            f"{_quote(self._fixture_id('idempotency'))},'','','2C.2A')).job_id);"
        )
        if created.get("job_id") != job_id:
            raise StagingHarnessError("scientific job creation did not return the expected fixture")
        dispatched = self.database.json(
            "select json_build_object('dispatched',count(*)) from public.mystic_dispatch_scientific_job_outbox(25);"
        )
        if not isinstance(dispatched.get("dispatched"), int) or dispatched["dispatched"] < 1:
            raise StagingHarnessError("durable outbox did not dispatch the created fixture")
        return Fixture(campaign_id=campaign_id, job_id=job_id)

    def acquire(self, fixture: Fixture, worker_id: str, *, lease_seconds: int = 10) -> tuple[str, str]:
        self._ensure_no_foreign_active_work()
        payload = self.database.json(
            "select json_build_object('job_id',job_id,'lease_token',lease_token) "
            f"from public.mystic_acquire_scientific_job_lease({_quote(worker_id)},{lease_seconds});"
        )
        job_id = payload.get("job_id")
        lease_token = payload.get("lease_token")
        if job_id != fixture.job_id or not isinstance(lease_token, str) or not lease_token:
            raise StagingHarnessError("expected fixture lease was not acquired")
        return job_id, lease_token

    def start(self, fixture: Fixture, worker_id: str, lease_token: str) -> str:
        payload = self.database.json(
            "select json_build_object('status',(public.mystic_start_scientific_job("
            f"{_quote(fixture.job_id)},{_quote(worker_id)},{_quote(lease_token)})).status);"
        )
        if payload.get("status") != "RUNNING":
            raise StagingHarnessError("leased fixture did not enter RUNNING")
        return "RUNNING"

    def _result_expression(self, fixture: Fixture, value: int) -> tuple[str, str]:
        result_payload = f"jsonb_build_object('answer',{value},'fixture','phase2c2a-staging')"
        result_hash = f"public.mystic_scientific_job_payload_hash({result_payload})"
        envelope = (
            "jsonb_build_object("
            f"'job_id',{_quote(fixture.job_id)},'engine_name',{_quote(ENGINE_ID)},'engine_version',{_quote(ENGINE_VERSION)},"
            f"'result_payload',{result_payload},'result_hash',{result_hash},'runner_version','staging-harness',"
            "'schema_version','2C.2A','created_at',timezone('utc',now())::text)"
        )
        return envelope, result_hash

    def complete(self, fixture: Fixture, worker_id: str, lease_token: str, *, value: int = 42) -> str:
        envelope, result_hash = self._result_expression(fixture, value)
        payload = self.database.json(
            "with completed as (select public.mystic_complete_scientific_job("
            f"{_quote(fixture.job_id)},{_quote(worker_id)},{_quote(lease_token)},{_quote(ENGINE_ID)},"
            f"{_quote(ENGINE_VERSION)},{envelope},{result_hash},'2C.2A') as response) "
            "select json_build_object('outcome',response->>'outcome','status',response->'job'->>'status',"
            "'result_hash',response->'job'->>'result_hash') from completed;"
        )
        outcome = payload.get("outcome")
        if not isinstance(outcome, str):
            raise StagingHarnessError("scientific completion did not return a safe outcome")
        return outcome

    def fail(self, fixture: Fixture, worker_id: str, lease_token: str, *, retryable: bool) -> str:
        payload = self.database.json(
            "select json_build_object('status',(public.mystic_fail_scientific_job("
            f"{_quote(fixture.job_id)},{_quote(worker_id)},{_quote(lease_token)},'ENGINE_TRANSIENT',"
            f"'Synthetic bounded infrastructure failure',{str(retryable).lower()})).status);"
        )
        status = payload.get("status")
        if status not in {"FAILED", "CANCELLED"}:
            raise StagingHarnessError("scientific failure did not reach an expected durable state")
        return str(status)

    def reconcile(self) -> dict[str, Any]:
        return self.database.json(
            "select public.mystic_reconcile_scientific_jobs(100,1,4,10) as result;"
        )

    def job_state(self, fixture: Fixture) -> dict[str, Any]:
        return self.database.json(
            "select "
            f"{ACCEPTANCE_HELPER_SCHEMA}.inspect_fixture({_quote(fixture.job_id)});"
        )

    def _parallel(self, action: Callable[[], str]) -> list[str]:
        gate = threading.Barrier(2)

        def run() -> str:
            gate.wait(timeout=10)
            return action()

        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="staging-job-race") as executor:
            futures = [executor.submit(run), executor.submit(run)]
            return [future.result(timeout=45) for future in futures]

    def check_identity(self) -> dict[str, object]:
        self.database.json("select json_build_object('database','connected');")
        return self.database.config.safe_metadata()

    def check_schema(self) -> dict[str, object]:
        payload = self.database.json(
            "with functions(proname) as (values "
            "('mystic_create_scientific_job'),('mystic_acquire_scientific_job_lease'),"
            "('mystic_start_scientific_job'),('mystic_complete_scientific_job'),"
            "('mystic_reconcile_scientific_jobs')) "
            "select json_build_object("
            "'job_tables',(select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace "
            "where n.nspname='public' and c.relname in ('lab_scientific_jobs','lab_scientific_job_leases',"
            "'lab_scientific_job_outbox_events','lab_scientific_job_attachments','lab_scientific_job_events') and c.relrowsecurity),"
            "'worker_rpcs',(select count(*) from pg_proc p join pg_namespace n on n.oid=p.pronamespace join functions f on f.proname=p.proname where n.nspname='public'),"
            "'anon_worker_rpcs',(select count(*) from pg_proc p join pg_namespace n on n.oid=p.pronamespace join functions f on f.proname=p.proname where n.nspname='public' and has_function_privilege('anon',p.oid,'execute')),"
            "'raw_token_columns',(select count(*) from information_schema.columns where table_schema='public' and table_name in ('lab_scientific_jobs','lab_scientific_job_leases') and column_name in ('lease_token','completed_lease_token')));"
        )
        expected = {"job_tables": 5, "worker_rpcs": 5, "anon_worker_rpcs": 0, "raw_token_columns": 0}
        if any(payload.get(key) != value for key, value in expected.items()):
            raise StagingHarnessError("staging job schema does not satisfy required security invariants")
        return {"schema": "ok", **expected}

    def lease_race(self, *, iterations: int = 25) -> dict[str, object]:
        successes = 0
        for _ in range(iterations):
            fixture = self.create_ready_job(kind="lease")
            workers = [self._fixture_id("worker_a"), self._fixture_id("worker_b")]
            gate = threading.Barrier(2)

            def acquire(worker_id: str) -> tuple[bool, str | None]:
                gate.wait(timeout=10)
                try:
                    _job_id, token = self.acquire(fixture, worker_id)
                except StagingHarnessError:
                    return False, None
                return True, token

            with ThreadPoolExecutor(max_workers=2, thread_name_prefix="staging-lease-race") as executor:
                results = [future.result(timeout=45) for future in (executor.submit(acquire, worker) for worker in workers)]
            winners = [(worker, token) for worker, (won, token) in zip(workers, results) if won and token]
            state = self.job_state(fixture)
            if len(winners) != 1 or state.get("active_leases") != 1 or state.get("attempt") != 1:
                raise StagingHarnessError("atomic lease invariant failed")
            self.database.scalar(
                f"select public.mystic_cancel_scientific_job({_quote(fixture.job_id)});"
            )
            self.database.scalar(
                "select (public.mystic_start_scientific_job("
                f"{_quote(fixture.job_id)},{_quote(winners[0][0])},{_quote(winners[0][1] or '')})).status;"
            )
            if self.job_state(fixture).get("status") != "CANCELLED":
                raise StagingHarnessError("lease race fixture could not be cooperatively cancelled")
            successes += 1
        return {"iterations": iterations, "single_winner_iterations": successes}

    def completion_race(self) -> dict[str, object]:
        fixture = self.create_ready_job(kind="completion")
        worker_id = self._fixture_id("completion_worker")
        _job_id, token = self.acquire(fixture, worker_id)
        self.start(fixture, worker_id, token)
        outcomes = self._parallel(lambda: self.complete(fixture, worker_id, token, value=42))
        if sorted(outcomes) != ["ACCEPTED", "REPLAY_IGNORED"]:
            raise StagingHarnessError("same-result completion race was not idempotent")
        conflict = self.complete(fixture, worker_id, token, value=43)
        self.reconcile()
        self.reconcile()
        state = self.job_state(fixture)
        if conflict != "CONFLICT_REJECTED" or state.get("status") != "SUCCEEDED" or state.get("attachments") != 1:
            raise StagingHarnessError("conflicting completion or result attachment invariant failed")
        if state.get("conflicting_result_count") != 1 or state.get("result_replay_count") != 1:
            raise StagingHarnessError("completion replay accounting invariant failed")
        return {
            "fixture_job_id": fixture.job_id,
            "outcomes": sorted(outcomes),
            "conflict": conflict,
            "attachments": state["attachments"],
        }

    def lease_expiry(self) -> dict[str, object]:
        fixture = self.create_ready_job(kind="expiry")
        worker_id = self._fixture_id("expiry_worker")
        _job_id, token = self.acquire(fixture, worker_id, lease_seconds=10)
        self.start(fixture, worker_id, token)
        time.sleep(11)
        self.reconcile()
        first = self.job_state(fixture)
        if first.get("status") != "RETRY_WAIT" or first.get("attempt") != 1 or first.get("attempt_records") != 1:
            raise StagingHarnessError("expired lease did not enter deterministic retry wait")
        time.sleep(1.2)
        self.reconcile()
        if self.job_state(fixture).get("status") != "READY":
            raise StagingHarnessError("expired lease retry was not released when due")
        replacement_worker = self._fixture_id("replacement_worker")
        _job_id, replacement_token = self.acquire(fixture, replacement_worker)
        self.start(fixture, replacement_worker, replacement_token)
        stale_rejected = False
        try:
            self.complete(fixture, worker_id, token)
        except StagingHarnessError:
            stale_rejected = True
        if not stale_rejected:
            raise StagingHarnessError("expired worker completion was not rejected")
        self.database.scalar(f"select public.mystic_cancel_scientific_job({_quote(fixture.job_id)});")
        self.database.scalar(
            "select (public.mystic_start_scientific_job("
            f"{_quote(fixture.job_id)},{_quote(replacement_worker)},{_quote(replacement_token)})).status;"
        )
        return {"fixture_job_id": fixture.job_id, "expired_attempt": first["attempt"], "stale_owner_rejected": True}

    def attachment_reconcile(self) -> dict[str, object]:
        fixture = self.create_ready_job(kind="attachment")
        worker_id = self._fixture_id("attachment_worker")
        _job_id, token = self.acquire(fixture, worker_id)
        self.start(fixture, worker_id, token)
        if self.complete(fixture, worker_id, token) != "ACCEPTED":
            raise StagingHarnessError("attachment fixture completion was not accepted")
        pre = self.job_state(fixture)
        if pre.get("attachment_status") != "PENDING" or pre.get("attachments") != 0:
            raise StagingHarnessError("completion-before-attachment crash state was not preserved")
        self.reconcile()
        self.reconcile()
        post = self.job_state(fixture)
        if post.get("attachment_status") != "ATTACHED" or post.get("attachments") != 1:
            raise StagingHarnessError("reconciliation did not attach exactly once")
        return {"fixture_job_id": fixture.job_id, "attachment_status": post["attachment_status"], "attachments": post["attachments"]}

    def reconciliation_race(self) -> dict[str, object]:
        fixture = self.create_ready_job(kind="reconciliation")
        worker_id = self._fixture_id("reconciliation_worker")
        _job_id, token = self.acquire(fixture, worker_id)
        self.start(fixture, worker_id, token)
        if self.complete(fixture, worker_id, token) != "ACCEPTED":
            raise StagingHarnessError("reconciliation fixture completion was not accepted")
        outcomes = self._parallel(lambda: json.dumps(self.reconcile(), sort_keys=True))
        state = self.job_state(fixture)
        if state.get("status") != "SUCCEEDED" or state.get("attachments") != 1:
            raise StagingHarnessError("concurrent reconciliation did not preserve one logical attachment")
        return {"fixture_job_id": fixture.job_id, "reconcilers": len(outcomes), "attachments": state["attachments"]}

    def outbox_recovery(self) -> dict[str, object]:
        fixture = self.create_ready_job(kind="outbox")
        self.database.scalar(
            f"select {ACCEPTANCE_HELPER_SCHEMA}.mark_fixture_outbox_stale({_quote(fixture.job_id)});"
        )
        self.reconcile()
        state = self.job_state(fixture)
        if state.get("pending_outbox_events") != 1 or state.get("dispatched_outbox_events") != 0:
            raise StagingHarnessError("stale outbox dispatch was not deterministically requeued")
        return {"fixture_job_id": fixture.job_id, "pending_outbox_events": state["pending_outbox_events"]}

    def cancellation_race(self) -> dict[str, object]:
        fixture = self.create_ready_job(kind="cancellation")
        worker_id = self._fixture_id("cancellation_worker")
        _job_id, token = self.acquire(fixture, worker_id)
        self.start(fixture, worker_id, token)
        gate = threading.Barrier(2)

        def cancel() -> str:
            gate.wait(timeout=10)
            payload = self.database.json(
                "select json_build_object('status',(public.mystic_cancel_scientific_job("
                f"{_quote(fixture.job_id)})).status);"
            )
            return str(payload.get("status"))

        def complete() -> str:
            gate.wait(timeout=10)
            try:
                return self.complete(fixture, worker_id, token)
            except StagingHarnessError:
                return "REJECTED"

        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="staging-cancel-race") as executor:
            results = [future.result(timeout=45) for future in (executor.submit(cancel), executor.submit(complete))]
        self.reconcile()
        state = self.job_state(fixture)
        success_attached = state.get("status") == "SUCCEEDED" and state.get("attachments") == 1
        cancelled = state.get("status") == "CANCELLED" and state.get("attachments") == 0
        if not (success_attached or cancelled):
            raise StagingHarnessError("cancellation/completion race produced an incoherent terminal state")
        return {"fixture_job_id": fixture.job_id, "race_calls": results, "terminal_status": state["status"], "attachments": state["attachments"]}

    def dead_letter(self) -> dict[str, object]:
        fixture = self.create_ready_job(kind="dead_letter", max_attempts=2)
        for attempt in (1, 2):
            worker_id = self._fixture_id(f"dead_worker_{attempt}")
            _job_id, token = self.acquire(fixture, worker_id)
            self.start(fixture, worker_id, token)
            if self.fail(fixture, worker_id, token, retryable=True) != "FAILED":
                raise StagingHarnessError("retryable infrastructure fixture was not marked FAILED")
            self.reconcile()
            if attempt == 1:
                if self.job_state(fixture).get("status") != "RETRY_WAIT":
                    raise StagingHarnessError("first retryable failure did not enter RETRY_WAIT")
                time.sleep(1.2)
                self.reconcile()
        state = self.job_state(fixture)
        if state.get("status") != "DEAD_LETTER" or state.get("attempt") != 2 or state.get("failure_attachment_state") != "ATTACHED":
            raise StagingHarnessError("retry exhaustion did not reach terminal dead letter")
        return {"fixture_job_id": fixture.job_id, "attempt": state["attempt"], "terminal_status": state["status"]}

    def cleanup(self) -> dict[str, object]:
        self.database.scalar(
            "select "
            f"{ACCEPTANCE_HELPER_SCHEMA}.cleanup_fixtures({_quote(self.fixture_prefix)});"
        )
        return {"cleanup": "completed", "fixture_prefix": self.fixture_prefix}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in (
        "identity",
        "schema",
        "lease-race",
        "completion-race",
        "lease-expiry",
        "attachment-reconcile",
        "reconciliation-race",
        "outbox-recovery",
        "cancellation-race",
        "dead-letter",
        "all",
        "cleanup",
    ):
        modes.add_argument(f"--{mode}", action="store_true")
    parser.add_argument("--lease-race-iterations", type=int, default=25)
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    try:
        config = StagingConfig.from_environment()
        harness = ScientificJobStagingHarness(PsqlDatabase(config))
        selected = next(name for name, value in vars(arguments).items() if value is True)
        if selected == "identity":
            result: dict[str, object] = harness.check_identity()
        elif selected == "schema":
            result = harness.check_schema()
        elif selected == "lease_race":
            if not 1 <= arguments.lease_race_iterations <= 100:
                raise StagingHarnessError("lease race iterations must be between 1 and 100")
            result = harness.lease_race(iterations=arguments.lease_race_iterations)
        elif selected == "completion_race":
            result = harness.completion_race()
        elif selected == "lease_expiry":
            result = harness.lease_expiry()
        elif selected == "attachment_reconcile":
            result = harness.attachment_reconcile()
        elif selected == "reconciliation_race":
            result = harness.reconciliation_race()
        elif selected == "outbox_recovery":
            result = harness.outbox_recovery()
        elif selected == "cancellation_race":
            result = harness.cancellation_race()
        elif selected == "dead_letter":
            result = harness.dead_letter()
        elif selected == "cleanup":
            result = harness.cleanup()
        else:
            result = {
                "identity": harness.check_identity(),
                "schema": harness.check_schema(),
                "lease_race": harness.lease_race(iterations=arguments.lease_race_iterations),
                "completion_race": harness.completion_race(),
                "lease_expiry": harness.lease_expiry(),
                "attachment_reconcile": harness.attachment_reconcile(),
                "reconciliation_race": harness.reconciliation_race(),
                "outbox_recovery": harness.outbox_recovery(),
                "cancellation_race": harness.cancellation_race(),
                "dead_letter": harness.dead_letter(),
            }
    except (StagingHarnessError, subprocess.TimeoutExpired) as error:
        # Error strings are intentionally generic and must never include a URL,
        # password, raw token, or server-side diagnostic.
        print(json.dumps({"ok": False, "error": str(error)}, sort_keys=True))
        return 2
    print(json.dumps({"ok": True, "result": result}, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
