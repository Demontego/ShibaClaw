"""Browser logins for the Claude subscription and Gemini CLI.

The Claude login reuses Claude Code's public OAuth client. Gemini reuses the
public client id shipped by google-gemini/gemini-cli. Tokens stay on disk.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
import urllib.parse
from pathlib import Path
from typing import Any

import httpx

CLAUDE_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
CLAUDE_AUTHORIZE_URL = "https://claude.ai/oauth/authorize"
CLAUDE_TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
CLAUDE_REDIRECT_URI = "https://platform.claude.com/oauth/code/callback"
CLAUDE_SCOPES = (
    "org:create_api_key user:profile user:inference "
    "user:sessions:claude_code user:mcp_servers user:file_upload"
)

GEMINI_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GEMINI_TOKEN_URL = "https://oauth2.googleapis.com/token"
GEMINI_REDIRECT_URI = "https://codeassist.google.com/authcode"
GEMINI_SCOPES = (
    "https://www.googleapis.com/auth/cloud-platform "
    "https://www.googleapis.com/auth/userinfo.email "
    "https://www.googleapis.com/auth/userinfo.profile"
)


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def new_pkce() -> tuple[str, str, str]:
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    state = _b64url(secrets.token_bytes(24))
    return verifier, challenge, state


def claude_credentials_path() -> Path:
    return Path.home() / ".claude" / ".credentials.json"


def claude_credentials_present() -> bool:
    path = claude_credentials_path()
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    oauth = data.get("claudeAiOauth") if isinstance(data, dict) else None
    return isinstance(oauth, dict) and bool(oauth.get("accessToken") and oauth.get("refreshToken"))


def claude_authorize_url(challenge: str, state: str) -> str:
    query = urllib.parse.urlencode(
        {
            "code": "true",
            "client_id": CLAUDE_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": CLAUDE_REDIRECT_URI,
            "scope": CLAUDE_SCOPES,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
    )
    return f"{CLAUDE_AUTHORIZE_URL}?{query}"


def split_claude_paste(pasted: str, expected_state: str) -> str:
    code, sep, state = pasted.strip().partition("#")
    if not sep or not code or state != expected_state:
        raise ValueError("Paste the Claude page value exactly, including the #.")
    return code


def gemini_authorize_url(challenge: str, state: str) -> str:
    client_id, _secret = gemini_client()
    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": GEMINI_REDIRECT_URI,
            "response_type": "code",
            "scope": GEMINI_SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
    )
    return f"{GEMINI_AUTHORIZE_URL}?{query}"


def _http_error(response: httpx.Response) -> str:
    return f"HTTP {response.status_code}"


def _write_claude_oauth(oauth: dict[str, Any]) -> None:
    path = claude_credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, json.JSONDecodeError):
            data = {}
    data["claudeAiOauth"] = oauth
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def remove_claude_oauth() -> None:
    """Remove the subscription login without deleting other Claude credentials."""
    path = claude_credentials_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return
    if not isinstance(data, dict):
        raise ValueError("Claude credentials must be a JSON object")
    if "claudeAiOauth" not in data:
        return
    del data["claudeAiOauth"]
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _claude_oauth_from_token(payload: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    expires_in = int(payload.get("expires_in") or 28800)
    refresh = payload.get("refresh_token") or (previous or {}).get("refreshToken") or ""
    scopes = payload.get("scope") or payload.get("scopes") or CLAUDE_SCOPES
    if isinstance(scopes, str):
        scope_list = scopes.split()
    else:
        scope_list = list(scopes)
    return {
        "accessToken": payload.get("access_token") or "",
        "refreshToken": refresh,
        "expiresAt": int(time.time() * 1000) + expires_in * 1000,
        "scopes": scope_list,
        "subscriptionType": payload.get("subscription_type")
        or (previous or {}).get("subscriptionType"),
        "rateLimitTier": (previous or {}).get("rateLimitTier"),
    }


def exchange_claude_code(code: str, state: str, verifier: str) -> None:
    response = httpx.post(
        CLAUDE_TOKEN_URL,
        json={
            "grant_type": "authorization_code",
            "client_id": CLAUDE_CLIENT_ID,
            "code": code,
            "state": state,
            "redirect_uri": CLAUDE_REDIRECT_URI,
            "code_verifier": verifier,
        },
        headers={
            "Accept": "application/json",
            "anthropic-beta": "oauth-2025-04-20",
            "User-Agent": "claude-cli/2.1.207 (external, cli)",
        },
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Claude token exchange failed: {_http_error(response)}")
    payload = response.json()
    oauth = _claude_oauth_from_token(payload, None)
    if not oauth["accessToken"]:
        raise RuntimeError("Claude token exchange returned no access token")
    _write_claude_oauth(oauth)


def claude_access_token() -> str | None:
    path = claude_credentials_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    oauth = data.get("claudeAiOauth") if isinstance(data, dict) else None
    if not isinstance(oauth, dict):
        return None
    access = str(oauth.get("accessToken") or "")
    refresh = str(oauth.get("refreshToken") or "")
    if not access:
        return None
    expires_at = int(oauth.get("expiresAt") or 0)
    if expires_at and expires_at - 120_000 > time.time() * 1000:
        return access
    if not refresh:
        return access or None
    response = httpx.post(
        CLAUDE_TOKEN_URL,
        json={
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": CLAUDE_CLIENT_ID,
        },
        headers={
            "Accept": "application/json",
            "anthropic-beta": "oauth-2025-04-20",
            "User-Agent": "claude-cli/2.1.207 (external, cli)",
        },
        timeout=30,
    )
    if response.status_code != 200:
        return access or None
    payload = response.json()
    updated = _claude_oauth_from_token(payload, oauth)
    if not updated["accessToken"]:
        return access
    _write_claude_oauth(updated)
    return str(updated["accessToken"])


def exchange_gemini_code(code: str, verifier: str) -> dict[str, Any]:
    client_id, client_secret = gemini_client()
    response = httpx.post(
        GEMINI_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code.strip(),
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": GEMINI_REDIRECT_URI,
            "code_verifier": verifier,
        },
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Gemini token exchange failed: {_http_error(response)}")
    payload = response.json()
    if not payload.get("access_token"):
        raise RuntimeError("Gemini token exchange returned no access token")
    expires_in = int(payload.get("expires_in") or 3600)
    payload["expires_at"] = int(time.time()) + expires_in
    return payload


def gemini_client() -> tuple[str, str]:
    client_id = os.environ.get("SHIBACLAW_GEMINI_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.environ.get("SHIBACLAW_GEMINI_OAUTH_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError(
            "Set SHIBACLAW_GEMINI_OAUTH_CLIENT_ID and "
            "SHIBACLAW_GEMINI_OAUTH_CLIENT_SECRET to the public Gemini CLI client."
        )
    return client_id, client_secret


async def start_subscription_login(job_id: str, jobs: dict, kind: str):
    """WebUI login. The page shows a code; the user pastes it back."""
    import asyncio

    from starlette.responses import JSONResponse

    verifier, challenge, state = new_pkce()
    if kind == "anthropic":
        url = claude_authorize_url(challenge, state)
        instruction = "Open Claude and paste the page value exactly, including the #."
        label = "Claude"
    else:
        try:
            url = gemini_authorize_url(challenge, state)
        except RuntimeError:
            return JSONResponse({"error": "Not configured by administrator"}, status_code=400)
        instruction = "Open Google and paste the code the page shows."
        label = "Gemini"

    loop = asyncio.get_running_loop()
    code_event = asyncio.Event()
    code_holder: dict[str, str] = {"value": ""}
    jobs[job_id]["status"] = "awaiting_paste"
    jobs[job_id]["console_url"] = url
    jobs[job_id]["instruction"] = instruction
    jobs[job_id]["_code_event"] = code_event
    jobs[job_id]["_code_holder"] = code_holder
    jobs[job_id]["logs"] = [instruction, url]

    async def _run() -> None:
        try:
            await asyncio.wait_for(code_event.wait(), timeout=900)
            pasted = code_holder["value"].strip()
            if kind == "anthropic":
                await asyncio.to_thread(
                    exchange_claude_code, split_claude_paste(pasted, state), state, verifier
                )
            else:
                from shibaclaw.security.oauth_store import OAuthTokenStore

                token = await asyncio.to_thread(exchange_gemini_code, pasted, verifier)
                await asyncio.to_thread(
                    OAuthTokenStore().save_token, "google_gemini_cli", token
                )
            jobs[job_id]["status"] = "done"
            jobs[job_id]["logs"].append(f"{label} connected")
        except Exception as exc:
            jobs[job_id]["status"] = "error"
            jobs[job_id]["logs"].append(str(exc)[:300])
        finally:
            loop.call_later(300, lambda: jobs.pop(job_id, None))

    asyncio.create_task(_run())
    return JSONResponse(
        {
            "job_id": job_id,
            "provider": kind,
            "status": "awaiting_paste",
            "console_url": url,
            "instruction": instruction,
        }
    )
