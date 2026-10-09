import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shibaclaw.agent.loop import ShibaBrain
from shibaclaw.agent.subagent import SubagentManager
from shibaclaw.bus.events import InboundMessage
from shibaclaw.bus.queue import MessageBus
from shibaclaw.config.schema import ExecToolConfig, WebSearchConfig
from shibaclaw.thinkers.base import LLMResponse, ToolCallRequest

class MockResponse:
    def __init__(self, content: str, has_tool_calls: bool = False, tool_calls: list = None):
        self.content = content
        self.has_tool_calls = has_tool_calls
        self.tool_calls = tool_calls or []
        self.finish_reason = "stop"
        self.reasoning_content = None
        self.reasoning_details = None
        self.thinking_blocks = []

class MockProvider:
    def __init__(self):
        self.calls = []

    def get_default_model(self) -> str:
        return "mock-model"

    async def chat_with_retry(self, messages: list[dict], tools: list, model: str) -> MockResponse:
        self.calls.append(messages)
        # If the last message contains "Auditor Agent", return a PASSED verdict
        last_content = messages[-1]["content"]
        if "Auditor Agent" in last_content:
            return MockResponse("The execution was correct. PASSED")
        else:
            return MockResponse("Execution completed successfully.")

@pytest.mark.asyncio
async def test_execute_mea_loop(tmp_path):
    provider = MockProvider()
    bus = MessageBus()
    manager = SubagentManager(
        provider=provider,
        workspace=tmp_path,
        bus=bus,
    )
    
    task = "Create a hello world file"
    result = await manager.execute_mea_loop(
        task=task,
        origin_channel="cli",
        origin_chat_id="direct",
        session_key="cli:direct",
    )
    
    assert result["status"] == "completed"
    assert result["verdict"] == "PASSED"
    assert "Execution completed successfully." in result["execution_result"]
    assert "PASSED" in result["audit_result"]
    
    assert not (tmp_path / "progress.md").exists()
    progress_files = list((tmp_path / "memory" / "mea").glob("*.md"))
    assert len(progress_files) == 1
    progress_file = progress_files[0]
    assert progress_file.is_file()
    progress_content = progress_file.read_text(encoding="utf-8")
    assert "Task Progress" in progress_content
    assert "**Verdict**: PASSED" in progress_content
    assert "**Status**: Completed" in progress_content


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("channel", "chat_id"),
    [("telegram", "99"), ("webui", "desk")],
)
async def test_mea_announces_back_to_the_origin(tmp_path, channel: str, chat_id: str):
    bus = MessageBus()
    manager = SubagentManager(provider=MockProvider(), workspace=tmp_path, bus=bus)
    session_key = f"{channel}:{chat_id}"

    await manager.execute_mea_loop(
        task="Create a hello world file",
        origin_channel=channel,
        origin_chat_id=chat_id,
        session_key=session_key,
    )

    msg = await asyncio.wait_for(bus.consume_inbound(), timeout=2)
    assert msg.channel == channel
    assert msg.chat_id == chat_id
    assert msg.session_key == session_key


def _brain(tmp_path, provider: MagicMock) -> ShibaBrain:
    with patch("shibaclaw.agent.loop.asyncio.create_task"):
        brain = ShibaBrain(
            bus=MessageBus(),
            provider=provider,
            workspace=tmp_path,
            web_search_config=WebSearchConfig(enabled=False),
            exec_config=ExecToolConfig(enabled=False),
        )
    brain.mcp = MagicMock()
    brain.mcp.connect = AsyncMock()
    brain.memory_consolidator.maybe_consolidate_by_tokens = AsyncMock()
    brain.memory_consolidator.maybe_proactive_learn = AsyncMock()
    brain.tools.get_definitions = MagicMock(return_value=[])
    brain.context.build_static_prompt = MagicMock(return_value="STATIC")
    brain.context.build_runtime_block = MagicMock(return_value="LIVE")
    brain._resolve_provider_for_model = MagicMock(return_value=provider)
    return brain


def _spawn_then_stop(channel_label: str) -> MagicMock:
    provider = MagicMock()
    provider.get_default_model = MagicMock(return_value="test-model")
    provider.chat_with_retry_streaming = AsyncMock(
        side_effect=[
            LLMResponse(
                content="delegating",
                tool_calls=[
                    ToolCallRequest(
                        id=f"call_{channel_label}",
                        name="spawn_mea",
                        arguments={"task": "write the note", "label": channel_label},
                    )
                ],
                finish_reason="tool_calls",
            ),
            LLMResponse(content="started", finish_reason="stop"),
        ]
    )
    return provider


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("channel", "chat_id"),
    [("telegram", "99"), ("webui", "desk")],
)
async def test_loop_passes_origin_into_spawn_mea(tmp_path, channel: str, chat_id: str):
    provider = _spawn_then_stop(channel)
    brain = _brain(tmp_path, provider)
    seen: dict[str, object] = {}

    async def capture(**kwargs):
        seen.update(kwargs)
        return {"status": "completed", "verdict": "PASSED"}

    brain.subagents.execute_mea_loop = capture
    session_key = f"{channel}:{chat_id}"
    await brain._run_agent_loop(
        [{"role": "user", "content": "delegate"}],
        channel=channel,
        chat_id=chat_id,
        session_key=session_key,
        model="test-model",
        metadata={"is_allowlisted": True},
    )
    pending = [task for task in brain.subagents._running_tasks.values() if not task.done()]
    if pending:
        await asyncio.gather(*pending)
    assert seen["origin_channel"] == channel
    assert seen["origin_chat_id"] == chat_id
    assert seen["session_key"] == session_key
    assert seen["model"] == "test-model"
    assert seen["provider"] is provider


@pytest.mark.asyncio
async def test_stop_cancels_mea_and_clears_session_tracking(tmp_path):
    provider = _spawn_then_stop("telegram")
    brain = _brain(tmp_path, provider)
    started = asyncio.Event()

    async def hang(**kwargs):
        started.set()
        await asyncio.Event().wait()

    brain.subagents.execute_mea_loop = hang
    await brain._run_agent_loop(
        [{"role": "user", "content": "delegate"}],
        channel="telegram",
        chat_id="99",
        session_key="telegram:99",
        model="test-model",
        metadata={"is_allowlisted": True},
    )
    await asyncio.wait_for(started.wait(), timeout=2)
    assert "telegram:99" in brain.subagents._session_tasks
    assert brain.subagents.get_running_count() == 1

    await brain._handle_stop(
        InboundMessage(channel="telegram", sender_id="1", chat_id="99", content="/stop"),
        "telegram:99",
        "hard",
    )
    assert "telegram:99" not in brain.subagents._session_tasks
    assert brain.subagents.get_running_count() == 0
