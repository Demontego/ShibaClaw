"""Android companion tool proxy: phone hosts tools, gateway LLM invokes them."""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Protocol

from loguru import logger

from shibaclaw.agent.tools.base import Tool
from shibaclaw.agent.tools.registry import SkillVault

INVOKE_TIMEOUT_S = 45.0
_DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")

SendInvoke = Callable[[dict[str, Any]], Awaitable[None]]


class _Vault(Protocol):
    def register(self, tool: Tool) -> None: ...
    def unregister(self, name: str) -> None: ...


ANDROID_TOOL_SPECS: tuple[dict[str, Any], ...] = (
    {
        "name": "list_apps",
        "description": (
            "List launchable apps on the paired Android phone. "
            "Returns JSON array of {label, package}. Optional query filters by name."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Optional case-insensitive substring filter",
                }
            },
        },
    },
    {
        "name": "launch_app",
        "description": (
            "Launch an installed app on the paired Android phone by package name. "
            "The phone may prompt the user before opening."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "package": {
                    "type": "string",
                    "description": "Android application id, e.g. com.whatsapp",
                }
            },
            "required": ["package"],
        },
    },
    {
        "name": "open_setting",
        "description": (
            "Open a system Settings screen on the paired Android phone. "
            "Does not flip toggles; opens the page so the user (or Shiba via later tools) can act."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "which": {
                    "type": "string",
                    "description": (
                        "wifi | bluetooth | display | sound | apps | battery | wireless | "
                        "notifications | nfc | location | accessibility | development | date | locale"
                    ),
                }
            },
            "required": ["which"],
        },
    },
)

ALLOWED_ANDROID_TOOLS = {spec["name"] for spec in ANDROID_TOOL_SPECS}


@dataclass
class DeviceConnection:
    device_id: str
    label: str
    send: SendInvoke
    tool_names: list[str] = field(default_factory=list)


class DeviceProxyTool(Tool):
    """Tool whose execute() waits for the paired Android device."""

    def __init__(self, hub: DeviceHub, spec: dict[str, Any]) -> None:
        self._hub = hub
        self._spec = spec

    @property
    def name(self) -> str:
        return str(self._spec["name"])

    @property
    def description(self) -> str:
        return str(self._spec["description"])

    @property
    def parameters(self) -> dict[str, Any]:
        return dict(self._spec["parameters"])

    async def execute(self, **kwargs: Any) -> str:
        return await self._hub.invoke(self.name, kwargs)


class DeviceHub:
    """One active Android companion. Re-register after agent.reconfigure()."""

    def __init__(self, vault: SkillVault | None = None) -> None:
        self._vault: SkillVault | None = vault
        self._device: DeviceConnection | None = None
        self._pending: dict[str, asyncio.Future[str]] = {}

    @property
    def device_id(self) -> str | None:
        return self._device.device_id if self._device else None

    @property
    def connected(self) -> bool:
        return self._device is not None

    def bind_vault(self, vault: SkillVault) -> None:
        self._vault = vault
        if self._device:
            self._register_tools()

    def attach(self, device_id: str, send: SendInvoke, *, label: str = "") -> DeviceConnection:
        device_id = (device_id or "").strip()
        if not _DEVICE_ID_RE.match(device_id):
            raise ValueError("invalid device_id")
        self.detach()
        conn = DeviceConnection(
            device_id=device_id,
            label=label.strip() or device_id,
            send=send,
            tool_names=[spec["name"] for spec in ANDROID_TOOL_SPECS],
        )
        self._device = conn
        self._register_tools()
        logger.info("📱 Android device attached: {} ({})", conn.device_id, conn.label)
        return conn

    def detach(self, device_id: str | None = None) -> None:
        conn = self._device
        if conn is None:
            return
        if device_id and conn.device_id != device_id:
            return
        self._unregister_tools(conn.tool_names)
        self._device = None
        pending = list(self._pending.values())
        self._pending.clear()
        for fut in pending:
            if not fut.done():
                fut.set_result("Error: Android device disconnected")
        logger.info("📱 Android device detached: {}", conn.device_id)

    def complete(self, invoke_id: str, *, ok: bool, result: str = "", error: str = "") -> bool:
        fut = self._pending.pop(invoke_id, None)
        if fut is None or fut.done():
            return False
        if ok:
            fut.set_result(result if result else "(ok)")
        else:
            fut.set_result(f"Error: {error or 'Android tool failed'}")
        return True

    async def invoke(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        conn = self._device
        if conn is None:
            return "Error: No Android device connected"
        if name not in ALLOWED_ANDROID_TOOLS:
            return f"Error: Unknown Android tool '{name}'"
        invoke_id = uuid.uuid4().hex[:16]
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[str] = loop.create_future()
        self._pending[invoke_id] = fut
        payload = {
            "id": invoke_id,
            "name": name,
            "arguments": arguments or {},
        }
        try:
            await conn.send(payload)
        except Exception as exc:
            self._pending.pop(invoke_id, None)
            return f"Error: Failed to reach Android device: {exc}"
        try:
            return await asyncio.wait_for(fut, timeout=INVOKE_TIMEOUT_S)
        except asyncio.TimeoutError:
            self._pending.pop(invoke_id, None)
            return f"Error: Android tool '{name}' timed out after {int(INVOKE_TIMEOUT_S)}s"

    def session_key(self) -> str:
        device_id = self.device_id or "phone"
        return f"android:{device_id}"

    def status(self) -> dict[str, Any]:
        conn = self._device
        if conn is None:
            return {"connected": False}
        return {
            "connected": True,
            "device_id": conn.device_id,
            "label": conn.label,
            "tools": list(conn.tool_names),
            "session_key": self.session_key(),
        }

    def _register_tools(self) -> None:
        vault = self._vault
        if vault is None or self._device is None:
            return
        for spec in ANDROID_TOOL_SPECS:
            vault.register(DeviceProxyTool(self, spec))

    def _unregister_tools(self, names: list[str]) -> None:
        vault = self._vault
        if vault is None:
            return
        for name in names:
            vault.unregister(name)


def dump_tool_catalog() -> str:
    """JSON catalog the phone can ignore; docs / tests."""
    return json.dumps(list(ANDROID_TOOL_SPECS), ensure_ascii=False)
