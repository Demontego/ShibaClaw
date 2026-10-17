from __future__ import annotations

import asyncio

from shibaclaw.apps.models import AppDefinition
from shibaclaw.apps.registry.curated import CuratedAppRegistry
from shibaclaw.apps.registry.mcp_registry import MCPRegistryProvider
from shibaclaw.apps.registry.native import NativePluginRegistryProvider


class AppRegistryManager:
    """Aggregates multiple marketplace sources with priority and deduplication.

    Priority order:
    1. Curated Registry (official / recommended integrations)
    2. Native Plugins (local / entry-point plugins)
    3. MCP Registry (open catalog)
    """

    def __init__(
        self,
        curated_provider: CuratedAppRegistry | None = None,
        native_provider: NativePluginRegistryProvider | None = None,
        mcp_provider: MCPRegistryProvider | None = None,
    ) -> None:
        self.curated = curated_provider or CuratedAppRegistry()
        self.native = native_provider or NativePluginRegistryProvider()
        self.mcp = mcp_provider or MCPRegistryProvider()

    async def list_all(self) -> list[AppDefinition]:
        curated_task = self.curated.list_apps()
        native_task = self.native.list_apps()
        mcp_task = self.mcp.list_apps()

        curated_apps, native_apps, mcp_apps = await asyncio.gather(
            curated_task, native_task, mcp_task, return_exceptions=True
        )

        curated_list = curated_apps if isinstance(curated_apps, list) else []
        native_list = native_apps if isinstance(native_apps, list) else []
        mcp_list = mcp_apps if isinstance(mcp_apps, list) else []

        combined: dict[str, AppDefinition] = {}

        # 1. Curated first
        for app in curated_list:
            combined[app.id] = app

        # 2. Native plugins (don't overwrite curated)
        for app in native_list:
            if app.id not in combined:
                combined[app.id] = app

        # 3. MCP Registry (don't overwrite curated or native)
        for app in mcp_list:
            if app.id not in combined:
                combined[app.id] = app

        return list(combined.values())

    async def get_app(self, app_id: str) -> AppDefinition | None:
        app = await self.curated.get_app(app_id)
        if app:
            return app
        app = await self.native.get_app(app_id)
        if app:
            return app
        app = await self.mcp.get_app(app_id)
        if app:
            return app
        return None

    async def search(self, query: str = "", category: str | None = None) -> list[AppDefinition]:
        all_apps = await self.list_all()
        q = (query or "").strip().lower()
        cat = (category or "").strip().lower()

        results = []
        for app in all_apps:
            if cat and cat != "all" and app.category.lower() != cat:
                continue
            if q:
                match = (
                    q in app.name.lower()
                    or q in app.id.lower()
                    or q in app.description.lower()
                    or any(q in cap.lower() for cap in app.capabilities)
                )
                if not match:
                    continue
            results.append(app)
        return results
