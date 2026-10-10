"""Spawn tool for creating background subagents."""

import asyncio
from typing import TYPE_CHECKING, Any

from shibaclaw.agent.tools.base import Tool

if TYPE_CHECKING:
    from shibaclaw.agent.subagent import SubagentManager


class SpawnTool(Tool):
    """Tool to spawn a subagent for background task execution."""

    def __init__(self, manager: "SubagentManager"):
        self._manager = manager
        self._origin_channel = "cli"
        self._origin_chat_id = "direct"
        self._session_key = "cli:direct"
        self._active_model: str | None = None
        self._active_provider: Any | None = None
        self._parent_messages: list[dict[str, Any]] | None = None

    def set_context(
        self,
        channel: str,
        chat_id: str,
        session_key: str | None = None,
        model: str | None = None,
        provider: Any | None = None,
        parent_messages: list[dict[str, Any]] | None = None,
    ) -> None:
        """Set the origin context and active LLM configuration for subagent execution."""
        self._origin_channel = channel
        self._origin_chat_id = chat_id
        self._session_key = session_key or f"{channel}:{chat_id}"
        self._active_model = model
        self._active_provider = provider
        self._parent_messages = parent_messages

    @property
    def name(self) -> str:
        return "spawn"

    @property
    def description(self) -> str:
        return (
            "Spawn a subagent to handle a task in the background. "
            "Use this for complex or time-consuming tasks that can run independently. "
            "The subagent will complete the task and report back when done. "
            "For deliverables or existing projects, inspect the workspace first "
            "and use a dedicated subdirectory when helpful."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The task for the subagent to complete",
                },
                "label": {
                    "type": "string",
                    "description": "Optional short label for the task (for display)",
                },
                "mode": {
                    "type": "string",
                    "enum": ["isolated", "fork"],
                    "description": (
                        "Context mode: 'isolated' (default, fresh clean context window for independent research/review) "
                        "or 'fork' (copies supervisor conversation history for worker continuation tasks)."
                    ),
                    "default": "isolated",
                },
            },
            "required": ["task"],
        }

    async def execute(
        self,
        task: str,
        label: str | None = None,
        mode: str = "isolated",
        **kwargs: Any,
    ) -> str:
        """Spawn a subagent to execute the given task."""
        return await self._manager.spawn(
            task=task,
            label=label,
            mode=mode,
            origin_channel=self._origin_channel,
            origin_chat_id=self._origin_chat_id,
            session_key=self._session_key,
            model=self._active_model,
            provider=self._active_provider,
            parent_messages=self._parent_messages,
        )


class SpawnMeaTool(Tool):
    """Tool to execute a Manage-Execute-Audit (MEA) loop for complex tasks."""

    def __init__(self, manager: "SubagentManager"):
        self._manager = manager
        self._origin_channel = "cli"
        self._origin_chat_id = "direct"
        self._session_key = "cli:direct"
        self._active_model: str | None = None
        self._active_provider: Any | None = None
        self._parent_messages: list[dict[str, Any]] | None = None

    def set_context(
        self,
        channel: str,
        chat_id: str,
        session_key: str | None = None,
        model: str | None = None,
        provider: Any | None = None,
        parent_messages: list[dict[str, Any]] | None = None,
    ) -> None:
        """Set the origin context and active LLM configuration for subagent execution."""
        self._origin_channel = channel
        self._origin_chat_id = chat_id
        self._session_key = session_key or f"{channel}:{chat_id}"
        self._active_model = model
        self._active_provider = provider
        self._parent_messages = parent_messages

    @property
    def name(self) -> str:
        return "spawn_mea"

    @property
    def description(self) -> str:
        return (
            "Execute a Manage-Execute-Audit (MEA) loop for a complex task. "
            "This runs the task in a clean, fresh context, and then automatically "
            "spawns an auditor subagent to verify the results (e.g., via tests or checks)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The complex task to execute and audit",
                },
                "label": {
                    "type": "string",
                    "description": "Optional short label for the task (for display)",
                },
                "mode": {
                    "type": "string",
                    "enum": ["isolated", "fork"],
                    "description": "Context mode for MEA subagents: 'isolated' (default) or 'fork'.",
                    "default": "isolated",
                },
            },
            "required": ["task"],
        }

    async def execute(
        self,
        task: str,
        label: str | None = None,
        mode: str = "isolated",
        **kwargs: Any,
    ) -> str:
        """Execute the MEA loop for the given task."""
        asyncio.create_task(
            self._manager.execute_mea_loop(
                task=task,
                label=label,
                mode=mode,
                origin_channel=self._origin_channel,
                origin_chat_id=self._origin_chat_id,
                session_key=self._session_key,
                model=self._active_model,
                provider=self._active_provider,
                parent_messages=self._parent_messages,
            )
        )
        return f"MEA Loop [{label or task[:30]}] started in the background. I will manage, execute, and audit the task, and notify you when complete."
