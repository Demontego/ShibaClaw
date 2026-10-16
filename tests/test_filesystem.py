from pathlib import Path

import pytest

from shibaclaw.agent.context_overflow_guard import tombstone_tool_result
from shibaclaw.agent.tools.filesystem import FileReadCache, ReadFileTool


@pytest.mark.parametrize("path", ["memory/secretary", "memory/secretary/123.md"])
def test_filesystem_tools_block_secretary_archive_and_children(tmp_path: Path, path: str):
    archive = tmp_path / "memory" / "secretary"
    archive.mkdir(parents=True)
    (archive / "123.md").write_text("private", encoding="utf-8")

    with pytest.raises(PermissionError, match="Secretary archive"):
        ReadFileTool(workspace=tmp_path)._resolve(path)


@pytest.mark.asyncio
async def test_read_file_reports_binary_content(tmp_path: Path):
    binary = tmp_path / "sample.bin"
    binary.write_bytes(b"\xff\x00\x01")

    result = await ReadFileTool(workspace=tmp_path).execute("sample.bin")

    assert "Binary file (3 bytes)" in result
    assert "Cannot read as UTF-8 text" in result


@pytest.mark.asyncio
async def test_read_file_pdftotext_replaces_invalid_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4\xff\xfe binary")

    class _Result:
        returncode = 0
        stdout = "hello\xffworld"
        stderr = ""

    def _fake_run(*_args, **kwargs):
        assert kwargs.get("errors") == "replace"
        assert kwargs.get("encoding") == "utf-8"
        return _Result()

    monkeypatch.setattr("shibaclaw.agent.tools.filesystem.shutil.which", lambda _name: "/usr/bin/pdftotext")
    monkeypatch.setattr("shibaclaw.agent.tools.filesystem.subprocess.run", _fake_run)

    result = await ReadFileTool(workspace=tmp_path).execute("scan.pdf")

    assert "1| hello" in result
    assert "world" in result


@pytest.mark.asyncio
async def test_read_file_returns_each_requested_range(tmp_path: Path):
    (tmp_path / "sample.txt").write_text("one\ntwo\nthree\nfour\n", encoding="utf-8")
    tool = ReadFileTool(workspace=tmp_path)

    first = await tool.execute("sample.txt", offset=1, limit=2)
    second = await tool.execute("sample.txt", offset=3, limit=2)
    complete = await tool.execute("sample.txt")

    assert "1| one\n2| two" in first
    assert "3| three\n4| four" in second
    assert "1| one\n2| two\n3| three\n4| four" in complete
    assert "beyond end of file" in await tool.execute("sample.txt", offset=99)


@pytest.mark.asyncio
async def test_read_file_shared_cache_cannot_suppress_another_session(tmp_path: Path):
    (tmp_path / "sample.txt").write_text("session-visible text", encoding="utf-8")
    cache = FileReadCache()
    first_session = ReadFileTool(workspace=tmp_path, read_cache=cache)
    second_session = ReadFileTool(workspace=tmp_path, read_cache=cache)

    first = await first_session.execute("sample.txt")
    second = await second_session.execute("sample.txt")

    assert "1| session-visible text" in first
    assert second == first


@pytest.mark.asyncio
async def test_read_file_returns_content_after_prior_observation_is_masked(tmp_path: Path):
    (tmp_path / "sample.txt").write_text("recoverable source text", encoding="utf-8")
    tool = ReadFileTool(workspace=tmp_path)
    first = await tool.execute("sample.txt")
    masked = tombstone_tool_result({"role": "tool", "tool_call_id": "read", "content": first})
    assert "recoverable source text" not in masked["content"]

    assert await tool.execute("sample.txt") == first
