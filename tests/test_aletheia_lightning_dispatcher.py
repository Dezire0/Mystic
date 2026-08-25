from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shlex
import sys
from types import SimpleNamespace

import pytest

from mystic.specialist_dispatcher import (
    LightningBusyError,
    LightningDispatcher,
    LightningDispatcherError,
    LightningSDKClient,
    LightningSettings,
    LightningScientificJobAdapter,
    SpecialistRouter,
    SpecialistJob,
)


class FakeLightningClient:
    def __init__(self, *, failure: str = "", payload: dict | None = None, stdout: str = "", stderr: str = "", command_output: str = "", probe_output: str = "", artifact_responses: dict[str, list[bool]] | None = None, shell_responses: dict[str, list[bool]] | None = None, corrupt_shell_path: str = "") -> None:
        self.failure, self.payload = failure, payload or {
            "job_id": "safe-job", "task": "pdf_retrieval", "status": "SUCCEEDED", "runtime_seconds": 4.2,
            "gpu": {"available": True, "name": "Tesla T4"},
            "results": [{"page": 1, "pdf": "~/aletheia_worker/jobs/safe-job/inputs/0.pdf", "preview": "lens evidence", "text_score": 0.9, "visual_score": 0.8, "fusion_score": 0.7, "rerank_score": 0.6}],
        }
        self.stdout, self.stderr, self.command_output, self.probe_output = stdout, stderr, command_output, probe_output
        self.artifact_responses = artifact_responses or {}
        self.shell_responses = shell_responses or {}
        self.corrupt_shell_path = corrupt_shell_path
        self.artifact_checks: list[str] = []
        self.remote_hashes: dict[str, str] = {}
        self.started = self.stopped = 0; self.uploads: list[tuple[str, str]] = []; self.downloads: list[tuple[str, str]] = []; self.commands: list[str] = []

    def start_t4(self) -> None:
        self.started += 1
        if self.failure == "start": raise RuntimeError("start failure")
    def stop(self) -> None:
        self.stopped += 1
        if self.failure == "stop": raise RuntimeError("stop failure")
    def upload(self, local_path: Path, remote_path: str) -> None:
        self.uploads.append((str(local_path), remote_path))
        self.remote_hashes[remote_path] = hashlib.sha256(local_path.read_bytes()).hexdigest()
        if self.failure == "upload": raise RuntimeError("upload failure")
    def run(self, command: str) -> tuple[str, int]:
        self.commands.append(command)
        if command.startswith("lightning studio cp "):
            if self.failure == "materialize" and "lit://" in shlex.split(command)[3]: return "Authorization: Bearer bridge-token", 1
            if self.failure == "publish" and "lit://" in shlex.split(command)[4]: return "token=bridge-token", 1
            source, destination = shlex.split(command)[3:5]
            if source.startswith("lit://"):
                transfer_path = source.split("/studios/", 1)[1].split("/", 1)[1]
                self.remote_hashes[destination] = self.remote_hashes[transfer_path]
            else:
                transfer_path = destination.split("/studios/", 1)[1].split("/", 1)[1]
                self.remote_hashes[transfer_path] = self.remote_hashes[source]
            return "", 0
        if command.startswith("test -f "):
            path = command.removeprefix("test -f ")
            if path in self.shell_responses and self.shell_responses[path]:
                return "", 0 if self.shell_responses[path].pop(0) else 1
            if self.failure == "missing-upload-job" and command.endswith("/job.json"): return "", 1
            if self.failure == "missing-remote-result" and command.endswith("/result.json"): return "", 1
            return "", 0
        if command.startswith("tail -c "):
            return (self.stdout if "stdout.log" in command else self.stderr), 0
        if command.startswith('printf "PWD='):
            return self.probe_output, 0
        if command.startswith("sha256sum "):
            path = shlex.split(command)[1]
            digest = self.remote_hashes.get(path, hashlib.sha256(json.dumps(self.payload).encode()).hexdigest())
            if path == self.corrupt_shell_path: digest = "0" * 64
            return f"{digest}  {path}", 0
        if "aletheia_job.py" in command:
            output_path = shlex.split(command)[shlex.split(command).index("--output") + 1]
            self.remote_hashes[output_path] = hashlib.sha256(json.dumps(self.payload).encode()).hexdigest()
            if self.failure in {"run", "timeout"}:
                return self.command_output, 124 if self.failure == "timeout" else 1
        return "", 0

    def artifact_exists(self, remote_path: str) -> bool:
        self.artifact_checks.append(remote_path)
        if remote_path in self.artifact_responses and self.artifact_responses[remote_path]:
            return self.artifact_responses[remote_path].pop(0)
        return self.failure != "missing-artifact-input"
    def download(self, remote_path: str, local_path: Path) -> None:
        self.downloads.append((remote_path, str(local_path)))
        if self.failure == "download": raise RuntimeError("download failure")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        if remote_path.endswith("result.json"):
            if self.failure == "missing": raise FileNotFoundError(remote_path)
            local_path.write_text("{" if self.failure == "malformed" else json.dumps(self.payload), encoding="utf-8")
        else: local_path.write_text("worker log", encoding="utf-8")


