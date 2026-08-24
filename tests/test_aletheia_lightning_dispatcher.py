from __future__ import annotations

import json
from pathlib import Path

import pytest

from mystic.specialist_dispatcher import (
    LightningBusyError,
    LightningDispatcher,
    LightningDispatcherError,
    LightningSettings,
    LightningScientificJobAdapter,
    SpecialistRouter,
    SpecialistJob,
)


class FakeLightningClient:
    def __init__(self, *, failure: str = "", payload: dict | None = None) -> None:
        self.failure, self.payload = failure, payload or {
            "job_id": "safe-job", "task": "pdf_retrieval", "status": "SUCCEEDED", "runtime_seconds": 4.2,
            "gpu": {"available": True, "name": "Tesla T4"},
            "results": [{"page": 1, "pdf": "~/aletheia_worker/jobs/safe-job/inputs/0.pdf", "preview": "lens evidence", "text_score": 0.9, "visual_score": 0.8, "fusion_score": 0.7, "rerank_score": 0.6}],
        }
        self.started = self.stopped = 0; self.uploads: list[tuple[str, str]] = []; self.commands: list[str] = []

    def start_t4(self) -> None:
        self.started += 1
        if self.failure == "start": raise RuntimeError("start failure")
    def stop(self) -> None:
        self.stopped += 1
        if self.failure == "stop": raise RuntimeError("stop failure")
    def upload(self, local_path: Path, remote_path: str) -> None:
        self.uploads.append((str(local_path), remote_path))
        if self.failure == "upload": raise RuntimeError("upload failure")
    def run(self, command: str) -> tuple[str, int]:
        self.commands.append(command)
        if self.failure in {"run", "timeout"} and "aletheia_job.py" in command: return "", 124 if self.failure == "timeout" else 1
        return "", 0
    def download(self, remote_path: str, local_path: Path) -> None:
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
