from types import SimpleNamespace

import httpx
import pytest

from shibaclaw.thinkers import openai_codex_provider as codex


def _mock_codex_api(monkeypatch, handler):
    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        codex.httpx,
        "AsyncClient",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handler), timeout=kwargs["timeout"]),
    )
    monkeypatch.setattr(
        codex,
        "_get_codex_token",
        lambda: SimpleNamespace(access="oauth-token", account_id="account-123"),
    )


@pytest.mark.asyncio
async def test_codex_models_uses_versioned_oauth_catalog_and_hides_internal_models(monkeypatch):
    def handler(request):
        assert str(request.url) == (
            f"{codex.DEFAULT_MODELS_URL}?client_version={codex.CODEX_CLIENT_VERSION}"
        )
        assert request.headers["authorization"] == "Bearer oauth-token"
        assert request.headers["chatgpt-account-id"] == "account-123"
        return httpx.Response(
            200,
            json={
                "models": [
                    {"slug": "gpt-6-sol", "display_name": "GPT-6 Sol", "visibility": "list"},
                    {"slug": "gpt-reserve", "display_name": "Reserve", "visibility": "hide"},
                    {"id": "gpt-5.6-terra", "name": "GPT-5.6 Terra"},
                ]
            },
        )

    _mock_codex_api(monkeypatch, handler)

    assert await codex.OpenAICodexThinker().get_available_models() == [
        {"id": "openai-codex/gpt-6-sol", "name": "GPT-6 Sol"},
        {"id": "openai-codex/gpt-5.6-terra", "name": "GPT-5.6 Terra"},
    ]


@pytest.mark.asyncio
async def test_codex_models_failure_does_not_show_stale_api_models(monkeypatch):
    _mock_codex_api(monkeypatch, lambda request: httpx.Response(400))

    with pytest.raises(RuntimeError, match="Codex /models returned HTTP 400"):
        await codex.OpenAICodexThinker().get_available_models()


@pytest.mark.asyncio
async def test_codex_models_empty_catalog_stays_empty(monkeypatch):
    _mock_codex_api(monkeypatch, lambda request: httpx.Response(200, json={"models": []}))

    assert await codex.OpenAICodexThinker().get_available_models() == []
