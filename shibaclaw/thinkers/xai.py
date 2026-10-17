"""xAI endpoints. The X Subscription session is not a console API key."""

# Issuer https://auth.x.ai/.well-known/openid-configuration (accounts.x.ai device login is closed).
XAI_CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
XAI_DEVICE_CODE_URL = "https://auth.x.ai/oauth2/device/code"
XAI_TOKEN_URL = "https://auth.x.ai/oauth2/token"
XAI_SCOPE = "openid profile email offline_access grok-cli:access api:access"
XAI_SUBSCRIPTION_API_BASE = "https://cli-chat-proxy.grok.com/v1"
XAI_API_KEY_BASE = "https://api.x.ai/v1"
# shortcut: proxy floor from the 426 body, bump when that body names a higher version
GROK_CLIENT_VERSION = "1.0.13"


def xai_api_base(token: str | None) -> str:
    """Subscription OAuth uses the Grok inference proxy. Console keys stay on api.x.ai."""
    if token and token.startswith("xai-"):
        return XAI_API_KEY_BASE
    return XAI_SUBSCRIPTION_API_BASE


def xai_client_headers(api_base: str | None) -> dict[str, str]:
    """The Grok proxy rejects subscription calls that omit a CLI version."""
    if api_base and "cli-chat-proxy.grok.com" in api_base:
        return {
            "x-grok-client-mode": "cli",
            "x-grok-client-version": GROK_CLIENT_VERSION,
        }
    return {}
