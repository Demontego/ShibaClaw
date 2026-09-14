from pathlib import Path

import pytest

from shibaclaw.agent.tools.filesystem import ReadFileTool


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
