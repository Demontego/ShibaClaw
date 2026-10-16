"""Tests for Subagent Context Modes ('isolated' vs 'fork') and Prompt Cache Discipline."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from shibaclaw.agent.subagent import SubagentManager
from shibaclaw.agent.tools.spawn import SpawnMeaTool, SpawnTool


@pytest.fixture
def mock_bus():
    bus = MagicMock()
    bus.publish_outbound = AsyncMock()
    return bus


@pytest.fixture
def subagent_manager(tmp_path: Path, mock_bus):
    provider = MagicMock()
    provider.get_default_model.return_value = "mock-model"
    manager = SubagentManager(
        provider=provider,
        workspace=tmp_path,
        bus=mock_bus,
    )
    return manager


def test_prepare_subagent_messages_isolated(subagent_manager):
    system_prompt = "Subagent System Prompt"
    task = "Do research on X"
    parent_messages = [
        {"role": "system", "content": "Parent System Prompt"},
        {"role": "user", "content": "Parent user query"},
        {"role": "assistant", "content": "Parent response"},
    ]

    messages = subagent_manager._prepare_subagent_messages(
        system_prompt=system_prompt,
        task=task,
        mode="isolated",
        parent_messages=parent_messages,
    )

    # Isolated mode should only have system prompt at index 0 and user task at index 1
    assert len(messages) == 2
    assert messages[0] == {"role": "system", "content": system_prompt}
    assert messages[1] == {"role": "user", "content": task}


def test_prepare_subagent_messages_fork(subagent_manager):
    system_prompt = "Subagent System Prompt"
    task = "Implement fix for issue Y"
    parent_messages = [
        {"role": "system", "content": "Parent System Prompt"},
        {"role": "user", "content": "User reported bug in module Y"},
        {"role": "assistant", "content": "Diagnosed bug in module Y at line 42"},
    ]

    messages = subagent_manager._prepare_subagent_messages(
        system_prompt=system_prompt,
        task=task,
        mode="fork",
        parent_messages=parent_messages,
    )

    # Index 0 must be subagent's system prompt (for prefix cache stability)
    assert messages[0] == {"role": "system", "content": system_prompt}

    # Inherited parent messages (system prompt excluded)
    assert messages[1] == {"role": "user", "content": "User reported bug in module Y"}
    assert messages[2] == {"role": "assistant", "content": "Diagnosed bug in module Y at line 42"}

    # Final directive
    assert messages[3]["role"] == "user"
    assert "[Subagent Task Directive (fork mode)]" in messages[3]["content"]
    assert "Implement fix for issue Y" in messages[3]["content"]


@pytest.mark.asyncio
async def test_spawn_tool_mode_context_passing(subagent_manager):
    spawn_tool = SpawnTool(manager=subagent_manager)
    parent_messages = [{"role": "user", "content": "test parent"}]
    spawn_tool.set_context(
        channel="cli",
        chat_id="direct",
        session_key="cli:direct",
        parent_messages=parent_messages,
    )

    assert "mode" in spawn_tool.parameters["properties"]

    # Mock manager.spawn
    subagent_manager.spawn = AsyncMock(return_value="Subagent started")

    result = await spawn_tool.execute(
        task="worker task", label="test worker", mode="fork"
    )

    assert result == "Subagent started"
    subagent_manager.spawn.assert_called_once_with(
        task="worker task",
        label="test worker",
        mode="fork",
        origin_channel="cli",
        origin_chat_id="direct",
        session_key="cli:direct",
        model=None,
        provider=None,
        parent_messages=parent_messages,
    )


@pytest.mark.asyncio
async def test_spawn_mea_tool_mode_context_passing(subagent_manager):
    mea_tool = SpawnMeaTool(manager=subagent_manager)
    parent_messages = [{"role": "user", "content": "mea parent"}]
    mea_tool.set_context(
        channel="cli",
        chat_id="direct",
        session_key="cli:direct",
        parent_messages=parent_messages,
    )

    assert "mode" in mea_tool.parameters["properties"]

    subagent_manager.execute_mea_loop = AsyncMock(
        return_value={"status": "completed", "verdict": "PASSED"}
    )

    result = await mea_tool.execute(
        task="complex feature", label="mea label", mode="fork"
    )

    assert "MEA Loop [mea label] started" in result
    # Give background task time to invoke manager
    await asyncio.sleep(0.01)

    subagent_manager.execute_mea_loop.assert_called_once_with(
        task="complex feature",
        label="mea label",
        mode="fork",
        origin_channel="cli",
        origin_chat_id="direct",
        session_key="cli:direct",
        model=None,
        provider=None,
        ephemeral=False,
        parent_messages=parent_messages,
    )


@pytest.mark.parametrize("tool_class", [SpawnTool, SpawnMeaTool])
async def test_delegation_history_is_snapshot_and_isolated_between_tasks(tool_class):
    manager = MagicMock()
    calls, background = {}, []

    async def capture(**kwargs):
        calls[kwargs["task"]] = kwargs
        return "started"

    manager.spawn = capture
    manager.execute_mea_loop = capture
    manager.track.side_effect = lambda key, task: background.append(task)
    tool = tool_class(manager)
    waiting, other_finished = asyncio.Event(), asyncio.Event()
    first_provider, second_provider = object(), object()
    first_history = [{"role": "user", "content": [{"type": "text", "text": "first history"}]}]

    async def first():
        tool.set_context("webui", "first", model="first-model", provider=first_provider, parent_messages=first_history)
        first_history[0]["content"][0]["text"] = "later mutation"
        waiting.set()
        await other_finished.wait()
        await tool.execute("first task", mode="fork")

    async def second():
        await waiting.wait()
        tool.set_context("telegram", "second", model="second-model", provider=second_provider, parent_messages=[{"role": "user", "content": "second history"}])
        await tool.execute("second task", mode="fork")
        other_finished.set()

    await asyncio.gather(first(), second())
    await asyncio.gather(*background)
    assert calls["first task"]["origin_chat_id"] == "first"
    assert calls["first task"]["provider"] is first_provider
    assert calls["first task"]["model"] == "first-model"
    assert calls["first task"]["parent_messages"] == [{"role": "user", "content": [{"type": "text", "text": "first history"}]}]
    assert calls["second task"]["parent_messages"] == [{"role": "user", "content": "second history"}]


@pytest.mark.parametrize("completed", [0, 1, 2])
def test_fork_inherits_only_complete_tool_groups(subagent_manager, completed):
    history = [
        {"role": "system", "content": "parent"},
        {"role": "user", "content": "task"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "old"}]},
        {"role": "tool", "tool_call_id": "old", "content": "old result"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "read"}, {"id": "spawn"}]},
    ]
    history.extend([
        {"role": "tool", "tool_call_id": "read", "content": "read result"},
        {"role": "tool", "tool_call_id": "spawn", "content": "spawn result"},
    ][:completed])
    messages = subagent_manager._prepare_subagent_messages("child", "continue", "fork", history)
    declared = {call["id"] for msg in messages for call in msg.get("tool_calls", [])}
    results = {msg["tool_call_id"] for msg in messages if msg.get("role") == "tool"}
    assert declared == results == ({"old", "read", "spawn"} if completed == 2 else {"old"})
    assert messages[-1]["role"] == "user"
    # The parent's nested tool data must not be shared with the child.
    messages[2]["tool_calls"][0]["id"] = "changed"
    assert history[2]["tool_calls"][0]["id"] == "old"
