"""Gateway token resolution. Empty stays open for local installs."""

from shibaclaw.config.schema import GatewayConfig


def test_resolve_token_prefers_env(monkeypatch):
    monkeypatch.setenv("SHIBACLAW_GATEWAY_TOKEN", "from-env")
    assert GatewayConfig(token="from-file").resolve_token() == "from-env"


def test_resolve_token_uses_config_field(monkeypatch):
    monkeypatch.delenv("SHIBACLAW_GATEWAY_TOKEN", raising=False)
    assert GatewayConfig(token="from-file").resolve_token() == "from-file"


def test_resolve_token_empty_without_sources(monkeypatch):
    monkeypatch.delenv("SHIBACLAW_GATEWAY_TOKEN", raising=False)
    assert GatewayConfig().resolve_token() == ""
