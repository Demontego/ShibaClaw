"""Send an opt-in Telegram Chat Automation message through the outbound callback."""

from __future__ import annotations

import hashlib
import time
from datetime import datetime
from typing import Any, Awaitable, Callable

from shibaclaw.agent.tools.base import Tool
from shibaclaw.agent.tools.secretary.acl import resolve_secretary_access
from shibaclaw.bus.events import OutboundMessage

_RECENT_SENDS: dict[str, float] = {}
_DEDUPE_TTL_S = 15.0


def _meta(message: dict[str, Any]) -> dict[str, Any]:
    metadata = message.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _peer_id(key: str) -> int | None:
    parts = key.split(":")
    return int(parts[1]) if len(parts) >= 2 and parts[1].lstrip("-").isdigit() else None


def _is_business(messages: list[dict[str, Any]]) -> bool:
    return any(_meta(message).get("business_connection_id") for message in messages)


def _is_bot_peer(messages: list[dict[str, Any]], peer_id: int) -> bool:
    return any(
        _meta(message).get("is_bot_sender") and str(_meta(message).get("user_id")) == str(peer_id)
        for message in messages
    )


def _label(messages: list[dict[str, Any]], peer_id: int, fallback: str) -> str:
    for message in reversed(messages):
        metadata = _meta(message)
        if message.get("role") == "user" and str(metadata.get("user_id")) == str(peer_id):
            name = metadata.get("first_name") or metadata.get("username") or peer_id
            return f"{name} ({peer_id})"
    return fallback


class BusinessSendTool(Tool):
    """Send a secretary peer DM via a Telegram business connection."""

    def __init__(
        self,
        sessions: Any,
        send_callback: Callable[[OutboundMessage], Awaitable[None]] | None = None,
        owner_ids: set[str] | None = None,
    ):
        self._sessions = sessions
        self._send_callback = send_callback
        self._owner_ids = owner_ids
        self._channel = ""
        self._chat_id = ""
        self._meta: dict[str, Any] = {}

    def set_context(
        self, channel: str, chat_id: str, metadata: dict[str, Any] | None = None, **_: Any
    ) -> None:
        self._channel, self._chat_id, self._meta = channel or "", str(chat_id or ""), dict(metadata or {})

    @property
    def name(self) -> str:
        return "business_send"

    @property
    def description(self) -> str:
        return (
            "Send an owner-requested message into a Telegram Chat Automation peer DM. "
            "Owner-only. Do not use for drafts; use business_search to resolve ambiguous peers."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "peer": {"type": "string", "description": "Telegram id, @username, or first name."},
                "content": {"type": "string", "description": "Exact text to send."},
            },
            "required": ["peer", "content"],
        }

    def _matches(self, peer: str) -> list[tuple[str, str, int, str]]:
        matches: list[tuple[str, str, int, str]] = []
        for info in self._sessions.list_sessions():
            key = str(info.get("key") or "")
            peer_id = _peer_id(key)
            if not key.startswith("telegram:") or peer_id is None or peer_id <= 0:
                continue
            session = self._sessions.get_or_create(key)
            messages = session.messages
            if not _is_business(messages) or _is_bot_peer(messages, peer_id):
                continue
            connection = next(
                (
                    str(_meta(message)["business_connection_id"])
                    for message in reversed(messages)
                    if _meta(message).get("business_connection_id")
                ),
                None,
            )
            if not connection:
                continue
            label = _label(messages, peer_id, key)
            identifiers = {str(peer_id)}
            identifiers.update(
                str(value).lstrip("@").casefold()
                for message in messages
                if message.get("role") == "user"
                and str(_meta(message).get("user_id")) == str(peer_id)
                for value in (_meta(message).get("username"), _meta(message).get("first_name"))
                if value
            )
            if peer not in identifiers:
                continue
            matches.append((key, label, peer_id, connection))
        unique: dict[int, tuple[str, str, int, str]] = {}
        for match in matches:
            unique.setdefault(match[2], match)
        return list(unique.values())

    async def execute(self, *, peer: str, content: str, **_: Any) -> str:
        if not self._send_callback:
            return "Error: Message sending not configured"
        access, detail = resolve_secretary_access(
            self._channel, self._chat_id, self._meta, self._owner_ids
        )
        if access != "full":
            return f"Denied: {detail or 'business_send is owner-only.'}"
        text, peer_input = content.strip(), peer.strip().lstrip("@").casefold()
        if not text:
            return "Error: empty content"
        if not peer_input:
            return "Error: peer required (id, @username, or name)"
        matches = self._matches(peer_input)
        if not matches:
            return f"No secretary peer matching {peer!r}. Use business_search mode=list first."
        if len(matches) > 1:
            return "\n".join(
                [f"Ambiguous peer {peer!r} — pick one id and retry:", *(f"- {label} → peer={peer_id}" for _, label, peer_id, _ in matches[:10])]
            )
        key, label, peer_id, connection = matches[0]
        now = time.monotonic()
        dedupe_key = hashlib.sha1(f"{peer_id}\n{text}".encode()).hexdigest()
        _RECENT_SENDS.update({k: started for k, started in _RECENT_SENDS.items() if now - started <= _DEDUPE_TTL_S})
        if dedupe_key in _RECENT_SENDS:
            return f"Skipped duplicate business_send to {label} (same text within {_DEDUPE_TTL_S:.0f}s)."
        _RECENT_SENDS[dedupe_key] = now
        outbound = OutboundMessage(
            channel="telegram",
            chat_id=str(peer_id),
            content=text,
            metadata={
                "business_connection_id": connection,
                "origin_channel": self._channel or "telegram",
                "origin_chat_id": self._chat_id,
                "secretary_send": True,
            },
        )
        try:
            await self._send_callback(outbound)
        except Exception as error:
            _RECENT_SENDS.pop(dedupe_key, None)
            return f"Error queueing business_send to {label}: {error}"
        try:
            session = self._sessions.get_or_create(key)
            session.messages.append(
                {
                    "role": "user",
                    "content": text,
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {"business_connection_id": connection, "secretary_send": True},
                }
            )
            if hasattr(session, "save"):
                session.save()
        except Exception:
            pass
        return f"Queued business_send to {label} (chat_id={peer_id}) via business_connection_id."
