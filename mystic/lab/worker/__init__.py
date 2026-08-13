"""Trusted execution service for the durable ScientificJob runtime.

This package intentionally exposes no MCP tools.  It is a process-private
service boundary over the Phase 2C.2A runtime, not an autonomous scientist or
an engine plugin framework.
"""

from .auth import WorkerCredentialError, WorkerCredentialVerifier
from .config import ScientificWorkerConfig
from .health import WorkerState
from .service import ScientificJobWorkerService

__all__ = [
    "ScientificJobWorkerService",
    "ScientificWorkerConfig",
    "WorkerCredentialError",
    "WorkerCredentialVerifier",
    "WorkerState",
]
