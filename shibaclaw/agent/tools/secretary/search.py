"""Search and list Telegram Chat Automation secretary archives."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from shibaclaw.agent.tools.base import Tool
from shibaclaw.agent.tools.secretary.acl import resolve_secretary_access
from shibaclaw.agent.tools.secretary import sync


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block["text"]
            for block in content
            if isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
        )
    return ""


def _meta(message: dict[str, Any]) -> dict[str, Any]:
    metadata = message.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _peer_id(key: str) -> int | None:
    parts = key.split(":")
    return int(parts[1]) if len(parts) >= 2 and parts[1].lstrip("-").isdigit() else None


def _is_business(messages: list[dict[str, Any]]) -> bool:
    return any(_meta(message).get("business_connection_id") for message in messages)


def _is_bot_peer(messages: list[dict[str, Any]], peer_id: int | None) -> bool:
    return any(
        _meta(message).get("is_bot_sender")
        and peer_id is not None
        and str(_meta(message).get("user_id")) == str(peer_id)
        for message in messages
    )


def _peer_label(messages: list[dict[str, Any]], peer_id: int | None, key: str) -> str:
    for message in reversed(messages):
        metadata = _meta(message)
        if message.get("role") != "user" or (
            peer_id is not None and str(metadata.get("user_id")) != str(peer_id)
        ):
            continue
        name = metadata.get("first_name") or metadata.get("username") or peer_id
        return f"{name} ({peer_id})" if peer_id is not None else str(name)
    return key


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.astimezone().replace(tzinfo=None) if parsed.tzinfo else parsed


class BusinessSearchTool(Tool):
    """List and qmd-search Chat Automation peer archives."""

    def __init__(self, sessions: Any, owner_ids: set[str] | None = None):
        self._sessions = sessions
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
        return "business_search"

    @property
    def description(self) -> str:
        return (
            "Search the owner's Telegram Chat Automation secretary archive. "
            "Owner-only; unavailable in Guest Mode, groups, and peer secretary summons. "
            "Modes: list, recent, search. Does not send messages."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["list", "recent", "search"]},
                "query": {"type": "string"},
                "peer": {"type": "string"},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 40},
                "days": {"type": "integer", "minimum": 1, "maximum": 365},
            },
            "required": [],
        }

    def _sessions_for_peer(self, peer_filter: str) -> list[tuple[Any, str, int | None]]:
        result: list[tuple[Any, str, int | None]] = []
        for info in self._sessions.list_sessions():
            key = str(info.get("key") or "")
            if not key.startswith("telegram:"):
                continue
            session = self._sessions.get_or_create(key)
            peer_id = _peer_id(key)
            if not _is_business(session.messages) or _is_bot_peer(session.messages, peer_id):
                continue
            label = _peer_label(session.messages, peer_id, key)
            if peer_filter and peer_filter not in f"{key} {label}".casefold():
                continue
            result.append((session, label, peer_id))
        return result

    def _list(self, peer_filter: str, top_k: int, days: int) -> str:
        cutoff = datetime.now() - timedelta(days=days)
        rows: list[tuple[datetime, str]] = []
        for session, label, _ in self._sessions_for_peer(peer_filter):
            messages = [
                message for message in session.messages
                if message.get("role") == "user"
                and _meta(message).get("business_connection_id")
                and (_timestamp(message.get("timestamp")) or datetime.min) >= cutoff
            ]
            if not messages:
                continue
            latest = max((_timestamp(message.get("timestamp")) or datetime.min for message in messages))
            rows.append((latest, f"- {label} | messages={len(messages)} | last {latest:%Y-%m-%d %H:%M}"))
        rows.sort(reverse=True)
        if not rows:
            return f"Secretary archive empty (last {days}d). No Chat Automation peer sessions."
        return "\n".join(
            [f"Secretary archive — {min(top_k, len(rows))} peers (last {days}d):", *(row[1] for row in rows[:top_k])]
        )

    def _recent(self, peer_filter: str, top_k: int, days: int) -> str:
        cutoff = datetime.now() - timedelta(days=days)
        rows: list[tuple[datetime, str]] = []
        for session, label, peer_id in self._sessions_for_peer(peer_filter):
            for message in session.messages:
                metadata = _meta(message)
                text = _content_text(message.get("content")).strip()
                timestamp = _timestamp(message.get("timestamp"))
                if (
                    message.get("role") != "user"
                    or not metadata.get("business_connection_id")
                    or not text
                    or (timestamp is not None and timestamp < cutoff)
                ):
                    continue
                speaker = label.split(" (", 1)[0] if str(metadata.get("user_id")) == str(peer_id) else "owner"
                timestamp_text = timestamp.strftime("%Y-%m-%d %H:%M") if timestamp else "?"
                rows.append(
                    (timestamp or datetime.min, f"- [{timestamp_text}] {label} | {speaker}: {text[:160]}")
                )
        rows.sort(reverse=True)
        if not rows:
            return f"No recent secretary messages (last {days}d)."
        return "\n".join(
            [f"Secretary archive — {min(top_k, len(rows))} most recent:", *(row[1] for row in rows[:top_k])]
        )

    def _workspace(self) -> Path:
        sessions_dir = getattr(self._sessions, "sessions_dir", None)
        return Path(sessions_dir).parent if sessions_dir is not None else Path.home() / ".shibaclaw" / "workspace"

    def _search(self, query: str, peer_filter: str, top_k: int) -> str:
        if not query.strip():
            return "Empty query — use mode=recent or mode=list instead."
        try:
            workspace = self._workspace()
            sync.sync_secretary_markdown(workspace)
            if error := sync.ensure_qmd_collection(workspace):
                return f"Secretary qmd unavailable: {error}"
            if error := sync.qmd_reindex():
                return f"Secretary qmd unavailable: {error}"
            error, results = sync.qmd_search(query, top_k=top_k)
            if error:
                return f"Secretary qmd search failed: {error}"
            return sync.format_qmd_hits(results, query, peer=peer_filter or None)
        except (OSError, RuntimeError) as error:
            return f"Secretary qmd search failed: {error}"

    async def execute(
        self,
        *,
        mode: str | None = None,
        query: str | None = None,
        peer: str | None = None,
        top_k: int | None = None,
        days: int | None = None,
        **_: Any,
    ) -> str:
        access, detail = resolve_secretary_access(
            self._channel, self._chat_id, self._meta, self._owner_ids
        )
        if access != "full":
            return f"Denied: {detail or 'Secretary archive access denied.'}"
        selected = (mode or ("search" if query else "recent")).casefold().strip()
        if selected not in {"list", "recent", "search"}:
            return f"Unknown mode {mode!r}. Use list|recent|search."
        peer_filter = (peer or "").lstrip("@").casefold()
        limit = max(1, min(40, int(top_k or (15 if selected == "list" else 20))))
        age = max(1, min(365, int(days or (90 if selected == "search" else 7))))
        if selected == "list":
            return self._list(peer_filter, limit, age)
        if selected == "recent":
            return self._recent(peer_filter, limit, age)
        return self._search(query or "", peer_filter, limit)
