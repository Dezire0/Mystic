from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystic.mcp.server import MysticMCPServer


def main() -> int:
    return MysticMCPServer().serve_stdio()


if __name__ == "__main__":
    raise SystemExit(main())
