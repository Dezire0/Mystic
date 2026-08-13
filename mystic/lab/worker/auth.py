from __future__ import annotations

import hashlib
import hmac
import re
from typing import Iterable


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class WorkerCredentialError(PermissionError):
    """Raised when a process is not provisioned as a trusted job worker."""


class WorkerCredentialVerifier:
    """Verifies a dedicated worker bootstrap credential in constant time.

    The verifier is deliberately independent from MCP OAuth, console sessions,
    runner tokens, and provider credentials.  Multiple hashes permit overlap
    during rotation; removing a digest is immediate revocation.  It only
    answers an authentication decision and never retains or renders plaintext
    credentials.
    """

    def __init__(self, credential_hashes: Iterable[str]) -> None:
        hashes = tuple(credential_hashes)
        if not hashes:
            raise ValueError("At least one worker credential verifier is required")
        if any(not isinstance(value, str) or not _SHA256.fullmatch(value) for value in hashes):
            raise ValueError("Worker credential verifiers must be SHA-256 hex digests")
        self._credential_hashes = hashes

    @classmethod
    def from_secret(cls, credential: str) -> "WorkerCredentialVerifier":
        if not isinstance(credential, str) or not credential:
            raise ValueError("Worker credential must be non-empty")
        return cls((hashlib.sha256(credential.encode("utf-8")).hexdigest(),))

    @classmethod
    def from_environment_value(cls, value: str) -> "WorkerCredentialVerifier":
        digests = tuple(part.strip() for part in value.split(",") if part.strip())
        return cls(digests)

    def verify(self, credential: str) -> bool:
        if not isinstance(credential, str) or not credential:
            return False
        supplied = hashlib.sha256(credential.encode("utf-8")).hexdigest()
        # Do not short-circuit: all configured verifiers take the same path.
        accepted = False
        for expected in self._credential_hashes:
            accepted = hmac.compare_digest(expected, supplied) or accepted
        return accepted

    def require(self, credential: str) -> None:
        if not self.verify(credential):
            raise WorkerCredentialError("Scientific worker authentication was rejected")

    def safe_metadata(self) -> dict[str, object]:
        return {
            "credential_verifier_count": len(self._credential_hashes),
            "rotation_supported": len(self._credential_hashes) > 1,
            "credential_material_exposed": False,
        }
