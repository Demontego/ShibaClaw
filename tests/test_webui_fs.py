import json
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.routers.fs import api_file_get, api_file_save, api_upload


def _request(method: str, body: dict | None = None, query: str = "") -> Request:
    payload = json.dumps(body or {}).encode("utf-8")

    async def receive():
        return {"type": "http.request", "body": payload, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": method,
            "path": "/api/file-get" if method == "GET" else "/api/file-save",
            "query_string": query.encode("utf-8"),
            "headers": [(b"content-type", b"application/json")],
        },
        receive,
    )


@pytest.mark.asyncio
async def test_media_files_are_readable_but_cannot_be_saved(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    media = tmp_path / "media"
    workspace.mkdir()
    media.mkdir()
    media_file = media / "recording.txt"
    media_file.write_text("original", encoding="utf-8")
    workspace_file = workspace / "note.txt"
    workspace_file.write_text("old", encoding="utf-8")

    monkeypatch.setattr(agent_manager, "config", SimpleNamespace(workspace_path=workspace))
    monkeypatch.setattr("shibaclaw.webui.utils.get_media_dir", lambda: media)
    monkeypatch.setattr("shibaclaw.webui.auth._auth_enabled", lambda: False)

    media_get = await api_file_get(_request("GET", query=f"path={media_file.as_posix()}"))
    media_save = await api_file_save(
        _request("POST", {"path": str(media_file), "content": "changed"})
    )
    workspace_save = await api_file_save(
        _request("POST", {"path": str(workspace_file), "content": "new"})
    )

    assert media_get.status_code == 200
    assert media_save.status_code == 403
    assert media_file.read_text(encoding="utf-8") == "original"
    assert workspace_save.status_code == 200
    assert workspace_file.read_text(encoding="utf-8") == "new"


@pytest.mark.asyncio
async def test_upload_reads_large_files_in_chunks(monkeypatch, tmp_path):
    data = b"x" * (1024 * 1024 + 7)

    class Upload:
        filename = "sample.bin"

        def __init__(self):
            self.position = 0
            self.read_sizes = []

        async def read(self, size):
            self.read_sizes.append(size)
            chunk = data[self.position : self.position + size]
            self.position += len(chunk)
            return chunk

    upload = Upload()

    class Form:
        def getlist(self, key):
            return [upload] if key == "file" else []

    async def form(self):
        return Form()

    monkeypatch.setattr(agent_manager, "config", SimpleNamespace(workspace_path=tmp_path))
    monkeypatch.setattr("shibaclaw.webui.auth._auth_enabled", lambda: False)
    monkeypatch.setattr(Request, "form", form)

    response = await api_upload(_request("POST"))

    assert response.status_code == 200
    assert upload.read_sizes == [1024 * 1024] * 3
    assert (tmp_path / "uploads" / "sample.bin").read_bytes() == data
