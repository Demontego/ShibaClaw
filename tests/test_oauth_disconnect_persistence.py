import json
from pathlib import Path
from types import SimpleNamespace

from cryptography.fernet import Fernet
import pytest

from shibaclaw.config.schema import Config
from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.routers import oauth


@pytest.fixture
def isolated_auth(monkeypatch, tmp_path):
    import shibaclaw.security.credential_manager as credentials

    monkeypatch.setattr(credentials, "_load_or_create_key", lambda _: Fernet.generate_key())
    manager = credentials.CredentialManager(store_dir=tmp_path / "vault")
    monkeypatch.setattr(credentials, "get_credential_manager", lambda: manager)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(oauth.os.path, "expanduser", lambda _: str(tmp_path))
    monkeypatch.setenv("OAUTH_CLI_KIT_TOKEN_PATH", str(tmp_path / "oauth.json"))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GITHUB_COPILOT_TOKEN", raising=False)
    monkeypatch.setattr(agent_manager, "config", Config())

    async def reload_config(config):
        pass

    monkeypatch.setattr(agent_manager, "reload_config", reload_config)
    return manager


def _request(provider):
    async def payload():
        return {"provider": provider}

    return SimpleNamespace(json=payload)


def _status(provider):
    return next(p for p in oauth.get_oauth_providers_status() if p["name"] == provider)["status"]


@pytest.mark.asyncio
async def test_codex_disconnect_prevents_reimport_and_preserves_cli_login(isolated_auth, tmp_path):
    from shibaclaw.cli.auth import _is_oauth_authenticated, _oauth_provider_status
    from shibaclaw.security.codex_oauth import get_codex_token
    from shibaclaw.thinkers.openai_codex_provider import _get_codex_token

    cli_auth = tmp_path / ".codex" / "auth.json"
    cli_auth.parent.mkdir()
    original = json.dumps({"tokens": {
        "access_token": "test-access", "refresh_token": "test-refresh", "account_id": "test-account",
    }})
    cli_auth.write_text(original, encoding="utf-8")
    # Initial discovery remains compatible with oauth-cli-kit's CLI import.
    assert get_codex_token().access == "test-access"
    assert _status("openai_codex") == "configured"
    mirror = tmp_path / ".config" / "shibaclaw" / "openai_codex" / "credentials.json"
    mirror.parent.mkdir(parents=True)
    mirror.write_text("{}")

    response = await oauth.api_oauth_disconnect(_request("openai-codex"))
    assert response.status_code == 200
    assert not (tmp_path / "oauth.json").exists()
    assert not mirror.exists()
    assert cli_auth.read_text(encoding="utf-8") == original
    for _ in range(2):
        assert _status("openai_codex") == "not_configured"
        assert not _is_oauth_authenticated(SimpleNamespace(name="openai_codex"))
        assert "not authenticated" in _oauth_provider_status(SimpleNamespace(name="openai_codex"))
        with pytest.raises(RuntimeError, match="credentials not found"):
            _get_codex_token()
    assert not (tmp_path / "oauth.json").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["openrouter", "xai", "google_gemini_cli"])
async def test_vault_disconnect_persists_after_new_manager(isolated_auth, provider):
    import shibaclaw.security.credential_manager as credentials

    isolated_auth.set_secret("oauth_tokens", provider, {"access_token": "test-token"})
    if provider == "openrouter":
        isolated_auth.set_secret("providers", "openrouter.api_key", "test-key")
    assert _status(provider) == "configured"
    response = await oauth.api_oauth_disconnect(_request(provider))
    assert response.status_code == 200
    fresh = credentials.CredentialManager(store_dir=isolated_auth._store_path.parent)
    assert fresh.get_secret("oauth_tokens", provider) is None
    assert fresh.get_secret("providers", "openrouter.api_key") is None
    assert _status(provider) == "not_configured"


@pytest.mark.asyncio
@pytest.mark.parametrize(("provider", "env_name"), [
    ("openrouter", "OPENROUTER_API_KEY"), ("github_copilot", "GITHUB_COPILOT_TOKEN"),
])
async def test_disconnect_reports_environment_credentials(isolated_auth, monkeypatch, provider, env_name):
    monkeypatch.setenv(env_name, "test-env-secret")
    response = await oauth.api_oauth_disconnect(_request(provider))
    assert response.status_code == 409
    assert env_name in json.loads(response.body)["error"]
    assert "test-env-secret" not in response.body.decode()
    assert _status(provider) == "configured"


