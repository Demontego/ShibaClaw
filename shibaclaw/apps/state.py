from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from loguru import logger

from shibaclaw.apps.models import AppDefinition, InstalledAppRecord, AuthState, RuntimeType
from shibaclaw.config.loader import load_config
from shibaclaw.config.paths import get_app_root
from shibaclaw.security.oauth_store import OAuthTokenStore
from shibaclaw.security.credential_manager import get_credential_manager


class AppStateManager:
    """Tracks and resolves the live state and persistence of installed apps."""

    def __init__(self, storage_path: Path | None = None) -> None:
        self._file = storage_path or (get_app_root() / "installed_apps.json")
        self._oauth_store = OAuthTokenStore()
        self._credential_manager = get_credential_manager()

    @staticmethod
    def _has_newer_version(available: str, installed: str) -> bool:
        """Only compare dotted numeric versions; unknown formats are not updates."""
        pattern = r"v?\d+(?:\.\d+)*"
        if not re.fullmatch(pattern, available) or not re.fullmatch(pattern, installed):
            return False
        available_parts = tuple(int(part) for part in available.lstrip("v").split("."))
        installed_parts = tuple(int(part) for part in installed.lstrip("v").split("."))
        length = max(len(available_parts), len(installed_parts))
        return available_parts + (0,) * (length - len(available_parts)) > installed_parts + (0,) * (length - len(installed_parts))

    def get_installed_records(self, cfg: Any = None) -> dict[str, InstalledAppRecord]:
        """Load installed app records from config and local storage."""
        records: dict[str, InstalledAppRecord] = {}

        if self._file.exists():
            try:
                raw = json.loads(self._file.read_text(encoding="utf-8"))
                for app_id, data in raw.items():
                    try:
                        records[app_id] = InstalledAppRecord.model_validate(data)
                    except Exception:
                        pass
            except Exception as e:
                logger.debug("Failed to read local installed_apps.json: {}", e)

        # Merge with config.apps if available
        if cfg and hasattr(cfg, "apps") and isinstance(cfg.apps, dict):
            for app_id, data in cfg.apps.items():
                try:
                    records[app_id] = InstalledAppRecord.model_validate(data)
                except Exception:
                    pass

        return records

    def save_installed_record(self, record: InstalledAppRecord) -> None:
        records = self.get_installed_records()
        records[record.id] = record

        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            payload = {app_id: rec.model_dump(mode="json") for app_id, rec in records.items()}
            self._file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error("Failed to save installed_apps.json: {}", e)

    def remove_installed_record(self, app_id: str) -> None:
        records = self.get_installed_records()
        if app_id in records:
            del records[app_id]
            try:
                payload = {aid: rec.model_dump(mode="json") for aid, rec in records.items()}
                self._file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            except Exception as e:
                logger.error("Failed to update installed_apps.json: {}", e)

    def resolve_auth_state(self, app: AppDefinition, cfg: Any = None) -> str:
        """Resolve current authentication state without leaking credentials."""
        auth_type = app.auth.type
        if auth_type == "none":
            return AuthState.CONNECTED.value

        mcp_name = app.id

        if auth_type == "oauth2":
            stored = self._oauth_store.load_token(mcp_name)
            if not stored or not stored.get("access_token"):
                return AuthState.DISCONNECTED.value
            if self._oauth_store.is_expired(mcp_name):
                if self._oauth_store.has_refresh_token(mcp_name):
                    return AuthState.CONNECTED.value  # Can refresh dynamically
                return AuthState.EXPIRED.value
            return AuthState.CONNECTED.value

        if auth_type in ("api_key", "bearer", "custom"):
            # Check secret in vault
            secret = self._credential_manager.get_secret("apps", f"{app.id}.api_key")
            if not secret:
                secret = self._credential_manager.get_secret("mcp_servers", f"{app.id}.api_key")
            if not secret:
                secret = self._credential_manager.get_secret("apps", f"{app.id}.connection_string")
            if not secret and cfg and hasattr(cfg, "tools"):
                mcp_servers = getattr(cfg.tools, "mcp_servers", {}) or {}
                sc = mcp_servers.get(app.id)
                if sc and getattr(sc, "headers", None):
                    auth_h = sc.headers.get("Authorization") or sc.headers.get("authorization")
                    if auth_h:
                        secret = auth_h

            return AuthState.CONNECTED.value if secret else AuthState.DISCONNECTED.value

        return AuthState.CONNECTED.value

    def enrich_app_state(self, app: AppDefinition, cfg: Any = None, records: dict[str, InstalledAppRecord] | None = None) -> AppDefinition:
        """Enrich AppDefinition with live installed status, tools, and health state."""
        cfg = cfg or load_config()
        if records is None:
            records = self.get_installed_records(cfg)

        rec = records.get(app.id)
        mcp_servers = getattr(cfg.tools, "mcp_servers", {}) or {} if hasattr(cfg, "tools") else {}
        is_mcp_configured = app.id in mcp_servers

        # Check native plugin install state
        is_native_installed = False
        if app.runtime_type == RuntimeType.NATIVE_PLUGIN.value:
            if rec and not rec.enabled:
                is_native_installed = False
            elif app.package_name == "shibaclaw-channel-whatsapp":
                from shibaclaw.integrations.registry import discover_plugins, discover_local_plugins
                ch = {**discover_plugins(), **discover_local_plugins()}
                is_native_installed = "whatsapp" in ch
            elif app.package_name == "shibaclaw-tts-supertonic":
                from shibaclaw.tts.registry import discover_tts_plugins
                is_native_installed = "supertonic" in discover_tts_plugins()
            elif app.package_name == "shibaclaw-rag":
                from shibaclaw.agent.knowledge_manager import is_rag_available
                is_native_installed = is_rag_available()

        installed = bool(rec is not None or is_mcp_configured or is_native_installed)
        app.installed = installed
        app.installed_version = rec.version if rec else None
        app.update_available = bool(rec and installed and self._has_newer_version(app.version, rec.version))

        if rec:
            app.enabled = rec.enabled
            app.installed_at = rec.installed_at
            app.enabled_tools = rec.enabled_tools or ["*"]
        elif is_mcp_configured:
            sc = mcp_servers[app.id]
            app.enabled = True
            app.enabled_tools = getattr(sc, "enabled_tools", ["*"]) or ["*"]
        elif is_native_installed:
            app.enabled = True
            if app.package_name == "shibaclaw-channel-whatsapp":
                w_sec = getattr(cfg.channels, "whatsapp", None)
                app.enabled = bool(getattr(w_sec, "enabled", False) if w_sec else False)
            elif app.package_name == "shibaclaw-tts-supertonic":
                app.enabled = bool(getattr(cfg.audio, "tts_provider", "") == "supertonic")

        # Fast path: only query secrets / oauth stores if the app is actually installed
        if app.installed:
            auth_state = self.resolve_auth_state(app, cfg)
        else:
            auth_state = AuthState.CONNECTED.value if app.auth.type == "none" else AuthState.DISCONNECTED.value

        # Derive tools if MCP server
        available_tools = []
        try:
            from shibaclaw.agent.tools.mcp import _mcp_wrapped_tools, _mcp_sessions
            if app.id in _mcp_sessions:
                allow_all = "*" in app.enabled_tools
                for wt in _mcp_wrapped_tools:
                    if getattr(wt, "_server_name", None) == app.id:
                        tool_nm = getattr(wt, "_tool_name", wt.name)
                        is_tool_en = allow_all or (tool_nm in app.enabled_tools)
                        available_tools.append({
                            "name": tool_nm,
                            "description": wt.description,
                            "parameters": wt.parameters,
                            "enabled": is_tool_en,
                        })
        except Exception:
            pass

        app.available_tools = available_tools
        app.tools_count = len(available_tools)

        # Calculate overall status
        if not app.installed:
            app.status = "ready"
        elif not app.enabled:
            app.status = "disabled"
        elif auth_state == AuthState.DISCONNECTED.value:
            app.status = "needs_auth" if app.auth.type == "oauth2" else "needs_config"
        elif auth_state == AuthState.EXPIRED.value:
            app.status = "expired"
        else:
            app.status = "connected"

        return app
