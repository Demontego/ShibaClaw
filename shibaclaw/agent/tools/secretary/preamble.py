"""Prompt context for Telegram Guest Mode and secretary summons."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from shibaclaw.agent.tools.secretary.acl import _is_owner


def _meta(message: dict[str, Any]) -> dict[str, Any]:
    value = message.get("metadata")
    return value if isinstance(value, dict) else {}


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block["text"]
            for block in content
            if isinstance(block, dict) and block.get("type") == "text" and block.get("text")
        )
    return ""


def _speaker(meta: dict[str, Any]) -> str:
    user_id = meta.get("user_id")
    name = str(meta.get("first_name") or meta.get("username") or user_id or "unknown").strip()
    username = str(meta.get("username") or "").strip()
    return " ".join(part for part in (name, f"@{username}" if username else "", f"id={user_id}" if user_id is not None else "") if part)


def _archive(sessions: Any, chat_id: str, *, owner_ids: set[str], limit: int = 60) -> list[str]:
    """Return a compact transcript for this business DM only."""
    if not chat_id.lstrip("-").isdigit() or _is_owner(chat_id, owner_ids):
        return []
    try:
        messages = sessions.get_or_create(f"telegram:{chat_id}").messages
    except Exception:
        return []
    rows: list[tuple[datetime, str]] = []
    for message in messages:
        if message.get("role") not in ("user", "assistant") or message.get("tool_calls"):
            continue
        meta = _meta(message)
        if message["role"] == "user" and not meta.get("business_connection_id"):
            continue
        text = _content_text(message.get("content")).strip()
        if not text:
            continue
        try:
            timestamp = datetime.fromisoformat(message.get("timestamp", ""))
        except (TypeError, ValueError):
            timestamp = datetime.min
        if timestamp.tzinfo is not None:
            timestamp = timestamp.astimezone().replace(tzinfo=None)
        user_id = meta.get("user_id")
        who = "secretary" if message["role"] == "assistant" else (
            "owner" if _is_owner(user_id, owner_ids) else _speaker(meta)
        )
        flat_text = re.sub(r"\s+", " ", text)[:180]
        rows.append((timestamp, f"- [{timestamp:%Y-%m-%d %H:%M}] {who}: {flat_text}"))
    return [line for _, line in sorted(rows)[-limit:]]


def build_guest_preamble(
    sessions: Any, *, chat_id: str, meta: dict[str, Any] | None, owner_ids: set[str]
) -> str:
    """Build identity and access boundaries for a Guest Mode turn."""
    meta = meta or {}
    speaker = _speaker(meta)
    is_owner = _is_owner(meta.get("user_id"), owner_ids)
    lines = [
        "[Guest Mode context — follow strictly]",
        f"The person speaking NOW is: {speaker}.",
        "Reply to this speaker only.",
    ]
    if is_owner:
        lines.append("This speaker is the owner.")
        if archive := _archive(sessions, chat_id, owner_ids=owner_ids, limit=40):
            lines.extend(["Recent Chat Automation archive for this peer DM:", *archive])
    else:
        lines.extend(
            [
                "This speaker is not the owner. USER.md describes the owner, not this person.",
                "Allowed tools only: web_search and web_fetch.",
                "Refuse access to the secretary archive, business_search, business_send, owner secrets, "
                "and other people's DMs.",
            ]
        )
    return "\n".join([*lines, "[End Guest Mode context]", ""])


def build_secretary_preamble(
    sessions: Any, *, chat_id: str, meta: dict[str, Any] | None, owner_ids: set[str]
) -> str:
    """Build context for a Chat Automation summon in a personal DM."""
    meta = meta or {}
    speaker = _speaker(meta)
    is_owner = _is_owner(meta.get("user_id"), owner_ids)
    lines = [
        "[Secretary summon context — follow strictly]",
        f"Person speaking NOW: {speaker}.",
        "Reply in this same DM as the owner's secretary.",
    ]
    if is_owner:
        lines.append("This speaker is the owner.")
    else:
        lines.extend(
            [
                "This speaker is not the owner. Address this speaker, never call them owner.",
                "Use only this-DM context. Refuse business_search, business_send, the full secretary "
                "archive, other chats, and owner secrets.",
            ]
        )
    if archive := _archive(sessions, chat_id, owner_ids=owner_ids):
        lines.extend(["Recent Chat Automation archive for this DM only (newest last):", *archive])
    else:
        lines.append("No secretary archive matched this DM.")
    return "\n".join([*lines, "[End Secretary summon context]", ""])
