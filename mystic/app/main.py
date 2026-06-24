"""ASGI app entrypoint."""

from __future__ import annotations

from mystic.app.api import create_app

try:  # pragma: no cover
    app = create_app()
except RuntimeError:  # pragma: no cover
    app = None

