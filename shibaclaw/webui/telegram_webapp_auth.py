"""Validate Telegram Mini App initData (WebApp data-check-string)."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import parse_qsl

# Max age for initData auth_date (seconds). Plan: 86400.
DEFAULT_MAX_AGE_SEC = 86400


def validate_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_sec: int = DEFAULT_MAX_AGE_SEC,
    now: float | None = None,
) -> dict[str, Any] | None:
    """Return parsed fields if *init_data* is valid, else ``None``.

    Spec: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    secret_key = HMAC_SHA256(key=\"WebAppData\", msg=bot_token)
    """
    if not init_data or not bot_token:
        return None

    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    calculated = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(calculated, received_hash):
        return None

    try:
        auth_date = int(parsed.get("auth_date") or "0")
    except ValueError:
        return None
    ts = time.time() if now is None else now
    if auth_date <= 0 or abs(ts - auth_date) > max_age_sec:
        return None

    user: dict[str, Any] | None = None
    if "user" in parsed and parsed["user"]:
        try:
            user = json.loads(parsed["user"])
        except json.JSONDecodeError:
            return None
        if not isinstance(user, dict) or user.get("id") is None:
            return None

    return {
        "user": user,
        "auth_date": auth_date,
        "query_id": parsed.get("query_id"),
        "raw": parsed,
    }


def user_id_allowed(user_id: int | str, allow_from: list[str]) -> bool:
    """Owner-only: numeric id must be in allow_from. Bare '*' is rejected for Mini App."""
    if not allow_from:
        return False
    uid = str(user_id).strip()
    if not uid or uid == "*":
        return False
    allowed = {str(x).strip() for x in allow_from if str(x).strip() and str(x).strip() != "*"}
    return uid in allowed
