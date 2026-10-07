import pytest

from shibaclaw.thinkers.base import LLMResponse, Thinker, ToolCallRequest


def test_sanitize_empty_content_early_return():
    msg = {"role": "user", "content": "hello"}
    messages = [msg]
    sanitized = Thinker._sanitize_empty_content(messages)
    assert sanitized[0] is msg


def test_sanitize_empty_content_empty_string():
    messages = [
        {"role": "user", "content": ""},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "tc1"}]},
        {"role": "assistant", "content": ""},
    ]
    sanitized = Thinker._sanitize_empty_content(messages)

    assert sanitized[0]["content"] == "(empty)"
    assert sanitized[1]["content"] is None
    assert sanitized[2]["content"] == "(empty)"


def test_sanitize_empty_content_list():
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "hello"},
                {"type": "text", "text": ""},
                {"type": "image_url", "image_url": {"url": "data:image/png"}, "_meta": {"path": "test"}},
            ],
        }
    ]
    sanitized = Thinker._sanitize_empty_content(messages)

    content = sanitized[0]["content"]
    assert len(content) == 2
    assert content[0] == {"type": "text", "text": "hello"}
    assert content[1] == {"type": "image_url", "image_url": {"url": "data:image/png"}}


def test_get_model_reasoning_efforts():
    from shibaclaw.thinkers.registry import get_model_reasoning_efforts

    # OpenAI o-series & Azure/OpenRouter deployments
    assert get_model_reasoning_efforts("o1") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("openai/o1-mini") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("openai/o3-mini") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("azure/my-o1-deploy") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("azure/o3-mini-test") == ["low", "medium", "high"]

    # Anthropic
    assert get_model_reasoning_efforts("anthropic/claude-3.7-sonnet") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("claude-3-7-sonnet-20250219") == ["low", "medium", "high"]

    # Gemini
    assert get_model_reasoning_efforts("gemini-2.0-flash-thinking-exp") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("google/gemini-2.5-flash") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("google/gemini-3.6-flash") == ["low", "medium", "high"]

    # DeepSeek
    assert get_model_reasoning_efforts("deepseek/deepseek-r1") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("deepseek/r1") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("ollama/r1:8b") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("deepseek-reasoner") == ["low", "medium", "high"]

    # Qwen QwQ
    assert get_model_reasoning_efforts("qwen/qwq-32b") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("qwq-32b-preview") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("qwen/qvq-72b") == ["low", "medium", "high"]

    # Grok
    assert get_model_reasoning_efforts("xai/grok-3") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("grok-3-think") == ["low", "medium", "high"]

    # Kimi / Moonshot
    assert get_model_reasoning_efforts("moonshot/kimi-k1.5") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("kimi-k2") == ["low", "medium", "high"]

    # GLM
    assert get_model_reasoning_efforts("zhipu/glm-4-zero-preview") == ["low", "medium", "high"]

    # Open Reasoning
    assert get_model_reasoning_efforts("marco-o1") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("sky-t1") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("smallthinker") == ["low", "medium", "high"]

    # Non-reasoning models return []
    assert get_model_reasoning_efforts("gpt-4o") == []
    assert get_model_reasoning_efforts("claude-3-5-sonnet") == []
    assert get_model_reasoning_efforts("gemini-1.5-pro") == []
    assert get_model_reasoning_efforts("") == []


class _Scripted(Thinker):
    def __init__(self, replies: list[LLMResponse]):
        super().__init__()
        self.replies = list(replies)
        self.models: list[str | None] = []

    async def chat(self, **kwargs):
        self.models.append(kwargs.get("model"))
        if len(self.replies) > 1:
            return self.replies.pop(0)
        return self.replies[0]

    async def chat_streaming(self, **kwargs):
        return await self.chat(**kwargs)

    def get_default_model(self) -> str:
        return "primary"


@pytest.fixture(autouse=True)
def _clear_response_cache():
    Thinker._RESPONSE_CACHE.clear()
    yield
    Thinker._RESPONSE_CACHE.clear()


async def _no_sleep(*_args, **_kwargs):
    return None


@pytest.mark.asyncio
async def test_permanent_error_does_not_retry(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    thinker = _Scripted([
        LLMResponse(content="Error 401 unauthorized", finish_reason="error"),
    ])
    result = await thinker.chat_with_retry(
        messages=[{"role": "user", "content": "hi"}],
        model="primary",
    )
    assert result.finish_reason == "error"
    assert thinker.models == ["primary"]


@pytest.mark.asyncio
async def test_transient_error_retries_and_caches_first_success(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    thinker = _Scripted([
        LLMResponse(content="Error 429 rate limit", finish_reason="error"),
        LLMResponse(content="ok", finish_reason="stop"),
    ])
    result = await thinker.chat_with_retry(
        messages=[{"role": "user", "content": "hi"}],
        model="primary",
    )
    assert result.content == "ok"
    assert len(Thinker._RESPONSE_CACHE) == 1


@pytest.mark.asyncio
async def test_omitted_fallback_does_not_switch_model(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    thinker = _Scripted([
        LLMResponse(content="Error 503 overloaded", finish_reason="error"),
    ])
    await thinker.chat_with_retry(
        messages=[{"role": "user", "content": "hi"}],
        model="primary",
    )
    assert set(thinker.models) == {"primary"}


@pytest.mark.asyncio
async def test_cache_does_not_return_tool_calls_when_tools_disabled(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    tool_reply = LLMResponse(
        content=None,
        tool_calls=[ToolCallRequest(id="1", name="exec", arguments={})],
        finish_reason="stop",
    )
    thinker = _Scripted([
        tool_reply,
        LLMResponse(content="Error 503 overloaded", finish_reason="error"),
    ])
    messages = [{"role": "user", "content": "run"}]
    await thinker.chat_with_retry(messages=messages, model="primary", tools=[{"type": "function"}])
    result = await thinker.chat_with_retry(
        messages=messages,
        model="primary",
        tools=None,
        tool_choice="none",
    )
    assert not result.tool_calls


@pytest.mark.asyncio
async def test_exhausted_fallback_uses_primary_cache(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    messages = [{"role": "user", "content": "same"}]
    thinker = _Scripted([
        LLMResponse(content="cached-primary", finish_reason="stop"),
        LLMResponse(content="Error 503 overloaded", finish_reason="error"),
    ])
    await thinker.chat_with_retry(messages=messages, model="primary")
    result = await thinker.chat_with_retry(
        messages=messages,
        model="primary",
        fallback_models=["other"],
    )
    assert "cached-primary" in (result.content or "")

