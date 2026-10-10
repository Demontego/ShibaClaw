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

    assert spawn_tool._parent_messages == parent_messages
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

    assert mea_tool._parent_messages == parent_messages
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
        parent_messages=parent_messages,
    )
