from __future__ import annotations

import json
import re
import time
import urllib.parse
from pathlib import Path
from typing import Any
import httpx
from loguru import logger

from shibaclaw.apps.models import AppDefinition, TrustLevel, RuntimeType, AppAuthDefinition
from shibaclaw.apps.registry.base import BaseAppRegistry
from shibaclaw.config.paths import get_app_root

_REGISTRY_BASE_URL = "https://registry.modelcontextprotocol.io/v0.1/servers"
_CACHE_TTL_SECONDS = 86400  # 24 hours


def _sanitize_app_id(raw_name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]+", "-", raw_name.strip().lower())
    return cleaned.strip("-")


def _is_safe_remote_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = (parsed.hostname or "").lower()
        if not host:
            return False
        if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
            return False
        return True
    except Exception:
        return False


def _infer_category(name: str, desc: str) -> str:
    text = f"{name} {desc}".lower()
    if any(k in text for k in ("db", "database", "postgres", "sql", "sqlite", "mongo", "redis")):
        return "databases"
    if any(k in text for k in ("mail", "calendar", "task", "todo", "sheet", "doc", "workspace", "notion")):
        return "productivity"
    if any(k in text for k in ("chat", "slack", "discord", "message", "telegram", "whatsapp", "teams")):
        return "communication"
    if any(k in text for k in ("code", "git", "github", "gitlab", "dev", "terminal", "debugger")):
        return "development"
    if any(k in text for k in ("search", "brave", "google", "web", "crawler", "scrape")):
        return "search"
    if any(k in text for k in ("image", "video", "audio", "tts", "media", "voice", "stream")):
        return "media"
    if any(k in text for k in ("ai", "llm", "inference", "prompt", "model", "rag")):
        return "ai"
    return "development"


class MCPRegistryProvider(BaseAppRegistry):
    def __init__(self, base_url: str = _REGISTRY_BASE_URL, cache_dir: Path | None = None) -> None:
        self._base_url = base_url
        self._cache_dir = cache_dir or (get_app_root() / "cache")
        self._cache_file = self._cache_dir / "mcp_registry_cache.json"

    def _read_cache(self) -> tuple[list[dict[str, Any]], bool]:
        """Return (servers, is_fresh)."""
        if not self._cache_file.exists():
            return [], False
        try:
            raw = json.loads(self._cache_file.read_text(encoding="utf-8"))
            saved_at = raw.get("_saved_at", 0)
            servers = raw.get("servers", [])
            is_fresh = (time.time() - saved_at) < _CACHE_TTL_SECONDS
            return servers, is_fresh
        except Exception as e:
            logger.debug("Failed to read MCP registry cache: {}", e)
            return [], False

    def _write_cache(self, servers: list[dict[str, Any]]) -> None:
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            payload = {"_saved_at": time.time(), "servers": servers}
            self._cache_file.write_text(json.dumps(payload), encoding="utf-8")
        except Exception as e:
            logger.debug("Failed to write MCP registry cache: {}", e)

    async def _fetch_servers(self, timeout: float = 6.0) -> list[dict[str, Any]]:
        cached_servers, is_fresh = self._read_cache()
        if is_fresh and len(cached_servers) >= 50:
            return cached_servers

        try:
            headers = {"User-Agent": "ShibaClaw-AppMarketplace/1.0", "Accept": "application/json"}
            all_servers: list[dict[str, Any]] = []
            cursor: str | None = None

            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
                for _ in range(4):
                    url = f"{self._base_url}?limit=100"
                    if cursor:
                        url += f"&cursor={urllib.parse.quote(cursor)}"
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        break
                    data = resp.json()
                    page_servers = data.get("servers", [])
                    if not isinstance(page_servers, list) or not page_servers:
                        break
                    all_servers.extend(page_servers)
                    meta = data.get("metadata", {})
                    cursor = meta.get("nextCursor")
                    if not cursor:
                        break

            if all_servers:
                self._write_cache(all_servers)
                return all_servers
        except Exception as e:
            logger.debug("MCP registry remote fetch skipped or timed out: {}", e)

        return cached_servers

    def _parse_server_entry(self, entry: dict[str, Any]) -> AppDefinition | None:
        server = entry.get("server") if "server" in entry else entry
        if not isinstance(server, dict):
            return None

        raw_name = server.get("name") or ""
        if not raw_name:
            return None

        app_id = _sanitize_app_id(raw_name)
        title = server.get("title") or raw_name.split("/")[-1].replace("-", " ").title()
        description = server.get("description") or f"MCP Server {title}"
        version = server.get("version") or "1.0.0"

        remotes = server.get("remotes") or []
        packages = server.get("packages") or []

        mcp_config: dict[str, Any] = {}
        runtime_type = RuntimeType.MCP_REMOTE

        if remotes and isinstance(remotes, list):
            first_remote = remotes[0]
            r_type = first_remote.get("type", "streamable-http")
            r_url = first_remote.get("url", "")
            if not _is_safe_remote_url(r_url):
                return None
            transport = "sse" if "sse" in r_type.lower() else "streamableHttp"
            mcp_config = {"type": transport, "url": r_url}
            runtime_type = RuntimeType.MCP_REMOTE
        elif packages and isinstance(packages, list):
            first_pkg = packages[0]
            pkg_id = first_pkg.get("identifier", "")
            if not pkg_id:
                return None
            mcp_config = {
                "type": "stdio",
                "command": "npx",
                "args": ["-y", pkg_id],
            }
            runtime_type = RuntimeType.MCP_LOCAL
        else:
            return None

        category = _infer_category(title, description)

        return AppDefinition(
            id=app_id,
            name=title,
            description=description,
            icon="hub",
            category=category,
            source="mcp_registry",
            runtime_type=runtime_type.value,
            trust_level=TrustLevel.COMMUNITY.value,
            version=version,
            auth=AppAuthDefinition(type="none"),
            capabilities=[],
            mcp_config=mcp_config,
        )

    async def list_apps(self) -> list[AppDefinition]:
        servers = await self._fetch_servers()
        apps: list[AppDefinition] = []
        seen: set[str] = set()

        for item in servers:
            try:
                parsed = self._parse_server_entry(item)
                if parsed and parsed.id not in seen:
                    apps.append(parsed)
                    seen.add(parsed.id)
            except Exception as e:
                logger.debug("Failed parsing server entry: {}", e)

        return apps

    async def get_app(self, app_id: str) -> AppDefinition | None:
        apps = await self.list_apps()
        for app in apps:
            if app.id == app_id:
                return app
        return None
