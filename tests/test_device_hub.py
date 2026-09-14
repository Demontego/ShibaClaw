"""Android device hub: register tools, invoke, complete, disconnect."""

from __future__ import annotations

import asyncio

import pytest

from shibaclaw.agent.device_hub import ALLOWED_ANDROID_TOOLS, DeviceHub
from shibaclaw.agent.tools.registry import SkillVault


@pytest.mark.asyncio
async def test_attach_registers_proxy_tools_and_invoke_roundtrip():
    vault = SkillVault()
    hub = DeviceHub(vault)
    sent: list[dict] = []

    async def send(payload: dict) -> None:
        sent.append(payload)
        hub.complete(payload["id"], ok=True, result='[{"label":"Phone","package":"com.android.dialer"}]')

    hub.attach("pixel.test", send, label="Pixel")
    assert hub.connected
    assert ALLOWED_ANDROID_TOOLS <= set(vault.tool_names)
    assert hub.session_key() == "android:pixel.test"

    result = await vault.execute("list_apps", {"query": "phone"})
    assert "com.android.dialer" in result
    assert sent and sent[0]["name"] == "list_apps"
    assert sent[0]["arguments"]["query"] == "phone"


@pytest.mark.asyncio
async def test_invoke_times_out_without_result(monkeypatch):
    vault = SkillVault()
    hub = DeviceHub(vault)

    async def send(_payload: dict) -> None:
        return None

    import shibaclaw.agent.device_hub as device_hub_mod

    monkeypatch.setattr(device_hub_mod, "INVOKE_TIMEOUT_S", 0.05)
    hub.attach("pixel.test", send)
    result = await vault.execute("launch_app", {"package": "com.whatsapp"})
    assert result.startswith("Error:")
    assert "timed out" in result


@pytest.mark.asyncio
async def test_detach_fails_pending_and_unregisters():
    vault = SkillVault()
    hub = DeviceHub(vault)
    started = asyncio.Event()

    async def send(_payload: dict) -> None:
        started.set()

    hub.attach("pixel.test", send)
    task = asyncio.create_task(vault.execute("open_setting", {"which": "wifi"}))
    await started.wait()
    hub.detach()
    result = await task
    assert "disconnected" in result
    assert "list_apps" not in vault.tool_names
    assert not hub.connected


def test_invalid_device_id_rejected():
    hub = DeviceHub(SkillVault())

    async def send(_payload: dict) -> None:
        return None

    with pytest.raises(ValueError):
        hub.attach("bad id with spaces", send)


@pytest.mark.asyncio
async def test_complete_unknown_id_is_false():
    hub = DeviceHub(SkillVault())
    assert hub.complete("nope", ok=True, result="x") is False
