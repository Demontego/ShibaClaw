"""Secretary markdown sync incremental behavior."""

from __future__ import annotations

import json
from pathlib import Path

from shibaclaw.agent.tools.secretary import sync


def _write_business_session(workspace: Path, peer_id: int = 42) -> Path:
    sessions = workspace / "sessions"
    sessions.mkdir(parents=True)
    path = sessions / f"telegram_{peer_id}.jsonl"
    lines = [
        {
            "_type": "metadata",
            "key": f"telegram:{peer_id}",
            "created_at": "2026-01-01T00:00:00",
            "metadata": {},
        },
        {
            "role": "user",
            "content": "hello from peer",
            "timestamp": "2026-01-01T12:00:00",
            "metadata": {
                "business_connection_id": "bc1",
                "user_id": str(peer_id),
                "first_name": "Peer",
            },
        },
    ]
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    return path


def test_sync_secretary_markdown_skips_unchanged(tmp_path: Path):
    _write_business_session(tmp_path)
    first = sync.sync_secretary_markdown(tmp_path)
    assert first["written"] == 1
    second = sync.sync_secretary_markdown(tmp_path)
    assert second["written"] == 0
    assert second["files"] == 1
