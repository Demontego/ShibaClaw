import pytest
from unittest.mock import AsyncMock, MagicMock
from shibaclaw.integrations.telegram import (
    TelegramChannel,
    TelegramConfig,
    build_rich_message_body,
)
from shibaclaw.bus.queue import MessageBus
from loguru import logger

logger.remove()


@pytest.mark.asyncio
async def test_telegram_channel_chat_ids_eviction():
    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(enabled=True, token="fake_token", allow_from=["*"])
    channel = TelegramChannel(config, bus)

    channel._download_message_media = AsyncMock(return_value=([], []))
    channel._handle_message = AsyncMock()
    channel._is_group_message_for_bot = AsyncMock(return_value=True)
    channel._build_message_metadata = MagicMock(return_value={})
    channel._derive_topic_session_key = MagicMock(return_value="session_key")

    for i in range(505):
        update = MagicMock()
        user = MagicMock()
        user.id = i
        user.first_name = f"User{i}"
        user.username = f"user{i}"
        user.is_bot = False
        update.effective_user = user

        message = MagicMock()
        message.chat.id = 1000 + i
        message.chat.type = "private"
        message.from_user = user
        message.text = "hello"
        message.caption = None
        message.reply_to_message = None
        message.media_group_id = None
        message.message_id = i
        message.message_thread_id = None
        message.business_connection_id = None
        message.forward_origin = None
        message.is_automatic_forward = False
        update.message = message
        update.edited_message = None
        update.effective_message = message
        update.guest_message = None

        await channel._on_message(update, MagicMock())

    assert len(channel._chat_ids) == 500
    assert "0|user0" not in channel._chat_ids
    assert "4|user4" not in channel._chat_ids
    assert "5|user5" in channel._chat_ids
    assert "504|user504" in channel._chat_ids


def test_telegram_channel_threads_eviction():
    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(enabled=True, token="fake_token")
    channel = TelegramChannel(config, bus)

    for i in range(1010):
        message = MagicMock()
        message.chat_id = "chat_abc"
        message.message_id = i
        message.message_thread_id = 9999
        channel._remember_thread_context(message)

    assert len(channel._message_threads) == 1000
    assert ("chat_abc", 0) not in channel._message_threads
    assert ("chat_abc", 9) not in channel._message_threads
    assert ("chat_abc", 10) in channel._message_threads
    assert ("chat_abc", 1009) in channel._message_threads


@pytest.mark.asyncio
async def test_telegram_channel_network_error_re_raises():
    from telegram.error import NetworkError

    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(enabled=True, token="fake_token")
    channel = TelegramChannel(config, bus)

    channel._app = MagicMock()
    channel._app.bot = MagicMock()

    channel._call_with_retry = AsyncMock(side_effect=NetworkError("Network timeout"))

    with pytest.raises(NetworkError):
        await channel._send_text(chat_id=123, text="Hello...")


@pytest.mark.asyncio
async def test_telegram_channel_progress_network_error_re_raises():
    from telegram.error import NetworkError, RetryAfter, TimedOut

    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(enabled=True, token="fake_token")
    channel = TelegramChannel(config, bus)

    channel._app = MagicMock()
    channel._app.bot = MagicMock()

    channel._call_with_retry = AsyncMock(side_effect=NetworkError("Network timeout"))
    with pytest.raises(NetworkError):
        await channel._edit_progress_message(chat_id=123, message_id=456, text="Hello...")

    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=Warning)
        channel._call_with_retry = AsyncMock(side_effect=RetryAfter(10))
    with pytest.raises(RetryAfter):
        await channel._send_or_edit_progress(chat_id=123, text="Hello...")

    channel._call_with_retry = AsyncMock(side_effect=TimedOut())
    with pytest.raises(TimedOut):
        await channel._edit_progress_message(chat_id=123, message_id=456, text="Hello...")


