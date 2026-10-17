import asyncio
from types import SimpleNamespace

import httpx
import pytest
from openai import AsyncOpenAI

from shibaclaw.thinkers.openai_provider import OpenAIThinker, _merge_reasoning_details


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("base_url", "uses_gemini_catalog"),
    [
        ("https://generativelanguage.googleapis.com/v1beta/openai/", True),
        ("https://generativelanguage.googleapis.com.evil.example/v1/", False),
    ],
)
async def test_model_catalog_requires_exact_gemini_hostname(base_url, uses_gemini_catalog):
    calls = {"openai": 0, "gemini": 0}

    class FakeModels:
        async def list(self):
            calls["openai"] += 1
            return SimpleNamespace(data=[{"id": "openai-compatible"}])

    thinker = object.__new__(OpenAIThinker)
    thinker._client = SimpleNamespace(base_url=httpx.URL(base_url), models=FakeModels())

    async def gemini_catalog():
        calls["gemini"] += 1
        return [{"id": "gemini-catalog"}]

    thinker._gemini_catalog = gemini_catalog

    models = await thinker._catalog_rows()

    assert calls["gemini"] == int(uses_gemini_catalog)
    assert calls["openai"] == int(not uses_gemini_catalog)
    assert models == [{"id": "gemini-catalog" if uses_gemini_catalog else "openai-compatible"}]


@pytest.mark.asyncio
@pytest.mark.parametrize("host", ["localhost", "127.0.0.1"])
async def test_local_model_catalog_preserves_configured_auth_and_headers(host):
    requests = []

    async def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"data": [{"id": "local-model"}], "object": "list"})

    thinker = object.__new__(OpenAIThinker)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http_client:
        async with AsyncOpenAI(
            api_key="local-secret",
            base_url=f"http://{host}:3000/v1",
            default_headers={"X-Proxy-Auth": "configured-header"},
            http_client=http_client,
        ) as client:
            thinker._client = client
            models = await thinker.get_available_models()

    assert models == [{"id": "local-model", "name": "local-model"}]
    assert len(requests) == 1
    assert requests[0].url.path == "/v1/models"
    assert requests[0].headers["authorization"] == "Bearer local-secret"
    assert requests[0].headers["X-Proxy-Auth"] == "configured-header"


def test_parse_response_preserves_provider_specific_tool_call_fields():
    thinker = object.__new__(OpenAIThinker)
    tool_call = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(
            name="default_api:list_dir",
            arguments='{"path": "/tmp"}',
            model_extra={"vendor_field": "nested-extra"},
        ),
        model_extra={
            "thought_signature": "sig-123",
            "provider_field": "top-extra",
        },
    )
    msg = SimpleNamespace(content=None, tool_calls=[tool_call])
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=msg, finish_reason="tool_calls")],
        usage=None,
    )

    parsed = OpenAIThinker._parse_response(thinker, response)

    assert len(parsed.tool_calls) == 1
    serialized = parsed.tool_calls[0].to_openai_tool_call()
    assert serialized["thought_signature"] == "sig-123"
    assert serialized["provider_field"] == "top-extra"
    assert serialized["function"]["vendor_field"] == "nested-extra"


def test_tool_call_serialization_flattens_extra_fields():
    thinker = object.__new__(OpenAIThinker)
    tool_call = SimpleNamespace(
        id="call_2",
        function=SimpleNamespace(
            name="default_api:list_dir",
            arguments='{"path": "/Users"}',
        ),
        model_extra={"thought_signature": "sig-456"},
    )
    msg = SimpleNamespace(content=None, tool_calls=[tool_call])
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=msg, finish_reason="tool_calls")],
        usage=None,
    )

    serialized = (
        OpenAIThinker._parse_response(thinker, response).tool_calls[0].to_openai_tool_call()
    )

    assert "provider_specific_fields" not in serialized
    assert "function" in serialized
    assert serialized["thought_signature"] == "sig-456"