def make_dispatcher(tmp_path: Path, fake: FakeLightningClient) -> LightningDispatcher:
    settings = LightningSettings("user", "super-secret-key", "owner", "team", "existing-studio")
    return LightningDispatcher(root_path=tmp_path, settings=settings, client_factory=lambda _: fake)


def make_job(tmp_path: Path, job_id: str = "safe-job") -> SpecialistJob:
    pdf = tmp_path / "source.pdf"; pdf.write_bytes(b"%PDF-1.4\nfixture")
    return SpecialistJob(job_id, "Where is lensing explained?", (pdf,))


def test_success_persists_evidence_stops_gpu_and_is_idempotent(tmp_path: Path) -> None:
    client = FakeLightningClient(); dispatcher = make_dispatcher(tmp_path, client); job = make_job(tmp_path)
    result = dispatcher.execute(job)
    assert result.evidence_candidates[0].page == 1 and result.evidence_candidates[0].status == "CANDIDATE"
    assert result.evidence_candidates[0].source_hash and client.started == client.stopped == 1
    assert any(event["event_type"] == "EVIDENCE_CANDIDATES_CREATED" for event in result.lifecycle_events)
    reused = dispatcher.execute(job)
    assert reused.reused and client.started == 1


@pytest.mark.parametrize("failure", ["start", "upload", "run", "timeout", "missing", "malformed", "download"])
def test_failures_are_closed_and_stop_after_start(tmp_path: Path, failure: str) -> None:
    client = FakeLightningClient(failure=failure); dispatcher = make_dispatcher(tmp_path, client)
    job = make_job(tmp_path)
    with pytest.raises(LightningDispatcherError): dispatcher.execute(job)
    assert client.stopped == (1 if client.started else 0)
    state = json.loads((dispatcher.base_dir / job.job_id / "dispatch.json").read_text())
    assert state["status"] == "FAILED" and "super-secret-key" not in json.dumps(state)


def test_remote_execution_failure_persists_bounded_sanitized_diagnostics_and_stops_gpu(tmp_path: Path) -> None:
    client = FakeLightningClient(
        failure="run",
        command_output='Authorization: Bearer command-token {"token": "json-token"}',
        stdout="prefix-" + "x" * 5_000,
        stderr="LIGHTNING_API_KEY=super-secret-key\nLIGHTNING_USER_ID=user\napi_key=other-secret\nworker failed",
    )
    dispatcher, job = make_dispatcher(tmp_path, client), make_job(tmp_path)

    with pytest.raises(LightningDispatcherError) as raised:
        dispatcher.execute(job)

    message = str(raised.value)
    state = json.loads((dispatcher.base_dir / job.job_id / "dispatch.json").read_text())
    diagnostics = state["diagnostics"]
    assert client.stopped == 1 and diagnostics["remote_exit_code"] == 1
    assert diagnostics["stages"]["remote_execute"] == "FAILED"
    assert diagnostics["stages"]["studio_stop"] == "OK"
    assert diagnostics["result_json_exists"] is True
    assert len(diagnostics["remote_stdout_tail"].encode()) <= 4 * 1024
    assert "prefix-" not in diagnostics["remote_stdout_tail"]
    assert "super-secret-key" not in json.dumps(diagnostics)
    assert "command-token" not in json.dumps(diagnostics)
    assert "json-token" not in json.dumps(diagnostics)
    assert "other-secret" not in json.dumps(diagnostics)
    assert "LIGHTNING_USER_ID=user" not in json.dumps(diagnostics)
    assert "REMOTE_EXIT_CODE: 1" in message and "REMOTE_STDERR_TAIL:" in message


