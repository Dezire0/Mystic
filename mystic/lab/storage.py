from __future__ import annotations

from dataclasses import fields
import json
import os
from pathlib import Path
from typing import Any

import requests

from mystic.lab.reports import render_report
from mystic.lab.scene import LabScene, LabSceneBundle, LabSceneObject, LabSimulation
from mystic.lab.schema import PHASE_TO_ROOM
from mystic.lab.session import Claim, Experiment, Failure, LabSession, LabSessionBundle, LabTurn, MemoryEdge


DEFAULT_SUPABASE_SCHEMA = "public"
ARTIFACT_NAMES = (
    "session",
    "turns",
    "claims",
    "experiments",
    "failures",
    "memory_edges",
    "notebook",
    "report",
)

SCENE_ARTIFACT_NAMES = (
    "scene",
    "objects",
    "simulations",
    "report",
    "snapshot",
)


def _session_field_names() -> set[str]:
    return {field.name for field in fields(LabSession)}


LAB_SESSION_FIELD_NAMES = _session_field_names()


def _scene_field_names() -> set[str]:
    return {field.name for field in fields(LabScene)}


LAB_SCENE_FIELD_NAMES = _scene_field_names()


class LocalJSONLabStorage:
    backend_name = "local"

    def __init__(self, root_path: str | Path) -> None:
        self.root_path = Path(root_path)
        self.base_dir = self.root_path / "mystic_data" / "lab_sessions"
        self.scenes_base_dir = self.root_path / "mystic_data" / "lab_scenes"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.scenes_base_dir.mkdir(parents=True, exist_ok=True)

    def session_dir(self, session_id: str) -> Path:
        return self.base_dir / session_id

    def save_bundle(self, bundle: LabSessionBundle) -> dict[str, str]:
        session_dir = self.session_dir(bundle.session.session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "artifacts").mkdir(exist_ok=True)
        (session_dir / "summaries").mkdir(exist_ok=True)

        paths = {
            "session": session_dir / "session.json",
            "turns": session_dir / "turns.json",
            "claims": session_dir / "claims.json",
            "experiments": session_dir / "experiments.json",
            "failures": session_dir / "failures.json",
            "memory_edges": session_dir / "memory_edges.json",
            "notebook": session_dir / "notebook.md",
            "report": session_dir / "report.md",
        }
        bundle.session.artifact_paths = {name: str(path) for name, path in paths.items()}
        bundle.session.active_room = PHASE_TO_ROOM.get(bundle.session.current_phase, bundle.session.active_room)

        paths["session"].write_text(json.dumps(bundle.session.to_dict(), indent=2), encoding="utf-8")
        paths["turns"].write_text(json.dumps([item.to_dict() for item in bundle.turns], indent=2), encoding="utf-8")
        paths["claims"].write_text(json.dumps([item.to_dict() for item in bundle.claims], indent=2), encoding="utf-8")
        paths["experiments"].write_text(
            json.dumps([item.to_dict() for item in bundle.experiments], indent=2), encoding="utf-8"
        )
        paths["failures"].write_text(json.dumps([item.to_dict() for item in bundle.failures], indent=2), encoding="utf-8")
        paths["memory_edges"].write_text(
            json.dumps([item.to_dict() for item in bundle.memory_edges], indent=2), encoding="utf-8"
        )
        paths["notebook"].write_text(bundle.notebook_markdown or "", encoding="utf-8")
        paths["report"].write_text(bundle.report_markdown or "", encoding="utf-8")
        return {name: str(path) for name, path in paths.items()}

    def load_bundle(self, session_id: str) -> LabSessionBundle:
        session_dir = self.session_dir(session_id)
        session_payload = self._load_json(session_dir / "session.json")
        if not isinstance(session_payload, dict):
            raise FileNotFoundError(session_dir / "session.json")
        return LabSessionBundle(
            session=LabSession(**session_payload),
            turns=[LabTurn(**payload) for payload in self._load_json(session_dir / "turns.json", [])],
            claims=[Claim(**payload) for payload in self._load_json(session_dir / "claims.json", [])],
            experiments=[Experiment(**payload) for payload in self._load_json(session_dir / "experiments.json", [])],
            failures=[Failure(**payload) for payload in self._load_json(session_dir / "failures.json", [])],
            memory_edges=[MemoryEdge(**payload) for payload in self._load_json(session_dir / "memory_edges.json", [])],
            notebook_markdown=(session_dir / "notebook.md").read_text(encoding="utf-8")
            if (session_dir / "notebook.md").exists()
            else "",
            report_markdown=(session_dir / "report.md").read_text(encoding="utf-8")
            if (session_dir / "report.md").exists()
            else "",
        )

    def list_session_ids(self) -> list[str]:
        if not self.base_dir.exists():
            return []
        return [path.name for path in sorted(self.base_dir.iterdir(), reverse=True) if path.is_dir()]

    def scene_dir(self, scene_id: str) -> Path:
        return self.scenes_base_dir / scene_id

    def save_scene(self, scene_bundle: LabSceneBundle) -> dict[str, str]:
        scene_dir = self.scene_dir(scene_bundle.scene.scene_id)
        scene_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "scene": scene_dir / "scene.json",
            "objects": scene_dir / "objects.json",
            "simulations": scene_dir / "simulations.json",
            "report": scene_dir / "report.md",
            "snapshot": scene_dir / "exports.json",
        }
        scene_bundle.scene.artifact_paths = {name: str(path) for name, path in paths.items()}
        paths["scene"].write_text(json.dumps(scene_bundle.scene.to_dict(), indent=2), encoding="utf-8")
        paths["objects"].write_text(json.dumps([item.to_dict() for item in scene_bundle.objects], indent=2), encoding="utf-8")
        paths["simulations"].write_text(
            json.dumps([item.to_dict() for item in scene_bundle.simulations], indent=2), encoding="utf-8"
        )
        paths["report"].write_text(scene_bundle.scene.report_markdown or "", encoding="utf-8")
        paths["snapshot"].write_text(json.dumps(scene_bundle.scene.exports_json, indent=2), encoding="utf-8")
        return {name: str(path) for name, path in paths.items()}

    def load_scene(self, scene_id: str) -> LabSceneBundle:
        scene_dir = self.scene_dir(scene_id)
        scene_payload = self._load_json(scene_dir / "scene.json")
        if not isinstance(scene_payload, dict):
            raise FileNotFoundError(scene_dir / "scene.json")
        scene = LabScene(**scene_payload)
        if (scene_dir / "report.md").exists():
            scene.report_markdown = (scene_dir / "report.md").read_text(encoding="utf-8")
        if (scene_dir / "exports.json").exists():
            scene.exports_json = self._load_json(scene_dir / "exports.json", {})
        return LabSceneBundle(
            scene=scene,
            objects=[LabSceneObject(**payload) for payload in self._load_json(scene_dir / "objects.json", [])],
            simulations=[LabSimulation(**payload) for payload in self._load_json(scene_dir / "simulations.json", [])],
        )

    def list_scene_ids(self, session_id: str | None = None) -> list[str]:
        if not self.scenes_base_dir.exists():
            return []
        scene_ids = [path.name for path in sorted(self.scenes_base_dir.iterdir(), reverse=True) if path.is_dir()]
        if not session_id:
            return scene_ids
        matched: list[str] = []
        for scene_id in scene_ids:
            try:
                scene = self.load_scene(scene_id).scene
            except Exception:
                continue
            if scene.session_id == session_id:
                matched.append(scene_id)
        return matched

    def describe_status(self) -> dict[str, Any]:
        return {
            "backend": self.backend_name,
            "configured": True,
            "write_capable": True,
            "storage_root": str(self.base_dir),
            "storage_root_uri": str(self.base_dir),
            "schema": "",
            "project_url": "",
            "missing_env": [],
        }

    @staticmethod
    def _load_json(path: Path, default: Any | None = None) -> Any:
        if not path.exists():
            return [] if default is None else default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return [] if default is None else default


