"""GET/POST /api/evolve — evolution snapshot, switch, and prompt."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse

import shibaclaw.webui.auth as webui_auth
from shibaclaw.automation.service import AutomationService
from shibaclaw.config.paths import get_automation_dir
from shibaclaw.evolve.gate import JOB_NAME, load, save
from shibaclaw.evolve.snapshot import is_digest_job, snapshot
from shibaclaw.evolve.switch import handle, owner_chat, sync_alarm
from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.routers.mcp_manager import _get_mcp_servers

_CAMPAIGN_CAP = 8000


def _check_auth(request: Request) -> bool:
    if not webui_auth._auth_enabled():
        return True
    token = request.query_params.get("token") or ""
    if not token:
        auth_hdr = request.headers.get("authorization", "")
        if auth_hdr.startswith("Bearer "):
            token = auth_hdr[7:].strip()
    return bool(token and webui_auth._verify_session_token(token))


def _ready():
    if not agent_manager.config:
        agent_manager.load_latest_config()
    if not agent_manager.config:
        return None
    return agent_manager.config.workspace_path


def _mcp_catalog() -> list[str]:
    servers = _get_mcp_servers(agent_manager.config)
    if not isinstance(servers, dict):
        return []
    return sorted(str(name) for name in servers)


def _view(workspace, automation_file):
    view = snapshot(workspace, automation_file)
    view["mcp_servers"] = _mcp_catalog()
    return view


def _model_text(raw) -> str | None:
    if raw is not None and not isinstance(raw, str):
        raise ValueError("model")
    text = (raw or "").strip()
    if "\n" in text or len(text) > 200:
        raise ValueError("model")
    return text or None


async def api_evolve_get(request: Request) -> JSONResponse:
    if not _check_auth(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    try:
        workspace = _ready()
        if workspace is None:
            return JSONResponse({"error": "No configuration loaded"}, status_code=500)
        return JSONResponse(_view(workspace, get_automation_dir() / "automation.json"))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


async def api_evolve_post(request: Request) -> JSONResponse:
    if not _check_auth(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "bad json"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "bad json"}, status_code=400)
    try:
        workspace = _ready()
        if workspace is None:
            return JSONResponse({"error": "No configuration loaded"}, status_code=500)
        automation_file = get_automation_dir() / "automation.json"
        service = AutomationService(store_path=automation_file, workspace=workspace)
        owner = owner_chat(getattr(agent_manager.config, "channels", None))
        if any(key in body for key in ("every_min", "model", "mcps")):
            data = load(workspace)
            if "every_min" in body:
                raw = body.get("every_min")
                if isinstance(raw, bool) or not isinstance(raw, int) or not 5 <= raw <= 24 * 60:
                    return JSONResponse({"error": "every_min out of range"}, status_code=400)
                data["every_min"] = raw
            if "model" in body:
                data["model"] = _model_text(body.get("model"))
            if "mcps" in body:
                raw = body.get("mcps")
                catalog = set(_mcp_catalog())
                if not isinstance(raw, list) or len(raw) > 12:
                    return JSONResponse({"error": "mcps invalid"}, status_code=400)
                names: list[str] = []
                for item in raw:
                    if not isinstance(item, str) or item not in catalog or item in names:
                        return JSONResponse({"error": "mcps invalid"}, status_code=400)
                    names.append(item)
                data["mcps"] = names
            if any(job.name == JOB_NAME for job in service.list_jobs()):
                sync_alarm(service, data, enabled=bool(data.get("enabled")), owner=owner)
            save(workspace, data)
        if "campaign" in body:
            raw = body.get("campaign")
            if raw is not None and not isinstance(raw, str):
                return JSONResponse({"error": "campaign must be text"}, status_code=400)
            text = (raw or "").strip()
            if len(text) > _CAMPAIGN_CAP:
                return JSONResponse({"error": "campaign too long"}, status_code=400)
            data = load(workspace)
            data["campaign"] = text or None
            exists = any(job.name == JOB_NAME for job in service.list_jobs())
            if exists:
                sync_alarm(service, data, enabled=bool(data.get("enabled")), owner=owner)
            save(workspace, data)
        if "enabled" in body:
            if not isinstance(body.get("enabled"), bool):
                return JSONResponse({"error": "enabled must be bool"}, status_code=400)
            handle(
                "on" if body["enabled"] else "off",
                workspace=workspace,
                automation=service,
                owner=owner,
            )
        if any(key in body for key in ("digest", "digest_enabled", "digest_model")):
            found = next(
                (
                    job
                    for job in service.list_jobs()
                    if is_digest_job(job.name, job.payload.message or "")
                ),
                None,
            )
            if found is None:
                return JSONResponse({"error": "digest job missing"}, status_code=404)
            patch: dict = {}
            if "digest_enabled" in body:
                if not isinstance(body.get("digest_enabled"), bool):
                    return JSONResponse({"error": "digest_enabled must be bool"}, status_code=400)
                patch["enabled"] = body["digest_enabled"]
            payload: dict = {}
            if "digest" in body:
                raw = body.get("digest")
                if raw is not None and not isinstance(raw, str):
                    return JSONResponse({"error": "digest must be text"}, status_code=400)
                text = (raw or "").strip()
                if len(text) > _CAMPAIGN_CAP:
                    return JSONResponse({"error": "digest too long"}, status_code=400)
                payload["message"] = text
            if "digest_model" in body:
                payload["model"] = _model_text(body.get("digest_model"))
            if payload:
                patch["payload"] = payload
            if patch:
                service.update_job(found.id, patch)
        return JSONResponse(_view(workspace, automation_file))
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
