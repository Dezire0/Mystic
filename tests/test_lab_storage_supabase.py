from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mystic.mcp.tools import MysticToolbox
from mystic.models.router import ModelRouter


TEST_CONFIG = """
models:
  local_prime:
    provider: mock
    model: mock-prime
    role_defaults:
      - draft
  local_raven:
    provider: mock
    model: mock-raven
    role_defaults:
      - critique
policy:
  max_models_per_compare: 3
  timeout_per_model_seconds: 5
"""


class _FakeResponse:
    def __init__(self, status_code: int, payload: object | None = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = "" if payload is None else json.dumps(payload)

    def json(self) -> object:
        if self._payload is None:
            raise ValueError("No JSON payload")
        return self._payload


class _FakeSupabaseAPI:
    PRIMARY_KEYS = {
        "lab_sessions": "session_id",
        "lab_turns": "turn_id",
        "claims": "claim_id",
        "failures": "failure_id",
        "memory_edges": "edge_id",
        "reports": "session_id",
    }

    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, object]]] = {name: [] for name in self.PRIMARY_KEYS}

    def request(  # type: ignore[no-untyped-def]
        self,
        method,
        url,
        params=None,
        json=None,
        headers=None,
        timeout=None,
    ):
        table = str(url).split("/rest/v1/", 1)[1]
        params = params or {}
        method = str(method).upper()
        if method == "GET":
            rows = self._select(table, params)
            return _FakeResponse(200, rows)
        if method == "DELETE":
            self._delete(table, params)
            return _FakeResponse(204, None)
        if method == "POST":
            rows = json if isinstance(json, list) else [json]
            if "on_conflict" in params:
                self._upsert(table, rows)
            else:
                self._insert(table, rows)
            return _FakeResponse(201, rows)
        raise AssertionError(f"Unsupported method: {method}")

    def _select(self, table: str, params: dict[str, str]) -> list[dict[str, object]]:
        rows = [dict(row) for row in self.tables[table]]
        for key, value in params.items():
            if key in {"select", "order", "on_conflict"}:
                continue
            if isinstance(value, str) and value.startswith("eq."):
                expected = value[3:]
                rows = [row for row in rows if str(row.get(key, "")) == expected]
        order = params.get("order")
        if isinstance(order, str) and order:
            field_name, _, direction = order.partition(".")
            rows.sort(key=lambda row: str(row.get(field_name, "")), reverse=direction.lower() == "desc")
        selected = params.get("select", "*")
        if selected != "*" and isinstance(selected, str):
            requested = [item.strip() for item in selected.split(",") if item.strip()]
            rows = [{key: row.get(key) for key in requested} for row in rows]
        return rows

    def _delete(self, table: str, params: dict[str, str]) -> None:
        remaining = self.tables[table]
        for key, value in params.items():
            if isinstance(value, str) and value.startswith("eq."):
                expected = value[3:]
                remaining = [row for row in remaining if str(row.get(key, "")) != expected]
        self.tables[table] = remaining

    def _insert(self, table: str, rows: list[dict[str, object]]) -> None:
        self.tables[table].extend(dict(row) for row in rows)

    def _upsert(self, table: str, rows: list[dict[str, object]]) -> None:
        key_name = self.PRIMARY_KEYS[table]
        existing = {str(row.get(key_name, "")): dict(row) for row in self.tables[table]}
        for row in rows:
            existing[str(row.get(key_name, ""))] = dict(row)
        self.tables[table] = list(existing.values())


class SupabaseLabStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.config_path = self.root / "models.yaml"
        self.config_path.write_text(TEST_CONFIG, encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_supabase_backed_session_round_trip_and_report_generation(self):
        fake_api = _FakeSupabaseAPI()
        with patch.dict(
            os.environ,
            {
                "MYSTIC_STORAGE_BACKEND": "supabase",
                "MYSTIC_SUPABASE_URL": "https://example.supabase.co",
                "MYSTIC_SUPABASE_SERVICE_ROLE_KEY": "service-role-key",
            },
            clear=False,
        ), patch("mystic.lab.storage.requests.request", side_effect=fake_api.request):
            router = ModelRouter(root_path=self.root, config_path=self.config_path)
            toolbox = MysticToolbox(root_path=self.root, router=router)
            created = toolbox.lab_session_create(
                problem="Find positive integers x, y such that x + y = 5.",
                domain="math",
                goal="Store a session in Supabase.",
                mode="cheap",
                participants=["local_prime", "local_raven"],
            )
            loaded = toolbox.lab_session_get(session_id=created["session_id"])
            report = toolbox.lab_report_generate(
                session_id=created["session_id"],
                format="markdown",
                include_failures=True,
                include_next_actions=True,
            )

        self.assertTrue(created["paths"]["session"].startswith("supabase://public/lab_sessions/"))
        self.assertEqual(loaded["session"]["session_id"], created["session_id"])
        self.assertTrue(loaded["notebook_path"].startswith("supabase://public/lab_sessions/"))
        self.assertTrue(report["report_path"].startswith("supabase://public/reports/"))
        self.assertIn(created["session_id"], report["markdown"])
        self.assertEqual(len(fake_api.tables["lab_sessions"]), 1)
        self.assertEqual(len(fake_api.tables["reports"]), 1)


if __name__ == "__main__":
    unittest.main()
