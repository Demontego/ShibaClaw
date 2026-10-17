from __future__ import annotations

import json
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, patch

from shibaclaw.apps.models import AppDefinition, TrustLevel, RuntimeType
from shibaclaw.apps.registry.curated import CuratedAppRegistry
from shibaclaw.apps.registry.mcp_registry import MCPRegistryProvider, _sanitize_app_id, _is_safe_remote_url
from shibaclaw.apps.registry.native import NativePluginRegistryProvider
from shibaclaw.apps.registry.manager import AppRegistryManager


@pytest.mark.asyncio
async def test_curated_registry_loads_bundled():
    reg = CuratedAppRegistry()
    apps = await reg.list_apps()
    assert len(apps) >= 5

    app_ids = {a.id for a in apps}
    assert "google-workspace" in app_ids
    assert "github" in app_ids
    assert "postgresql" in app_ids
    assert "whatsapp" in app_ids

    gw = await reg.get_app("google-workspace")
    assert gw is not None
    assert gw.name == "Google Workspace"
    assert gw.auth.type == "oauth2"
    assert gw.runtime_type == RuntimeType.MCP_REMOTE.value
    assert gw.trust_level == TrustLevel.VERIFIED.value


@pytest.mark.asyncio
async def test_curated_registry_malformed_metadata(tmp_path: Path):
    bad_file = tmp_path / "bad_registry.json"
    bad_file.write_text(json.dumps({"apps": [{"id": "valid", "name": "V", "description": "D"}, {"broken": True}]}), encoding="utf-8")

    reg = CuratedAppRegistry(bundled_path=bad_file)
    apps = await reg.list_apps()
    assert len(apps) == 1
    assert apps[0].id == "valid"


@pytest.mark.asyncio
async def test_curated_search():
    reg = CuratedAppRegistry()
    results = await reg.search_apps(query="gmail")
    assert any(a.id == "google-workspace" for a in results)

    cat_results = await reg.search_apps(category="databases")
    assert any(a.id == "postgresql" for a in cat_results)


def test_mcp_registry_url_validation():
    assert _is_safe_remote_url("https://mcp.github.com/mcp") is True
    assert _is_safe_remote_url("http://api.company.com/v1") is True
    assert _is_safe_remote_url("http://localhost:8000") is False
    assert _is_safe_remote_url("http://127.0.0.1:8000") is False
    assert _is_safe_remote_url("file:///etc/passwd") is False
    assert _is_safe_remote_url("javascript:alert(1)") is False


def test_mcp_sanitize_id():
    assert _sanitize_app_id("ac.inference.sh/mcp") == "ac-inference-sh-mcp"
    assert _sanitize_app_id("  @org/tool_name-- ") == "org-tool_name"


@pytest.mark.asyncio
async def test_mcp_registry_provider_cached_fallback(tmp_path: Path):
    provider = MCPRegistryProvider(cache_dir=tmp_path)
    sample_servers = [
        {
            "server": {
                "name": "io.github/sample-remote",
                "title": "Sample Remote Server",
                "description": "Remote test server",
                "remotes": [{"type": "streamable-http", "url": "https://mcp.sample.com"}],
            }
        }
    ]
    provider._write_cache(sample_servers)

    # When remote fails, falls back to cache
    with patch("httpx.AsyncClient.get", side_effect=Exception("Network down")):
        apps = await provider.list_apps()
        assert len(apps) == 1
        assert apps[0].id == "io-github-sample-remote"
        assert apps[0].runtime_type == RuntimeType.MCP_REMOTE.value
        assert apps[0].mcp_config["type"] == "streamableHttp"
        assert apps[0].trust_level == TrustLevel.COMMUNITY.value


@pytest.mark.asyncio
async def test_app_registry_manager_priority():
    curated_mock = AsyncMock(spec=CuratedAppRegistry)
    curated_mock.list_apps.return_value = [
        AppDefinition(id="github", name="GitHub Curated", description="Curated", source="curated")
    ]
    curated_mock.get_app.return_value = AppDefinition(id="github", name="GitHub Curated", description="Curated", source="curated")

    mcp_mock = AsyncMock(spec=MCPRegistryProvider)
    mcp_mock.list_apps.return_value = [
        AppDefinition(id="github", name="GitHub MCP", description="From MCP", source="mcp_registry"),
        AppDefinition(id="unique-mcp", name="Unique MCP", description="Only MCP", source="mcp_registry"),
    ]
    mcp_mock.get_app.return_value = None

    native_mock = AsyncMock(spec=NativePluginRegistryProvider)
    native_mock.list_apps.return_value = []
    native_mock.get_app.return_value = None

    mgr = AppRegistryManager(
        curated_provider=curated_mock,
        native_provider=native_mock,
        mcp_provider=mcp_mock,
    )

    all_apps = await mgr.list_all()
    app_map = {a.id: a for a in all_apps}

    assert len(all_apps) == 2
    assert app_map["github"].name == "GitHub Curated"
    assert app_map["github"].source == "curated"
    assert "unique-mcp" in app_map
