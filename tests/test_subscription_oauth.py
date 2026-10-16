import asyncio
import threading

import pytest

from shibaclaw.cli.subscription_oauth import (
    CLAUDE_CLIENT_ID,
    GEMINI_REDIRECT_URI,
    claude_authorize_url,
    gemini_authorize_url,
    split_claude_paste,
)


def test_split_claude_paste_checks_state():
    assert split_claude_paste("abc#xyz", "xyz") == "abc"
    with pytest.raises(ValueError):
        split_claude_paste("abc#nope", "xyz")
    with pytest.raises(ValueError):
        split_claude_paste("abc", "xyz")


def test_login_urls_point_at_the_public_clients(monkeypatch):
    monkeypatch.setenv("SHIBACLAW_GEMINI_OAUTH_CLIENT_ID", "test-client")
    monkeypatch.setenv("SHIBACLAW_GEMINI_OAUTH_CLIENT_SECRET", "test-secret")
    claude_url = claude_authorize_url("challenge", "state")
    gemini_url = gemini_authorize_url("challenge", "state")
    assert CLAUDE_CLIENT_ID in claude_url
    assert "oauth%2Fcode%2Fcallback" in claude_url
    assert "test-client" in gemini_url
    assert GEMINI_REDIRECT_URI.split("://", 1)[1].replace("/", "%2F") in gemini_url


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["anthropic", "gemini"])
async def test_subscription_exchange_runs_off_event_loop(monkeypatch, kind):
    import shibaclaw.cli.subscription_oauth as subscription
    from shibaclaw.security.oauth_store import OAuthTokenStore

    loop_thread = threading.get_ident()
    exchange_threads = []
    saved = []
    monkeypatch.setattr(subscription, "new_pkce", lambda: ("verifier", "challenge", "state"))
    monkeypatch.setenv("SHIBACLAW_GEMINI_OAUTH_CLIENT_ID", "test-client")
    monkeypatch.setenv("SHIBACLAW_GEMINI_OAUTH_CLIENT_SECRET", "test-secret")

    def exchange(*args):
        exchange_threads.append(threading.get_ident())
        assert threading.get_ident() != loop_thread
        if kind == "anthropic":
            assert args == ("code", "state", "verifier")
        else:
            assert args == ("code", "verifier")
        return {"access_token": "test-token"}

    monkeypatch.setattr(subscription, "exchange_claude_code", exchange)
    monkeypatch.setattr(subscription, "exchange_gemini_code", exchange)
    monkeypatch.setattr(OAuthTokenStore, "__init__", lambda self: None)
    monkeypatch.setattr(
        OAuthTokenStore, "save_token", lambda self, provider, token: saved.append((provider, token))
    )
    jobs = {"job": {"logs": []}}
    await subscription.start_subscription_login("job", jobs, kind)
    jobs["job"]["_code_holder"]["value"] = "code#state" if kind == "anthropic" else "code"
    jobs["job"]["_code_event"].set()

    async def wait_for_login():
        while jobs["job"]["status"] == "awaiting_paste":
            await asyncio.sleep(0.001)

    await asyncio.wait_for(wait_for_login(), timeout=2)
    assert jobs["job"]["status"] == "done"
    assert len(exchange_threads) == 1
    if kind == "gemini":
        assert saved == [("google_gemini_cli", {"access_token": "test-token"})]