def test_sdk_transfers_use_content_root_relative_paths_and_job_json_uses_studio_paths(tmp_path: Path) -> None:
    client = FakeLightningClient()
    dispatcher, job = make_dispatcher(tmp_path, client), make_job(tmp_path)

    dispatcher.execute(job)

    transfer_root = "aletheia_worker/jobs/safe-job"
    assert [remote_path for _, remote_path in client.uploads] == [
        f"{transfer_root}/job.json", f"{transfer_root}/inputs/0.pdf",
    ]
    assert all("~" not in remote_path and not remote_path.startswith("/teamspace/") for _, remote_path in client.uploads)
    assert client.downloads == [(f"{transfer_root}/result.json", str(dispatcher.base_dir / "safe-job" / "result.json"))]
    remote_spec = json.loads((dispatcher.base_dir / "safe-job" / "job.json").read_text())
    assert remote_spec["pdfs"] == ["/teamspace/studios/this_studio/aletheia_worker/jobs/safe-job/inputs/0.pdf"]
    assert str(job.pdf_paths[0]) not in json.dumps(remote_spec)
    assert "mkdir -p /teamspace/studios/this_studio/aletheia_worker/jobs/safe-job/inputs" in client.commands
    execution_index = next(index for index, command in enumerate(client.commands) if "aletheia_job.py" in command)
    assert any(command == "test -f /teamspace/studios/this_studio/aletheia_worker/jobs/safe-job/job.json" for command in client.commands[:execution_index])
    assert any(command == "test -f /teamspace/studios/this_studio/aletheia_worker/jobs/safe-job/inputs/0.pdf" for command in client.commands[:execution_index])
    result_check = "test -f /teamspace/studios/this_studio/aletheia_worker/jobs/safe-job/result.json"
    assert client.commands.index(result_check) > execution_index


def test_missing_uploaded_job_json_fails_before_remote_execution_and_stops_gpu(tmp_path: Path) -> None:
    client = FakeLightningClient(failure="missing-upload-job")
    dispatcher, job = make_dispatcher(tmp_path, client), make_job(tmp_path)

    with pytest.raises(LightningDispatcherError) as raised:
        dispatcher.execute(job)

    diagnostics = json.loads((dispatcher.base_dir / job.job_id / "dispatch.json").read_text())["diagnostics"]
    assert client.stopped == 1
    assert not any("aletheia_job.py" in command for command in client.commands)
    assert diagnostics["stages"]["verify_remote_input"] == "FAILED"
    assert diagnostics["missing_remote_path"] == "/teamspace/studios/this_studio/aletheia_worker/jobs/safe-job/job.json"
    assert "STAGE verify_remote_input: FAILED" in str(raised.value)


def test_missing_remote_result_fails_before_download_and_stops_gpu(tmp_path: Path) -> None:
    client = FakeLightningClient(failure="missing-remote-result")
    dispatcher, job = make_dispatcher(tmp_path, client), make_job(tmp_path)

    with pytest.raises(LightningDispatcherError):
        dispatcher.execute(job)

    diagnostics = json.loads((dispatcher.base_dir / job.job_id / "dispatch.json").read_text())["diagnostics"]
    assert client.stopped == 1 and not client.downloads
    assert diagnostics["stages"]["verify_shell_result"] == "FAILED"
    assert diagnostics["missing_remote_path"] == "/teamspace/studios/this_studio/aletheia_worker/jobs/safe-job/result.json"


def test_artifact_verification_occurs_after_upload_and_before_shell_probe(tmp_path: Path) -> None:
    client = FakeLightningClient()
    dispatcher = make_dispatcher(tmp_path, client)

    dispatcher.execute(make_job(tmp_path))

    assert client.artifact_checks[:2] == [
        "aletheia_worker/jobs/safe-job/job.json",
        "aletheia_worker/jobs/safe-job/inputs/0.pdf",
    ]
    first_shell_probe = next(index for index, command in enumerate(client.commands) if command.startswith("test -f "))
    assert client.uploads and client.artifact_checks[:2]
    assert first_shell_probe > 0


