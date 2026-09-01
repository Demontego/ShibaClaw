"""Interactive agent↔user requests (ask / credential / progress cards).

OpenClaw-2.0-inspired: secrets never return to the model; structured asks
pause the tool until the WebUI (or gateway) resolves them.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Awaitable, Callable

from loguru import logger

PERMISSION_MODES = frozenset({"full", "workspace", "readonly"})
DEFAULT_INTERACTIVE_TIMEOUT = 300.0

EmitFn = Callable[[dict[str, Any]], Awaitable[None]]


class InteractiveHub:
    """In-process pending-request registry (lives in the gateway process)."""

    def __init__(self) -> None:
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._pending_meta: dict[str, dict[str, Any]] = {}
        self._emit: EmitFn | None = None
        self._progress_cards: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    def set_emit(self, callback: EmitFn | None) -> None:
        self._emit = callback

    async def emit(self, event: dict[str, Any]) -> None:
        """Fire-and-forget interactive/progress event (no wait)."""
        if self._emit is None:
            return
        await self._emit(event)

    def get_progress_card(self, session_key: str) -> dict[str, Any] | None:
        return self._progress_cards.get(session_key)

    def set_progress_card(self, session_key: str, card: dict[str, Any]) -> None:
        self._progress_cards[session_key] = card

    async def request(
        self,
        *,
        kind: str,
        session_key: str,
        payload: dict[str, Any],
        timeout: float = DEFAULT_INTERACTIVE_TIMEOUT,
    ) -> dict[str, Any]:
        """Emit an interactive prompt and wait for ``resolve``."""
        request_id = uuid.uuid4().hex[:12]
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[dict[str, Any]] = loop.create_future()
        async with self._lock:
            self._pending[request_id] = fut
            self._pending_meta[request_id] = {
                "kind": kind,
                "session_key": session_key,
                **{k: payload.get(k) for k in ("key", "namespace", "title") if k in payload},
            }

        event = {
            "kind": kind,
            "request_id": request_id,
            "session_key": session_key,
            **payload,
        }
        if self._emit is None:
            async with self._lock:
                self._pending.pop(request_id, None)
                self._pending_meta.pop(request_id, None)
            return {
                "ok": False,
                "skipped": True,
                "error": "no_interactive_ui",
                "request_id": request_id,
            }

        try:
            await self._emit(event)
        except Exception as e:
            logger.warning("Interactive emit failed: {}", e)
            async with self._lock:
                self._pending.pop(request_id, None)
                self._pending_meta.pop(request_id, None)
            return {"ok": False, "error": f"emit_failed: {e}", "request_id": request_id}

        try:
            result = await asyncio.wait_for(asyncio.shield(fut), timeout=timeout)
            if isinstance(result, dict):
                result.setdefault("request_id", request_id)
                return result
            return {"ok": True, "request_id": request_id, "value": result}
        except TimeoutError:
            return {"ok": False, "error": "timeout", "request_id": request_id}
        except asyncio.CancelledError:
            raise
        finally:
            async with self._lock:
                self._pending.pop(request_id, None)
                self._pending_meta.pop(request_id, None)

    def resolve(self, request_id: str, response: dict[str, Any]) -> bool:
        """Resolve a pending request (called from gateway ``interactive_reply``).

        For credential requests, if ``secret`` is present it is written to the
        vault here and stripped from the value returned to the waiting tool.
        """
        fut = self._pending.get(request_id)
        if fut is None or fut.done():
            return False
        payload = dict(response) if isinstance(response, dict) else {"value": response}
        meta = self._pending_meta.get(request_id) or {}
        if meta.get("kind") == "credential" and isinstance(payload.get("secret"), str):
            secret = payload.pop("secret")
            if secret and payload.get("action") != "skip":
                ns = str(meta.get("namespace") or "runtime")
                key = str(meta.get("key") or "")
                if key:
                    try:
                        from shibaclaw.security.credential_manager import (
                            get_credential_manager,
                        )

                        get_credential_manager().set_secret(ns, key, secret)
                        payload["stored"] = True
                        payload["ok"] = True
                    except Exception as e:
                        logger.error("Failed to store credential: {}", e)
                        payload = {
                            "ok": False,
                            "error": f"store_failed: {e}",
                            "request_id": request_id,
                        }
            else:
                payload.setdefault("stored", False)
        payload.setdefault("ok", True)
        fut.set_result(payload)
        return True

    def cancel_all(self, reason: str = "cancelled") -> int:
        n = 0
        for rid, fut in list(self._pending.items()):
            if not fut.done():
                fut.set_result({"ok": False, "error": reason, "request_id": rid})
                n += 1
        self._pending.clear()
        self._pending_meta.clear()
        return n


_HUB: InteractiveHub | None = None


def get_interactive_hub() -> InteractiveHub:
    global _HUB
    if _HUB is None:
        _HUB = InteractiveHub()
    return _HUB


def normalize_permission_mode(
    raw: Any,
    *,
    restrict_to_workspace: bool = True,
) -> str:
    """Return a valid permission mode; default mirrors global workspace restrict."""
    if isinstance(raw, str):
        mode = raw.strip().lower()
        if mode in PERMISSION_MODES:
            return mode
    return "workspace" if restrict_to_workspace else "full"
