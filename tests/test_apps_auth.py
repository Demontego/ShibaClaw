from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from shibaclaw.apps.models import AppDefinition, AppAuthDefinition, AppAuthField, AuthState
from shibaclaw.apps.auth import AppAuthManager
from shibaclaw.config.schema import Config, MCPServerConfig


@pytest.fixture
def auth_mgr():
    with patch("shibaclaw.apps.auth.get_credential_manager") as mock_cm, \
         patch("shibaclaw.apps.auth.OAuthTokenStore") as mock_ts:
        cm_instance = MagicMock()
        ts_instance = MagicMock()
        mock_cm.return_value = cm_instance
        mock_ts.return_value = ts_instance

        manager = AppAuthManager()
        manager._cm = cm_instance
        manager._oauth_store = ts_instance
        return manager


@pytest.mark.asyncio
async def test_auth_api_key_storage(auth_mgr):
    app = AppDefinition(
        id="github",
        name="GitHub",
        description="GitHub",
        auth=AppAuthDefinition(type="api_key"),
    )

    mock_cfg = Config()
    mock_cfg.tools.mcp_servers["github"] = MCPServerConfig(
        type="streamableHttp", url="https://api.github.com/mcp"
    )

    with patch("shibaclaw.apps.auth._get_agent_mgr") as mock_get_mgr, \
         patch("shibaclaw.apps.auth.save_config") as mock_save:
        mock_agent_mgr = MagicMock()
        mock_get_mgr.return_value = mock_agent_mgr
        mock_agent_mgr.config = mock_cfg
        mock_agent_mgr.reload_config = AsyncMock()

        res = await auth_mgr.connect_app(app, {"api_key": "ghp_secret123"})
        assert res["ok"] is True
        assert res["status"] == AuthState.CONNECTED.value

        # Credential manager stored secrets encrypted
        auth_mgr._cm.set_secret.assert_any_call("apps", "github.api_key", "ghp_secret123")
        auth_mgr._cm.set_secret.assert_any_call("mcp_servers", "github.api_key", "ghp_secret123")

        # Secret is NOT returned in response
        assert "ghp_secret123" not in str(res)


@pytest.mark.asyncio
async def test_auth_oauth_requires_client_credentials(auth_mgr):
    app = AppDefinition(
        id="google-workspace",
        name="Google Workspace",
        description="Google",
        auth=AppAuthDefinition(type="oauth2", requires_client_credentials=True),
    )
    auth_mgr._cm.get_secret.return_value = None

    # No credentials provided
    res = await auth_mgr.connect_app(app, {})
    assert res["ok"] is False
    assert res["status"] == "needs_client_credentials"
    assert "client_id" in res["required_fields"]


@pytest.mark.asyncio
async def test_auth_disconnect_cleans_secrets(auth_mgr):
    mock_cfg = Config()
    mock_cfg.tools.mcp_servers["slack"] = MCPServerConfig(
        type="streamableHttp",
        url="https://mcp.slack.com/mcp",
        headers={"Authorization": "Bearer token123"},
    )

    with patch("shibaclaw.apps.auth._get_agent_mgr") as mock_get_mgr, \
         patch("shibaclaw.apps.auth.save_config") as mock_save:
        mock_agent_mgr = MagicMock()
        mock_get_mgr.return_value = mock_agent_mgr
        mock_agent_mgr.config = mock_cfg
        mock_agent_mgr.reload_config = AsyncMock()

        res = await auth_mgr.disconnect_app("slack")
        assert res["ok"] is True
        assert res["status"] == AuthState.DISCONNECTED.value

        # Deleted token and secrets
        auth_mgr._oauth_store.delete_token.assert_called_with("slack")
        auth_mgr._cm.delete_secret.assert_any_call("apps", "slack.api_key")
        auth_mgr._cm.delete_secret.assert_any_call("mcp_servers", "slack.api_key")

        # Authorization header removed
        assert "Authorization" not in mock_cfg.tools.mcp_servers["slack"].headers
