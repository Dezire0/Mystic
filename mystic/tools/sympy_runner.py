"""SymPy runner placeholder."""

from __future__ import annotations


class SymPyRunner:
    def available(self) -> bool:
        try:
            import sympy  # noqa: F401
        except ImportError:
            return False
        return True

