from __future__ import annotations

from mystic.core.orchestrator import MysticOrchestrator


def main() -> None:
    orchestrator = MysticOrchestrator()
    for path in orchestrator.export_dataset("all"):
        print(path)


if __name__ == "__main__":
    main()

