"""Wake another profile in its own session and reply in the owner's chat."""

from __future__ import annotations

from typing import Any

from shibaclaw.agent.profiles import ProfileManager
from shibaclaw.agent.tools.base import Tool
from shibaclaw.agent.tools.secretary.acl import resolve_secretary_access
from shibaclaw.bus.events import InboundMessage

def hide_agent_send(tool_defs: list[dict], session_key: str | None) -> list[dict]:
    """Drop agent_send on an agent session so bots cannot wake each other."""
    if not str(session_key or "").startswith("agent:"):
        return tool_defs
    kept: list[dict] = []
    for item in tool_defs:
        name = (item.get("function") or {}).get("name") or item.get("name") or ""
        if name != "agent_send":
            kept.append(item)
    return kept


class AgentSendTool(Tool):
    """Owner asks one profile to work. The reply returns to this chat."""

    def __init__(self, sessions: Any, bus: Any, workspace: Any, owner_ids: set[str] | None = None):
        self._sessions = sessions
        self._bus = bus
        self._workspace = workspace
        self._owner_ids = owner_ids
        self._channel = ""
        self._chat_id = ""
        self._session_key = ""
        self._meta: dict[str, Any] = {}
        self._profile_id = ""

    def set_context(
        self,
        channel: str,
        chat_id: str,
        session_key: str | None = None,
        metadata: dict[str, Any] | None = None,
        profile_id: str | None = None,
        **_: Any,
    ) -> None:
        self._channel = channel or ""
        self._chat_id = str(chat_id or "")
        self._session_key = session_key or ""
        self._meta = dict(metadata or {})
        self._profile_id = profile_id or ""

    @property
    def name(self) -> str:
        return "agent_send"

    @property
    def description(self) -> str:
        return (
            "Wake another agent profile. Owner-only. "
            "The profile works in its own session and replies in this chat."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "profile_id": {"type": "string", "description": "Profile id from the manifest."},
                "message": {"type": "string", "description": "Task for that profile."},
            },
            "required": ["profile_id", "message"],
        }

    def _known_profile(self, profile_id: str) -> str | None:
        if not profile_id or any(ch in profile_id for ch in ":/\\"):
            return None
        for row in ProfileManager(self._workspace).list_profiles():
            if row.get("id") == profile_id:
                return str(row.get("label") or profile_id)
        return None

    async def execute(self, profile_id: str = "", message: str = "", **_: Any) -> str:
        access, detail = resolve_secretary_access(
            self._channel, self._chat_id, self._meta, self._owner_ids
        )
        if access != "full":
            return detail or "agent_send is owner-only."
        if str(self._session_key).startswith("agent:"):
            return "Error: agent_send is hidden on an agent session."
        target = str(profile_id or "").strip()
        text = str(message or "").strip()
        if not text:
            return "Error: message is empty."
        if not self._channel or not self._chat_id:
            return "Error: no owner chat to reply to."
        label = self._known_profile(target)
        if label is None:
            return f"Error: unknown profile '{target}'."
        key = f"agent:{target}"
        session = self._sessions.get_or_create(key)
        session.metadata["profile_id"] = target
        self._sessions.save(session)
        sender = self._profile_id or "default"
        await self._bus.publish_inbound(
            InboundMessage(
                channel=self._channel,
                sender_id=sender,
                chat_id=self._chat_id,
                content=f"[From {sender}]\n{text}",
                metadata={"is_allowlisted": True, "from_profile": sender},
                session_key_override=key,
            )
        )
        return f"Woke {label}. Reply will come back to this chat."