class SupabaseLabStorage:
    backend_name = "supabase"

    def __init__(
        self,
        root_path: str | Path,
        *,
        supabase_url: str | None = None,
        service_role_key: str | None = None,
        schema: str | None = None,
    ) -> None:
        self.root_path = Path(root_path)
        self.base_dir: Path | None = None
        self.supabase_url = self._normalize_base_url(supabase_url or os.getenv("MYSTIC_SUPABASE_URL", ""))
        self.service_role_key = str(service_role_key or os.getenv("MYSTIC_SUPABASE_SERVICE_ROLE_KEY", "")).strip()
        self.schema = str(schema or os.getenv("MYSTIC_SUPABASE_SCHEMA", DEFAULT_SUPABASE_SCHEMA)).strip() or DEFAULT_SUPABASE_SCHEMA

    def save_bundle(self, bundle: LabSessionBundle) -> dict[str, str]:
        self._ensure_configured()
        paths = self._artifact_paths(bundle.session.session_id)
        bundle.session.artifact_paths = paths
        bundle.session.active_room = PHASE_TO_ROOM.get(bundle.session.current_phase, bundle.session.active_room)

        session_row = bundle.session.to_dict()
        session_row["notebook_markdown"] = bundle.notebook_markdown or ""
        session_row["experiments_json"] = [item.to_dict() for item in bundle.experiments]
        self._upsert_rows("lab_sessions", [session_row], on_conflict="session_id")

        self._replace_session_rows("lab_turns", bundle.session.session_id, [item.to_dict() for item in bundle.turns], key_name="turn_id")
        self._replace_session_rows("claims", bundle.session.session_id, [item.to_dict() for item in bundle.claims], key_name="claim_id")
        self._replace_session_rows(
            "failures",
            bundle.session.session_id,
            [item.to_dict() for item in bundle.failures],
            key_name="failure_id",
        )
        self._replace_session_rows(
            "memory_edges",
            bundle.session.session_id,
            [item.to_dict() for item in bundle.memory_edges],
            key_name="edge_id",
        )

        if bundle.report_markdown:
            report = render_report(bundle).to_dict()
            report["markdown"] = bundle.report_markdown
            self._upsert_rows("reports", [report], on_conflict="session_id")
        else:
            self._delete_rows("reports", {"session_id": f"eq.{bundle.session.session_id}"})

        return paths

    def load_bundle(self, session_id: str) -> LabSessionBundle:
        self._ensure_configured()
        session_row = self._select_one("lab_sessions", {"session_id": f"eq.{session_id}"})
        if session_row is None:
            raise FileNotFoundError(session_id)

        session_payload = {
            key: session_row[key]
            for key in LAB_SESSION_FIELD_NAMES
            if key in session_row
        }
        experiments_payload = session_row.get("experiments_json", [])
        report_row = self._select_one("reports", {"session_id": f"eq.{session_id}"}) or {}
        return LabSessionBundle(
            session=LabSession(**session_payload),
            turns=[LabTurn(**payload) for payload in self._select_rows("lab_turns", {"session_id": f"eq.{session_id}"}, order="created_at.asc")],
            claims=[Claim(**payload) for payload in self._select_rows("claims", {"session_id": f"eq.{session_id}"}, order="created_at.asc")],
            experiments=[Experiment(**payload) for payload in self._coerce_list(experiments_payload)],
            failures=[Failure(**payload) for payload in self._select_rows("failures", {"session_id": f"eq.{session_id}"}, order="created_at.asc")],
            memory_edges=[
                MemoryEdge(**payload)
                for payload in self._select_rows("memory_edges", {"session_id": f"eq.{session_id}"}, order="created_at.asc")
            ],
            notebook_markdown=str(session_row.get("notebook_markdown", "")),
            report_markdown=str(report_row.get("markdown", "")),
        )

    def list_session_ids(self) -> list[str]:
        self._ensure_configured()
        rows = self._select_rows("lab_sessions", {}, order="updated_at.desc", columns="session_id")
        return [str(row.get("session_id", "")).strip() for row in rows if str(row.get("session_id", "")).strip()]

    def save_scene(self, scene_bundle: LabSceneBundle) -> dict[str, str]:
        self._ensure_configured()
        scene_bundle.scene.artifact_paths = self._scene_artifact_paths(scene_bundle.scene.scene_id)
        self._upsert_rows("lab_scenes", [scene_bundle.scene.to_dict()], on_conflict="scene_id")
        self._replace_scene_rows(
            "lab_scene_objects",
            scene_bundle.scene.scene_id,
            [item.to_dict() for item in scene_bundle.objects],
            key_name="id",
        )
        self._replace_scene_rows(
            "lab_simulations",
            scene_bundle.scene.scene_id,
            [item.to_dict() for item in scene_bundle.simulations],
            key_name="simulation_id",
        )
        return scene_bundle.scene.artifact_paths

    def load_scene(self, scene_id: str) -> LabSceneBundle:
        self._ensure_configured()
        scene_row = self._select_one("lab_scenes", {"scene_id": f"eq.{scene_id}"})
        if scene_row is None:
            raise FileNotFoundError(scene_id)
        scene_payload = {
            key: scene_row[key]
            for key in LAB_SCENE_FIELD_NAMES
            if key in scene_row
        }
        return LabSceneBundle(
            scene=LabScene(**scene_payload),
            objects=[
                LabSceneObject(**payload)
                for payload in self._select_rows("lab_scene_objects", {"scene_id": f"eq.{scene_id}"}, order="created_at.asc")
            ],
            simulations=[
                LabSimulation(**payload)
                for payload in self._select_rows("lab_simulations", {"scene_id": f"eq.{scene_id}"}, order="created_at.asc")
            ],
        )

    def list_scene_ids(self, session_id: str | None = None) -> list[str]:
        self._ensure_configured()
        filters: dict[str, str] = {}
        if session_id:
            filters["session_id"] = f"eq.{session_id}"
        rows = self._select_rows("lab_scenes", filters, order="updated_at.desc", columns="scene_id")
        return [str(row.get("scene_id", "")).strip() for row in rows if str(row.get("scene_id", "")).strip()]

    def describe_status(self) -> dict[str, Any]:
        missing_env = []
        if not self.supabase_url:
            missing_env.append("MYSTIC_SUPABASE_URL")
        if not self.service_role_key:
            missing_env.append("MYSTIC_SUPABASE_SERVICE_ROLE_KEY")
        return {
            "backend": self.backend_name,
            "configured": not missing_env,
            "write_capable": not missing_env,
            "storage_root": f"supabase://{self.schema}/lab_sessions",
            "storage_root_uri": f"supabase://{self.schema}/lab_sessions",
            "schema": self.schema,
            "project_url": self.supabase_url,
            "missing_env": missing_env,
        }

    def _ensure_configured(self) -> None:
        status = self.describe_status()
        if status["configured"]:
            return
        missing = ", ".join(status["missing_env"])
        raise RuntimeError(f"Supabase lab storage is not configured: missing {missing}")

    def _artifact_paths(self, session_id: str) -> dict[str, str]:
        return {
            "session": f"supabase://{self.schema}/lab_sessions/{session_id}",
            "turns": f"supabase://{self.schema}/lab_turns?session_id={session_id}",
            "claims": f"supabase://{self.schema}/claims?session_id={session_id}",
            "experiments": f"supabase://{self.schema}/lab_sessions/{session_id}#experiments",
            "failures": f"supabase://{self.schema}/failures?session_id={session_id}",
            "memory_edges": f"supabase://{self.schema}/memory_edges?session_id={session_id}",
            "notebook": f"supabase://{self.schema}/lab_sessions/{session_id}#notebook",
            "report": f"supabase://{self.schema}/reports/{session_id}",
        }

    def _scene_artifact_paths(self, scene_id: str) -> dict[str, str]:
        return {
            "scene": f"supabase://{self.schema}/lab_scenes/{scene_id}",
            "objects": f"supabase://{self.schema}/lab_scene_objects?scene_id={scene_id}",
            "simulations": f"supabase://{self.schema}/lab_simulations?scene_id={scene_id}",
            "report": f"supabase://{self.schema}/lab_scenes/{scene_id}#report",
            "snapshot": f"supabase://{self.schema}/lab_scenes/{scene_id}#exports",
        }

    def _replace_session_rows(
        self,
        table: str,
        session_id: str,
        rows: list[dict[str, Any]],
        *,
        key_name: str,
    ) -> None:
        self._delete_rows(table, {"session_id": f"eq.{session_id}"})
        if not rows:
            return
        payload = []
        for row in rows:
            item = dict(row)
            item.setdefault("session_id", session_id)
            if key_name not in item:
                raise ValueError(f"{table} row missing key {key_name}")
            payload.append(item)
        self._insert_rows(table, payload)

    def _replace_scene_rows(
        self,
        table: str,
        scene_id: str,
        rows: list[dict[str, Any]],
        *,
        key_name: str,
    ) -> None:
        self._delete_rows(table, {"scene_id": f"eq.{scene_id}"})
        if not rows:
            return
        payload = []
        for row in rows:
            item = dict(row)
            item.setdefault("scene_id", scene_id)
            if key_name not in item:
                raise ValueError(f"{table} row missing key {key_name}")
            payload.append(item)
        self._insert_rows(table, payload)

    def _select_one(self, table: str, filters: dict[str, str]) -> dict[str, Any] | None:
        rows = self._select_rows(table, filters)
        return rows[0] if rows else None

    def _select_rows(
        self,
        table: str,
        filters: dict[str, str],
        *,
        order: str | None = None,
        columns: str = "*",
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {"select": columns}
        params.update(filters)
        if order:
            params["order"] = order
        payload = self._request_json("GET", table, params=params)
        return payload if isinstance(payload, list) else []

    def _delete_rows(self, table: str, filters: dict[str, str]) -> None:
        self._request_json("DELETE", table, params=filters, prefer="return=minimal")

    def _insert_rows(self, table: str, rows: list[dict[str, Any]]) -> None:
        self._request_json("POST", table, json_payload=rows, prefer="return=representation")

    def _upsert_rows(self, table: str, rows: list[dict[str, Any]], *, on_conflict: str) -> None:
        self._request_json(
            "POST",
            table,
            params={"on_conflict": on_conflict},
            json_payload=rows,
            prefer="resolution=merge-duplicates,return=representation",
        )

    def _request_json(
        self,
        method: str,
        table: str,
        *,
        params: dict[str, str] | None = None,
        json_payload: Any | None = None,
        prefer: str | None = None,
    ) -> Any:
        headers = {
            "Accept": "application/json",
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
        }
        if json_payload is not None:
            headers["Content-Type"] = "application/json"
        if self.schema and self.schema != DEFAULT_SUPABASE_SCHEMA:
            headers["Accept-Profile"] = self.schema
            headers["Content-Profile"] = self.schema
        if prefer:
            headers["Prefer"] = prefer
        response = requests.request(
            method=method,
            url=f"{self.supabase_url}/rest/v1/{table}",
            params=params,
            json=json_payload,
            headers=headers,
            timeout=30,
        )
        if response.status_code >= 400:
            message = response.text.strip()
            raise RuntimeError(f"Supabase {method} {table} failed with {response.status_code}: {message[:400]}")
        if not response.text.strip():
            return None
        return response.json()

    @staticmethod
    def _normalize_base_url(value: str) -> str:
        return str(value).strip().rstrip("/")

    @staticmethod
    def _coerce_list(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        return []


class LabStorage:
    def __init__(
        self,
        root_path: str | Path,
        *,
        backend: str | None = None,
        supabase_url: str | None = None,
        service_role_key: str | None = None,
        schema: str | None = None,
    ) -> None:
        selected_backend = str(backend or os.getenv("MYSTIC_STORAGE_BACKEND", "local")).strip().lower() or "local"
        if selected_backend == "supabase":
            self._backend = SupabaseLabStorage(
                root_path,
                supabase_url=supabase_url,
                service_role_key=service_role_key,
                schema=schema,
            )
        else:
            self._backend = LocalJSONLabStorage(root_path)
        self.backend_name = self._backend.backend_name
        self.base_dir = getattr(self._backend, "base_dir", None)

    def save_bundle(self, bundle: LabSessionBundle) -> dict[str, str]:
        return self._backend.save_bundle(bundle)

    def load_bundle(self, session_id: str) -> LabSessionBundle:
        return self._backend.load_bundle(session_id)

    def list_session_ids(self) -> list[str]:
        return self._backend.list_session_ids()

    def save_scene(self, scene_bundle: LabSceneBundle) -> dict[str, str]:
        return self._backend.save_scene(scene_bundle)

    def load_scene(self, scene_id: str) -> LabSceneBundle:
        return self._backend.load_scene(scene_id)

    def list_scene_ids(self, session_id: str | None = None) -> list[str]:
        return self._backend.list_scene_ids(session_id)

    def describe_status(self) -> dict[str, Any]:
        return self._backend.describe_status()
