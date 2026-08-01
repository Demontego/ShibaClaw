"""Human-readable nicknames for Telegram sessions in the WebUI list.

Rules:
- Chat Automation (business) DM: "You + {peer}"
- Group / supergroup: chat title
- Private bot DM / guest: peer first name (owner DM → "You")

Manual Rename wins unless nickname_auto is set.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_PEOPLE_NAME_RE = re.compile(r"^(\d+)_(.+)\.md$")


def telegram_owner_ids(channels_config: Any | None) -> set[str]:
    """Resolve owner Telegram user ids from channels.telegram.allowFrom."""
    if channels_config is None:
        return set()
    extra = getattr(channels_config, "model_extra", None) or {}
    tg = extra.get("telegram") if isinstance(extra, dict) else None
    if tg is None:
        tg = getattr(channels_config, "telegram", None)
    if tg is None:
        return set()
    if hasattr(tg, "model_dump"):
        data = tg.model_dump(by_alias=True)
    elif isinstance(tg, dict):
        data = tg
    else:
        return set()
    raw = data.get("allowFrom") or data.get("allow_from") or []
    if not isinstance(raw, list):
        return set()
    return {str(x) for x in raw if x is not None and str(x).strip() and str(x) != "*"}


def _msg_meta(msg: dict[str, Any]) -> dict[str, Any]:
    meta = msg.get("metadata")
    return meta if isinstance(meta, dict) else {}


def _session_chat_id(session_key: str) -> str | None:
    parts = (session_key or "").split(":")
    if len(parts) < 2 or parts[0] != "telegram":
        return None
    if parts[1] == "guest":
        return parts[2] if len(parts) >= 3 else None
    return parts[1] if parts[1].lstrip("-").isdigit() else None


def _people_name(people_dir: Path | None, peer_id: str | None) -> str | None:
    if not people_dir or not peer_id or not people_dir.is_dir():
        return None
    for path in people_dir.glob(f"{peer_id}_*.md"):
        m = _PEOPLE_NAME_RE.match(path.name)
        if not m:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return m.group(2)
        if text.startswith("---"):
            end = text.find("\n---", 3)
            block = text[3:end] if end > 0 else ""
            for line in block.splitlines():
                if line.startswith("peer_name:"):
                    val = line.split(":", 1)[1].strip().strip("\"'")
                    if val:
                        return val
        return m.group(2)
    return None


def _peer_name_from_messages(
    messages: list[dict[str, Any]],
    peer_id: str | None,
    owner_ids: set[str],
) -> str | None:
    if peer_id is None:
        return None
    for msg in reversed(messages):
        if msg.get("role") != "user":
            continue
        meta = _msg_meta(msg)
        uid = meta.get("user_id")
        if uid is None or str(uid) != str(peer_id):
            continue
        name = (meta.get("first_name") or meta.get("username") or "").strip()
        if name:
            return name
    for msg in reversed(messages):
        if msg.get("role") != "user":
            continue
        meta = _msg_meta(msg)
        uid = meta.get("user_id")
        if uid is None or str(uid) in owner_ids:
            continue
        name = (meta.get("first_name") or meta.get("username") or "").strip()
        if name:
            return name
    return None


def _is_business(messages: list[dict[str, Any]], meta: dict[str, Any] | None) -> bool:
    if meta and meta.get("business_connection_id"):
        return True
    return any(_msg_meta(m).get("business_connection_id") for m in messages)


def _group_title(messages: list[dict[str, Any]], meta: dict[str, Any] | None) -> str | None:
    if meta:
        title = (meta.get("chat_title") or "").strip()
        if title:
            return title
    for msg in reversed(messages):
        title = (_msg_meta(msg).get("chat_title") or "").strip()
        if title:
            return title
    return None


def suggest_label(
    session_key: str,
    messages: list[dict[str, Any]] | None = None,
    *,
    meta: dict[str, Any] | None = None,
    workspace: Path | str | None = None,
    owner_ids: set[str] | None = None,
    owner_label: str = "You",
) -> str | None:
    """Return a display label for a telegram session key, or None if unknown."""
    if not (session_key or "").startswith("telegram:"):
        return None
    msgs = messages or []
    meta = meta or {}
    owners = owner_ids or set()
    people_dir = Path(workspace) / "memory" / "people" if workspace else None
    chat_id = _session_chat_id(session_key)
    is_guest = session_key.startswith("telegram:guest:") or bool(meta.get("is_guest"))

    groupish = bool(chat_id and chat_id.startswith("-")) or bool(meta.get("is_group"))
    if not groupish:
        groupish = bool(_group_title(msgs, meta))
    if groupish and not is_guest:
        title = _group_title(msgs, meta)
        if title:
            return title
        if chat_id and chat_id.startswith("-"):
            return None

    if is_guest:
        name = (meta.get("first_name") or meta.get("username") or "").strip() or None
        if not name:
            for msg in reversed(msgs):
                if msg.get("role") != "user":
                    continue
                m = _msg_meta(msg)
                if m.get("is_bot_sender"):
                    continue
                name = (m.get("first_name") or m.get("username") or "").strip() or None
                if name:
                    break
        return name

    peer_id = chat_id
    name = None
    if meta.get("user_id") is not None and str(meta.get("user_id")) == str(peer_id):
        name = (meta.get("first_name") or meta.get("username") or "").strip() or None
    if not name:
        name = _peer_name_from_messages(msgs, peer_id, owners)
    if not name:
        name = _people_name(people_dir, peer_id)

    if _is_business(msgs, meta):
        if not name:
            return None
        return f"{owner_label} + {name}"

    if peer_id and peer_id in owners:
        return owner_label
    return name


def maybe_autolabel_session(
    session: Any,
    meta: dict[str, Any] | None,
    workspace: Path | str | None,
    *,
    owner_ids: set[str] | None = None,
    owner_label: str = "You",
) -> bool:
    """Set session.metadata nickname when missing or previously auto-labeled.

    Returns True if metadata changed.
    """
    key = getattr(session, "key", "") or ""
    if not key.startswith("telegram:"):
        return False
    smeta = getattr(session, "metadata", None)
    if not isinstance(smeta, dict):
        return False
    existing = (smeta.get("nickname") or "").strip()
    if existing and smeta.get("nickname_auto") is not True:
        return False

    label = suggest_label(
        key,
        getattr(session, "messages", None) or [],
        meta=meta or {},
        workspace=workspace,
        owner_ids=owner_ids,
        owner_label=owner_label,
    )
    if not label or label == existing:
        return False
    smeta["nickname"] = label
    smeta["nickname_auto"] = True
    return True
