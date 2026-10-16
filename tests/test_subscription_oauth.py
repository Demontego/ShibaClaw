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


def test_login_urls_point_at_the_public_clients(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SHIBACLAW_GEMINI_OAUTH_CLIENT_ID", "test-client")
    monkeypatch.setenv("SHIBACLAW_GEMINI_OAUTH_CLIENT_SECRET", "test-secret")
    claude_url = claude_authorize_url("challenge", "state")
    gemini_url = gemini_authorize_url("challenge", "state")
    assert "test-client" in gemini_url
    assert CLAUDE_CLIENT_ID in claude_url
    assert "oauth%2Fcode%2Fcallback" in claude_url
    assert GEMINI_REDIRECT_URI.split("://", 1)[1].replace("/", "%2F") in gemini_url
