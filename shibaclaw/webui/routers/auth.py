"""Auth API routes — setup, login, verify, status."""

from __future__ import annotations

from collections import deque
import time

from loguru import logger
from starlette.requests import Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from shibaclaw.webui.auth import _auth_enabled, _is_user_setup, is_telegram_mini_surface

_TELEGRAM_AUTH_MAX_ATTEMPTS = 10
_TELEGRAM_AUTH_WINDOW_SEC = 60
_telegram_auth_attempts: dict[str, deque[float]] = {}


def _telegram_auth_rate_limited(client_ip: str, *, now: float | None = None) -> bool:
    """Record an auth attempt and return whether its IP exceeded the one-minute limit."""
    current_time = time.monotonic() if now is None else now
    attempts = _telegram_auth_attempts.setdefault(client_ip, deque())
    while attempts and attempts[0] <= current_time - _TELEGRAM_AUTH_WINDOW_SEC:
        attempts.popleft()
    if len(attempts) >= _TELEGRAM_AUTH_MAX_ATTEMPTS:
        return True
    attempts.append(current_time)
    return False


def _reject_password_on_mini(request: Request) -> JSONResponse | None:
    if is_telegram_mini_surface(request):
        return JSONResponse(
            {"error": "Password login disabled on Telegram Mini App. Use Telegram auth."},
            status_code=403,
        )
    return None


# ------------------------------------------------------------------
# POST /api/auth/setup  —  first-run admin user creation
# ------------------------------------------------------------------


async def api_auth_setup(request: Request):
    """Create the admin user.  Only allowed once (first run)."""
    blocked = _reject_password_on_mini(request)
    if blocked is not None:
        return blocked

    from shibaclaw.security.credential_manager import get_credential_manager

    cm = get_credential_manager()

    if await run_in_threadpool(cm.is_setup):
        return JSONResponse(
            {"error": "Admin user already configured."},
            status_code=409,
        )

    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body."}, status_code=400)

    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not password:
        return JSONResponse(
            {"error": "Both username and password are required."},
            status_code=400,
        )

    if len(password) < 6:
        return JSONResponse(
            {"error": "Password must be at least 6 characters."},
            status_code=400,
        )

    ok = await run_in_threadpool(cm.setup_user, username, password)
    if not ok:
        return JSONResponse({"error": "Setup failed."}, status_code=500)

    # Migrate existing config.json secrets into the credential vault
    try:
        _migrate_config_secrets_to_vault(cm)
    except Exception:
        logger.exception("Failed to migrate config secrets into vault")

    # Issue a session token immediately so the user doesn't need to login again
    session_token = await run_in_threadpool(cm.create_session_token)

    logger.info("Admin user '{}' created via WebUI setup.", username)
    return JSONResponse({
        "status": "ok",
        "session_token": session_token,
    })


# ------------------------------------------------------------------
# POST /api/auth/login
# ------------------------------------------------------------------


async def api_auth_login(request: Request):
    """Authenticate with username + password, return a session token."""
    blocked = _reject_password_on_mini(request)
    if blocked is not None:
        return blocked

    from shibaclaw.security.credential_manager import get_credential_manager

    cm = get_credential_manager()

    if not await run_in_threadpool(cm.is_setup):
        return JSONResponse(
            {"error": "Admin user not configured. Please run setup first."},
            status_code=403,
        )

    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body."}, status_code=400)

    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not await run_in_threadpool(cm.verify_password, username, password):
        logger.warning("Failed login attempt for user '{}' from {}",
                        username, request.client.host if request.client else "unknown")
        return JSONResponse(
            {"error": "Invalid username or password."},
            status_code=401,
        )

    session_token = await run_in_threadpool(cm.create_session_token)
    logger.info("User '{}' logged in from {}.",
                username, request.client.host if request.client else "unknown")
    return JSONResponse({
        "status": "ok",
        "session_token": session_token,
    })


# ------------------------------------------------------------------
# POST /api/auth/verify  —  legacy token verification
# ------------------------------------------------------------------


async def api_auth_verify(request: Request):
    """Verify a session token."""
    data = await request.json()
    token = data.get("token", "").strip()
    auth_req = _auth_enabled()

    if not auth_req:
        return JSONResponse({"valid": True, "auth_required": False})

    # Try session token
    from shibaclaw.security.credential_manager import CredentialManager
    if await run_in_threadpool(CredentialManager.verify_session_token, token):
        return JSONResponse({"valid": True, "auth_required": True})

    return JSONResponse({"valid": False, "auth_required": True})


# ------------------------------------------------------------------
# GET /api/auth/status
# ------------------------------------------------------------------


