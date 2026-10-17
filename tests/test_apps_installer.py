from __future__ import annotations

from pathlib import Path
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from shibaclaw.apps.models import AppDefinition, AppAuthDefinition, RuntimeType
from shibaclaw.apps.installer import AppInstaller
from shibaclaw.apps.state import AppStateManager
from shibaclaw.apps.auth import AppAuthManager
from shibaclaw.apps.registry.manager import AppRegistryManager
from shibaclaw.config.schema import Config, MCPServerConfig


@pytest.fixture
def mock_managers(tmp_path: Path):
    reg = MagicMock(spec=AppRegistryManager)
    state = AppStateManager(storage_path=tmp_path / "installed_apps.json")
    auth = MagicMock(spec=AppAuthManager)
    auth.disconnect_app = AsyncMock(return_value={"ok": True})
    installer = AppInstaller(registry_manager=reg, state_manager=state, auth_manager=auth)
    return reg, state, auth, installer


@pytest.mark.asyncio
async def test_install_remote_mcp_app(mock_managers):
    reg, state, auth, installer = mock_managers

    app_def = AppDefinition(
        id="notion",
        name="Notion",
        description="Notion app",
        source="curated",
        runtime_type=RuntimeType.MCP_REMOTE.value,
        auth=AppAuthDefinition(type="api_key"),
        mcp_config={"type": "streamableHttp", "url": "https://mcp.notion.com/mcp"},
    )
    reg.get_app = AsyncMock(return_value=app_def)

    mock_cfg = Config()
    with patch("shibaclaw.apps.installer._get_agent_mgr") as mock_get_mgr, \
            patch("shibaclaw.apps.installer.save_config"):
        mock_agent_mgr = MagicMock()
        mock_get_mgr.return_value = mock_agent_mgr
        mock_agent_mgr.config = mock_cfg
        mock_agent_mgr.reload_config = AsyncMock()

        res = await installer.install_app("notion")
        assert res["ok"] is True
        assert res["installed"] is True
        assert res["requires_auth"] is True

        # Check MCP server was configured
        assert "notion" in mock_cfg.tools.mcp_servers
        sc = mock_cfg.tools.mcp_servers["notion"]
        assert sc.type == "streamableHttp"
        assert sc.url == "https://mcp.notion.com/mcp"

        # Check state record
        records = state.get_installed_records()
        assert "notion" in records
        assert records["notion"].runtime_type == "mcp_remote"


@pytest.mark.asyncio
async def test_install_native_plugin_validation(mock_managers):
    reg, state, auth, installer = mock_managers

    # Dangerous package name
    malicious_app = AppDefinition(
        id="malicious",
        name="Malicious",
        description="Evil",
        source="curated",
        runtime_type=RuntimeType.NATIVE_PLUGIN.value,
        package_name="arbitrary-malicious-package; rm -rf /",
    )
    reg.get_app = AsyncMock(return_value=malicious_app)

    res = await installer.install_app("malicious")
    assert res["ok"] is False
    assert "Security violation" in res["error"]


@pytest.mark.asyncio
async def test_uninstall_app_cleans_up(mock_managers):
    reg, state, auth, installer = mock_managers

    mock_cfg = Config()
    mock_cfg.tools.mcp_servers["github"] = MCPServerConfig(
        type="streamableHttp", url="https://api.github.com/mcp"
    )

    with patch("shibaclaw.apps.installer._get_agent_mgr") as mock_get_mgr, \
            patch("shibaclaw.apps.installer.save_config"):
        mock_agent_mgr = MagicMock()
        mock_get_mgr.return_value = mock_agent_mgr
        mock_agent_mgr.config = mock_cfg
        mock_agent_mgr.reload_config = AsyncMock()

        # Pre-populate state
        from shibaclaw.apps.models import InstalledAppRecord
        state.save_installed_record(InstalledAppRecord(id="github", name="GitHub", source="curated", runtime_type="mcp_remote"))

        res = await installer.uninstall_app("github")
        assert res["ok"] is True

        assert "github" not in mock_cfg.tools.mcp_servers
        assert "github" not in state.get_installed_records()
        auth.disconnect_app.assert_awaited_with("github")


@pytest.mark.asyncio
async def test_toggle_app_enabled(mock_managers):
    reg, state, auth, installer = mock_managers

    mock_cfg = Config()
    mock_cfg.tools.mcp_servers["github"] = MCPServerConfig(
        type="streamableHttp", url="https://api.github.com/mcp", enabled_tools=["*"]
    )

    with patch("shibaclaw.apps.installer._get_agent_mgr") as mock_get_mgr, \
            patch("shibaclaw.apps.installer.save_config"):
        mock_agent_mgr = MagicMock()
        mock_get_mgr.return_value = mock_agent_mgr
        mock_agent_mgr.config = mock_cfg
        mock_agent_mgr.reload_config = AsyncMock()

        from shibaclaw.apps.models import InstalledAppRecord
        state.save_installed_record(InstalledAppRecord(id="github", name="GitHub", source="curated", runtime_type="mcp_remote"))

        # Disable
        res = await installer.toggle_app_enabled("github", False)
        assert res["ok"] is True
        assert res["enabled"] is False
        assert mock_cfg.tools.mcp_servers["github"].enabled_tools == []

        # Enable
        res = await installer.toggle_app_enabled("github", True)
        assert res["ok"] is True
        assert res["enabled"] is True
        assert mock_cfg.tools.mcp_servers["github"].enabled_tools == ["*"]


@pytest.mark.asyncio
async def test_update_enabled_tools(mock_managers):
    reg, state, auth, installer = mock_managers

    mock_cfg = Config()
    mock_cfg.tools.mcp_servers["github"] = MCPServerConfig(
        type="streamableHttp", url="https://api.github.com/mcp", enabled_tools=["*"]
    )

    with patch("shibaclaw.apps.installer._get_agent_mgr") as mock_get_mgr, \
            patch("shibaclaw.apps.installer.save_config"):
        mock_agent_mgr = MagicMock()
        mock_get_mgr.return_value = mock_agent_mgr
        mock_agent_mgr.config = mock_cfg
        mock_agent_mgr.reload_config = AsyncMock()

        res = await installer.update_enabled_tools("github", ["read_repositories", "create_issue"])
        assert res["ok"] is True
        assert mock_cfg.tools.mcp_servers["github"].enabled_tools == ["read_repositories", "create_issue"]
