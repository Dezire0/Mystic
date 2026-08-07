from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import fcntl
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Iterator

from mystic.lab.campaign import (
    CampaignConflictError,
    CampaignIntegrityError,
    CampaignNotFoundError,
    Checkpoint,
    ResearchCampaign,
)


_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,159}$")


class CampaignStorage:
    """Atomic local campaign persistence with cross-process optimistic locking."""

    backend_name = "local_json"

    def __init__(self, root_path: str | Path) -> None:
        self.root_path = Path(root_path)
        self.base_dir = self.root_path / "mystic_data" / "research_campaigns"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def validate_id(identifier: str) -> str:
        value = str(identifier)
        if not _SAFE_ID.fullmatch(value):
            raise ValueError("Campaign identifiers must be opaque safe identifiers")
        return value

    def campaign_dir(self, campaign_id: str) -> Path:
        return self.base_dir / self.validate_id(campaign_id)

    def campaign_path(self, campaign_id: str) -> Path:
        return self.campaign_dir(campaign_id) / "campaign.json"

    def checkpoint_path(self, campaign_id: str, checkpoint_id: str) -> Path:
        return self.campaign_dir(campaign_id) / "checkpoints" / f"{self.validate_id(checkpoint_id)}.json"

    @contextmanager
    def _locked(self, campaign_id: str) -> Iterator[None]:
        directory = self.campaign_dir(campaign_id)
        directory.mkdir(parents=True, exist_ok=True)
        lock_path = directory / ".lock"
        with lock_path.open("a+", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def create(self, campaign: ResearchCampaign) -> ResearchCampaign:
        with self._locked(campaign.campaign_id):
            if self.campaign_path(campaign.campaign_id).exists():
                raise CampaignConflictError(f"Campaign already exists: {campaign.campaign_id}")
            # Write referenced checkpoints first so a visible campaign aggregate
            # can never point at a missing initial recovery snapshot.
            for checkpoint in campaign.checkpoints:
                self._write_checkpoint(checkpoint)
            self._write_campaign(campaign)
        return campaign

    def save(self, campaign: ResearchCampaign, *, expected_revision: int) -> ResearchCampaign:
        with self._locked(campaign.campaign_id):
            current = self._load_unlocked(campaign.campaign_id)
            if current.revision != expected_revision:
                raise CampaignConflictError(
                    f"Campaign revision conflict: expected {expected_revision}, found {current.revision}"
                )
            if campaign.revision != expected_revision + 1:
                raise CampaignConflictError("Campaign mutations must increment revision exactly once")
            self._write_campaign(campaign)
        return campaign

    def load(self, campaign_id: str) -> ResearchCampaign:
        return self._load_unlocked(campaign_id)

    def _load_unlocked(self, campaign_id: str) -> ResearchCampaign:
        path = self.campaign_path(campaign_id)
        if not path.exists():
            raise CampaignNotFoundError(f"Campaign not found: {campaign_id}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise CampaignIntegrityError(f"Campaign state is unreadable: {campaign_id}") from exc
        if not isinstance(payload, dict):
            raise CampaignIntegrityError(f"Campaign state is invalid: {campaign_id}")
        return ResearchCampaign.from_dict(payload)

    def list(self, *, limit: int = 50, status: str | None = None) -> list[ResearchCampaign]:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        campaigns: list[ResearchCampaign] = []
        for path in sorted(self.base_dir.glob("*/campaign.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                campaign = ResearchCampaign.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (CampaignIntegrityError, json.JSONDecodeError, OSError, TypeError, ValueError):
                continue
            if status and campaign.status.value != status:
                continue
            campaigns.append(campaign)
            if len(campaigns) >= limit:
                break
        return campaigns

    def save_checkpoint(self, checkpoint: Checkpoint) -> Path:
        checkpoint.verify()
        return self._write_checkpoint(checkpoint)

    def _write_checkpoint(self, checkpoint: Checkpoint) -> Path:
        path = self.checkpoint_path(checkpoint.campaign_id, checkpoint.checkpoint_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write(path, asdict(checkpoint))
        return path

    def load_checkpoint(self, campaign_id: str, checkpoint_id: str) -> Checkpoint:
        path = self.checkpoint_path(campaign_id, checkpoint_id)
        if not path.exists():
            raise CampaignNotFoundError(f"Checkpoint not found: {checkpoint_id}")
        try:
            checkpoint = Checkpoint(**json.loads(path.read_text(encoding="utf-8")))
            checkpoint.verify()
        except (json.JSONDecodeError, OSError, TypeError, CampaignIntegrityError) as exc:
            raise CampaignIntegrityError(f"Checkpoint is invalid: {checkpoint_id}") from exc
        return checkpoint

    def _write_campaign(self, campaign: ResearchCampaign) -> None:
        self._atomic_write(self.campaign_path(campaign.campaign_id), campaign.to_dict())

    @staticmethod
    def _atomic_write(path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
        fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if temporary.exists():
                temporary.unlink()

    def describe_status(self) -> dict[str, object]:
        return {
            "backend": self.backend_name,
            "configured": True,
            "write_capable": True,
            "storage_root": str(self.base_dir),
            "integrity_algorithm": "sha256",
        }
