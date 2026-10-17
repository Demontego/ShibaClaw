from __future__ import annotations

import asyncio
import secrets
import urllib.parse
from typing import Any
from loguru import logger

from shibaclaw.apps.models import AppDefinition, AuthState
from shibaclaw.config.loader import load_config, save_config
from shibaclaw.security.oauth_flow import OAuthFlow, _generate_pkce_pair, _CallbackServer
from shibaclaw.security.oauth_store import OAuthTokenStore
from shibaclaw.security.credential_manager import get_credential_manager
def _get_agent_mgr():
    from shibaclaw.webui.agent_manager import agent_manager
    return agent_manager


_ACTIVE_AUTH_JOBS: dict[str, asyncio.Task] = {}


class AppAuthManager:
    """Manages authentication lifecycle (OAuth2, API keys, credentials) for Apps."""

    def __init__(self) -> None:
        self._oauth_store = OAuthTokenStore()
        self._cm = get_credential_manager()
        self._flow = OAuthFlow(store=self._oauth_store)

    async def connect_app(
        self, app: AppDefinition, credentials: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Authenticate or configure an app based on its auth definition."""
        auth_type = app.auth.type
        credentials = credentials or {}

        if auth_type == "none":
            return {"ok": True, "status": AuthState.CONNECTED.value}

        if auth_type in ("api_key", "bearer"):
            api_key = credentials.get("api_key") or credentials.get("token") or ""
            if not api_key:
                return {"ok": False, "error": "api_key is required", "status": "needs_config"}

            self._cm.set_secret("apps", f"{app.id}.api_key", api_key)
            self._cm.set_secret("mcp_servers", f"{app.id}.api_key", api_key)

            # Inject into MCP server config headers if remote MCP
            mgr = _get_agent_mgr()
            cfg = mgr.config or load_config()
            mcp_servers = getattr(cfg.tools, "mcp_servers", {}) or {}
            if app.id in mcp_servers:
                sc = mcp_servers[app.id]
                headers = dict(getattr(sc, "headers", {}) or {})
                headers["Authorization"] = f"Bearer {api_key}"
                sc.headers = headers
                save_config(cfg)
                await mgr.reload_config(cfg)

            return {"ok": True, "status": AuthState.CONNECTED.value}

        if auth_type == "custom":
            for k, v in credentials.items():
                if v:
                    self._cm.set_secret("apps", f"{app.id}.{k}", v)

            mgr = _get_agent_mgr()
            cfg = mgr.config or load_config()
            save_config(cfg)
            await mgr.reload_config(cfg)
            return {"ok": True, "status": AuthState.CONNECTED.value}

        if auth_type == "oauth2":
            # Check BYO client credentials
            client_id = credentials.get("client_id") or app.auth.client_id
            client_secret = credentials.get("client_secret")

            if not client_id:
                client_id = self._cm.get_secret("mcp_servers", f"{app.id}.client_id") or ""

            if client_secret:
                self._cm.set_secret("mcp_servers", f"{app.id}.client_secret", client_secret)

            if app.auth.requires_client_credentials and not client_id:
                return {
                    "ok": False,
                    "status": "needs_client_credentials",
                    "error": "Client ID and Client Secret required for this provider.",
                    "required_fields": ["client_id", "client_secret"],
                }

            if client_id:
                self._cm.set_secret("mcp_servers", f"{app.id}.client_id", client_id)

            # Start local OAuth authorization flow
            auth_info = await self._start_oauth_flow(app, client_id)
            return auth_info

        return {"ok": False, "error": f"Unsupported auth type: {auth_type}"}

    async def _start_oauth_flow(self, app: AppDefinition, client_id: str) -> dict[str, Any]:
        """Start local callback server and return auth URL to open in browser."""
        code_verifier, code_challenge = _generate_pkce_pair()
        state = secrets.token_urlsafe(16)

        callback_server = _CallbackServer()
        await callback_server.start()
        redirect_uri = f"http://127.0.0.1:{callback_server.port}/callback/{callback_server.token}"

        auth_params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        if app.auth.scopes:
            auth_params["scope"] = " ".join(app.auth.scopes)

        sep = "&" if "?" in app.auth.auth_url else "?"
        auth_url = app.auth.auth_url + sep + urllib.parse.urlencode(auth_params)

        # Background task to wait for code and complete token exchange
        async def _await_callback():
            try:
                params = await callback_server.wait_for_code(timeout=180.0)
                if params.get("state") != state:
                    logger.error("OAuth state mismatch for {}", app.id)
                    return
                code = params.get("code")
                if not code:
                    logger.error("No code returned in OAuth callback for {}", app.id)
                    return

                # Build dummy config for token exchange
                from shibaclaw.config.schema import MCPOAuthConfig
                mcp_oauth_cfg = MCPOAuthConfig(
                    auth_url=app.auth.auth_url,
                    token_url=app.auth.token_url,
                    client_id=client_id,
                    scopes=app.auth.scopes,
                )
                token_data = await self._flow._exchange_code(
                    server_name=app.id,
                    cfg=mcp_oauth_cfg,
                    code=code,
                    code_verifier=code_verifier,
                    redirect_uri=redirect_uri,
                )
                self._oauth_store.save_token(app.id, token_data)
                logger.info("OAuth completed successfully for App '{}'", app.id)

                # Hot-reload gateway to connect MCP server
                mgr = _get_agent_mgr()
                cfg = mgr.config or load_config()
                await mgr.reload_config(cfg)
            except Exception as e:
                logger.error("OAuth background callback failed for '{}': {}", app.id, e)
            finally:
                await callback_server.stop()
                _ACTIVE_AUTH_JOBS.pop(app.id, None)

        task = asyncio.create_task(_await_callback())
        _ACTIVE_AUTH_JOBS[app.id] = task

        return {
            "ok": True,
            "status": AuthState.CONNECTING.value,
            "auth_url": auth_url,
            "redirect_uri": redirect_uri,
        }

    async def disconnect_app(self, app_id: str) -> dict[str, Any]:
        """Revoke / remove credentials for an app."""
        self._oauth_store.delete_token(app_id)
        self._cm.delete_secret("apps", f"{app_id}.api_key")
        self._cm.delete_secret("apps", f"{app_id}.connection_string")
        self._cm.delete_secret("mcp_servers", f"{app_id}.api_key")
        self._cm.delete_secret("mcp_servers", f"{app_id}.client_id")
        self._cm.delete_secret("mcp_servers", f"{app_id}.client_secret")

        mgr = _get_agent_mgr()
        cfg = mgr.config or load_config()
        mcp_servers = getattr(cfg.tools, "mcp_servers", {}) or {}
        if app_id in mcp_servers:
            sc = mcp_servers[app_id]
            if getattr(sc, "headers", None) and "Authorization" in sc.headers:
                del sc.headers["Authorization"]
            save_config(cfg)
            await mgr.reload_config(cfg)

        return {"ok": True, "status": AuthState.DISCONNECTED.value}
