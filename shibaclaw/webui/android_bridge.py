"""Bridge Android companion sockets through the WebUI to gateway DeviceHub."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger
from starlette.websockets import WebSocket

from shibaclaw.webui.gateway_client import gateway_client

_android_ws: dict[str, WebSocket] = {}
_ws_to_device: dict[str, str] = {}


async def register_phone(ws_id: str, websocket: WebSocket, device_id: str, label: str) -> dict[str, Any]:
    _android_ws[device_id] = websocket
    _ws_to_device[ws_id] = device_id
    status = await gateway_client.request(
        "device.register",
        {"device_id": device_id, "label": label},
    )
    logger.info("📱 Android phone registered via WebUI: {}", device_id)
    return status or {"connected": True, "device_id": device_id}


async def unregister_phone(ws_id: str) -> None:
    device_id = _ws_to_device.pop(ws_id, None)
    if not device_id:
        return
    _android_ws.pop(device_id, None)
    try:
        await gateway_client.request("device.detach", {"device_id": device_id})
    except Exception as exc:
        logger.debug("Android detach failed: {}", exc)
    logger.info("📱 Android phone unregistered via WebUI: {}", device_id)


async def forward_invoke(msg: dict[str, Any]) -> None:
    payload = msg.get("payload") or {}
    body = json.dumps(
        {
            "type": "device_invoke",
            "id": payload.get("id"),
            "name": payload.get("name"),
            "arguments": payload.get("arguments") or {},
        }
    )
    dead: list[str] = []
    for device_id, ws in list(_android_ws.items()):
        try:
            await ws.send_text(body)
        except Exception:
            dead.append(device_id)
    for device_id in dead:
        _android_ws.pop(device_id, None)


async def submit_result(data: dict[str, Any]) -> None:
    await gateway_client.request(
        "device.tools.result",
        {
            "id": data.get("id"),
            "ok": bool(data.get("ok", True)),
            "result": data.get("result") or "",
            "error": data.get("error") or "",
        },
    )


def session_key_for(device_id: str) -> str:
    return f"android:{device_id}"
