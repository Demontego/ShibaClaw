"""Tests for Telegram edit-on-user-edit mapping and silent empty replies."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.error import BadRequest

from shibaclaw.bus.events import OutboundMessage
from shibaclaw.integrations.telegram import TelegramChannel


def test_inbound_reply_map_remember_and_lookup():
    ch = object.__new__(TelegramChannel)
    ch._inbound_reply_map = {}
    ch._INBOUND_REPLY_MAP_CAP = 2

    ch._remember_inbound_reply(10, 1, 100)
    ch._remember_inbound_reply(10, 2, 200)
    assert ch._lookup_inbound_reply(10, 1) == 100
    assert ch._lookup_inbound_reply(10, 2) == 200

    # Cap evicts oldest insertion order
    ch._remember_inbound_reply(10, 3, 300)
    assert len(ch._inbound_reply_map) == 2
    assert ch._lookup_inbound_reply(10, 3) == 300


def test_inbound_reply_map_ignores_incomplete():
    ch = object.__new__(TelegramChannel)
    ch._inbound_reply_map = {}
    ch._INBOUND_REPLY_MAP_CAP = 10
    ch._remember_inbound_reply(1, None, 5)
    ch._remember_inbound_reply(1, 2, None)
    assert ch._inbound_reply_map == {}


@pytest.mark.asyncio
async def test_finalize_edit_splits_overlong_reply_after_first_edited_chunk():
    ch = object.__new__(TelegramChannel)
    ch._app = MagicMock()
    ch.config = MagicMock(streaming=False, rich_messages=False, reply_to_message=False)
    ch._message_threads = {}
    ch._progress_messages = {}
    ch._stop_typing = MagicMock()
    ch._send_with_streaming = AsyncMock(side_effect=[101, 102, 103])
    ch._clear_progress_message = AsyncMock()
    ch._clear_draft_id = MagicMock()
    ch._remember_inbound_reply = MagicMock()

    await ch.send(
        OutboundMessage(
            channel="telegram",
            chat_id="1",
            content="x" * 8_001,
            metadata={"edit_message_id": 100, "message_id": 1},
        )
    )

    calls = ch._send_with_streaming.await_args_list
    assert len(calls) == 3
    assert calls[0].args[1] == "x" * 4_000
    assert calls[0].kwargs["edit_message_id"] == 100
    assert all("edit_message_id" not in call.kwargs for call in calls[1:])


@pytest.mark.asyncio
async def test_finalize_edit_unchanged_message_does_not_send_duplicate():
    ch = object.__new__(TelegramChannel)
    ch._app = MagicMock()
    ch._call_with_retry = AsyncMock(side_effect=BadRequest("Message is not modified"))

    result = await ch._send_text(chat_id=1, text="unchanged", edit_message_id=100)

    assert result == 100
    assert ch._call_with_retry.await_count == 1
