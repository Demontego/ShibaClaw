from shibaclaw.thinkers.xai import GROK_CLIENT_VERSION, xai_api_base, xai_client_headers


def test_subscription_proxy_sends_cli_version():
    base = xai_api_base("oauth-token")
    headers = xai_client_headers(base)
    assert headers["x-grok-client-version"] == GROK_CLIENT_VERSION
    assert headers["x-grok-client-mode"] == "cli"


def test_console_key_stays_on_api():
    assert xai_api_base("xai-console-key") == "https://api.x.ai/v1"
    assert xai_client_headers("https://api.x.ai/v1") == {}
