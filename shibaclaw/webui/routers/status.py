"""Status and context WebUI API handlers."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse

from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.utils import (
    _build_real_system_prompt,
    _compute_session_tokens,
    _gateway_request,
)


async def api_status(request: Request):
    """Get general server and agent status."""
    cfg = agent_manager.config
    if not cfg:
        agent_manager.load_latest_config()
        cfg = agent_manager.config
    from shibaclaw import __version__

    gw = await _gateway_request("GET", "/")
    gw_ready = gw is not None and gw.get("status") in ("ok", "idle")

    from shibaclaw.webui.routers.oauth import get_oauth_providers_status

    oauth_providers = get_oauth_providers_status()
    oauth_configured = any(p.get("status") == "configured" for p in oauth_providers)

    active_channels = []
    if cfg and cfg.channels and cfg.channels.model_extra:
        for ch_name, ch_data in cfg.channels.model_extra.items():
            if isinstance(ch_data, dict) and ch_data.get("enabled", False):
                active_channels.append(ch_name)

    from shibaclaw.agent.knowledge_manager import RAG_AVAILABLE

    resp = {
        "status": "ok" if gw_ready else "gateway_offline",
        "version": __version__,
        "agent_configured": gw_ready and gw.get("provider_ready", False),
        "oauth_configured": oauth_configured,
        "provider": cfg.agents.defaults.provider if cfg else None,
        "model": cfg.agents.defaults.model if cfg else None,
        "workspace": str(cfg.workspace_path) if cfg else None,
        "restrict_workspace": cfg.tools.restrict_to_workspace if cfg else True,
        "active_channels": active_channels,
        "gateway": gw_ready,
        "rag_available": RAG_AVAILABLE,
    }
    return JSONResponse(resp)


async def api_context_get(request: Request):
    """Generate a context summary for the workspace and session.

    The 'system_prompt' section now reflects the real prompt assembled by
    ScentBuilder (identity, bootstrap files, memory, skills) — the same
    text that is sent to the LLM.  Token counts use tiktoken instead of
    the old ``len // 4`` heuristic.
    """
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)

    wp = agent_manager.config.workspace_path
    session_id = request.query_params.get("session_id", "")
    defaults = agent_manager.config.agents.defaults
    sections = []

    from shibaclaw.helpers.helpers import estimate_message_tokens, estimate_prompt_tokens

    profile_id = None
    if session_id and agent_manager.pm:
        sess_ctx = agent_manager.pm.get_or_create(session_id)
        profile_id = sess_ctx.metadata.get("profile_id") or None

    system_prompt, prompt_tokens = _build_real_system_prompt(wp, defaults, profile_id=profile_id)

    from shibaclaw.agent.context import ScentBuilder

    active_kbs = []
    if session_id and agent_manager.pm:
        sess_ctx = agent_manager.pm.get_or_create(session_id)
        active_kbs = sess_ctx.metadata.get("knowledge_bases", [])

    runtime_block = ScentBuilder.build_runtime_block(
        chat_id=session_id,
        active_kbs=active_kbs,
    )
    if runtime_block:
        system_prompt += "\n\n" + runtime_block
        prompt_tokens += estimate_prompt_tokens([{"role": "system", "content": runtime_block}])

    total_tokens = prompt_tokens
    sections.append(
        f"## 🧠 System Prompt ({prompt_tokens} tokens)\n\n```markdown\n{system_prompt}\n```"
    )

    tools_tokens = 0
    total_tokens = prompt_tokens + tools_tokens

    msg_tokens = 0
    if session_id and agent_manager.pm:
        msg_tokens, msg_lines = _compute_session_tokens(
            session_id, wp, agent_manager.pm, estimate_message_tokens
        )
        if msg_lines:
            sections.append(
                f"## 💬 Session Messages ({len(msg_lines)} messages)\n\n"
                + "\n".join(msg_lines)
            )
    total_tokens += msg_tokens

    active_model = None
    if session_id and agent_manager.pm:
        sess_ctx = agent_manager.pm.get_or_create(session_id)
        active_model = sess_ctx.metadata.get("model")
    if not active_model and agent_manager.config:
        active_model = agent_manager.config.agents.defaults.model

    model_limit = None
    if active_model:
        from shibaclaw.cli.model_info import get_model_context_limit

        model_limit = get_model_context_limit(active_model)

    user_cfg_limit = defaults.context_window_tokens or 0
    ctx_window = (
        model_limit
        if (model_limit and model_limit > 0)
        else (user_cfg_limit if user_cfg_limit > 0 else 65536)
    )

    pct = min(100, round(total_tokens / ctx_window * 100)) if ctx_window > 0 else 0

    if request.query_params.get("summary", "").lower() in ("1", "true", "yes"):
        return JSONResponse(
            {
                "tokens": {
                    "system_prompt": prompt_tokens,
                    "tools": tools_tokens,
                    "messages": msg_tokens,
                    "total": total_tokens,
                    "context_window": ctx_window,
                    "usage_pct": pct,
                    "auto_detected": model_limit is not None,
                    "active_model": active_model,
                }
            }
        )

    context_md = (
        "\n\n---\n\n".join(sections) if sections else "_No context files or session data found._"
    )
    return JSONResponse(
        {
            "context": context_md,
            "tokens": {
                "system_prompt": prompt_tokens,
                "tools": tools_tokens,
                "messages": msg_tokens,
                "total": total_tokens,
                "context_window": ctx_window,
                "usage_pct": pct,
            },
        }
    )
