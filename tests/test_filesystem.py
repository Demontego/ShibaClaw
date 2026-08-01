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
