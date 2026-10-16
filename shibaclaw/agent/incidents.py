"""Deduped runtime faults for the evolve night pass. Not a second agent."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

_SKIP = (
    "api_key",
    "api key",
    "token",
    "password",
    "secret",
    "allowfrom",
    "allowlist-only",
    "is disabled",
    "is hidden",
    "guest",
)


def path() -> Path:
    override = os.environ.get("SHIBA_INCIDENTS")
    if override:
        return Path(override)
    return Path.home() / ".shibaclaw/workspace/memory/evolution/incidents.jsonl"


def note(kind: str, signature: str, detail: str = "") -> None:
    """Increment one signature. Skip secrets and guest refusals."""
    sig = " ".join((signature or "").split())[:180]
    if not sig:
        return
    blob = f"{sig} {detail}".lower()
    if any(mark in blob for mark in _SKIP):
        return
    file = path()
    file.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    if file.is_file():
        for line in file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    now = datetime.now(timezone.utc).isoformat()
    short = (detail or "")[:300]
    for row in rows:
        if row.get("kind") == kind and row.get("signature") == sig:
            row["count"] = int(row.get("count") or 1) + 1
            row["ts"] = now
            row["detail"] = short
            break
    else:
        rows.append({"ts": now, "kind": kind, "signature": sig, "detail": short, "count": 1})
    rows = rows[-200:]
    file.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
