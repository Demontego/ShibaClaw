"""Owner creates a custom agent. Shiba is the only built-in profile."""

from __future__ import annotations

import re
from contextvars import ContextVar
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from shibaclaw.agent.profiles import DEFAULT_PROFILE_ID, ProfileManager
from shibaclaw.agent.tools.base import Tool
from shibaclaw.agent.tools.secretary.acl import resolve_secretary_access

_PROFILE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,48}[a-zA-Z0-9]$")


def _slug(label: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", label.lower())
    return "-".join(parts)[:50].strip("-")


@dataclass(frozen=True)
class _AgentCreateContext:
    channel: str = ""
    chat_id: str = ""
    session_key: str = ""
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    ephemeral: bool = False


class AgentCreateTool(Tool):
    """Create one specialist from a short description. Does not wake it."""

    def __init__(self, workspace: Any, owner_ids: set[str] | None = None):
        self._workspace = workspace
        self._owner_ids = owner_ids
        self._context: ContextVar[_AgentCreateContext] = ContextVar(
            "agent_create_context", default=_AgentCreateContext()
        )

    def set_context(
        self,
        channel: str,
        chat_id: str,
        session_key: str | None = None,
        metadata: dict[str, Any] | None = None,
        ephemeral: bool = False,
        **_: Any,
    ) -> None:
        self._context.set(_AgentCreateContext(
            channel=channel or "",
            chat_id=str(chat_id or ""),
            session_key=session_key or "",
            metadata=MappingProxyType(dict(metadata or {})),
            ephemeral=ephemeral,
        ))

    @property
    def name(self) -> str:
        return "agent_create"

    @property
    def description(self) -> str:
        return (
            "Create a new agent profile for a task. Owner-only. "
            "Shiba is the only built-in agent. Pass a label and a brief that becomes the soul. "
            "Does not wake the new agent."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "label": {"type": "string", "description": "Display name."},
                "brief": {
                    "type": "string",
                    "description": "Who this agent is and which task it is for. Stored as the soul.",
                },
                "profile_id": {
                    "type": "string",
                    "description": "Optional id. Letters, numbers, hyphens. Derived from the label when omitted.",
                },
            },
            "required": ["label", "brief"],
        }

    async def execute(
        self,
        label: str = "",
        brief: str = "",
        profile_id: str = "",
        **_: Any,
    ) -> str:
        context = self._context.get()
        access, detail = resolve_secretary_access(
            context.channel, context.chat_id, context.metadata, self._owner_ids
        )
        if access != "full":
            return detail or "agent_create is owner-only."
        if context.session_key.startswith("agent:"):
            return "Error: agent_create is hidden on an agent session."
        private = context.ephemeral or context.metadata.get("incognito") or context.metadata.get("ephemeral")
        if private:
            return "Error: agent_create is unavailable in incognito or ephemeral sessions."
        name = str(label or "").strip()
        text = str(brief or "").strip()
        if not name or not text:
            return "Error: label and brief are required."
        target = str(profile_id or "").strip() or _slug(name)
        if target == DEFAULT_PROFILE_ID or not _PROFILE_ID_RE.match(target):
            return f"Error: invalid profile id '{target}'."
        manager = ProfileManager(self._workspace)
        if manager.get_profile(target):
            return f"Error: profile '{target}' already exists."
        manager.create_profile(target, name, text, text)
        return f"Created {name} ({target})."