@pytest.mark.asyncio
async def test_send_guest_query_uses_answer_guest_query():
    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(enabled=True, token="fake_token", guest_mode=True)
    channel = TelegramChannel(config, bus)
    channel._app = MagicMock()
    channel._app.bot = MagicMock()
    channel._call_with_retry = AsyncMock()
    channel._stop_typing = MagicMock()

    from shibaclaw.bus.events import OutboundMessage

    msg = OutboundMessage(
        channel="telegram",
        chat_id="1",
        content="hello guest",
        metadata={"guest_query_id": "gq-123"},
    )
    await channel.send(msg)
    channel._call_with_retry.assert_awaited()
    assert channel._call_with_retry.await_args.args[0] == channel._app.bot.answer_guest_query


@pytest.mark.asyncio
async def test_private_progress_uses_send_message_draft():
    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(enabled=True, token="fake_token", streaming=True)
    channel = TelegramChannel(config, bus)
    channel._app = MagicMock()
    channel._app.bot = MagicMock()
    channel._call_with_retry = AsyncMock(return_value=True)
    channel._stop_typing = MagicMock()

    from shibaclaw.bus.events import OutboundMessage

    msg = OutboundMessage(
        channel="telegram",
        chat_id="42",
        content="partial…",
        metadata={"_progress": True, "message_id": 7},
    )
    await channel.send(msg)
    assert channel._call_with_retry.await_args.args[0] == channel._app.bot.send_message_draft


@pytest.mark.asyncio
async def test_ignores_bot_sender_when_disallowed():
    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(enabled=True, token="fake_token", allow_bot_messages=False)
    channel = TelegramChannel(config, bus)
    channel._handle_message = AsyncMock()
    channel.is_allowed = MagicMock(return_value=True)

    update = MagicMock()
    user = MagicMock()
    user.id = 99
    user.first_name = "OtherBot"
    user.username = "otherbot"
    user.is_bot = True
    update.effective_user = user
    message = MagicMock()
    message.chat.id = 99
    message.chat_id = 99
    message.chat.type = "private"
    message.text = "hi"
    message.caption = None
    message.reply_to_message = None
    message.media_group_id = None
    message.message_id = 1
    message.message_thread_id = None
    message.guest_query_id = None
    message.business_connection_id = None
    update.effective_message = message
    update.guest_message = None
    update.message = message
    update.edited_message = None

    await channel._on_message(update, MagicMock())
    channel._handle_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_guest_message_sets_guest_metadata():
    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(enabled=True, token="fake_token", guest_mode=True, allow_from=["*"])
    channel = TelegramChannel(config, bus)
    channel._download_message_media = AsyncMock(return_value=([], []))
    channel._handle_message = AsyncMock()

    update = MagicMock()
    user = MagicMock()
    user.id = 7
    user.first_name = "Rinat"
    user.username = "rinat"
    user.is_bot = False
    update.effective_user = user
    message = MagicMock()
    message.chat.id = -100
    message.chat_id = -100
    message.chat.type = "supergroup"
    message.text = "@shiba help"
    message.caption = None
    message.reply_to_message = None
    message.media_group_id = None
    message.message_id = 5
    message.message_thread_id = None
    message.guest_query_id = "guest-abc"
    message.business_connection_id = None
    message.forward_origin = None
    message.is_automatic_forward = False
    message.photo = None
    message.voice = None
    message.audio = None
    message.document = None
    update.effective_message = message
    update.guest_message = message
    update.message = None
    update.edited_message = None

    await channel._on_message(update, MagicMock())
    assert channel._handle_message.await_count == 1
    kwargs = channel._handle_message.await_args.kwargs
    assert kwargs["metadata"]["guest_query_id"] == "guest-abc"
    assert kwargs["metadata"]["is_allowlisted"] is True
    assert kwargs["session_key"].startswith("telegram:guest:")


@pytest.mark.asyncio
async def test_guest_message_respects_allow_from():
    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(
        enabled=True, token="fake_token", guest_mode=True, allow_from=["111"]
    )
    channel = TelegramChannel(config, bus)
    channel._handle_message = AsyncMock()

    update = MagicMock()
    user = MagicMock()
    user.id = 999
    user.first_name = "Stranger"
    user.username = "stranger"
    user.is_bot = False
    update.effective_user = user
    message = MagicMock()
    message.chat.id = -100
    message.chat_id = -100
    message.chat.type = "supergroup"
    message.text = "@shiba help"
    message.caption = None
    message.reply_to_message = None
    message.media_group_id = None
    message.message_id = 5
    message.message_thread_id = None
    message.guest_query_id = "guest-xyz"
    message.business_connection_id = None
    update.effective_message = message
    update.guest_message = message
    update.message = None
    update.edited_message = None

    await channel._on_message(update, MagicMock())
    channel._handle_message.assert_not_awaited()


