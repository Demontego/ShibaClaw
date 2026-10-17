from __future__ import annotations

import pytest
from types import SimpleNamespace
from shibaclaw.apps.models import (
    AppDefinition,
    AppAuthDefinition,
    AppAuthField,
    InstalledAppRecord,
    TrustLevel,
    RuntimeType,
    AuthType,
    AuthState,
)
from shibaclaw.apps.state import AppStateManager


def test_app_definition_defaults():
    app = AppDefinition(
        id="test-app",
        name="Test App",
        description="A test integration",
    )
    assert app.id == "test-app"
    assert app.name == "Test App"
    assert app.icon == "extension"
    assert app.category == "productivity"
    assert app.source == "curated"
    assert app.runtime_type == RuntimeType.MCP_REMOTE.value
    assert app.trust_level == TrustLevel.OFFICIAL.value
    assert app.installed is False
    assert app.enabled is True
    assert app.status == "ready"
    assert app.tools_count == 0
    assert app.enabled_tools == ["*"]
    assert app.update_available is False
    assert app.installed_version is None


def test_app_auth_definition():
    auth = AppAuthDefinition(
        type=AuthType.OAUTH2.value,
        auth_url="https://provider.com/oauth/auth",
        token_url="https://provider.com/oauth/token",
        client_id="client123",
        scopes=["read", "write"],
        requires_client_credentials=True,
        fields=[
            AppAuthField(key="client_id", label="Client ID", type="text"),
            AppAuthField(key="client_secret", label="Client Secret", type="password"),
        ],
    )
    assert auth.type == "oauth2"
    assert auth.requires_client_credentials is True
    assert len(auth.fields) == 2
    assert auth.fields[1].type == "password"


def test_installed_app_record():
    rec = InstalledAppRecord(
        id="github",
        name="GitHub",
        source="curated",
        runtime_type="mcp_remote",
        version="1.0.0",
        installed_at=123456789.0,
        enabled=True,
        auth_state=AuthState.CONNECTED.value,
        enabled_tools=["repo", "issue"],
        mcp_server_name="github",
    )
    assert rec.id == "github"
    assert rec.auth_state == "connected"
    assert rec.enabled_tools == ["repo", "issue"]


@pytest.mark.parametrize(
    ("catalog", "installed", "expected"),
    [
        ("1.2.0", "1.1.9", True),
        ("1.2", "1.2.0", False),
        ("1.1.9", "1.2.0", False),
        ("v2.0", "1.9.9", True),
        ("latest", "1.0.0", False),
    ],
)
def test_catalog_update_requires_newer_comparable_version(catalog, installed, expected):
    assert AppStateManager._has_newer_version(catalog, installed) is expected


def test_installed_app_exposes_update_availability():
    state = AppStateManager.__new__(AppStateManager)
    state.resolve_auth_state = lambda app, cfg: AuthState.CONNECTED.value
    cfg = SimpleNamespace(tools=SimpleNamespace(mcp_servers={}))
    app = AppDefinition(id="test-app", name="Test App", description="Test", version="1.2.0")
    record = InstalledAppRecord(id=app.id, name=app.name, version="1.1.0")

    enriched = state.enrich_app_state(app, cfg, records={app.id: record})

    assert enriched.installed_version == "1.1.0"
    assert enriched.update_available is True