def test_lit_uri_materialization_precedes_shell_verification_and_worker_launch(tmp_path: Path) -> None:
    client = FakeLightningClient()
    dispatcher = make_dispatcher(tmp_path, client)

    dispatcher.execute(make_job(tmp_path))

    job_uri = "lit://owner/team/studios/existing-studio/aletheia_worker/jobs/safe-job/job.json"
    pdf_uri = "lit://owner/team/studios/existing-studio/aletheia_worker/jobs/safe-job/inputs/0.pdf"
    assert dispatcher._artifact_uri("aletheia_worker/jobs/safe-job/job.json") == job_uri
    execution_index = next(index for index, command in enumerate(client.commands) if "aletheia_job.py" in command)
    bridge_commands = [command for command in client.commands[:execution_index] if command.startswith("lightning studio cp ")]
    assert any(job_uri in command for command in bridge_commands)
    assert any(pdf_uri in command for command in bridge_commands)
    assert all("/teamspace/studios/this_studio/" in command for command in bridge_commands)


def test_materialization_failure_stops_studio_blocks_worker_and_redacts_output(tmp_path: Path) -> None:
    client = FakeLightningClient(failure="materialize")
    dispatcher, job = make_dispatcher(tmp_path, client), make_job(tmp_path)

    with pytest.raises(LightningDispatcherError):
        dispatcher.execute(job)

    diagnostics = json.loads((dispatcher.base_dir / job.job_id / "dispatch.json").read_text())["diagnostics"]
    assert client.stopped == 1 and not any("aletheia_job.py" in command for command in client.commands)
    assert diagnostics["stages"]["materialize_remote_input"] == "FAILED"
    assert diagnostics["materialization_exit_codes"] == [1]
    assert "bridge-token" not in diagnostics["materialization_output_tail"]


def test_materialized_input_hash_mismatch_blocks_worker(tmp_path: Path) -> None:
    shell_job = "/teamspace/studios/this_studio/aletheia_worker/jobs/safe-job/job.json"
    client = FakeLightningClient(corrupt_shell_path=shell_job)
    dispatcher, job = make_dispatcher(tmp_path, client), make_job(tmp_path)

    with pytest.raises(LightningDispatcherError):
        dispatcher.execute(job)

    diagnostics = json.loads((dispatcher.base_dir / job.job_id / "dispatch.json").read_text())["diagnostics"]
    assert diagnostics["sha256_mismatch_path"] == shell_job
    assert diagnostics["stages"]["verify_remote_input"] == "FAILED"
    assert not any("aletheia_job.py" in command for command in client.commands)


def test_missing_artifact_input_fails_before_shell_probe_and_worker_launch(tmp_path: Path) -> None:
    client = FakeLightningClient(failure="missing-artifact-input")
    dispatcher, job = make_dispatcher(tmp_path, client), make_job(tmp_path)

    with pytest.raises(LightningDispatcherError):
        dispatcher.execute(job)

    diagnostics = json.loads((dispatcher.base_dir / job.job_id / "dispatch.json").read_text())["diagnostics"]
    assert client.stopped == 1 and not any(command.startswith("test -f ") or "aletheia_job.py" in command for command in client.commands)
    assert diagnostics["stages"]["verify_artifact_input"] == "FAILED"
    assert diagnostics["missing_artifact_path"] == "aletheia_worker/jobs/safe-job/job.json"


def test_shell_result_is_explicitly_published_and_artifact_verified_before_download(tmp_path: Path) -> None:
    client = FakeLightningClient()
    dispatcher = make_dispatcher(tmp_path, client)

    dispatcher.execute(make_job(tmp_path))

    publish = next(command for command in client.commands if command.startswith("lightning studio cp /teamspace/studios/this_studio/") and "result.json" in command)
    assert "lit://owner/team/studios/existing-studio/aletheia_worker/jobs/safe-job/result.json" in publish
    assert client.artifact_checks[-1] == "aletheia_worker/jobs/safe-job/result.json"
    assert client.downloads[0][0] == "aletheia_worker/jobs/safe-job/result.json"


def test_result_publication_failure_blocks_download_and_stops_studio(tmp_path: Path) -> None:
    client = FakeLightningClient(failure="publish")
    dispatcher, job = make_dispatcher(tmp_path, client), make_job(tmp_path)

    with pytest.raises(LightningDispatcherError):
        dispatcher.execute(job)

    diagnostics = json.loads((dispatcher.base_dir / job.job_id / "dispatch.json").read_text())["diagnostics"]
    assert client.stopped == 1 and not client.downloads
    assert diagnostics["stages"]["publish_remote_result"] == "FAILED"
    assert diagnostics["publication_exit_codes"] == [1]
    assert "bridge-token" not in diagnostics["publication_output_tail"]