def test_draft_id_deterministic_from_message_id():
    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(enabled=True, token="fake_token")
    a = TelegramChannel(config, bus)
    b = TelegramChannel(config, bus)
    meta = {"message_id": 42}
    assert a._draft_id_for(1, None, meta) == b._draft_id_for(1, None, meta) == 42


def test_business_connections_eviction():
    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(enabled=True, token="fake_token")
    channel = TelegramChannel(config, bus)
    channel._BUSINESS_CONNECTIONS_CAP = 3
    for i in range(5):
        channel._store_capped(
            channel._business_connections, f"c{i}", {"n": i}, channel._BUSINESS_CONNECTIONS_CAP
        )
    assert list(channel._business_connections) == ["c2", "c3", "c4"]


def test_guest_result_title_uses_bot_username():
    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(enabled=True, token="fake_token")
    channel = TelegramChannel(config, bus)
    channel._bot_username = "my_bot"
    assert channel._guest_result_title() == "@my_bot"
    channel._bot_username = None
    assert channel._guest_result_title() == "ShibaClaw"


def test_telegram_config_ai_defaults():
    cfg = TelegramConfig()
    assert cfg.streaming is True
    assert cfg.guest_mode is False
    assert cfg.allow_bot_messages is False
    assert cfg.business_enabled is False
    assert cfg.managed_bots_enabled is False
    assert cfg.rich_messages is False
    assert cfg.open_groups is False


@pytest.mark.asyncio
async def test_rich_messages_uses_send_rich_message():
    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(enabled=True, token="t", rich_messages=True, streaming=False)
    channel = TelegramChannel(config, bus)
    channel._app = MagicMock()
    channel._app.bot.do_api_request = AsyncMock(return_value={"message_id": 42})
    channel._app.bot.send_message = AsyncMock()

    msg = MagicMock()
    msg.chat_id = "123"
    msg.content = "# Hello\n\n**bold** table reply"
    msg.media = None
    msg.metadata = {}

    await channel.send(msg)

    channel._app.bot.do_api_request.assert_awaited()
    endpoint = channel._app.bot.do_api_request.await_args.args[0]
    assert endpoint == "sendRichMessage"
    kwargs = channel._app.bot.do_api_request.await_args.kwargs["api_kwargs"]
    assert kwargs["chat_id"] == 123
    assert kwargs["rich_message"]["markdown"].startswith("# Hello")
    channel._app.bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_rich_messages_falls_back_to_send_message():
    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(enabled=True, token="t", rich_messages=True, streaming=False)
    channel = TelegramChannel(config, bus)
    channel._app = MagicMock()
    channel._app.bot.do_api_request = AsyncMock(side_effect=RuntimeError("no rich"))
    channel._app.bot.send_message = AsyncMock(return_value=MagicMock(message_id=7))

    msg = MagicMock()
    msg.chat_id = "123"
    msg.content = "plain fallback"
    msg.media = None
    msg.metadata = {}

    await channel.send(msg)
    assert channel._app.bot.send_message.await_count >= 1


@pytest.mark.asyncio
async def test_rich_progress_uses_rich_draft_in_private():
    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(enabled=True, token="t", rich_messages=True, streaming=True)
    channel = TelegramChannel(config, bus)
    channel._app = MagicMock()
    channel._app.bot.do_api_request = AsyncMock(return_value=True)
    channel._app.bot.send_message_draft = AsyncMock()

    msg = MagicMock()
    msg.chat_id = "123"  # private
    msg.content = "streaming…"
    msg.media = None
    msg.metadata = {"_progress": True, "message_id": 9}

    await channel.send(msg)

    channel._app.bot.do_api_request.assert_awaited()
    assert channel._app.bot.do_api_request.await_args.args[0] == "sendRichMessageDraft"
    channel._app.bot.send_message_draft.assert_not_awaited()


