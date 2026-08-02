"""Access control for secretary archive tools."""

from __future__ import annotations

from typing import Any

OWNER_CHANNELS = frozenset({"webui", "cli", "system", "automation"})


def _is_owner(user_id: object, owner_ids: set[str] | None) -> bool:
    """Match Telegram ``allowFrom``-style ids without treating ``*`` as an owner."""
    if user_id is None or not owner_ids:
        return False
    user_id = str(user_id).strip()
    for owner_id in owner_ids:
        candidate = str(owner_id).strip()
        if not candidate or candidate == "*":
            continue
        # Telegram accepts a numeric id, username, or "id|username".
        if user_id == candidate or user_id in candidate.split("|", 1):
            return True
    return False


def resolve_secretary_access(
    channel: str | None,
    chat_id: str | None,
    meta: dict[str, Any] | None,
    owner_ids: set[str] | None = None,
) -> tuple[str, str | None]:
    """Return ``(access, detail)`` for the secretary archive.

    ``access`` is ``full`` for owner-operated surfaces and configured owners,
    otherwise ``deny``. Secretary summons intentionally do not grant archive
    access: their current-DM context belongs in the prompt, not in this tool.
    """
    del chat_id  # Identity is carried by Telegram metadata, not the destination chat.
    meta = meta or {}
    if meta.get("is_guest"):
        return (
            "deny",
            "Secretary archive is private to the owner. "
            "Guest Mode cannot use business_search / business_send.",
        )

    if (channel or "").casefold().strip() in OWNER_CHANNELS:
        return ("full", None)

    if _is_owner(meta.get("user_id"), owner_ids):
        return ("full", None)

    if meta.get("secretary_summon"):
        return (
            "deny",
            "business_search is owner-only. On secretary summon for a peer, "
            "use only the THIS-DM context in the prompt; refuse questions about "
            "the full secretary archive or other chats.",
        )

    return (
        "deny",
        "Secretary archive is only available when the owner asks "
        "(owner Telegram DM / WebUI). Do not reveal other people's DMs.",
    )
