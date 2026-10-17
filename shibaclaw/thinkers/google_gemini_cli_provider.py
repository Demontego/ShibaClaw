"""Google Gemini CLI provider."""

import httpx
from loguru import logger

from shibaclaw.security.oauth_store import OAuthTokenStore
from shibaclaw.thinkers.openai_provider import OpenAIThinker


class GoogleGeminiCLIThinker(OpenAIThinker):
    """
    Thinker for Google Gemini CLI OAuth.

    Reads the OAuth token from OAuthTokenStore,
    refreshes it if necessary,
    and calls the OpenAI-compatible Gemini API endpoint.
    """

    _session_label = "Google Gemini CLI"

    def __init__(self, default_model: str = "gemini-2.0-flash"):
        self._store = OAuthTokenStore()

        super().__init__(
            api_key="dummy",
            api_base="https://generativelanguage.googleapis.com/v1beta/openai/",
            default_model=default_model,
        )

    async def _get_session_token(self) -> str:
        """Get or refresh the Google OAuth access token."""
        token_data = self._store.load_token("google_gemini_cli")
        if not token_data:
            raise ValueError(
                "Google Gemini CLI not authenticated. "
                "Run `shibaclaw provider login google-gemini-cli` or use the WebUI to login."
            )

        if not self._store.is_expired("google_gemini_cli", buffer_seconds=60):
            return token_data.get("access_token", "")

        refresh_token = token_data.get("refresh_token")
        if not refresh_token:
            raise ValueError(
                "Google Gemini CLI token expired and no refresh token available. "
                "Please login again."
            )

        from shibaclaw.cli.subscription_oauth import gemini_client

        client_id, client_secret = gemini_client()

        if not client_id:
            raise ValueError(
                "SHIBACLAW_GEMINI_OAUTH_CLIENT_ID environment variable is required to refresh Google Gemini CLI token."
            )

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )

            if resp.status_code != 200:
                err_text = resp.text
                try:
                    err_json = resp.json()
                    err_text = err_json.get("error_description", err_json.get("error", err_text))
                    if err_json.get("error") == "invalid_grant":
                        # Mark as disconnected
                        self._store.delete_token("google_gemini_cli")
                        raise ValueError(
                            "Google Gemini CLI session expired (invalid_grant). Please reconnect in the WebUI."
                        )
                except Exception:
                    pass
                raise RuntimeError(
                    f"Failed to refresh Google Gemini CLI token: {resp.status_code} - {err_text}"
                )

            new_token_data = resp.json()
            # Preserve refresh token if not returned in response
            if "refresh_token" not in new_token_data:
                new_token_data["refresh_token"] = refresh_token

            self._store.save_token("google_gemini_cli", new_token_data)
            return new_token_data.get("access_token", "")

    async def get_available_models(self) -> list[dict[str, str]]:
        try:
            session_token = await self._get_session_token()
            self._client.api_key = session_token
        except Exception as e:
            logger.error("Failed to authenticate Google Gemini CLI while fetching models: {}", e)
            return []

        models = await super().get_available_models()
        if models:
            return models
        from shibaclaw.cli.model_info import get_all_models

        # shortcut: the CLI token is accepted for chat, but the model-list call returns 403.
        return [{"id": mid, "name": mid} for mid in get_all_models() if mid.startswith("gemini-")]
