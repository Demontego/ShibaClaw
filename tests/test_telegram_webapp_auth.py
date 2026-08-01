"""Tests for Telegram Mini App initData validation."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from shibaclaw.webui.telegram_webapp_auth import user_id_allowed, validate_init_data


def _sign(bot_token: str, fields: dict[str, str]) -> str:
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    return hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()


def test_validate_init_data_ok_and_rejects_tamper_stale():
    bot_token = "123456:ABC-DEF"
    now = int(time.time())
    user = {"id": 42, "first_name": "Owner"}
    fields = {
        "auth_date": str(now),
        "user": json.dumps(user, separators=(",", ":")),
    }
    init_data = urlencode({**fields, "hash": _sign(bot_token, fields)})

    ok = validate_init_data(init_data, bot_token, now=float(now))
    assert ok is not None
    assert ok["user"]["id"] == 42

    assert validate_init_data(init_data + "x", bot_token, now=float(now)) is None

    stale_fields = {
        "auth_date": str(now - 90000),
        "user": json.dumps(user, separators=(",", ":")),
    }
    stale = urlencode({**stale_fields, "hash": _sign(bot_token, stale_fields)})
    assert validate_init_data(stale, bot_token, now=float(now)) is None


def test_user_id_allowed_rejects_star():
    assert user_id_allowed(42, ["42"])
    assert not user_id_allowed(42, ["*"])
    assert not user_id_allowed(1, ["42"])
