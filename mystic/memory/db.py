"""Database wrapper."""

from __future__ import annotations

from contextlib import contextmanager
import sqlite3
from pathlib import Path

from mystic.memory.schema import SCHEMA_STATEMENTS


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def session(self):
        connection = self.connect()
        try:
            yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.session() as connection:
            for statement in SCHEMA_STATEMENTS:
                connection.execute(statement)
            connection.commit()
