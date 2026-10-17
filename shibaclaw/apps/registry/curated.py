from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import httpx
from loguru import logger

from shibaclaw.apps.models import AppDefinition
from shibaclaw.apps.registry.base import BaseAppRegistry
from shibaclaw.config.paths import get_app_root

_BUNDLED_REGISTRY_PATH = Path(__file__).resolve().parent.parent / "curated_registry.json"
_REMOTE_URL = "https://raw.githubusercontent.com/RikyZ90/ShibaClaw/main/shibaclaw/apps/curated_registry.json"


class CuratedAppRegistry(BaseAppRegistry):
    def __init__(self, bundled_path: Path | None = None) -> None:
        self._bundled_path = bundled_path or _BUNDLED_REGISTRY_PATH
        self._cache_dir = get_app_root() / "cache"
        self._cached_path = self._cache_dir / "curated_registry.json"

    def _load_raw(self) -> dict[str, Any]:
        target = self._cached_path if self._cached_path.exists() else self._bundled_path
        if not target.exists():
            return {"apps": []}
        try:
            content = target.read_text(encoding="utf-8")
            return json.loads(content)
        except Exception as e:
            logger.warning("Failed to parse curated registry from {}: {}", target, e)
            if target != self._bundled_path and self._bundled_path.exists():
                try:
                    return json.loads(self._bundled_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            return {"apps": []}

    async def list_apps(self) -> list[AppDefinition]:
        data = self._load_raw()
        apps = []
        for item in data.get("apps", []):
            try:
                apps.append(AppDefinition.model_validate(item))
            except Exception as e:
                logger.debug("Skipping invalid curated app definition {}: {}", item.get("id"), e)
        return apps

    async def get_app(self, app_id: str) -> AppDefinition | None:
        apps = await self.list_apps()
        for app in apps:
            if app.id == app_id:
                return app
        return None

    async def sync_remote(self, timeout: float = 3.0) -> bool:
        """Fetch updated curated catalog from GitHub with fallback to bundled."""
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                resp = await client.get(_REMOTE_URL)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and "apps" in data:
                        self._cache_dir.mkdir(parents=True, exist_ok=True)
                        self._cached_path.write_text(resp.text, encoding="utf-8")
                        return True
        except Exception as e:
            logger.debug("Curated registry remote sync skipped: {}", e)
        return False