def test_chat_streaming_preserves_provider_specific_tool_call_fields():
    class FakeStream:
        def __init__(self, chunks):
            self._chunks = chunks

        def __aiter__(self):
            self._iter = iter(self._chunks)
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration:
                raise StopAsyncIteration

    class FakeCompletions:
        def __init__(self, chunks):
            self._chunks = chunks

        async def create(self, **kwargs):
            return FakeStream(self._chunks)

    thinker = object.__new__(OpenAIThinker)
    thinker._provider_name = "google_genai"
    thinker.default_model = "gemini-3.1-flash-lite-preview"
    thinker._provider_name = "dummy"
    thinker._gateway = None
    thinker._client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=FakeCompletions(
                [
                    SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                finish_reason=None,
                                delta=SimpleNamespace(
                                    content=None,
                                    reasoning_content=None,
                                    tool_calls=[
                                        SimpleNamespace(
                                            index=0,
                                            id="call_stream_1",
                                            function=SimpleNamespace(
                                                name="default_api:list_dir",
                                                arguments='{"path": "/tmp"}',
                                                model_extra={"vendor_field": "nested-extra"},
                                            ),
                                            model_extra={"thought_signature": "sig-stream"},
                                        ),
                                    ],
                                ),
                            ),
                        ],
                    ),
                    SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                finish_reason="tool_calls",
                                delta=SimpleNamespace(
                                    content=None,
                                    reasoning_content=None,
                                    tool_calls=None,
                                ),
                            ),
                        ],
                    ),
                ]
            ),
        ),
    )

    response = asyncio.run(
        OpenAIThinker.chat_streaming(
            thinker,
            messages=[{"role": "user", "content": "hi"}],
        ),
    )

    assert len(response.tool_calls) == 1
    serialized = response.tool_calls[0].to_openai_tool_call()
    assert serialized["thought_signature"] == "sig-stream"
    assert serialized["function"]["vendor_field"] == "nested-extra"


def test_merge_reasoning_details_replaces_repeated_streamed_blocks():
    accumulated = [{"type": "reasoning.encrypted", "data": "partial"}]

    _merge_reasoning_details(
        accumulated,
        [{"type": "reasoning.encrypted", "data": "complete"}],
    )

    assert accumulated == [{"type": "reasoning.encrypted", "data": "complete"}]


@pytest.mark.asyncio
async def test_session_label_installs_token_before_chat():
    from shibaclaw.thinkers.github_copilot_provider import GithubCopilotThinker

    seen: dict[str, str] = {}

    class FakeCompletions:
        async def create(self, **kwargs):
            seen["key"] = thinker._client.api_key
            message = SimpleNamespace(content="ok", tool_calls=None, reasoning_content=None)
            choice = SimpleNamespace(message=message, finish_reason="stop")
            return SimpleNamespace(choices=[choice], usage=None)

    thinker = object.__new__(GithubCopilotThinker)
    thinker._client = SimpleNamespace(
        api_key="dummy",
        chat=SimpleNamespace(completions=FakeCompletions()),
    )
    thinker.default_model = "gpt-4o"
    thinker._provider_name = None
    thinker._gateway = None

    async def fake_get_session_token():
        return "copilot-session-token"

    thinker._get_session_token = fake_get_session_token

    response = await thinker.chat([{"role": "user", "content": "hi"}])

    assert seen["key"] == "copilot-session-token"
    assert response.content == "ok"
    assert response.finish_reason == "stop"


def test_github_copilot_get_available_models_refreshes_session_token():
    from shibaclaw.thinkers.github_copilot_provider import GithubCopilotThinker

    class FakeModels:
        async def list(self):
            return SimpleNamespace(
                data=[SimpleNamespace(id="gpt-4.1", name="GPT-4.1")],
            )

    thinker = object.__new__(GithubCopilotThinker)
    thinker._client = SimpleNamespace(api_key="dummy", models=FakeModels())

    async def fake_get_session_token():
        return "copilot-session-token"

    thinker._get_session_token = fake_get_session_token

    models = asyncio.run(GithubCopilotThinker.get_available_models(thinker))

    assert thinker._client.api_key == "copilot-session-token"
    assert models == [{"id": "gpt-4.1", "name": "GPT-4.1"}]
