import json
from pathlib import Path

from shibaclaw.agent.tools.agent_send import AgentSendTool, hide_agent_send
from shibaclaw.brain.manager import PackManager
from shibaclaw.bus.events import InboundMessage


class _Bus:
    def __init__(self) -> None:
        self.inbound: list[InboundMessage] = []

    async def publish_inbound(self, msg: InboundMessage) -> None:
        self.inbound.append(msg)


def _workspace(tmp_path: Path) -> Path:
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "manifest.json").write_text(
        json.dumps({"polymarket": {"label": "Polymarket"}}),
        encoding="utf-8",
    )
    return tmp_path


def _tool(tmp_path: Path, bus: _Bus) -> tuple[AgentSendTool, PackManager]:
    sessions = PackManager(tmp_path)
    tool = AgentSendTool(sessions, bus, _workspace(tmp_path), owner_ids={"1"})
    return tool, sessions


async def test_guest_is_denied(tmp_path: Path):
    bus = _Bus()
    tool, _sessions = _tool(tmp_path, bus)
    tool.set_context("telegram", "42", metadata={"is_guest": True, "user_id": "42"})

    result = await tool.execute(profile_id="polymarket", message="check")

    assert "owner" in result.lower() or "Guest" in result
    assert bus.inbound == []


async def test_unknown_profile_is_denied(tmp_path: Path):
    bus = _Bus()
    tool, sessions = _tool(tmp_path, bus)
    tool.set_context("webui", "rinat", session_key="webui:rinat", profile_id="default")

    result = await tool.execute(profile_id="missing", message="check")

    assert "unknown profile" in result
    assert bus.inbound == []
    assert not (sessions.sessions_dir / "agent_missing.jsonl").exists()


async def test_owner_wakes_profile_without_touching_telegram(tmp_path: Path):
    bus = _Bus()
    tool, sessions = _tool(tmp_path, bus)
    foreign = sessions.get_or_create("telegram:999")
    foreign.metadata["profile_id"] = "default"
    sessions.save(foreign)
    before = (sessions.sessions_dir / "telegram_999.jsonl").read_bytes()
    tool.set_context("webui", "rinat", session_key="webui:rinat", profile_id="default")

    result = await tool.execute(profile_id="polymarket", message="what is open")

    assert result.startswith("Woke Polymarket")
    assert (sessions.sessions_dir / "telegram_999.jsonl").read_bytes() == before
    woken = sessions.get_or_create("agent:polymarket")
    assert woken.metadata["profile_id"] == "polymarket"
    assert len(bus.inbound) == 1
    msg = bus.inbound[0]
    assert msg.session_key == "agent:polymarket"
    assert msg.channel == "webui"
    assert msg.chat_id == "rinat"
    assert msg.content.startswith("[From default]")


async def test_agent_session_cannot_send(tmp_path: Path):
    bus = _Bus()
    tool, _sessions = _tool(tmp_path, bus)
    tool.set_context("webui", "rinat", session_key="agent:polymarket", profile_id="polymarket")

    result = await tool.execute(profile_id="gym", message="go")

    assert "hidden" in result
    assert bus.inbound == []


def test_hide_agent_send_drops_only_on_agent_sessions():
    defs = [{"function": {"name": "agent_send"}}, {"function": {"name": "message"}}]
    assert hide_agent_send(defs, "webui:rinat") == defs
    assert hide_agent_send(defs, "agent:polymarket") == [{"function": {"name": "message"}}]