def test_cleanup_failure_does_not_mask_remote_execution_failure(tmp_path: Path) -> None:
    client = FakeLightningClient(failure="run")
    client.stop = lambda: (_ for _ in ()).throw(RuntimeError("stop failure"))  # type: ignore[method-assign]

    with pytest.raises(LightningDispatcherError) as raised:
        make_dispatcher(tmp_path, client).execute(make_job(tmp_path))

    diagnostics = json.loads((tmp_path / "mystic_data" / "aletheia_lightning_jobs" / "safe-job" / "dispatch.json").read_text())["diagnostics"]
    assert isinstance(raised.value.__cause__, LightningDispatcherError)
    assert "Remote specialist execution failed." in str(raised.value.__cause__)
    assert diagnostics["stages"]["remote_execute"] == "FAILED"
    assert diagnostics["stages"]["studio_stop"] == "FAILED"
    assert diagnostics["cleanup_exception_type"] == "RuntimeError"


def test_remote_command_expands_home_path_without_quoting_the_tilde(tmp_path: Path) -> None:
    dispatcher = make_dispatcher(tmp_path, FakeLightningClient())
    command = dispatcher._remote_command(
        "~/aletheia_worker/jobs/safe-job",
        "~/aletheia_worker/jobs/safe-job/job.json",
        "~/aletheia_worker/jobs/safe-job/result.json",
        "~/aletheia_worker/jobs/safe-job/stdout.log",
        "~/aletheia_worker/jobs/safe-job/stderr.log",
    )
    assert "$HOME/aletheia_worker/" in command
    assert "'~/aletheia_worker'" not in command


@pytest.mark.parametrize("payload", [
    {"job_id": "other", "status": "SUCCEEDED", "results": []},
    {"job_id": "safe-job", "status": "FAILED", "results": []},
])
def test_mismatched_or_failed_remote_result_is_rejected(tmp_path: Path, payload: dict) -> None:
    with pytest.raises(LightningDispatcherError): make_dispatcher(tmp_path, FakeLightningClient(payload=payload)).execute(make_job(tmp_path))


def test_stop_failure_is_recorded_separately(tmp_path: Path) -> None:
    client = FakeLightningClient(failure="stop")
    result = make_dispatcher(tmp_path, client).execute(make_job(tmp_path))
    assert result.status == "SUCCEEDED" and result.shutdown_error and client.stopped == 1


def test_file_lease_blocks_concurrent_gpu_owner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeLightningClient(); dispatcher = make_dispatcher(tmp_path, client)
    from contextlib import contextmanager
    @contextmanager
    def occupied() -> object:
        raise LightningBusyError("occupied")
        yield
    monkeypatch.setattr(dispatcher, "_gpu_lease", occupied)
    with pytest.raises(LightningBusyError): dispatcher.execute(make_job(tmp_path))


@pytest.mark.parametrize("job_id", ["../escape", "unsafe/slash", "", "space value"])
def test_unsafe_job_ids_are_rejected(tmp_path: Path, job_id: str) -> None:
    with pytest.raises(ValueError): make_job(tmp_path, job_id)


def test_settings_fail_closed_without_credentials() -> None:
    with pytest.raises(LightningDispatcherError): LightningSettings.from_env({})


def test_settings_repr_redacts_secret() -> None:
    assert "super-secret-key" not in repr(LightningSettings("u", "super-secret-key", "o", "t", "s"))


@pytest.mark.parametrize(
    ("owner", "teamspace"),
    [
        ("dyrakd", "training-optimization-project"),
        ("personal-owner", "personal-teamspace"),
    ],
    ids=["organization-owned", "user-owned"],
)
def test_sdk_client_resolves_studio_with_generic_owner_teamspace_ref(
    monkeypatch: pytest.MonkeyPatch, owner: str, teamspace: str
) -> None:
    calls: list[tuple[str, object]] = []

    class FakeStudio:
        def __init__(self, *args: object, **kwargs: object) -> None:
            calls.append(("init", (args, kwargs)))

        def start(self, machine: object) -> None:
            calls.append(("start", machine))

    monkeypatch.setitem(sys.modules, "lightning_sdk", SimpleNamespace(Studio=FakeStudio, Machine=SimpleNamespace(T4="T4")))

    settings = LightningSettings("user", "secret", owner, teamspace, "existing-studio")
    LightningSDKClient(settings)

    assert settings.teamspace_ref == f"{owner}/{teamspace}"
    assert calls == [("init", ((), {"name": "existing-studio", "teamspace": f"{owner}/{teamspace}", "create_ok": False}))]


