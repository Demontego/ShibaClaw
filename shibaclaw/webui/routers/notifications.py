"""Notification center and internal session-notify WebUI API handlers."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse

from shibaclaw.helpers.notification_manager import notification_manager
from shibaclaw.webui.agent_manager import agent_manager


async def api_notifications_list(request: Request):
    """List notifications for the WebUI notification center."""
    try:
        limit = int(request.query_params.get("limit", "50"))
    except ValueError:
        return JSONResponse({"error": "Invalid limit"}, status_code=400)

    unread_only = request.query_params.get("unread", "").lower() in ("1", "true", "yes")
    return JSONResponse(notification_manager.list_notifications(limit=limit, unread_only=unread_only))


async def api_notifications_post(request: Request):
    """Create notifications or update their read state."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    operation = str(data.get("operation") or "create").strip().lower()
    if operation == "mark_read":
        notification_id = (data.get("id") or "").strip() or None
        marked = notification_manager.mark_read(notification_id)
        return JSONResponse({
            "marked": marked,
            **notification_manager.list_notifications(limit=50),
        })

    if operation == "mark_all_read":
        marked = notification_manager.mark_read()
        return JSONResponse({
            "marked": marked,
            **notification_manager.list_notifications(limit=50),
        })

    message = (data.get("message") or data.get("content") or "").strip()
    if not message:
        return JSONResponse({"error": "Missing notification message"}, status_code=400)

    try:
        notification = notification_manager.create_notification(
            message=message,
            kind=data.get("kind") or data.get("type"),
            source=data.get("source", "system"),
            title=data.get("title"),
            session_key=data.get("session_key", ""),
            action=data.get("action"),
            metadata=data.get("metadata"),
            dedupe_key=data.get("dedupe_key"),
            read=bool(data.get("read", False)),
            timestamp=data.get("timestamp"),
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    if data.get("broadcast", True):
        from shibaclaw.webui.ws_handler import broadcast_notification

        await broadcast_notification(notification)

    return JSONResponse({
        "notification": notification,
        **notification_manager.list_notifications(limit=50),
    })


async def api_notifications_delete(request: Request):
    """Delete one notification or clear the whole notification center."""
    notification_id = request.query_params.get("id", "").strip() or None
    deleted = notification_manager.delete(notification_id)
    return JSONResponse({
        "deleted": deleted,
        **notification_manager.list_notifications(limit=50),
    })


async def api_internal_session_notify(request: Request):
    """Receive background notifications from the gateway and emit to WebUI clients."""
    data = await request.json()
    session_key = data.get("session_key", "")
    content = data.get("content", "")
    source = data.get("source", "background")
    persist = data.get("persist", True)
    metadata = data.get("metadata")
    msg_type = data.get("msg_type", "response")
    media = data.get("media")

    result = await agent_manager.deliver_background_notification(
        session_key,
        content,
        source=source,
        persist=persist,
        metadata=metadata,
        msg_type=msg_type,
        media=media,
    )
    return JSONResponse(result)