@pytest.mark.asyncio
async def test_github_disconnect_does_not_hide_delete_failure(isolated_auth, monkeypatch, tmp_path):
    path = tmp_path / ".shibaclaw" / "github_copilot" / "access-token"
    path.parent.mkdir(parents=True)
    path.write_text("test-token")

    def fail_remove(path):
        raise PermissionError("private path")

    monkeypatch.setattr(oauth.os, "remove", fail_remove)
    response = await oauth.api_oauth_disconnect(_request("github_copilot"))
    assert response.status_code == 500
    assert "private path" not in response.body.decode()
    assert _status("github_copilot") == "configured"


@pytest.mark.asyncio
async def test_github_disconnect_removes_token_and_is_idempotent(isolated_auth, tmp_path):
    path = tmp_path / ".shibaclaw" / "github_copilot" / "access-token"
    path.parent.mkdir(parents=True)
    path.write_text("test-token")
    for _ in range(2):
        assert (await oauth.api_oauth_disconnect(_request("github_copilot"))).status_code == 200
        assert _status("github_copilot") == "not_configured"


@pytest.mark.asyncio
@pytest.mark.parametrize("already_disconnected", [False, True])
async def test_codex_disconnect_reports_delete_failure(
    isolated_auth, monkeypatch, tmp_path, already_disconnected
):
    from shibaclaw.security.codex_oauth import _disconnect_marker

    token_path = tmp_path / "oauth.json"
    token_path.write_text("{}")
    marker = _disconnect_marker()
    if already_disconnected:
        marker.parent.mkdir(parents=True)
        marker.touch()
    original_unlink = Path.unlink

    def fail_unlink(path, *args, **kwargs):
        if path == token_path:
            raise PermissionError("private path")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_unlink)
    for _ in range(2):
        response = await oauth.api_oauth_disconnect(_request("openai_codex"))
        assert response.status_code == 500
        assert token_path.exists()
        assert marker.exists() == already_disconnected
        assert "private path" not in response.body.decode()


@pytest.mark.asyncio
async def test_explicit_codex_cli_login_restores_auth_after_disconnect(isolated_auth, monkeypatch):
    from oauth_cli_kit.providers import OPENAI_CODEX_PROVIDER
    from oauth_cli_kit.storage import FileTokenStorage
    from oauth_cli_kit.models import OAuthToken
    from shibaclaw.cli.auth import _login_openai_codex
    from shibaclaw.security.codex_oauth import _disconnect_marker
    import time

    assert (await oauth.api_oauth_disconnect(_request("openai_codex"))).status_code == 200
    assert _disconnect_marker().exists()

    def explicit_login(**kwargs):
        token = OAuthToken(access="new-access", refresh="new-refresh",
                           expires=int(time.time() * 1000) + 3600000, account_id="account")
        FileTokenStorage(token_filename=OPENAI_CODEX_PROVIDER.token_filename).save(token)
        return token

    monkeypatch.setattr("oauth_cli_kit.login_oauth_interactive", explicit_login)
    _login_openai_codex()
    assert not _disconnect_marker().exists()
    assert _status("openai_codex") == "configured"


@pytest.mark.asyncio
async def test_vault_disconnect_does_not_hide_write_failure(isolated_auth, monkeypatch):
    isolated_auth.set_secret("oauth_tokens", "xai", {"access_token": "test-token"})
    original_write = Path.write_bytes

    def fail_write(path, data):
        if path == isolated_auth._store_path:
            raise PermissionError("private path")
        return original_write(path, data)

    monkeypatch.setattr(Path, "write_bytes", fail_write)
    response = await oauth.api_oauth_disconnect(_request("xai"))
    assert response.status_code == 500
    assert "private path" not in response.body.decode()
    assert _status("xai") == "configured"


@pytest.mark.asyncio
async def test_disconnect_rejects_unknown_provider(isolated_auth):
    isolated_auth.set_secret("oauth_tokens", "unrelated-mcp", {"access_token": "keep"})
    response = await oauth.api_oauth_disconnect(_request("unrelated-mcp"))
    assert response.status_code == 404
    assert isolated_auth.get_secret("oauth_tokens", "unrelated-mcp") == {"access_token": "keep"}
