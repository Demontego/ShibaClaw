from __future__ import annotations

from abc import ABC, abstractmethod
from shibaclaw.apps.models import AppDefinition


class BaseAppRegistry(ABC):
    @abstractmethod
    async def list_apps(self) -> list[AppDefinition]:
        """Return all available app definitions."""
        raise NotImplementedError

    @abstractmethod
    async def get_app(self, app_id: str) -> AppDefinition | None:
        """Return app definition for given app_id or None."""
        raise NotImplementedError

    async def search_apps(
        self, query: str = "", category: str | None = None
    ) -> list[AppDefinition]:
        """Search apps by name/description and optional category."""
        apps = await self.list_apps()
        q = (query or "").strip().lower()
        cat = (category or "").strip().lower()

        results = []
        for app in apps:
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
