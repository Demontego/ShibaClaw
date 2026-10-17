from __future__ import annotations

import json
import pytest
from starlette.requests import Request
from unittest.mock import AsyncMock, patch

from shibaclaw.webui.routers.apps import (
    api_list_apps,
    api_get_app,
    api_install_app,
    api_uninstall_app,
    api_enable_app,
    api_disable_app,
    api_connect_app,
    api_disconnect_app,
    api_update_app_tools,
    api_create_custom_app,
)


def _make_request(method: str, path: str, body: dict | None = None, query: dict | None = None, path_params: dict | None = None):
    raw_query = "&".join(f"{k}={v}" for k, v in (query or {}).items()).encode()
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": raw_query,
        "headers": [(b"content-type", b"application/json")],
        "path_params": path_params or {},
    }
    async def receive():
        return {
            "type": "http.request",
            "body": json.dumps(body or {}).encode(),
        }
    return Request(scope, receive)


@pytest.mark.asyncio
async def test_api_list_apps():
    req = _make_request("GET", "/api/apps")
    resp = await api_list_apps(req)
    assert resp.status_code == 200
    data = json.loads(resp.body.decode())
    assert "apps" in data
    assert len(data["apps"]) > 0
    # Verified that apps list has IDs
    ids = [a["id"] for a in data["apps"]]
    assert "google-workspace" in ids
    assert "github" in ids


@pytest.mark.asyncio
async def test_api_get_app():
    req = _make_request("GET", "/api/apps/github", path_params={"app_id": "github"})
    resp = await api_get_app(req)
    assert resp.status_code == 200
    data = json.loads(resp.body.decode())
    assert data["app"]["id"] == "github"
    assert data["app"]["name"] == "GitHub"


@pytest.mark.asyncio
async def test_api_get_app_not_found():
    req = _make_request("GET", "/api/apps/nonexistent-xyz", path_params={"app_id": "nonexistent-xyz"})
    resp = await api_get_app(req)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_install_and_uninstall():
    with patch("shibaclaw.webui.routers.apps._installer.install_app", new_callable=AsyncMock) as mock_inst, \
         patch("shibaclaw.webui.routers.apps._installer.uninstall_app", new_callable=AsyncMock) as mock_uninst:
        mock_inst.return_value = {"ok": True, "installed": True}
        mock_uninst.return_value = {"ok": True, "uninstalled": True}

        # Install
        req = _make_request("POST", "/api/apps/notion/install", path_params={"app_id": "notion"})
        resp = await api_install_app(req)
        assert resp.status_code == 200
        mock_inst.assert_awaited_with("notion")

        # Uninstall
        req2 = _make_request("POST", "/api/apps/notion/uninstall", path_params={"app_id": "notion"})
        resp2 = await api_uninstall_app(req2)
        assert resp2.status_code == 200
        mock_uninst.assert_awaited_with("notion")


@pytest.mark.asyncio
async def test_api_enable_and_disable():
    with patch("shibaclaw.webui.routers.apps._installer.toggle_app_enabled", new_callable=AsyncMock) as mock_toggle:
        mock_toggle.return_value = {"ok": True}

        req = _make_request("POST", "/api/apps/github/enable", path_params={"app_id": "github"})
        resp = await api_enable_app(req)
        assert resp.status_code == 200
        mock_toggle.assert_awaited_with("github", True)

        req2 = _make_request("POST", "/api/apps/github/disable", path_params={"app_id": "github"})
        resp2 = await api_disable_app(req2)
        assert resp2.status_code == 200
        mock_toggle.assert_awaited_with("github", False)


@pytest.mark.asyncio
async def test_api_connect_and_disconnect():
    with patch("shibaclaw.webui.routers.apps._auth_manager.connect_app", new_callable=AsyncMock) as mock_conn, \
         patch("shibaclaw.webui.routers.apps._auth_manager.disconnect_app", new_callable=AsyncMock) as mock_disconn:
        mock_conn.return_value = {"ok": True, "status": "connected"}
        mock_disconn.return_value = {"ok": True, "status": "disconnected"}

        req = _make_request("POST", "/api/apps/github/connect", body={"api_key": "token123"}, path_params={"app_id": "github"})
        resp = await api_connect_app(req)
        assert resp.status_code == 200

        req2 = _make_request("POST", "/api/apps/github/disconnect", path_params={"app_id": "github"})
        resp2 = await api_disconnect_app(req2)
        assert resp2.status_code == 200
        mock_disconn.assert_awaited_with("github")


@pytest.mark.asyncio
async def test_api_update_tools():
    with patch("shibaclaw.webui.routers.apps._installer.update_enabled_tools", new_callable=AsyncMock) as mock_upd:
        mock_upd.return_value = {"ok": True, "enabled_tools": ["repo_get"]}

        req = _make_request("PUT", "/api/apps/github/tools", body={"enabled_tools": ["repo_get"]}, path_params={"app_id": "github"})
        resp = await api_update_app_tools(req)
        assert resp.status_code == 200
        mock_upd.assert_awaited_with("github", ["repo_get"])


@pytest.mark.asyncio
async def test_api_create_custom_app():
    with patch("shibaclaw.webui.routers.apps._installer.install_app", new_callable=AsyncMock) as mock_inst:
        mock_inst.return_value = {"ok": True, "installed": True}

        req = _make_request("POST", "/api/apps/custom", body={
            "name": "Internal Docs MCP",
            "runtime_type": "mcp_remote",
            "url": "https://mcp.internal.corp/mcp",
        })
        resp = await api_create_custom_app(req)
        assert resp.status_code == 200
        mock_inst.assert_awaited()
