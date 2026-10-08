"""Turn journal: commit the tool call before I/O, then refuse to run it twice."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shibaclaw.agent.loop import ShibaBrain
from shibaclaw.agent.turn_journal import (
    JournalCorruptError,
    TurnJournal,
    UnsupportedVersionError,
)
from shibaclaw.bus.events import InboundMessage
from shibaclaw.config.schema import ExecToolConfig, WebSearchConfig
from shibaclaw.thinkers.base import LLMResponse, ToolCallRequest


def test_ready_is_on_disk_before_io(tmp_path: Path):
    journal = TurnJournal(tmp_path)
    seen: list[str] = []

    claim = journal.claim("s", "call_1", "exec")
    assert claim.run
    text = next(tmp_path.glob("*.jsonl")).read_text(encoding="utf-8")
    assert '"status": "ready"' in text
    assert "arguments" not in text
    row = json.loads(text)
    assert row["v"] == 1
    assert row["idempotency"] == "call_1"
    seen.append("after-ready")
    assert seen == ["after-ready"]


def test_crash_does_not_start_the_same_call_again(tmp_path: Path):
    first = TurnJournal(tmp_path)
    assert first.claim("s", "call_1", "exec").run
    second = TurnJournal(tmp_path)
    again = second.claim("s", "call_1", "exec")
    assert not again.run
    assert "not started again" in again.result


def test_completed_call_is_replayed(tmp_path: Path):
    journal = TurnJournal(tmp_path)
    assert journal.claim("s", "call_1", "exec").run
    journal.mark("s", "call_1", "completed", "ok")
    replay = journal.claim("s", "call_1", "exec")
    assert not replay.run
    assert replay.result == "ok"


def test_duplicate_input_is_dropped(tmp_path: Path):
    journal = TurnJournal(tmp_path)
    assert journal.accept_input("s", "telegram:9")
    assert not journal.accept_input("s", "telegram:9")
    assert journal.accept_input("s", None)
    assert journal.accept_input("s", "telegram:10")


def test_unknown_version_is_refused(tmp_path: Path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"v": 2, "kind": "input", "id": "x"}\n', encoding="utf-8")
    journal = TurnJournal(tmp_path)
    digest = __import__("hashlib").sha256(b"s").hexdigest()
    path.rename(tmp_path / f"{digest}.jsonl")
    with pytest.raises(UnsupportedVersionError):
        journal.accept_input("s", "x")


def test_torn_line_is_refused(tmp_path: Path):
    journal = TurnJournal(tmp_path)
    journal.accept_input("s", "keep")
    path = next(tmp_path.glob("*.jsonl"))
    path.write_text(path.read_text(encoding="utf-8") + '{"v":1\n', encoding="utf-8")
    with pytest.raises(JournalCorruptError):
        journal.claim("s", "call_1", "exec")


def test_when_idle_does_not_start_the_next_tool(tmp_path: Path):
    journal = TurnJournal(tmp_path)
    assert journal.claim("s", "call_1", "exec").run
    journal.mark("s", "call_1", "awaiting")
    journal.request_stop("s", "when_idle")
    journal.mark("s", "call_1", "completed", "done")
    nxt = journal.claim("s", "call_2", "exec")
    assert nxt.halt
    assert not nxt.run


def test_hard_stop_cancels_an_open_call(tmp_path: Path):
    journal = TurnJournal(tmp_path)
    assert journal.claim("s", "call_1", "exec").run
    journal.mark("s", "call_1", "awaiting")
    journal.request_stop("s", "hard")
    assert journal._operations("s")["call_1"]["status"] == "canceled"
    journal.clear_stop("s")
    assert journal.stop_mode("s") is None


def test_interrupt_note_is_consumed_once(tmp_path: Path):
    journal = TurnJournal(tmp_path)
    assert journal.claim("s", "call_1", "exec").run
    note = journal.consume_interruptions("s")
    assert note is not None
    assert "exec" in note
    assert journal.consume_interruptions("s") is None
    assert not journal.claim("s", "call_1", "exec").run


def test_memory_journal_does_not_touch_disk(tmp_path: Path):
    journal = TurnJournal(None)
    assert journal.claim("s", "call_1", "exec").run
    journal.mark("s", "call_1", "completed", "ok")
    assert journal.claim("s", "call_1", "exec").result == "ok"
    assert list(tmp_path.iterdir()) == []


def _brain(tmp_path: Path, provider: MagicMock) -> ShibaBrain:
    with patch("shibaclaw.agent.loop.asyncio.create_task"):
        brain = ShibaBrain(
            bus=MagicMock(),
            provider=provider,
            workspace=tmp_path,
            web_search_config=WebSearchConfig(enabled=False),
            exec_config=ExecToolConfig(enabled=False),
        )
    brain.mcp = MagicMock()
    brain.mcp.connect = AsyncMock()
    brain.memory_consolidator.maybe_consolidate_by_tokens = AsyncMock()
    brain.memory_consolidator.maybe_proactive_learn = AsyncMock()
    return brain


def _tool_then_stop() -> MagicMock:
    provider = MagicMock()
    provider.get_default_model = MagicMock(return_value="test-model")
    provider.chat_with_retry_streaming = AsyncMock(
        side_effect=[
            LLMResponse(
                content="looking",
                tool_calls=[ToolCallRequest(id="call_1", name="web_search", arguments={"query": "x"})],
                finish_reason="tool_calls",
            ),
            LLMResponse(content="done", finish_reason="stop"),
            LLMResponse(
                content="looking",
                tool_calls=[ToolCallRequest(id="call_1", name="web_search", arguments={"query": "x"})],
                finish_reason="tool_calls",
            ),
            LLMResponse(content="done", finish_reason="stop"),
        ]
    )
    return provider


@pytest.mark.asyncio
async def test_loop_skips_a_finished_tool_call(tmp_path: Path):
    provider = _tool_then_stop()
    brain = _brain(tmp_path, provider)
    brain.tools.execute = AsyncMock(return_value="sunny")
    brain.tools.get_definitions = MagicMock(return_value=[])
    brain.context.build_static_prompt = MagicMock(return_value="STATIC")
    brain.context.build_runtime_block = MagicMock(return_value="LIVE")
    brain._resolve_provider_for_model = MagicMock(return_value=provider)
    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}]

    await brain._run_agent_loop(messages, session_key="cli:direct", model="test-model")
    journal_text = next((tmp_path / "runtime" / "turns").glob("*.jsonl")).read_text(encoding="utf-8")
    assert '"status": "ready"' in journal_text
    assert journal_text.index('"status": "ready"') < journal_text.index('"status": "completed"')

    await brain._run_agent_loop(messages, session_key="cli:direct", model="test-model")
    brain.tools.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_incognito_journal_stays_in_memory(tmp_path: Path):
    provider = _tool_then_stop()
    brain = _brain(tmp_path, provider)
    session = brain.sessions.get_or_create("cli:direct")
    session.metadata["incognito"] = True
    brain.tools.execute = AsyncMock(return_value="sunny")
    brain.tools.get_definitions = MagicMock(return_value=[])
    brain.context.build_static_prompt = MagicMock(return_value="STATIC")
    brain.context.build_runtime_block = MagicMock(return_value="LIVE")
    brain._resolve_provider_for_model = MagicMock(return_value=provider)
    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}]

    await brain._run_agent_loop(messages, session_key="cli:direct", model="test-model")
    await brain._run_agent_loop(messages, session_key="cli:direct", model="test-model")
    brain.tools.execute.assert_awaited_once()
    assert list((tmp_path / "runtime" / "turns").glob("*.jsonl")) == []


@pytest.mark.asyncio
async def test_stop_idle_does_not_run_the_tool(tmp_path: Path):
    provider = MagicMock()
    provider.get_default_model = MagicMock(return_value="test-model")
    provider.chat_with_retry_streaming = AsyncMock(
        return_value=LLMResponse(
            content="looking",
            tool_calls=[ToolCallRequest(id="call_9", name="exec", arguments={"command": "ls"})],
            finish_reason="tool_calls",
        )
    )
    brain = _brain(tmp_path, provider)
    brain.tools.execute = AsyncMock(return_value="nope")
    brain.tools.get_definitions = MagicMock(return_value=[])
    brain.context.build_static_prompt = MagicMock(return_value="STATIC")
    brain.context.build_runtime_block = MagicMock(return_value="LIVE")
    brain._resolve_provider_for_model = MagicMock(return_value=provider)
    brain.turn_journal.request_stop("cli:direct", "when_idle")

    content, _, _ = await brain._run_agent_loop(
        [{"role": "user", "content": "go"}],
        session_key="cli:direct",
        model="test-model",
    )
    brain.tools.execute.assert_not_awaited()
    assert content is not None
    assert "not started" in content


@pytest.mark.asyncio
async def test_duplicate_telegram_input_skips_the_model(tmp_path: Path):
    provider = MagicMock()
    provider.get_default_model = MagicMock(return_value="test-model")
    provider.chat_with_retry_streaming = AsyncMock(
        return_value=LLMResponse(content="hello", finish_reason="stop")
    )
    brain = _brain(tmp_path, provider)
    brain._resolve_provider_for_model = MagicMock(return_value=provider)
    brain.context.build_static_prompt = MagicMock(return_value="STATIC")
    brain.context.build_runtime_block = MagicMock(return_value="LIVE")
    msg = InboundMessage(
        channel="cli",
        sender_id="1",
        chat_id="direct",
        content="hi",
        metadata={"input_id": "telegram:4"},
    )
    first = await brain._process_message(msg, session_key="cli:direct")
    second = await brain._process_message(msg, session_key="cli:direct")
    assert first is not None
    assert second is None
    assert provider.chat_with_retry_streaming.await_count == 1
