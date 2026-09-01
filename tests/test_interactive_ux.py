"""Tests for OpenClaw-inspired interactive + session search + permission modes."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from shibaclaw.agent.interactive import (
    InteractiveHub,
    get_interactive_hub,
    normalize_permission_mode,
)
from shibaclaw.agent.tools.filesystem import ReadFileTool, WriteFileTool
from shibaclaw.agent.tools.interactive import (
    AskUserTool,
    RequestCredentialTool,
    UpdateProgressTool,
)
from shibaclaw.brain.manager import PackManager
from shibaclaw.security.credential_manager import CredentialManager


def test_normalize_permission_mode():
    assert normalize_permission_mode("readonly") == "readonly"
    assert normalize_permission_mode("FULL") == "full"
    assert normalize_permission_mode(None, restrict_to_workspace=True) == "workspace"
    assert normalize_permission_mode("nope", restrict_to_workspace=False) == "full"


def test_fs_readonly_blocks_write(tmp_path: Path):
    tool = WriteFileTool(workspace=tmp_path, allowed_dir=tmp_path)
    tool.configure_sandbox(allowed_dir=tmp_path, readonly=True)

    async def _run():
        return await tool.execute(path="x.txt", content="hi")

    out = asyncio.run(_run())
    assert "readonly" in out.lower()


def test_fs_workspace_blocks_outside(tmp_path: Path):
    tool = ReadFileTool(workspace=tmp_path, allowed_dir=tmp_path)
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    with pytest.raises(PermissionError):
        tool._resolve(str(outside))


def test_packmanager_search_messages(tmp_path: Path):
    pm = PackManager(tmp_path)
    s = pm.get_or_create("webui:abc")
    s.add_message("user", "hello unique-phrase-42 world")
    s.add_message("assistant", "ok")
    pm.save(s)

    hits = pm.search_messages("unique-phrase-42", limit=5)
    assert len(hits) == 1
    assert hits[0]["session_key"] == "webui:abc"
    assert "unique-phrase-42" in hits[0]["snippet"]


@pytest.mark.asyncio
async def test_interactive_hub_resolve_ask():
    hub = InteractiveHub()
    events: list[dict] = []

    async def emit(ev: dict) -> None:
        events.append(ev)

    hub.set_emit(emit)

    async def answer():
        await asyncio.sleep(0.05)
        assert events and events[0]["kind"] == "ask"
        rid = events[0]["request_id"]
        assert hub.resolve(rid, {"ok": True, "option_id": "yes", "label": "Yes"})

    task = asyncio.create_task(answer())
    result = await hub.request(
        kind="ask",
        session_key="webui:t",
        payload={"prompt": "Go?", "options": [{"id": "yes", "label": "Yes"}]},
        timeout=2,
    )
    await task
    assert result["ok"] is True
    assert result["option_id"] == "yes"


@pytest.mark.asyncio
async def test_credential_hub_stores_without_returning_secret(tmp_path: Path, monkeypatch):
    mgr = CredentialManager(store_dir=tmp_path)
    monkeypatch.setattr(
        "shibaclaw.security.credential_manager.get_credential_manager",
        lambda: mgr,
    )

    hub = InteractiveHub()
    events: list[dict] = []

    async def emit(ev: dict) -> None:
        events.append(ev)

    hub.set_emit(emit)

    async def answer():
        await asyncio.sleep(0.05)
        rid = events[0]["request_id"]
        hub.resolve(rid, {"secret": "super-secret-value"})

    task = asyncio.create_task(answer())
    result = await hub.request(
        kind="credential",
        session_key="webui:t",
        payload={"title": "API key", "key": "demo_key", "namespace": "runtime"},
        timeout=2,
    )
    await task
    assert result.get("stored") is True
    assert "secret" not in result
    assert mgr.get_secret("runtime", "demo_key") == "super-secret-value"


@pytest.mark.asyncio
async def test_ask_user_tool_fallback_without_emit():
    # Reset singleton emit
    hub = get_interactive_hub()
    hub.set_emit(None)
    tool = AskUserTool()
    tool.set_context("telegram", "1", "telegram:1")
    out = await tool.execute(
        prompt="Pick one",
        options=[{"id": "a", "label": "A"}],
    )
    assert "No interactive UI" in out or "Question for user" in out


@pytest.mark.asyncio
async def test_request_credential_rejects_telegram_channel():
    tool = RequestCredentialTool()
    tool.set_context("telegram", "1", "telegram:1")
    out = await tool.execute(title="Key", key="k1")
    assert "only allowed on WebUI" in out


@pytest.mark.asyncio
async def test_update_progress_tool():
    hub = get_interactive_hub()
    events: list[dict] = []

    async def emit(ev: dict) -> None:
        events.append(ev)

    hub.set_emit(emit)
    tool = UpdateProgressTool()
    tool.set_context("webui", "direct", "webui:direct")
    out = await tool.execute(title="Plan", status="working", steps=["one", "two"])
    assert "Progress card updated" in out
    card = hub.get_progress_card("webui:direct")
    assert card and card["title"] == "Plan"
    assert events and events[0]["kind"] == "progress_card"
    hub.set_emit(None)
