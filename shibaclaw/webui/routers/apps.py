from __future__ import annotations

import re
from starlette.requests import Request
from starlette.responses import JSONResponse

from shibaclaw.apps.models import AppDefinition, RuntimeType, TrustLevel, AppAuthDefinition
from shibaclaw.apps.registry.manager import AppRegistryManager
from shibaclaw.apps.state import AppStateManager
from shibaclaw.apps.auth import AppAuthManager
from shibaclaw.apps.installer import AppInstaller
from shibaclaw.config.loader import load_config
from shibaclaw.webui.agent_manager import agent_manager

_registry_manager = AppRegistryManager()
_state_manager = AppStateManager()
_auth_manager = AppAuthManager()
_installer = AppInstaller(_registry_manager, _state_manager, _auth_manager)


async def api_list_apps(request: Request) -> JSONResponse:
    """GET /api/apps - Return all marketplace and installed apps."""
    cfg = agent_manager.config or load_config()
    all_apps = await _registry_manager.list_all()
    records = _state_manager.get_installed_records(cfg)

    enriched_apps = [_state_manager.enrich_app_state(app, cfg, records=records) for app in all_apps]

    # Include any custom MCP servers configured in config that aren't in catalogs
    catalog_ids = {a.id for a in enriched_apps}
    mcp_servers = getattr(cfg.tools, "mcp_servers", {}) or {}
    for name, sc in mcp_servers.items():
        if name not in catalog_ids:
            sc_dict = sc.model_dump(mode="json") if hasattr(sc, "model_dump") else dict(sc)
            transport = sc_dict.get("type", "streamableHttp")
            is_remote = bool(sc_dict.get("url"))
            custom_app = AppDefinition(
                id=name,
                name=name.replace("-", " ").replace("_", " ").title(),
                description=f"Custom MCP server ({transport})",
                icon="terminal" if not is_remote else "cloud",
                category="development",
                source="custom",
                runtime_type=RuntimeType.MCP_REMOTE.value if is_remote else RuntimeType.MCP_LOCAL.value,
                trust_level=TrustLevel.CUSTOM.value,
                version="1.0.0",
                installed=True,
                enabled=bool(sc_dict.get("enabled_tools") != []),
                enabled_tools=sc_dict.get("enabled_tools", ["*"]),
                mcp_config=sc_dict,
                capabilities=["Custom MCP tools"],
            )
            enriched_apps.append(_state_manager.enrich_app_state(custom_app, cfg))

    # Optional filter params
    category = request.query_params.get("category", "")
    tab = request.query_params.get("tab", "")
    query = request.query_params.get("q", "").strip().lower()

    filtered = []
    for app in enriched_apps:
        if tab == "installed" and not app.installed:
            continue
        if tab == "updates" and (not app.installed or not app.update_available):
            continue
        if category and category != "all" and app.category.lower() != category.lower():
            continue
        if query:
            match = (
                query in app.name.lower()
                or query in app.id.lower()
                or query in app.description.lower()
                or any(query in cap.lower() for cap in app.capabilities)
            )
            if not match:
                continue
        filtered.append(app.model_dump(mode="json"))

    return JSONResponse({"apps": filtered, "total": len(filtered)})


async def api_get_app(request: Request) -> JSONResponse:
    """GET /api/apps/{app_id}"""
    app_id = request.path_params.get("app_id", "")
    app = await _registry_manager.get_app(app_id)

    cfg = agent_manager.config or load_config()
    if not app:
        # Check custom MCP server
        mcp_servers = getattr(cfg.tools, "mcp_servers", {}) or {}
        if app_id in mcp_servers:
            sc = mcp_servers[app_id]
            sc_dict = sc.model_dump(mode="json") if hasattr(sc, "model_dump") else dict(sc)
            app = AppDefinition(
                id=app_id,
                name=app_id.title(),
                description="Custom MCP server",
                icon="terminal",
                category="development",
                source="custom",
                runtime_type=RuntimeType.MCP_REMOTE.value if sc_dict.get("url") else RuntimeType.MCP_LOCAL.value,
                trust_level=TrustLevel.CUSTOM.value,
                mcp_config=sc_dict,
            )

    if not app:
        return JSONResponse({"error": f"App '{app_id}' not found"}, status_code=404)

    enriched = _state_manager.enrich_app_state(app, cfg)
    return JSONResponse({"app": enriched.model_dump(mode="json")})


async def api_install_app(request: Request) -> JSONResponse:
    """POST /api/apps/{app_id}/install"""
    app_id = request.path_params.get("app_id", "")
    res = await _installer.install_app(app_id)
    status_code = 200 if res.get("ok") else 400
    return JSONResponse(res, status_code=status_code)


async def api_uninstall_app(request: Request) -> JSONResponse:
    """POST /api/apps/{app_id}/uninstall"""
    app_id = request.path_params.get("app_id", "")
    res = await _installer.uninstall_app(app_id)
    status_code = 200 if res.get("ok") else 400
    return JSONResponse(res, status_code=status_code)


async def api_enable_app(request: Request) -> JSONResponse:
    """POST /api/apps/{app_id}/enable"""
    app_id = request.path_params.get("app_id", "")
    res = await _installer.toggle_app_enabled(app_id, True)
    status_code = 200 if res.get("ok") else 400
    return JSONResponse(res, status_code=status_code)


async def api_disable_app(request: Request) -> JSONResponse:
    """POST /api/apps/{app_id}/disable"""
    app_id = request.path_params.get("app_id", "")
    res = await _installer.toggle_app_enabled(app_id, False)
    status_code = 200 if res.get("ok") else 400
    return JSONResponse(res, status_code=status_code)