async def api_auth_status(request: Request):
    """Return auth state: whether auth is required, whether setup is done."""
    mini = is_telegram_mini_surface(request)
    return JSONResponse(
        {
            "auth_required": _auth_enabled(),
            "needs_setup": (not _is_user_setup()) and not mini,
            "telegram_mini": mini,
            "password_login": not mini,
        },
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


# ------------------------------------------------------------------
# POST /api/auth/telegram  —  Mini App initData → session token
# ------------------------------------------------------------------


async def api_auth_telegram(request: Request):
    """Authenticate via Telegram WebApp initData (owner allowFrom only)."""
    from shibaclaw.config.loader import load_config
    from shibaclaw.security.credential_manager import get_credential_manager
    from shibaclaw.webui.telegram_webapp_auth import user_id_allowed, validate_init_data

    client_ip = request.client.host if request.client else "unknown"
    if _telegram_auth_rate_limited(client_ip):
        logger.warning("Telegram Mini App auth rate limited from {}", client_ip)
        return JSONResponse(
            {"error": "Too many authentication attempts. Try again in a minute."},
            status_code=429,
            headers={"Retry-After": str(_TELEGRAM_AUTH_WINDOW_SEC)},
        )

    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body."}, status_code=400)

    init_data = (data.get("initData") or data.get("init_data") or "").strip()
    if not init_data:
        return JSONResponse({"error": "initData is required."}, status_code=400)

    try:
        cfg = load_config()
        channels = getattr(cfg, "channels", None)
        if isinstance(channels, dict):
            tg = channels.get("telegram")
        else:
            tg = getattr(channels, "telegram", None)
    except Exception:
        logger.exception("Telegram Mini App auth: failed to load config")
        return JSONResponse({"error": "Auth unavailable."}, status_code=500)

    def _tg_get(obj, *names, default=None):
        if obj is None:
            return default
        if isinstance(obj, dict):
            for n in names:
                if n in obj and obj[n] is not None:
                    return obj[n]
            return default
        for n in names:
            if hasattr(obj, n):
                val = getattr(obj, n)
                if val is not None:
                    return val
        return default

    if tg is None or not bool(_tg_get(tg, "enabled", default=False)):
        return JSONResponse({"error": "Telegram channel disabled."}, status_code=403)

    bot_token = None
    resolve = getattr(tg, "resolve_token", None) if not isinstance(tg, dict) else None
    if callable(resolve):
        bot_token = resolve()
    if not bot_token:
        # Vault-first (same order as TelegramConfig.resolve_token)
        try:
            from shibaclaw.security.credential_manager import get_credential_manager

            bot_token = get_credential_manager().get_secret("channels", "telegram.token")
        except Exception:
            bot_token = None
    if not bot_token:
        bot_token = _tg_get(tg, "token", default=None)
    if not bot_token:
        return JSONResponse({"error": "Telegram bot token not configured."}, status_code=503)

    parsed = validate_init_data(init_data, str(bot_token))
    if parsed is None or not parsed.get("user"):
        # Diagnose without leaking initData/token
        from urllib.parse import parse_qsl

        keys = sorted(dict(parse_qsl(init_data, keep_blank_values=True)).keys())
        logger.warning(
            "Telegram Mini App auth failed from {} initData_keys={} len={}",
            request.client.host if request.client else "unknown",
            keys,
            len(init_data),
        )
        return JSONResponse({"error": "Invalid Telegram initData."}, status_code=401)

    user_id = parsed["user"].get("id")
    allow_from = list(_tg_get(tg, "allow_from", "allowFrom", default=[]) or [])
    username = parsed["user"].get("username")
    if not user_id_allowed(user_id, allow_from, username):
        logger.warning("Telegram Mini App denied user_id={}", user_id)
        return JSONResponse({"error": "Access denied."}, status_code=403)

    cm = get_credential_manager()
    if not await run_in_threadpool(cm.is_setup):
        return JSONResponse(
            {"error": "Admin user not configured. Complete WebUI setup on the private host first."},
            status_code=403,
        )

    session_token = await run_in_threadpool(cm.create_session_token)
    logger.info(
        "Telegram Mini App login user_id={} from {}",
        user_id,
        request.client.host if request.client else "unknown",
    )
    return JSONResponse({"status": "ok", "session_token": session_token})


# ------------------------------------------------------------------
# POST /api/auth/change-password
# ------------------------------------------------------------------

async def api_auth_change_password(request: Request):
    """Change the admin password."""
    from shibaclaw.security.credential_manager import get_credential_manager

    cm = get_credential_manager()
    if not await run_in_threadpool(cm.is_setup):
        return JSONResponse({"error": "Admin user not configured."}, status_code=400)

    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body."}, status_code=400)

    old_password = (data.get("old_password") or "").strip()
    new_password = (data.get("new_password") or "").strip()

    if not old_password or not new_password:
        return JSONResponse({"error": "Both old and new passwords are required."}, status_code=400)

    if len(new_password) < 6:
        return JSONResponse({"error": "New password must be at least 6 characters."}, status_code=400)

    username = await run_in_threadpool(cm.get_admin_username)
    if not username:
        return JSONResponse({"error": "Admin user not configured."}, status_code=400)

    ok = await run_in_threadpool(cm.change_password, username, old_password, new_password)
    if not ok:
        return JSONResponse({"error": "Incorrect old password."}, status_code=401)

    logger.info("Admin password changed successfully.")
    return JSONResponse({"status": "ok"})


# ------------------------------------------------------------------
# Migration helper
# ------------------------------------------------------------------


def _migrate_config_secrets_to_vault(cm) -> None:
    """Move plain-text secrets from config.json into the encrypted vault.

    Called once during setup.  After migration the secrets are removed from
    config.json and the file is re-saved.
    """
    import json
    import os
    import tempfile
    from shibaclaw.config.loader import get_config_path, _migrate_secrets_from_raw_dict

    path = get_config_path()
    if not path.exists():
        return

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        if _migrate_secrets_from_raw_dict(data, cm):
            # Save the raw data back (now without secrets)
            with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as tmp:
                json.dump(data, tmp, indent=2, ensure_ascii=False)
                tmp_name = tmp.name
            os.replace(tmp_name, path)
            logger.info("Migrated plain-text secrets from config.json → encrypted vault.")
    except Exception:
        logger.exception("Failed to run full migration of secrets into vault")
