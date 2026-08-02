"""Tests for profile tool filters, temperature, and knowledge base pinning."""

from __future__ import annotations

import json
from pathlib import Path

from shibaclaw.agent.loop import ShibaBrain
from shibaclaw.agent.profiles import ProfileManager


def _pm(tmp_path: Path, manifest: dict) -> ProfileManager:
    (tmp_path / "profiles").mkdir(parents=True, exist_ok=True)
    (tmp_path / "profiles" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return ProfileManager(tmp_path)


def test_disabled_and_enabled_tools(tmp_path: Path):
    pm = _pm(
        tmp_path,
        {
            "quiet": {"disabled_tools": ["*"]},
            "search_only": {"enabled_tools": ["web_search", "web_fetch"]},
        },
    )
    assert pm.get_disabled_tools("quiet") == ["*"]
    assert pm.get_enabled_tools("search_only") == ["web_search", "web_fetch"]
    assert pm.get_enabled_tools("quiet") is None


def test_filter_tools_enabled_wins_over_disabled_star():
    brain = object.__new__(ShibaBrain)
    brain.workspace = Path("/tmp")  # unused when we patch methods

    class _PM:
        def get_enabled_tools(self, _pid):
            return ["web_search"]

        def get_disabled_tools(self, _pid):
            return ["*"]

    import shibaclaw.agent.profiles as profiles_mod

    original = profiles_mod.ProfileManager
    profiles_mod.ProfileManager = lambda _ws: _PM()  # type: ignore[misc, assignment]
    try:
        defs = [
            {"function": {"name": "web_search"}},
            {"function": {"name": "exec"}},
        ]
        out = brain._filter_tools_for_profile(defs, "x")
        assert [d["function"]["name"] for d in out] == ["web_search"]
        assert brain._tool_disabled_for_profile("exec", "x") is True
        assert brain._tool_disabled_for_profile("web_search", "x") is False
    finally:
        profiles_mod.ProfileManager = original


def test_resolve_temperature_session_wins(tmp_path: Path):
    _pm(tmp_path, {"hot": {"temperature": 0.9}})
    assert ShibaBrain._resolve_temperature("hot", {"temperature": 0.1}, tmp_path) == 0.1
    assert ShibaBrain._resolve_temperature("hot", {}, tmp_path) == 0.9
    assert ShibaBrain._resolve_temperature("missing", {}, tmp_path) is None


def test_sync_session_knowledge_bases(tmp_path: Path):
    pm = _pm(
        tmp_path,
        {
            "a": {"knowledge_bases": ["kb-a"]},
            "b": {"knowledge_bases": ["kb-b"]},
        },
    )
    meta: dict = {}
    assert pm.sync_session_knowledge_bases(meta, "a", None) is True
    assert meta["knowledge_bases"] == ["kb-a"]
    assert pm.sync_session_knowledge_bases(meta, "b", "a") is True
    assert meta["knowledge_bases"] == ["kb-b"]
    # Manual pins are preserved and the new profile defaults are still attached.
    meta["knowledge_bases"] = ["manual"]
    assert pm.sync_session_knowledge_bases(meta, "a", "b") is True
    assert meta["knowledge_bases"] == ["manual", "kb-a"]


def test_sync_session_knowledge_bases_keeps_custom_pins_on_switch(tmp_path: Path):
    pm = _pm(
        tmp_path,
        {
            "old": {"knowledge_bases": ["old-default"]},
            "new": {"knowledge_bases": ["new-default"]},
        },
    )
    meta = {"knowledge_bases": ["custom", "old-default"]}

    assert pm.sync_session_knowledge_bases(meta, "new", "old") is True
    assert meta["knowledge_bases"] == ["custom", "new-default"]
