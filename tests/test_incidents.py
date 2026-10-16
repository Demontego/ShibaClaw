"""Incidents file dedupes one signature and skips secrets."""

import json

from shibaclaw.agent.incidents import note


def test_note_counts_and_skips_secrets(monkeypatch, tmp_path):
    file = tmp_path / "incidents.jsonl"
    monkeypatch.setenv("SHIBA_INCIDENTS", str(file))
    note("provider", "context_length_exceeded", "prompt too long")
    note("provider", "context_length_exceeded", "prompt too long")
    note("tool", "exec api_key=secret", "nope")
    rows = [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines()]
    assert rows == [
        {
            "ts": rows[0]["ts"],
            "kind": "provider",
            "signature": "context_length_exceeded",
            "detail": "prompt too long",
            "count": 2,
        }
    ]
