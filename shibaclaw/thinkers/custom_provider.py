"""Custom OpenAI-compatible provider — thin wrapper over OpenAIThinker."""

from __future__ import annotations

from shibaclaw.thinkers.openai_provider import OpenAIThinker


class CustomThinker(OpenAIThinker):
    """Local/custom OpenAI-compatible endpoint with session-affinity headers."""

    def __init__(
        self,
        api_key: str = "no-key",
        api_base: str = "http://localhost:8000/v1",
        default_model: str = "default",
        extra_headers: dict[str, str] | None = None,
    ):
        super().__init__(
            api_key=api_key,
            api_base=api_base,
            default_model=default_model,
            extra_headers=extra_headers,
            provider_name="custom",
        )
