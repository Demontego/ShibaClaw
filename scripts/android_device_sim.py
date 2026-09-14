#!/usr/bin/env python3
"""Fake Android companion: connect to gateway and serve list_apps / launch_app / open_setting."""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid

import websockets


FAKE_APPS = [
    {"label": "Phone", "package": "com.android.dialer"},
    {"label": "WhatsApp", "package": "com.whatsapp"},
    {"label": "Settings", "package": "com.android.settings"},
]


def _tool_result(name: str, arguments: dict) -> tuple[bool, str, str]:
    if name == "list_apps":
        q = str(arguments.get("query") or "").lower()
        apps = [
            a
            for a in FAKE_APPS
            if not q or q in a["label"].lower() or q in a["package"].lower()
        ]
        return True, json.dumps(apps), ""
    if name == "launch_app":
        pkg = str(arguments.get("package") or "")
        if not pkg:
            return False, "", "package required"
        return True, f"launched {pkg} (sim)", ""
    if name == "open_setting":
        which = str(arguments.get("which") or "settings")
        return True, f"opened {which} (sim)", ""
    return False, "", f"unknown tool {name}"


async def run(host: str, port: int, token: str, device_id: str) -> None:
    uri = f"ws://{host}:{port}"
    async with websockets.connect(uri, open_timeout=8, ping_interval=20) as ws:
        await ws.send(
            json.dumps(
                {
                    "type": "hello",
                    "role": "device",
                    "token": token,
                    "device_id": device_id,
                    "label": "device-sim",
                }
            )
        )
        hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
        if hello.get("type") != "hello_ok":
            raise SystemExit(f"hello failed: {hello}")
        print("connected", hello.get("device"))
        async for raw in ws:
            msg = json.loads(raw)
            if msg.get("type") != "event" or msg.get("name") != "device.tools.invoke":
                continue
            payload = msg.get("payload") or {}
            ok, result, error = _tool_result(payload.get("name", ""), payload.get("arguments") or {})
            print("invoke", payload.get("name"), arguments := payload.get("arguments"), "->", result or error)
            await ws.send(
                json.dumps(
                    {
                        "type": "request",
                        "id": "r" + uuid.uuid4().hex[:8],
                        "action": "device.tools.result",
                        "payload": {
                            "id": payload.get("id"),
                            "ok": ok,
                            "result": result,
                            "error": error,
                        },
                    }
                )
            )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=19998)
    p.add_argument("--token", default="")
    p.add_argument("--device-id", default="sim.pixel")
    args = p.parse_args()
    asyncio.run(run(args.host, args.port, args.token, args.device_id))


if __name__ == "__main__":
    main()
