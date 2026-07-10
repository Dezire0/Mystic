from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mystic_gemini_cli_bridge import SELF_TEST_PROMPT, run_bridge


def main() -> int:
    result = run_bridge(SELF_TEST_PROMPT)
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result["status"] == "ok" and SELF_TEST_PROMPT in result["output"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
