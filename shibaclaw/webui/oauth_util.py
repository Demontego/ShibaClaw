"""Shared OAuth helpers for WebUI flows."""

from __future__ import annotations

import base64


def base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
