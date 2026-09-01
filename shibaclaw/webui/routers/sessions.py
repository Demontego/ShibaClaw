from __future__ import annotations

import asyncio
import os

from starlette.requests import Request
from starlette.responses import JSONResponse

from shibaclaw.webui.agent_manager import agent_manager


async def api_sessions_list(request: Request):
    """List all saved sessions."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    pm = agent_manager.pm
    if not pm:
        return JSONResponse({"error": "Agent manager not ready"}, status_code=500)
    return JSONResponse({"sessions": pm.list_sessions()})


async def api_sessions_get(request: Request):
    """Get details for a specific session."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    session_id = request.path_params["session_id"]
    pm = agent_manager.pm
    if not pm:
        return JSONResponse({"error": "Agent manager not ready"}, status_code=500)
    session = pm.get_or_create(session_id)

    # Normalize model ID if present
    if model := session.metadata.get("model"):
        from shibaclaw.helpers.model_ids import canonicalize_model_id

        canonical = canonicalize_model_id(agent_manager.config, model)
        if canonical != model:
            session.metadata["model"] = canonical
            pm.save(session)

    # Dynamically build attachments for assistant messages
    for m in session.messages:
        if m.get("role") == "assistant" and "metadata" in m and "media" in m["metadata"]:
            from shibaclaw.webui.ws_handler import _build_attachments

            m.setdefault("metadata", {})["attachments"] = _build_attachments(m["metadata"]["media"])

    return JSONResponse(
        {
            "messages": session.messages,
            "nickname": session.metadata.get("nickname"),
            "profile_id": session.metadata.get("profile_id", "default"),
            "model": session.metadata.get("model", ""),
            "reasoning_effort": session.metadata.get("reasoning_effort", None),
            "knowledge_bases": session.metadata.get("knowledge_bases", []),
            "permission_mode": session.metadata.get("permission_mode"),
        }
    )


async def api_sessions_patch(request: Request):
    """Update session metadata (like nickname, model, reasoning_effort)."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    session_id = request.path_params["session_id"]
    data = await request.json()
    pm = agent_manager.pm
    if not pm:
        return JSONResponse({"error": "Agent manager not ready"}, status_code=500)
    session = pm.get_or_create(session_id)

    if "nickname" in data:
        session.metadata["nickname"] = data["nickname"]
    if "profile_id" in data:
        old_profile_id = session.metadata.get("profile_id", "default")
        session.metadata["profile_id"] = data["profile_id"]
        try:
            from shibaclaw.agent.profiles import ProfileManager

            wp = agent_manager.config.workspace_path
            ProfileManager(wp).sync_session_knowledge_bases(
                session.metadata, data["profile_id"], old_profile_id
            )
        except Exception:
            pass
    if "model" in data:
        session.metadata["model"] = data["model"]
    if "reasoning_effort" in data:
        session.metadata["reasoning_effort"] = data["reasoning_effort"]
    if "knowledge_bases" in data:
        session.metadata["knowledge_bases"] = data["knowledge_bases"]
    if "permission_mode" in data:
        from shibaclaw.agent.interactive import PERMISSION_MODES

        mode = str(data["permission_mode"] or "").strip().lower()
        if mode and mode not in PERMISSION_MODES:
            return JSONResponse(
                {"error": f"permission_mode must be one of {sorted(PERMISSION_MODES)}"},
                status_code=400,
            )
        session.metadata["permission_mode"] = mode or None
    touch_keys = (
        "nickname",
        "profile_id",
        "model",
        "reasoning_effort",
        "knowledge_bases",
        "permission_mode",
    )
    if any(k in data for k in touch_keys):
        pm.save(session)
        return JSONResponse(
            {
                "status": "updated",
                "profile_id": session.metadata.get("profile_id", "default"),
                "reasoning_effort": session.metadata.get("reasoning_effort"),
                "permission_mode": session.metadata.get("permission_mode"),
            }
        )
    return JSONResponse({"error": "Nothing to update"}, status_code=400)



async def api_sessions_delete(request: Request):
    """Delete a specific session."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    session_id = request.path_params["session_id"]
    pm = agent_manager.pm
    if not pm:
        return JSONResponse({"error": "Agent manager not ready"}, status_code=500)

    path = pm._get_session_path(session_id)
    if path.exists():
        os.remove(path)
        pm.invalidate(session_id)
        return JSONResponse({"status": "deleted"})
    return JSONResponse({"error": "Session not found"}, status_code=404)


async def api_sessions_archive(request: Request):
    """Archive session messages via gateway memory consolidation."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)

    session_id = request.path_params["session_id"]
    pm = agent_manager.pm
    if not pm:
        return JSONResponse({"error": "Agent manager not ready"}, status_code=500)
    session = pm.get_or_create(session_id)

    snapshot = list(session.messages[session.last_consolidated :])

    path = pm._get_session_path(session_id)
    if path.exists():
        os.remove(path)
    pm.invalidate(session_id)

    if snapshot:
        asyncio.create_task(agent_manager.archive_via_gateway(snapshot))

    return JSONResponse({"status": "archived"})


async def api_sessions_search(request: Request):
    """Search conversation message bodies across sessions."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    pm = agent_manager.pm
    if not pm:
        return JSONResponse({"error": "Agent manager not ready"}, status_code=500)
    q = (request.query_params.get("q") or "").strip()
    if not q:
        return JSONResponse({"error": "q is required"}, status_code=400)
    try:
        limit = int(request.query_params.get("limit") or 20)
    except ValueError:
        limit = 20
    hits = pm.search_messages(q, limit=limit)
    return JSONResponse({"query": q, "hits": hits})