def test_build_rich_message_body_plain_stays_markdown():
    body = build_rich_message_body("Hello **world**")
    assert body == {"markdown": "Hello **world**"}


def test_build_rich_message_body_math_uses_blocks():
    body = build_rich_message_body("Energy:\n\n$$E = mc^2$$\n\nDone.")
    assert "blocks" in body
    types = [b["type"] for b in body["blocks"]]
    assert "mathematical_expression" in types
    math = next(b for b in body["blocks"] if b["type"] == "mathematical_expression")
    assert math["expression"] == "E = mc^2"


def test_build_rich_message_body_table_uses_blocks():
    md = "| A | B |\n| --- | --- |\n| 1 | 2 |\n"
    body = build_rich_message_body(md)
    assert "blocks" in body
    table = next(b for b in body["blocks"] if b["type"] == "table")
    assert table["cells"][0][0]["text"] == "A"
    assert table["cells"][0][0].get("is_header") is True
    assert table["cells"][1][1]["text"] == "2"


def test_build_rich_message_body_images_become_collage():
    md = (
        "Pics:\n\n"
        "![a](https://example.com/a.jpg)\n"
        "![b](https://example.com/b.jpg)\n"
    )
    body = build_rich_message_body(md)
    assert "blocks" in body
    collage = next(b for b in body["blocks"] if b["type"] == "collage")
    assert len(collage["blocks"]) == 2
    assert collage["blocks"][0]["photo"]["media"] == "https://example.com/a.jpg"


def test_extract_forward_info_from_user():
    origin = MagicMock()
    origin.type = "user"
    origin.sender_user = MagicMock()
    origin.sender_user.full_name = "Alice"
    origin.sender_user.first_name = "Alice"
    origin.sender_user.username = "alice"
    origin.sender_user.id = 42
    origin.sender_user_name = None
    origin.sender_chat = None
    origin.chat = None
    message = MagicMock()
    message.forward_origin = origin
    message.is_automatic_forward = False
    info = TelegramChannel._extract_forward_info(message)
    assert info is not None
    assert info["is_forward"] is True
    assert info["forward_from_user_id"] == 42
    assert "Alice" in info["forward_label"]
    assert "@alice" in info["forward_label"]


def test_ingress_private_dm_requires_allowlist():
    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(
        enabled=True, token="t", allow_from=["111"], open_groups=True, business_enabled=True
    )
    channel = TelegramChannel(config, bus)
    assert channel._ingress_allowed(
        is_group=False, has_business=False, sender_id="111", username=None
    )
    assert not channel._ingress_allowed(
        is_group=False, has_business=False, sender_id="999", username="x"
    )
    assert channel._ingress_allowed(
        is_group=True, has_business=False, sender_id="999", username="x"
    )
    assert channel._ingress_allowed(
        is_group=False, has_business=True, sender_id="999", username="x"
    )
    assert not channel._ingress_allowed(
        is_group=True, has_business=False, sender_id="999", username="x", is_guest=True
    )


@pytest.mark.asyncio
async def test_open_groups_marks_non_allowlisted():
    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(
        enabled=True, token="t", allow_from=["111"], open_groups=True, group_policy="open"
    )
    channel = TelegramChannel(config, bus)
    channel._download_message_media = AsyncMock(return_value=([], []))
    channel._handle_message = AsyncMock()
    channel._is_group_message_for_bot = AsyncMock(return_value=True)

    update = MagicMock()
    user = MagicMock()
    user.id = 999
    user.first_name = "Peer"
    user.username = "peer"
    user.is_bot = False
    update.effective_user = user
    message = MagicMock()
    message.chat.id = -100
    message.chat_id = -100
    message.chat.type = "supergroup"
    message.text = "hi"
    message.caption = None
    message.reply_to_message = None
    message.media_group_id = None
    message.message_id = 1
    message.message_thread_id = None
    message.business_connection_id = None
    message.forward_origin = None
    message.is_automatic_forward = False
    message.photo = None
    message.voice = None
    message.audio = None
    message.document = None
    message.video = None
    message.video_note = None
    message.animation = None
    update.effective_message = message
    update.guest_message = None
    update.message = message
    update.edited_message = None

    await channel._on_message(update, MagicMock())
    meta = channel._handle_message.await_args.kwargs["metadata"]
    assert meta["is_allowlisted"] is False
    content = channel._handle_message.await_args.kwargs["content"]
    assert content.startswith("Peer: ")


