from __future__ import annotations

import re
import time
from typing import Any
from loguru import logger

from shibaclaw.apps.models import AppDefinition, InstalledAppRecord, RuntimeType, TrustLevel
from shibaclaw.apps.registry.manager import AppRegistryManager
from shibaclaw.apps.state import AppStateManager
from shibaclaw.apps.auth import AppAuthManager
from shibaclaw.config.loader import load_config, save_config
from shibaclaw.config.schema import MCPServerConfig, MCPOAuthConfig
from starlette.requests import Request


def _get_agent_mgr():
    from shibaclaw.webui.agent_manager import agent_manager
    return agent_manager


class AppInstaller:
    """Manages transactional installation, uninstallation, enabling, and disabling of Apps."""

    def __init__(
        self,
        registry_manager: AppRegistryManager | None = None,
        state_manager: AppStateManager | None = None,
        auth_manager: AppAuthManager | None = None,
    ) -> None:
        self.registry = registry_manager or AppRegistryManager()
        self.state = state_manager or AppStateManager()
        self.auth = auth_manager or AppAuthManager()

    async def install_app(self, app_id: str, custom_def: AppDefinition | None = None) -> dict[str, Any]:
        """Transactional installation of an app by id."""
        app = custom_def or await self.registry.get_app(app_id)
        if not app:
            return {"ok": False, "error": f"App '{app_id}' not found in any marketplace catalog."}

        mgr = _get_agent_mgr()
        cfg = mgr.config or load_config()

        # Step 1: Security and Compatibility Validations
        if app.runtime_type == RuntimeType.NATIVE_PLUGIN.value:
            pkg = app.package_name or app.id
            if not re.match(r"^shibaclaw-[a-zA-Z0-9_\-]+$", pkg):
                return {
                    "ok": False,
                    "error": f"Security violation: package name '{pkg}' is not a trusted shibaclaw plugin.",
                }
        elif app.runtime_type == RuntimeType.MCP_REMOTE.value:
            mcp_cfg = app.mcp_config
            url = mcp_cfg.get("url", "")
            if not url or not url.startswith(("http://", "https://")):
                return {"ok": False, "error": "Remote MCP app requires a valid http/https URL."}
        elif app.runtime_type == RuntimeType.MCP_LOCAL.value:
            mcp_cfg = app.mcp_config
            cmd = mcp_cfg.get("command", "")
            if not cmd or cmd not in ("npx", "uvx", "python", "node", "docker"):
                return {
                    "ok": False,
                    "error": f"Security restriction: command '{cmd}' is not permitted for marketplace stdio apps.",
                }

        # Step 2: Install execution
        record = InstalledAppRecord(
            id=app.id,
            name=app.name,
            source=app.source,
            runtime_type=app.runtime_type,
            version=app.version,
            installed_at=time.time(),
            enabled=True,
            auth_state="disconnected" if app.auth.type != "none" else "connected",
            enabled_tools=["*"],
            mcp_server_name=app.id if "mcp" in app.runtime_type else None,
            package_name=app.package_name,
        )

        try:
            if app.runtime_type in (RuntimeType.MCP_REMOTE.value, RuntimeType.MCP_LOCAL.value):
                # Build MCPServerConfig
                mcp_kwargs: dict[str, Any] = {
                    "type": app.mcp_config.get("type", "streamableHttp"),
                    "url": app.mcp_config.get("url", ""),
                    "command": app.mcp_config.get("command", ""),
                    "args": app.mcp_config.get("args", []),
                    "headers": app.mcp_config.get("headers", {}),
                    "enabled_tools": ["*"],
                }

                if app.auth.type == "oauth2":
                    mcp_kwargs["oauth"] = MCPOAuthConfig(
                        auth_url=app.auth.auth_url,
                        token_url=app.auth.token_url,
                        client_id=app.auth.client_id,
                        scopes=app.auth.scopes,
                    )

                new_mcp_server = MCPServerConfig(**mcp_kwargs)

                if not hasattr(cfg.tools, "mcp_servers") or cfg.tools.mcp_servers is None:
                    cfg.tools.mcp_servers = {}
                cfg.tools.mcp_servers[app.id] = new_mcp_server

                # Save config and record
                save_config(cfg)
                self.state.save_installed_record(record)
                await mgr.reload_config(cfg)

                return {
                    "ok": True,
                    "app_id": app.id,
                    "installed": True,
                    "requires_auth": app.auth.type != "none",
                    "auth_type": app.auth.type,
                }

            elif app.runtime_type == RuntimeType.NATIVE_PLUGIN.value:
                pkg = app.package_name or app.id
                from shibaclaw.webui.routers.plugins import (
                    _install_plugin_exe,
                    _install_plugin_source,
                    is_running_as_exe,
                )
                is_exe = is_running_as_exe()
                resp = await (_install_plugin_exe(pkg) if is_exe else _install_plugin_source(pkg))
                if getattr(resp, "status_code", 200) not in (200, 201):
                    return {"ok": False, "error": f"Failed installing native plugin: {resp.body.decode()}"}

                self.state.save_installed_record(record)
                return {
                    "ok": True,
                    "app_id": app.id,
                    "installed": True,
                    "requires_auth": False,
                    "restarting": True,
                }

        except Exception as exc:
            logger.exception("Failed installing app '{}': {}", app.id, exc)
            # Rollback
            try:
                if hasattr(cfg.tools, "mcp_servers") and app.id in cfg.tools.mcp_servers:
                    del cfg.tools.mcp_servers[app.id]
                    save_config(cfg)
                self.state.remove_installed_record(app.id)
            except Exception:
                pass
            return {"ok": False, "error": f"Installation failed: {str(exc)}"}

        return {"ok": False, "error": "Unknown runtime type"}

    async def uninstall_app(self, app_id: str) -> dict[str, Any]:
        """Cleanly uninstall an app, removing config, credentials, and state."""
        records = self.state.get_installed_records()
        rec = records.get(app_id)

        mgr = _get_agent_mgr()
        cfg = mgr.config or load_config()

        try:
            # 1. Clean MCP server configuration
            if hasattr(cfg.tools, "mcp_servers") and cfg.tools.mcp_servers and app_id in cfg.tools.mcp_servers:
                del cfg.tools.mcp_servers[app_id]
                save_config(cfg)
                mgr.config = cfg
                try:
                    await asyncio.wait_for(mgr.reload_config(cfg), timeout=3.0)
                except Exception:
                    pass

            # 2. Revoke and clean credentials
            await self.auth.disconnect_app(app_id)

            # 3. Clean local state record
            self.state.remove_installed_record(app_id)

            # 4. If native plugin, trigger uninstall logic
            app = await self.registry.get_app(app_id)
            pkg_name = (rec and rec.package_name) or (app and app.package_name) or (app_id if app_id.startswith("shibaclaw-") else None)
            is_native = (rec and rec.runtime_type == RuntimeType.NATIVE_PLUGIN.value) or (app and app.runtime_type == RuntimeType.NATIVE_PLUGIN.value)
            if is_native and pkg_name:
                from shibaclaw.webui.routers.plugins import api_uninstall_plugin
                mock_scope = {
                    "type": "http",
                    "method": "POST",
                    "path": "/api/plugins/uninstall",
                    "headers": [(b"content-type", b"application/json")],
                }
                async def mock_receive():
                    import json
                    return {"type": "http.request", "body": json.dumps({"package": pkg_name}).encode()}
                req = Request(mock_scope, mock_receive)
                try:
                    await api_uninstall_plugin(req)
                except Exception as ex:
                    logger.warning("Error running native plugin uninstall for '{}': {}", pkg_name, ex)

            return {"ok": True, "app_id": app_id, "uninstalled": True}
        except Exception as e:
            logger.exception("Failed uninstalling app '{}': {}", app_id, e)
            return {"ok": False, "error": str(e)}

    async def toggle_app_enabled(self, app_id: str, enabled: bool) -> dict[str, Any]:
        """Enable or disable an app without deleting its configuration or credentials."""
        records = self.state.get_installed_records()
        rec = records.get(app_id)
        if not rec:
            rec = InstalledAppRecord(id=app_id, enabled=enabled)
        else:
            rec.enabled = enabled
        self.state.save_installed_record(rec)

        mgr = _get_agent_mgr()
        cfg = mgr.config or load_config()

        if rec.runtime_type in (RuntimeType.MCP_REMOTE.value, RuntimeType.MCP_LOCAL.value):
            mcp_servers = getattr(cfg.tools, "mcp_servers", {}) or {}
            if app_id in mcp_servers:
                mcp_servers[app_id].enabled_tools = ["*"] if enabled else []
                save_config(cfg)
                await mgr.reload_config(cfg)

        elif rec.runtime_type == RuntimeType.NATIVE_PLUGIN.value:
            if rec.package_name == "shibaclaw-channel-whatsapp":
                w_sec = getattr(cfg.channels, "whatsapp", None)
                if w_sec:
                    if isinstance(w_sec, dict):
                        w_sec["enabled"] = enabled
                    else:
                        w_sec.enabled = enabled
                    save_config(cfg)
                    await mgr.reload_config(cfg)

        return {"ok": True, "app_id": app_id, "enabled": enabled}

    async def update_enabled_tools(self, app_id: str, enabled_tools: list[str]) -> dict[str, Any]:
        """Update individual tool allowlist for an MCP integration."""
        mgr = _get_agent_mgr()
        cfg = mgr.config or load_config()
        mcp_servers = getattr(cfg.tools, "mcp_servers", {}) or {}
        if app_id not in mcp_servers:
            return {"ok": False, "error": f"MCP App '{app_id}' is not configured."}

        mcp_servers[app_id].enabled_tools = enabled_tools
        save_config(cfg)

        records = self.state.get_installed_records()
        if app_id in records:
            records[app_id].enabled_tools = enabled_tools
            self.state.save_installed_record(records[app_id])

        await mgr.reload_config(cfg)
        return {"ok": True, "app_id": app_id, "enabled_tools": enabled_tools}
