"""Shared gateway WS/HTTP protocol helpers (no composition/wiring)."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable


class TokenCoalescer:
    """Batch streaming token WS sends (flush every ``interval_s`` or ``max_chars``)."""

    def __init__(
        self,
        send: Callable[[str], Awaitable[None]],
        *,
        interval_s: float = 0.04,
        max_chars: int = 48,
    ):
        self._send = send
        self._interval_s = interval_s
        self._max_chars = max_chars
        self._buf = ""
        self._flush_task: asyncio.Task | None = None
        self._send_count = 0
        self._token_count = 0
        self._dropped = 0
        self._closed = False

    @property
    def send_count(self) -> int:
        return self._send_count

    @property
    def token_count(self) -> int:
        return self._token_count

    @property
    def dropped(self) -> int:
        return self._dropped

    async def add(self, token: str) -> None:
        if self._closed or not token:
            return
        self._token_count += 1
        self._buf += token
        if len(self._buf) >= self._max_chars:
            await self.flush()
            return
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = asyncio.create_task(self._delayed_flush())

    async def _delayed_flush(self) -> None:
        await asyncio.sleep(self._interval_s)
        await self.flush()

    async def flush(self) -> None:
        if not self._buf:
            return
        chunk, self._buf = self._buf, ""
        try:
            await self._send(chunk)
            self._send_count += 1
        except Exception:
            self._dropped += 1

    async def close(self) -> None:
        self._closed = True
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self.flush()


def serialize_automation_job(job: Any) -> dict[str, Any]:
    """Serialize an AutomationJob for WebUI/gateway clients."""
    return {
        "id": job.id,
        "name": job.name,
        "enabled": job.enabled,
        "kind": job.payload.kind,
        "schedule": {
            "kind": job.schedule.kind,
            "atMs": job.schedule.at_ms,
            "everyMs": job.schedule.every_ms,
            "expr": job.schedule.expr,
            "tz": job.schedule.tz,
        },
        "payload": {
            "kind": job.payload.kind,
            "message": job.payload.message,
            "heartbeatFile": job.payload.heartbeat_file,
            "deliver": job.payload.deliver,
            "channel": job.payload.channel,
            "to": job.payload.to,
            "targets": job.payload.targets,
        },
        "state": {
            "nextRunAtMs": job.state.next_run_at_ms,
            "lastRunAtMs": job.state.last_run_at_ms,
            "lastStatus": job.state.last_status,
            "lastError": job.state.last_error,
            "runCount": job.state.run_count,
        },
        "deleteAfterRun": job.delete_after_run,
    }


def ws_ok(request_id: str, data: dict | None = None) -> str:
    return json.dumps(
        {"type": "response", "id": request_id, "ok": True, "payload": data or {}}
    )


def ws_err(request_id: str, error: str) -> str:
    return json.dumps(
        {"type": "response", "id": request_id, "ok": False, "error": error}
    )


def http_json_response(data: dict, status: int = 200) -> bytes:
    payload = json.dumps(data).encode()
    phrase = {200: "OK", 401: "Unauthorized", 404: "Not Found", 503: "Unavailable"}.get(
        status, "OK"
    )
    return (
        f"HTTP/1.0 {status} {phrase}\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(payload)}\r\n"
        f"\r\n"
    ).encode() + payload
