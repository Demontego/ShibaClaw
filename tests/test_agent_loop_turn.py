"""Characterization: agent turn pipeline (tool call → result → final reply)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shibaclaw.agent.loop import ShibaBrain
from shibaclaw.bus.events import InboundMessage
from shibaclaw.config.schema import ExecToolConfig, WebSearchConfig
from shibaclaw.thinkers.base import LLMResponse, ToolCallRequest


def _brain(tmp_path: Path, provider: MagicMock | None = None) -> ShibaBrain:
    with patch("shibaclaw.agent.loop.asyncio.create_task"):
        brain = ShibaBrain(
            bus=MagicMock(),
            provider=provider or MagicMock(),
            workspace=tmp_path,
            web_search_config=WebSearchConfig(enabled=False),
            exec_config=ExecToolConfig(enabled=False),
        )
    brain.mcp = MagicMock()
    brain.mcp.connect = AsyncMock()
    brain.mcp.close = AsyncMock()
    brain.memory_consolidator.maybe_consolidate_by_tokens = AsyncMock()
    return brain


@pytest.mark.asyncio
async def test_run_agent_loop_tool_then_final_reply(tmp_path: Path):
    provider = MagicMock()
    tool_response = LLMResponse(
        content="looking up",
        tool_calls=[
            ToolCallRequest(id="call_1", name="web_search", arguments={"query": "weather"})
        ],
        finish_reason="tool_calls",
        reasoning_details=[{"type": "reasoning.encrypted", "data": "sig1"}],
    )
    final_response = LLMResponse(
        content="It is sunny.",
        finish_reason="stop",
        reasoning_details=[{"type": "reasoning.encrypted", "data": "sig2"}],
    )
    provider.chat_with_retry_streaming = AsyncMock(side_effect=[tool_response, final_response])
    provider.get_default_model = MagicMock(return_value="test-model")

    brain = _brain(tmp_path, provider=provider)
    brain.tools.execute = AsyncMock(return_value="sunny, 22C")
    brain.tools.get_definitions = MagicMock(
        return_value=[
            {"type": "function", "function": {"name": "web_search"}},
            {"type": "function", "function": {"name": "exec"}},
        ]
    )
    brain.context.build_static_prompt = MagicMock(return_value="STATIC")
    brain.context.build_runtime_block = MagicMock(return_value="LIVE")
    brain._resolve_provider_for_model = MagicMock(return_value=provider)

    messages = [{"role": "system", "content": "placeholder"}, {"role": "user", "content": "weather?"}]
    content, tools_used, all_msgs = await brain._run_agent_loop(
        messages,
        channel="cli",
        chat_id="direct",
        session_key="cli:direct",
        metadata={"is_allowlisted": True},
        model="test-model",
    )

    assert content == "It is sunny."
    assert tools_used == ["web_search"]
    assert provider.chat_with_retry_streaming.await_count == 2
    brain.tools.execute.assert_awaited_once_with("web_search", {"query": "weather"})
    assistant_with_tools = next(m for m in all_msgs if m.get("tool_calls"))
    assert assistant_with_tools["reasoning_details"] == [
        {"type": "reasoning.encrypted", "data": "sig1"}
    ]
    final_assistant = [m for m in all_msgs if m.get("role") == "assistant" and not m.get("tool_calls")][-1]
    assert final_assistant["reasoning_details"] == [
        {"type": "reasoning.encrypted", "data": "sig2"}
    ]
    tool_msg = next(m for m in all_msgs if m.get("role") == "tool")
    assert "sunny" in tool_msg["content"]


@pytest.mark.asyncio
async def test_run_agent_loop_blocks_non_allowlisted_tool(tmp_path: Path):
    provider = MagicMock()
    tool_response = LLMResponse(
        content=None,
        tool_calls=[ToolCallRequest(id="c1", name="exec", arguments={"command": "ls"})],
        finish_reason="tool_calls",
    )
    final_response = LLMResponse(content="denied path handled", finish_reason="stop")
    provider.chat_with_retry_streaming = AsyncMock(side_effect=[tool_response, final_response])
    provider.get_default_model = MagicMock(return_value="test-model")

    brain = _brain(tmp_path, provider=provider)
    brain.tools.execute = AsyncMock(return_value="should-not-run")
    brain.tools.get_definitions = MagicMock(
        return_value=[
            {"type": "function", "function": {"name": "web_search"}},
            {"type": "function", "function": {"name": "exec"}},
        ]
    )
    brain.context.build_static_prompt = MagicMock(return_value="STATIC")
    brain.context.build_runtime_block = MagicMock(return_value="LIVE")
    brain._resolve_provider_for_model = MagicMock(return_value=provider)

    messages = [{"role": "system", "content": "x"}, {"role": "user", "content": "run ls"}]
    content, tools_used, all_msgs = await brain._run_agent_loop(
        messages,
        channel="telegram",
        chat_id="99",
        session_key="telegram:99",
        metadata={"is_allowlisted": False},
        model="test-model",
    )

    assert content == "denied path handled"
    assert tools_used == ["exec"]
    brain.tools.execute.assert_not_awaited()
    tool_msg = next(m for m in all_msgs if m.get("role") == "tool")
    assert "allowlist-only" in tool_msg["content"]


@pytest.mark.asyncio
async def test_process_direct_and_dispatch_share_process_message(tmp_path: Path):
    from shibaclaw.bus.events import OutboundMessage

    provider = MagicMock()
    provider.get_default_model = MagicMock(return_value="test-model")
    brain = _brain(tmp_path, provider=provider)
    brain.bus.publish_outbound = AsyncMock()
    expected = OutboundMessage(channel="webui", chat_id="abc", content="ok")
    brain._process_message = AsyncMock(return_value=expected)

    direct = await brain.process_direct(
        "hello",
        session_key="webui:abc",
        channel="webui",
        chat_id="abc",
        metadata={"is_allowlisted": True},
    )
    assert direct is expected
    brain.mcp.connect.assert_awaited()
    assert brain._process_message.await_args.kwargs["session_key"] == "webui:abc"
    inbound = brain._process_message.await_args.args[0]
    assert isinstance(inbound, InboundMessage)
    assert inbound.content == "hello"
    assert inbound.channel == "webui"

    brain._process_message.reset_mock()
    msg = InboundMessage(channel="telegram", sender_id="1", chat_id="1", content="hi")
    await brain._dispatch(msg)
    brain._process_message.assert_awaited_once()
    assert brain._process_message.await_args.args[0] is msg
    brain.bus.publish_outbound.assert_awaited_once_with(expected)


@pytest.mark.asyncio
async def test_process_direct_help_command(tmp_path: Path):
    provider = MagicMock()
    provider.get_default_model = MagicMock(return_value="test-model")
    brain = _brain(tmp_path, provider=provider)

    out = await brain.process_direct("/help", session_key="cli:direct", channel="cli")
    assert out is not None
    assert "/new" in out.content
    assert "/help" in out.content
