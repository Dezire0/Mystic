from __future__ import annotations

import os
from pathlib import Path


def load_dotenv_file(path: str | Path, *, override: bool = False) -> dict[str, str]:
    target = Path(path)
    loaded: dict[str, str] = {}
    if not target.exists():
        return loaded
    for raw_line in target.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env_key = key.strip()
        env_value = value.strip().strip('"').strip("'")
        if not env_key:
            continue
        if override or env_key not in os.environ:
            os.environ[env_key] = env_value
            loaded[env_key] = env_value
    return loaded
