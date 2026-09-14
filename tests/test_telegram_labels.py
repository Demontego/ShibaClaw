"""Tests for Telegram WebUI session autolabeling."""

from __future__ import annotations

from types import SimpleNamespace

from shibaclaw.integrations.telegram_labels import maybe_autolabel_session, suggest_label


def test_suggest_label_group_title():
    label = suggest_label(
        "telegram:-100123",
        meta={"is_group": True, "chat_title": "Poker Night"},
        owner_ids={"1"},
    )
    assert label == "Poker Night"


def test_suggest_label_business_peer():
    label = suggest_label(
        "telegram:99",
        [{"role": "user", "metadata": {"user_id": 99, "first_name": "Alex"}}],
        meta={"business_connection_id": "bc1", "user_id": 99, "first_name": "Alex"},
        owner_ids={"1"},
    )
    assert label == "You + Alex"


def test_suggest_label_owner_dm():
    label = suggest_label(
        "telegram:1",
        meta={"user_id": 1, "first_name": "Owner"},
        owner_ids={"1"},
    )
    assert label == "You"


def test_suggest_label_owner_dm_topic():
    label = suggest_label(
        "telegram:1:topic:6780867",
        meta={"user_id": 1, "first_name": "Owner"},
        owner_ids={"1"},
    )
    assert label == "You · topic 6780867"


def test_suggest_label_group_topic():
    label = suggest_label(
        "telegram:-100123:topic:42",
        meta={"is_group": True, "chat_title": "Poker Night"},
        owner_ids={"1"},
    )
    assert label == "Poker Night · topic 42"


def test_maybe_autolabel_respects_manual_nickname():
    session = SimpleNamespace(
        key="telegram:99",
        messages=[],
        metadata={"nickname": "Manual"},
    )
    changed = maybe_autolabel_session(
        session,
        {"business_connection_id": "bc1", "user_id": 99, "first_name": "Alex"},
        None,
        owner_ids={"1"},
    )
    assert changed is False
    assert session.metadata["nickname"] == "Manual"


def test_maybe_autolabel_updates_auto_nickname():
    session = SimpleNamespace(
        key="telegram:99",
        messages=[],
        metadata={"nickname": "Old", "nickname_auto": True},
    )
    changed = maybe_autolabel_session(
        session,
        {"business_connection_id": "bc1", "user_id": 99, "first_name": "Alex"},
        None,
        owner_ids={"1"},
    )
    assert changed is True
    assert session.metadata["nickname"] == "You + Alex"
