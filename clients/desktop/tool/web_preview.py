"""Serve the Flutter web build and proxy /api and /ws to the WebUI.

shortcut: local compare only. Replace with nginx when the desktop client is the product.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import uvicorn
import websockets
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, Response
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

ROOT = Path(__file__).resolve().parents[1] / "build" / "web"
UPSTREAM = "http://127.0.0.1:3000"
WS_UPSTREAM = "ws://127.0.0.1:3000/ws"
_HOP = {"content-encoding", "content-length", "transfer-encoding", "connection"}


async def api(request: Request) -> Response:
    url = f"{UPSTREAM}{request.url.path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"
    headers = {k: v for k, v in request.headers.items() if k.lower() not in {"host", "content-length"}}
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.request(request.method, url, content=await request.body(), headers=headers)
    out = {k: v for k, v in resp.headers.items() if k.lower() not in _HOP}
    return Response(content=resp.content, status_code=resp.status_code, headers=out)


async def ws_proxy(ws: WebSocket) -> None:
    await ws.accept()
    try:
        async with websockets.connect(WS_UPSTREAM) as upstream:

            async def client_to_server() -> None:
                while True:
                    message = await ws.receive()
                    if message["type"] == "websocket.disconnect":
                        break
                    if message.get("text") is not None:
                        await upstream.send(message["text"])
                    elif message.get("bytes") is not None:
                        await upstream.send(message["bytes"])

            async def server_to_client() -> None:
                async for message in upstream:
                    if isinstance(message, bytes):
                        await ws.send_bytes(message)
                    else:
                        await ws.send_text(message)

            await asyncio.gather(client_to_server(), server_to_client())
    except (WebSocketDisconnect, Exception):
        await ws.close()


def page(request: Request) -> FileResponse:
    raw = request.path_params.get("path", "")
    root = ROOT.resolve()
    file = (root / raw).resolve()
    if not str(file).startswith(str(root)) or not file.is_file():
        file = root / "index.html"
    return FileResponse(file)


app = Starlette(
    routes=[
        Route("/api/{path:path}", api, methods=["GET", "POST", "PUT", "PATCH", "DELETE"]),
        WebSocketRoute("/ws", ws_proxy),
        Route("/", page),
        Route("/{path:path}", page),
    ]
)


def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=8090)


if __name__ == "__main__":
    main()
