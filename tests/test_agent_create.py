"""Owner can create a specialist. Built-in leftovers are dropped on sync."""

import json
from pathlib import Path

from shibaclaw.agent.profiles import ProfileManager
from shibaclaw.agent.tools.agent_create import AgentCreateTool
from shibaclaw.helpers.helpers import sync_profiles


def _tool(tmp_path: Path) -> AgentCreateTool:
    (tmp_path / "profiles").mkdir()
    (tmp_path / "profiles" / "manifest.json").write_text(
        json.dumps({"default": {"label": "ShibaClaw", "builtin": True}}),
        encoding="utf-8",
    )
    return AgentCreateTool(tmp_path, owner_ids={"1"})


async def test_guest_cannot_create(tmp_path: Path):
    tool = _tool(tmp_path)
    tool.set_context("telegram", "42", metadata={"is_guest": True, "user_id": "42"})

    result = await tool.execute(label="Scout", brief="Reads the web and reports.")

    assert "owner" in result.lower() or "Guest" in result
    assert ProfileManager(tmp_path).get_profile("scout") is None


async def test_owner_creates_profile_from_label(tmp_path: Path):
    tool = _tool(tmp_path)
    tool.set_context("webui", "rinat", session_key="webui:rinat")

    result = await tool.execute(label="Gym Coach", brief="Logs the Friday leg day.")

    assert result == "Created Gym Coach (gym-coach)."
    profile = ProfileManager(tmp_path).get_profile("gym-coach")
    assert profile is not None
    assert profile["builtin"] is False
    assert profile["soul"] == "Logs the Friday leg day."
    assert ProfileManager(tmp_path).get_profile("default")["label"] == "ShibaClaw"


async def test_agent_session_cannot_create(tmp_path: Path):
    tool = _tool(tmp_path)
    tool.set_context("webui", "rinat", session_key="agent:gym-coach")

    result = await tool.execute(label="Scout", brief="Reads the web.")

    assert "hidden" in result
    assert ProfileManager(tmp_path).get_profile("scout") is None


async def test_existing_profile_is_not_overwritten(tmp_path: Path):
    tool = _tool(tmp_path)
    tool.set_context("webui", "rinat", session_key="webui:rinat")
    await tool.execute(label="Scout", brief="First brief.")

    result = await tool.execute(label="Scout", brief="Second brief.")

    assert "already exists" in result
    assert ProfileManager(tmp_path).get_profile("scout")["soul"] == "First brief."


def test_sync_drops_removed_builtins_and_keeps_custom(tmp_path: Path):
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "manifest.json").write_text(
        json.dumps({
            "default": {"label": "ShibaClaw", "builtin": True},
            "builder": {"label": "Builder", "builtin": True},
            "gym": {"label": "Gym", "builtin": False},
        }),
        encoding="utf-8",
    )
    (profiles / "builder").mkdir()
    (profiles / "builder" / "SOUL.md").write_text("old", encoding="utf-8")
    (profiles / "gym").mkdir()
    (profiles / "gym" / "SOUL.md").write_text("keep", encoding="utf-8")

    sync_profiles(tmp_path)

    manifest = json.loads((profiles / "manifest.json").read_text(encoding="utf-8"))
    assert "builder" not in manifest
    assert manifest["gym"]["label"] == "Gym"
    assert manifest["default"]["builtin"] is True
    assert not (profiles / "builder").exists()
    assert (profiles / "gym" / "SOUL.md").read_text(encoding="utf-8") == "keep"