@pytest.mark.asyncio
async def test_private_dm_blocks_non_allowlisted_even_with_open_groups():
    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(enabled=True, token="t", allow_from=["111"], open_groups=True)
    channel = TelegramChannel(config, bus)
    channel._handle_message = AsyncMock()

    update = MagicMock()
    user = MagicMock()
    user.id = 999
    user.first_name = "Peer"
    user.username = "peer"
    user.is_bot = False
    update.effective_user = user
    message = MagicMock()
    message.chat.id = 999
    message.chat_id = 999
    message.chat.type = "private"
    message.text = "hack"
    message.caption = None
    message.reply_to_message = None
    message.media_group_id = None
    message.message_id = 1
    message.message_thread_id = None
    message.business_connection_id = None
    update.effective_message = message
    update.guest_message = None
    update.message = message
    update.edited_message = None

    await channel._on_message(update, MagicMock())
    channel._handle_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_forward_prefix_in_content():
    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(enabled=True, token="t", allow_from=["*"])
    channel = TelegramChannel(config, bus)
    channel._download_message_media = AsyncMock(return_value=([], []))
    channel._handle_message = AsyncMock()

    origin = MagicMock()
    origin.type = "user"
    origin.sender_user = MagicMock()
    origin.sender_user.full_name = "Bob"
    origin.sender_user.first_name = "Bob"
    origin.sender_user.username = "bob"
    origin.sender_user.id = 5
    origin.sender_user_name = None
    origin.sender_chat = None
    origin.chat = None

    update = MagicMock()
    user = MagicMock()
    user.id = 1
    user.first_name = "Owner"
    user.username = "owner"
    user.is_bot = False
    update.effective_user = user
    message = MagicMock()
    message.chat.id = 1
    message.chat_id = 1
    message.chat.type = "private"
    message.text = "look"
    message.caption = None
    message.reply_to_message = None
    message.media_group_id = None
    message.message_id = 9
    message.message_thread_id = None
    message.business_connection_id = None
    message.forward_origin = origin
    message.is_automatic_forward = False
    message.photo = None
    message.voice = None
    message.audio = None
    message.document = None
    message.video = None
    message.video_note = None
    message.animation = None
    update.effective_message = message
    update.guest_message = None
    update.message = message
    update.edited_message = None

    await channel._on_message(update, MagicMock())
    content = channel._handle_message.await_args.kwargs["content"]
    assert content.startswith("[Forwarded from: Bob (@bob)]")
    meta = channel._handle_message.await_args.kwargs["metadata"]
    assert meta["is_forward"] is True


def test_filter_tools_for_non_allowlisted():
    from shibaclaw.agent.loop import ShibaBrain

    brain = object.__new__(ShibaBrain)
    defs = [
        {"type": "function", "function": {"name": "web_search"}},
        {"type": "function", "function": {"name": "exec"}},
        {"type": "function", "function": {"name": "read_file"}},
        {"type": "function", "function": {"name": "mcp_call_tool"}},
    ]
    kept = brain._filter_tools_for_allowlist(defs, {"is_allowlisted": False}, "telegram")
    names = [(d.get("function") or {}).get("name") for d in kept]
    assert names == ["web_search"]
    assert brain._tool_blocked_for_non_allowlisted("exec", {"is_allowlisted": False}, "telegram")
    assert not brain._tool_blocked_for_non_allowlisted(
        "exec", {"is_allowlisted": True}, "telegram"
    )
    assert not brain._tool_blocked_for_non_allowlisted("exec", {}, "webui")