def test_sdk_client_passes_content_root_relative_transfer_path(monkeypatch: pytest.MonkeyPatch) -> None:
    uploads: list[tuple[str, str, bool]] = []

    class FakeStudio:
        def __init__(self, **kwargs: object) -> None:
            pass

        def upload_file(self, file_path: str, *, remote_path: str, progress_bar: bool) -> None:
            uploads.append((file_path, remote_path, progress_bar))

    monkeypatch.setitem(sys.modules, "lightning_sdk", SimpleNamespace(Studio=FakeStudio, Machine=SimpleNamespace(T4="T4")))
    client = LightningSDKClient(LightningSettings("user", "secret", "owner", "team", "existing-studio"))

    client.upload(Path("source.pdf"), "aletheia_worker/jobs/safe-job/inputs/0.pdf")

    assert uploads == [("source.pdf", "aletheia_worker/jobs/safe-job/inputs/0.pdf", False)]


def test_sdk_client_checks_the_content_root_relative_artifact_path(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, str]] = []

    class FakeArtifactApi:
        def get_path_info(self, **kwargs: str) -> dict[str, object]:
            calls.append(kwargs)
            return {"exists": True, "type": "file", "size": 12}

    class FakeStudio:
        def __init__(self, **kwargs: object) -> None:
            self.id = "studio-id"
            self._teamspace = SimpleNamespace(id="teamspace-id")
            self._studio_api = FakeArtifactApi()

    monkeypatch.setitem(sys.modules, "lightning_sdk", SimpleNamespace(Studio=FakeStudio, Machine=SimpleNamespace(T4="T4")))
    client = LightningSDKClient(LightningSettings("user", "secret", "owner", "team", "existing-studio"))

    assert client.artifact_exists("aletheia_worker/jobs/safe-job/job.json")
    assert calls == [{"studio_id": "studio-id", "teamspace_id": "teamspace-id", "path": "aletheia_worker/jobs/safe-job/job.json"}]


def test_router_requests_capability_not_provider(tmp_path: Path) -> None:
    client = FakeLightningClient(); dispatcher = make_dispatcher(tmp_path, client)
    router = SpecialistRouter({"scientific.pdf_retrieval": dispatcher})
    assert router.execute(capability="scientific.pdf_retrieval", request=make_job(tmp_path)).status == "SUCCEEDED"
    with pytest.raises(ValueError): router.execute(capability="provider.lightning", request=make_job(tmp_path, "another-job"))


def test_durable_adapter_preserves_unproven_evidence(tmp_path: Path) -> None:
    adapter = LightningScientificJobAdapter(make_dispatcher(tmp_path, FakeLightningClient()))
    request = adapter.prepare_request(campaign_id="campaign-1", campaign_revision=0, input_payload={"job_id": "safe-job", "query": "Where?", "pdf_paths": [str(make_job(tmp_path).pdf_paths[0])]}, correlation_id="safe-job")
    assert request.job_type == "lightning_specialist_execution" and request.engine_name == adapter.engine_name


@pytest.mark.skipif(not all(__import__("os").environ.get(key) for key in ("LIGHTNING_USER_ID", "LIGHTNING_API_KEY", "LIGHTNING_OWNER", "LIGHTNING_TEAMSPACE", "LIGHTNING_STUDIO_NAME", "ALETHEIA_LIGHTNING_ACCEPTANCE_PDF")), reason="opt-in Lightning credentials and controlled PDF are not configured")
def test_real_lightning_acceptance_is_opt_in() -> None:
    from mystic.specialist_dispatcher import LightningSDKClient
    import os
    root = Path(os.environ.get("ALETHEIA_LIGHTNING_ACCEPTANCE_ROOT", "."))
    result = LightningDispatcher(root_path=root, settings=LightningSettings.from_env(), client_factory=LightningSDKClient).execute(
        SpecialistJob("lightning-acceptance-pytest", os.environ.get("ALETHEIA_LIGHTNING_ACCEPTANCE_QUERY", "Which page explains gravitational lensing?"), (Path(os.environ["ALETHEIA_LIGHTNING_ACCEPTANCE_PDF"]),))
    )
    assert result.status == "SUCCEEDED"
