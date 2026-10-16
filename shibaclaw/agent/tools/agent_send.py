"""Wake another profile in its own session and reply in the owner's chat."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from shibaclaw.agent.profiles import ProfileManager
from shibaclaw.agent.tools.base import Tool
from shibaclaw.agent.tools.secretary.acl import resolve_secretary_access
from shibaclaw.bus.events import InboundMessage


@dataclass(frozen=True)
class _AgentSendContext:
    channel: str = ""
    chat_id: str = ""
    session_key: str = ""
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    profile_id: str = ""
    ephemeral: bool = False


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
        self._context: ContextVar[_AgentSendContext] = ContextVar(
            "agent_send_context", default=_AgentSendContext()
        )

    def set_context(
        self,
        channel: str,
        chat_id: str,
        session_key: str | None = None,
        metadata: dict[str, Any] | None = None,
        profile_id: str | None = None,
        ephemeral: bool = False,
        **_: Any,
    ) -> None:
        self._context.set(_AgentSendContext(
            channel=channel or "",
            chat_id=str(chat_id or ""),
            session_key=session_key or "",
            metadata=MappingProxyType(dict(metadata or {})),
            profile_id=profile_id or "",
            ephemeral=ephemeral,
        ))

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
        context = self._context.get()
        access, detail = resolve_secretary_access(
            context.channel, context.chat_id, context.metadata, self._owner_ids
        )
        if access != "full":
            return detail or "agent_send is owner-only."
        if context.session_key.startswith("agent:"):
            return "Error: agent_send is hidden on an agent session."
        private = context.ephemeral or context.metadata.get("incognito") or context.metadata.get("ephemeral")
        if not private and context.session_key:
            source = self._sessions.get_or_create(context.session_key)
            private = source.metadata.get("incognito") or source.metadata.get("ephemeral")
        if private:
            return "Error: agent_send is unavailable in incognito or ephemeral sessions because agent conversations are saved."
        target = str(profile_id or "").strip()
        text = str(message or "").strip()
        if not text:
            return "Error: message is empty."
        if not context.channel or not context.chat_id:
            return "Error: no owner chat to reply to."
        label = self._known_profile(target)
        if label is None:
            return f"Error: unknown profile '{target}'."
        key = f"agent:{target}"
        session = self._sessions.get_or_create(key)
        session.metadata["profile_id"] = target
        self._sessions.save(session)
        sender = context.profile_id or "default"
        await self._bus.publish_inbound(
            InboundMessage(
                channel=context.channel,
                sender_id=sender,
                chat_id=context.chat_id,
                content=f"[From {sender}]\n{text}",
                metadata={"is_allowlisted": True, "from_profile": sender},
                session_key_override=key,
            )
        )
        return f"Woke {label}. Reply will come back to this chat."
