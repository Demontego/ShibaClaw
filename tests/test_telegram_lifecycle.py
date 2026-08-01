"""Tests for Telegram edit-on-user-edit mapping and silent empty replies."""

from __future__ import annotations

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
