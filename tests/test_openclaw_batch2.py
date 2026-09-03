"""Batch-2 OpenClaw-inspired features tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from shibaclaw.agent.profiles import ProfileManager
from shibaclaw.agent.skill_workshop import SkillWorkshop
from shibaclaw.automation.grants import job_is_approved, operation_fingerprint
from shibaclaw.automation.types import AutomationJob, AutomationPayload, AutomationSchedule
from shibaclaw.brain.manager import PackManager, Session
from shibaclaw.config.history import append_config_history, list_config_history


def test_automation_fingerprint_and_approval():
    sched = AutomationSchedule(kind="every", every_ms=60_000)
    payload = AutomationPayload(kind="scheduled", message="ping")
    fp = operation_fingerprint(sched, payload)
    job = AutomationJob(
        id="x",
        name="t",
        schedule=sched,
        payload=payload,
        require_approval=True,
        approved_fingerprint=None,
    )
    assert not job_is_approved(job)
    job.approved_fingerprint = fp
    assert job_is_approved(job)
    job.payload = AutomationPayload(kind="scheduled", message="pong")
    assert not job_is_approved(job)


def test_skill_workshop_max_three(tmp_path: Path):
    ws = SkillWorkshop(tmp_path)
    for i in range(3):
        r = ws.propose(
            name=f"skill{i}",
            description="d",
            skill_md=f"# Skill {i}\n",
        )
        assert r["ok"], r
    full = ws.propose(name="skill3", description="d", skill_md="# x\n")
    assert not full["ok"]
    assert "full" in full["error"]
    pending = ws.list_pending()
    assert len(pending) == 3
    ok = ws.approve(pending[0]["id"])
    assert ok["ok"]
    assert (tmp_path / "skills" / pending[0]["name"] / "SKILL.md").exists()
    assert len(ws.list_pending()) == 2


def test_profile_model_allowlist(tmp_path: Path):
    pm = ProfileManager(tmp_path)
    pm.create_profile(
        "trader",
        "Trader",
        allowed_models=["openai/gpt-4o", "google/*"],
    )
    assert pm.model_allowed("trader", "openai/gpt-4o")
    assert pm.model_allowed("trader", "google/gemini-3-flash")
    assert not pm.model_allowed("trader", "anthropic/claude-opus")
    # Substring must not match (e.g. gpt-4o inside a longer id).
    assert not pm.model_allowed("trader", "openai/gpt-4o-mini")
    assert pm.model_allowed("default", "anything")  # None = unrestricted

    pm.create_profile("locked", "Locked", allowed_models=[])
    assert not pm.model_allowed("locked", "openai/gpt-4o")  # [] = deny all


@pytest.mark.asyncio
async def test_memory_forget_rejects_short_needle(tmp_path: Path):
    from shibaclaw.agent.memory import ScentKeeper

    store = ScentKeeper(tmp_path)
    store.memory_file.parent.mkdir(parents=True, exist_ok=True)
    store.memory_file.write_text("keep this line\nsecret password here\n", encoding="utf-8")
    short = await store.forget_memory_lines("ab")
    assert short.get("error")
    assert "secret password here" in store.memory_file.read_text(encoding="utf-8")
    ok = await store.forget_memory_lines("password")
    assert not ok.get("error")
    assert ok["MEMORY.md"] == 1
    assert "password" not in store.memory_file.read_text(encoding="utf-8")


def test_session_rewind_fork_incognito(tmp_path: Path):
    pm = PackManager(tmp_path)
    s = pm.get_or_create("webui:main")
    for i in range(5):
        s.add_message("user" if i % 2 == 0 else "assistant", f"msg-{i}")
    pm.save(s)
    assert len(s.messages) == 5

    forked = pm.fork_session("webui:main", 3)
    assert forked is not None
    assert len(forked.messages) <= 3
    assert forked.metadata.get("forked_from") == "webui:main"

    pm.rewind_session("webui:main", 2)
    s2 = pm.get_or_create("webui:main")
    assert len(s2.messages) <= 2

    inc = pm.get_or_create("webui:secret")
    inc.metadata["incognito"] = True
    inc.add_message("user", "do not persist")
    pm.save(inc)
    path = pm._get_session_path("webui:secret")
    assert not path.exists()


def test_config_history(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "shibaclaw.config.history._history_path",
        lambda: tmp_path / "config_history.jsonl",
    )
    append_config_history(
        actor="test",
        reason="unit",
        data={"providers": {"openai": {"apiKey": "sk-secret"}}},
        changed_keys=["providers"],
    )
    rows = list_config_history(limit=5)
    assert rows
    assert rows[0]["snapshot"]["providers"]["openai"]["apiKey"] == "***"