async def api_connect_app(request: Request) -> JSONResponse:
    """POST /api/apps/{app_id}/connect"""
    app_id = request.path_params.get("app_id", "")
    app = await _registry_manager.get_app(app_id)
    if not app:
        # Fallback to custom config
        cfg = agent_manager.config or load_config()
        mcp_servers = getattr(cfg.tools, "mcp_servers", {}) or {}
        if app_id in mcp_servers:
            sc = mcp_servers[app_id]
            sc_dict = sc.model_dump(mode="json") if hasattr(sc, "model_dump") else dict(sc)
            app = AppDefinition(
                id=app_id,
                name=app_id.title(),
                description="Custom MCP server",
                source="custom",
                runtime_type=RuntimeType.MCP_REMOTE.value if sc_dict.get("url") else RuntimeType.MCP_LOCAL.value,
                trust_level=TrustLevel.CUSTOM.value,
                mcp_config=sc_dict,
            )

    if not app:
        return JSONResponse({"error": f"App '{app_id}' not found"}, status_code=404)

    try:
        body = await request.json()
    except Exception:
        body = {}

    res = await _auth_manager.connect_app(app, credentials=body)
    status_code = 200 if res.get("ok") else 400
    return JSONResponse(res, status_code=status_code)


async def api_disconnect_app(request: Request) -> JSONResponse:
    """POST or DELETE /api/apps/{app_id}/connect or /api/apps/{app_id}/disconnect"""
    app_id = request.path_params.get("app_id", "")
    res = await _auth_manager.disconnect_app(app_id)
    return JSONResponse(res)


async def api_get_app_auth_status(request: Request) -> JSONResponse:
    """GET /api/apps/{app_id}/status or /api/apps/{app_id}/auth-status"""
    app_id = request.path_params.get("app_id", "")
    app = await _registry_manager.get_app(app_id)
    cfg = agent_manager.config or load_config()

    if not app:
        mcp_servers = getattr(cfg.tools, "mcp_servers", {}) or {}
        if app_id in mcp_servers:
            app = AppDefinition(id=app_id, name=app_id, description="", source="custom")

    if not app:
        return JSONResponse({"error": f"App '{app_id}' not found"}, status_code=404)

    enriched = _state_manager.enrich_app_state(app, cfg)
    return JSONResponse({
        "ok": True,
        "app_id": app_id,
        "status": enriched.status,
        "connected": enriched.status == "connected",
        "auth_state": _state_manager.resolve_auth_state(app, cfg),
    })


async def api_get_app_tools(request: Request) -> JSONResponse:
    """GET /api/apps/{app_id}/tools"""
    app_id = request.path_params.get("app_id", "")
    app = await _registry_manager.get_app(app_id)
    cfg = agent_manager.config or load_config()

    if not app:
        mcp_servers = getattr(cfg.tools, "mcp_servers", {}) or {}
        if app_id in mcp_servers:
            app = AppDefinition(id=app_id, name=app_id, description="", source="custom")

    if not app:
        return JSONResponse({"error": f"App '{app_id}' not found"}, status_code=404)

    enriched = _state_manager.enrich_app_state(app, cfg)
    return JSONResponse({
        "app_id": app_id,
        "tools": enriched.available_tools,
        "enabled_tools": enriched.enabled_tools,
        "total": len(enriched.available_tools),
    })


async def api_update_app_tools(request: Request) -> JSONResponse:
    """PUT /api/apps/{app_id}/tools"""
    app_id = request.path_params.get("app_id", "")
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    enabled_tools = body.get("enabled_tools")
    if not isinstance(enabled_tools, list):
        return JSONResponse({"error": "enabled_tools must be a list of strings"}, status_code=400)

    res = await _installer.update_enabled_tools(app_id, enabled_tools)
    status_code = 200 if res.get("ok") else 400
    return JSONResponse(res, status_code=status_code)


async def api_create_custom_app(request: Request) -> JSONResponse:
    """POST /api/apps/custom - Register and install a custom MCP or local integration."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    name = (body.get("name") or "").strip()
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=400)

    app_id = re.sub(r"[^a-zA-Z0-9_\-]+", "-", name.lower()).strip("-")
    if not app_id:
        return JSONResponse({"error": "Invalid app name"}, status_code=400)

    runtime_type = body.get("runtime_type", "mcp_remote")
    url = (body.get("url") or "").strip()
    command = (body.get("command") or "").strip()
    args = body.get("args") or []
    auth_type = body.get("auth_type", "none")

    if runtime_type == "mcp_remote" and not url:
        return JSONResponse({"error": "URL is required for remote MCP apps"}, status_code=400)
    if runtime_type == "mcp_local" and not command:
        return JSONResponse({"error": "Command is required for local MCP apps"}, status_code=400)

    custom_def = AppDefinition(
        id=app_id,
        name=name,
        description=body.get("description") or f"Custom integration for {name}",
        icon=body.get("icon") or "extension",
        category=body.get("category") or "development",
        source="custom",
        runtime_type=runtime_type,
        trust_level=TrustLevel.CUSTOM.value,
        version="1.0.0",
        auth=AppAuthDefinition(type=auth_type),
        mcp_config={
            "type": body.get("transport", "streamableHttp" if runtime_type == "mcp_remote" else "stdio"),
            "url": url,
            "command": command,
            "args": args,
            "headers": body.get("headers", {}),
        },
        capabilities=body.get("capabilities") or ["Custom tools"],
    )

    res = await _installer.install_app(app_id, custom_def=custom_def)
    status_code = 200 if res.get("ok") else 400
    return JSONResponse(res, status_code=status_code)
