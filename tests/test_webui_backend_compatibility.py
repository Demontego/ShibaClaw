"""Backend contracts required by the retained v1.0.3 WebUI."""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request

from shibaclaw.config.schema import Config
from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.routers import oauth, settings


def _request(payload=None, *, job_id=None):
    async def receive():
        return {"type": "http.request", "body": json.dumps(payload or {}).encode()}

    return Request(
        {
            "type": "http",
            "method": "POST" if payload is not None else "GET",
            "path": "/api/models",
            "query_string": b"",
            "headers": [],
            "path_params": {"job_id": job_id} if job_id else {},
        },
        receive,
    )


@pytest.fixture
def isolated_backend(monkeypatch, tmp_path):
    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path)
    monkeypatch.setattr(agent_manager, "config", cfg)
    monkeypatch.setattr(agent_manager, "oauth_jobs", {})
    monkeypatch.setattr(agent_manager, "reload_config", AsyncMock())
    monkeypatch.setattr(settings, "_models_cache", None)
    monkeypatch.setattr(settings, "_models_cache_generation", 0)
    monkeypatch.setattr("shibaclaw.config.loader.get_config_path", lambda: tmp_path / "config.json")
    monkeypatch.setattr("shibaclaw.config.loader._get_cm_if_active", lambda: None)
    fetch = AsyncMock(side_effect=[([{"id": "before"}], []), ([{"id": "after"}], [])])
    monkeypatch.setattr(settings, "_fetch_all_configured_provider_models", fetch)
    return fetch


async def _assert_initial_catalog_is_cached(fetch):
    for _ in range(2):
        response = await settings.api_models_get(_request())
        assert json.loads(response.body)["models"] == [{"id": "before"}]
    assert fetch.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["settings", "login_done", "disconnect"])
async def test_models_refresh_after_account_or_settings_changes(isolated_backend, monkeypatch, change):
    fetch = isolated_backend
    await _assert_initial_catalog_is_cached(fetch)
    if change == "settings":
        response = await settings.api_settings_post(
            _request({"providers": {"custom": {"apiBase": "http://127.0.0.1:1234/v1"}}})
        )
        assert json.loads(response.body) == {"status": "updated", "restarted": False}
    elif change == "login_done":
        agent_manager.oauth_jobs["login"] = {"status": "done", "logs": [], "_private": object()}
        response = await oauth.api_oauth_job(_request(job_id="login"))
        assert json.loads(response.body) == {"job": {"status": "done", "logs": []}}
    else:
        from shibaclaw.security.oauth_store import OAuthTokenStore

        monkeypatch.setattr(OAuthTokenStore, "__init__", lambda self: None)
        monkeypatch.setattr(OAuthTokenStore, "delete_token", lambda self, provider: None)
        response = await oauth.api_oauth_disconnect(_request({"provider": "xai"}))
        assert json.loads(response.body) == {"ok": True}
    assert response.status_code == 200
    response = await settings.api_models_get(_request())
    assert json.loads(response.body)["models"] == [{"id": "after"}]
    assert fetch.await_count == 2


@pytest.mark.asyncio
async def test_inflight_catalog_cannot_restore_cache_after_settings_change(isolated_backend, monkeypatch):
    started, finish = asyncio.Event(), asyncio.Event()

    async def fetch_catalog(cfg):
        started.set()
        await finish.wait()
        return [{"id": "before"}], []

    monkeypatch.setattr(settings, "_fetch_all_configured_provider_models", fetch_catalog)
    pending = asyncio.create_task(settings.api_models_get(_request()))
    await asyncio.wait_for(started.wait(), timeout=2)
    response = await settings.api_settings_post(_request({"agents": {"defaults": {"temperature": 0.5}}}))
    assert response.status_code == 200
    finish.set()
    await asyncio.wait_for(pending, timeout=2)
    assert settings._models_cache is None


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["anthropic", "google_gemini_cli"])
async def test_subscription_login_uses_existing_paste_job_contract(isolated_backend, monkeypatch, provider):
    from shibaclaw.cli import subscription_oauth as subscription
    from shibaclaw.security.oauth_store import OAuthTokenStore

    monkeypatch.setenv("SHIBACLAW_GEMINI_OAUTH_CLIENT_ID", "test-client")
    monkeypatch.setenv("SHIBACLAW_GEMINI_OAUTH_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr(subscription, "new_pkce", lambda: ("verifier", "challenge", "state"))
    monkeypatch.setattr(subscription, "exchange_claude_code", lambda *args: None)
    monkeypatch.setattr(subscription, "exchange_gemini_code", lambda *args: {"access_token": "test"})
    monkeypatch.setattr(OAuthTokenStore, "__init__", lambda self: None)
    monkeypatch.setattr(OAuthTokenStore, "save_token", lambda *args: None)

    response = await oauth.api_oauth_login(_request({"provider": provider}))
    login = json.loads(response.body)
    assert response.status_code == 200
    assert login["status"] == "awaiting_paste"
    assert login["console_url"].startswith("https://")
    assert login["instruction"]
    job_id = login["job_id"]
    response = await oauth.api_oauth_job(_request(job_id=job_id))
    job = json.loads(response.body)["job"]
    assert job["status"] == "awaiting_paste"
    assert job["console_url"] == login["console_url"]
    assert not any(key.startswith("_") for key in job)
    pasted = "code#state" if provider == "anthropic" else "code"
    response = await oauth.api_oauth_code(_request({"job_id": job_id, "code": pasted}))
    assert json.loads(response.body) == {"ok": True}

    async def wait_for_login():
        while agent_manager.oauth_jobs[job_id]["status"] == "awaiting_paste":
            await asyncio.sleep(0.001)

    await asyncio.wait_for(wait_for_login(), timeout=2)
    response = await oauth.api_oauth_job(_request(job_id=job_id))
    job = json.loads(response.body)["job"]
    assert job["status"] == "done"
    assert not any(key.startswith("_") for key in job)
