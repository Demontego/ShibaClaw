"""Bridge Android companion sockets through the WebUI to gateway DeviceHub."""

from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field, ValidationError
from starlette.websockets import WebSocket

from shibaclaw.webui.gateway_client import gateway_client

_android_ws: dict[str, WebSocket] = {}
_ws_to_device: dict[str, str] = {}

_DIGEST_PROMPT = (
    "You are Shiba, a playful home-screen pet. Use web_search for 2 fresh world "
    "headlines from the last day. Also invent one surprising fun fact and a short "
    "mood line in character. Reply with ONLY JSON (no markdown fences) matching: "
    '{"mood":"IDLE|THINK|SLEEP|ALERT|ERROR","mood_line":"...","fact":"...",'
    '"news":["headline 1","headline 2"]}. Keep each string under 120 chars.'
)


class Digest(BaseModel):
    mood: str = "IDLE"
    mood_line: str = ""
    fact: str = ""
    news: list[str] = Field(default_factory=list)


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


def digest_session_key(device_id: str) -> str:
    return f"android:{device_id}:digest"


def parse_digest_text(raw: str) -> Digest | None:
    """Parse LLM digest output; fences/noise allowed. Invalid → None."""
    text = (raw or "").strip()
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    try:
        digest = Digest.model_validate(data)
    except ValidationError:
        return None
    digest.news = [n.strip() for n in digest.news if isinstance(n, str) and n.strip()][:4]
    digest.mood_line = digest.mood_line.strip()[:160]
    digest.fact = digest.fact.strip()[:160]
    mood = digest.mood.strip().upper()
    if mood not in {"IDLE", "THINK", "SLEEP", "ALERT", "ERROR", "BOOP"}:
        mood = "IDLE"
    digest.mood = mood
    return digest


async def build_digest(device_id: str) -> dict[str, Any] | None:
    """Run one agent turn on a dedicated digest session; return digest dict or None."""
    session_key = digest_session_key(device_id)
    payload = {
        "content": _DIGEST_PROMPT,
        "session_key": session_key,
        "channel": "android",
        "chat_id": session_key,
        "metadata": {"session_key": session_key, "android_digest": True},
    }
    response_content = ""
    try:
        async for event in gateway_client.chat_stream(payload, request_id=f"digest-{device_id}"):
            kind = event.get("t")
            if kind == "rt":
                response_content += event.get("c") or ""
            elif kind == "r":
                final = event.get("content") or response_content
                if isinstance(final, str) and final.strip():
                    response_content = final
            elif kind == "e":
                logger.warning("Android digest error: {}", event.get("error"))
                return None
    except Exception as exc:
        logger.warning("Android digest stream failed: {}", exc)
        return None
    parsed = parse_digest_text(response_content)
    if not parsed:
        logger.warning("Android digest parse failed for {}", device_id)
        return None
    return parsed.model_dump()
