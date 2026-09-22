"""GET /api/evolve — read-only self-evolution snapshot."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse

import shibaclaw.webui.auth as webui_auth
from shibaclaw.config.paths import get_automation_dir
from shibaclaw.evolve.snapshot import snapshot
from shibaclaw.webui.agent_manager import agent_manager


def _check_auth(request: Request) -> bool:
    if not webui_auth._auth_enabled():
        return True
    token = request.query_params.get("token") or ""
    if not token:
        auth_hdr = request.headers.get("authorization", "")
        if auth_hdr.startswith("Bearer "):
            token = auth_hdr[7:].strip()
    return bool(token and webui_auth._verify_session_token(token))


async def api_evolve_get(request: Request) -> JSONResponse:
    if not _check_auth(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    try:
        if not agent_manager.config:
            agent_manager.load_latest_config()
        if not agent_manager.config:
            return JSONResponse({"error": "No configuration loaded"}, status_code=500)
        workspace = agent_manager.config.workspace_path
        return JSONResponse(snapshot(workspace, get_automation_dir() / "automation.json"))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
