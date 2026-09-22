"""Gate, alarm arming, and secret diff refusal for opt-in evolution."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from shibaclaw.automation.service import AutomationService
from shibaclaw.evolve.diffcheck import check_repo
from shibaclaw.evolve.gate import MAX_APPLIES, gate, load
from shibaclaw.evolve.switch import handle, is_owner_surface, owner_chat

UTC = ZoneInfo("UTC")


def test_gate_budget_and_panic(tmp_path, monkeypatch):
    monkeypatch.setenv("EVOLVE_STATE", str(tmp_path / "state.json"))
    text, code = handle("gate", workspace=tmp_path, tz=UTC)
    assert code == 3
    assert "off" in text

    handle("on", workspace=tmp_path, tz=UTC)
    text, code = handle("gate", workspace=tmp_path, tz=UTC)
    assert code == 0
    assert text == "gate open"
    assert gate(load(tmp_path), UTC) == 5

    handle("end", workspace=tmp_path, tz=UTC)
    assert gate(load(tmp_path), UTC) == 0

    for _ in range(MAX_APPLIES):
        handle("note-apply", workspace=tmp_path, tz=UTC)
    assert gate(load(tmp_path), UTC) == 6

    handle("panic", workspace=tmp_path, tz=UTC)
    assert gate(load(tmp_path), UTC) == 2


def test_cooldown_blocks_gate(tmp_path, monkeypatch):
    monkeypatch.setenv("EVOLVE_STATE", str(tmp_path / "state.json"))
    handle("on", workspace=tmp_path, tz=UTC)
    handle("note-apply", workspace=tmp_path, tz=UTC)
    _text, code = handle("gate", workspace=tmp_path, tz=UTC)
    assert code == 7

    data = load(tmp_path)
    data["last_apply_at"] = (datetime.now(UTC) - timedelta(minutes=46)).isoformat()
    data["applies_today"] = 1
    from shibaclaw.evolve.gate import save

    save(tmp_path, data)
    assert gate(load(tmp_path), UTC) == 0


def test_alarm_job_is_every_thirty_minutes(tmp_path, monkeypatch):
    monkeypatch.setenv("EVOLVE_STATE", str(tmp_path / "state.json"))
    service = AutomationService(store_path=tmp_path / "automation.json", workspace=tmp_path)
    text, code = handle("on", workspace=tmp_path, automation=service, owner="1", tz=UTC)
    assert code == 0
    assert "enabled=True" in text
    job = next(j for j in service.list_jobs() if j.name == "Shiba evolve")
    assert job.enabled is True
    assert job.schedule.kind == "every"
    assert job.schedule.every_ms == 30 * 60 * 1000
    assert job.payload.to == "1"
    assert "EVOLVE_SKIP" in job.payload.message


def test_owner_surface_and_chat():
    owners = {"42"}
    assert is_owner_surface("webui", "x", {}, owners)
    assert is_owner_surface("telegram", "42", {}, owners)
    assert not is_owner_surface("telegram", "7", {}, owners)
    assert not is_owner_surface("telegram", "42", {"is_group": True}, owners)
    assert not is_owner_surface("telegram", "42", {"business_connection_id": "b"}, owners)
    assert owner_chat({"telegram": {"allowFrom": ["*", "42"]}}) == "42"
    assert owner_chat({"telegram": {"allowFrom": ["*"]}}) is None


def test_check_refuses_default_branch_and_env(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "evolve",
        "GIT_AUTHOR_EMAIL": "evolve@example.com",
        "GIT_COMMITTER_NAME": "evolve",
        "GIT_COMMITTER_EMAIL": "evolve@example.com",
    }

    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(repo), *args], check=True, env=env)

    git("init", "-b", "main")
    (repo / "readme.md").write_text("hi\n", encoding="utf-8")
    git("add", "readme.md")
    git("commit", "-m", "init")
    assert check_repo(repo) == "refuse: branch main"

    git("checkout", "-b", "evolve/demo")
    (repo / ".env").write_text("TOKEN=1\n", encoding="utf-8")
    git("add", "-f", ".env")
    git("commit", "-m", "leak")
    assert check_repo(repo) == "refuse: .env"

    git("rm", "--cached", ".env")
    (repo / ".env").unlink()
    (repo / "ok.py").write_text("x = 1\n", encoding="utf-8")
    git("add", "ok.py")
    git("commit", "-m", "fix")
    assert check_repo(repo) is None
