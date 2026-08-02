from shibaclaw.thinkers.base import Thinker


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

