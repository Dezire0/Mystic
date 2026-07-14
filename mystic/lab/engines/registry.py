from __future__ import annotations

from typing import Iterable

from .base import ScientificEnginePlugin
from .errors import EngineError
from .manifest import EngineManifest


class EngineRegistry:
    """Deterministic registry of server-owned, allowlisted plugins only."""
    def __init__(self, plugins: Iterable[ScientificEnginePlugin] = ()) -> None:
        self._plugins: dict[str, ScientificEnginePlugin] = {}
        for plugin in plugins:
            self.register(plugin)

    def register(self, plugin: ScientificEnginePlugin) -> None:
        manifest = plugin.manifest()
        self.verify_manifest(manifest)
        if manifest.engine_id in self._plugins:
            raise EngineError("engine_duplicate", f"Engine ID {manifest.engine_id} is already registered.")
        self._plugins[manifest.engine_id] = plugin

    def unregister_for_test(self, engine_id: str) -> None:
        self._plugins.pop(engine_id, None)

    def get(self, engine_id: str, *, require_enabled: bool = True) -> ScientificEnginePlugin:
        plugin = self._plugins.get(engine_id)
        if plugin is None:
            raise EngineError("engine_not_found", "The requested scientific engine is not available.")
        manifest = plugin.manifest()
        if require_enabled and not manifest.enabled:
            raise EngineError("engine_disabled", "The requested scientific engine is disabled.")
        if require_enabled and manifest.deprecated:
            raise EngineError("engine_disabled", "The requested scientific engine is deprecated.")
        return plugin

    def list(self, *, domain: str | None = None, capability: str | None = None, enabled_only: bool = True) -> list[EngineManifest]:
        manifests = (plugin.manifest() for plugin in self._plugins.values())
        return sorted((manifest for manifest in manifests if (not domain or manifest.domain == domain) and (not capability or capability in manifest.capabilities) and (not enabled_only or (manifest.enabled and not manifest.deprecated))), key=lambda item: item.engine_id)

    @staticmethod
    def verify_manifest(manifest: EngineManifest) -> None:
        if not manifest.engine_id or "." not in manifest.engine_id or not manifest.version or not manifest.display_name:
            raise EngineError("engine_manifest_invalid", "Engine manifests require stable ID, display name, and version.")
        if manifest.expected_resource_class not in {"tiny", "small", "medium", "large", "external_required"}:
            raise EngineError("engine_manifest_invalid", "Engine resource class is invalid.")
        if manifest.timeout_seconds_default < 1 or manifest.timeout_seconds_default > manifest.timeout_seconds_max:
            raise EngineError("engine_manifest_invalid", "Engine timeout limits are invalid.")
