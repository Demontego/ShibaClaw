"""Tests for Artifact-Preserving Context Compaction & File Read Deduplication."""

import pytest
from pathlib import Path

from shibaclaw.agent.context_overflow_guard import (
    ArtifactRegister,
    ContextOverflowGuard,
    PROMPT_CACHE_PREFIX_MARKER,
)
from shibaclaw.agent.tools.filesystem import (
    FileReadCache,
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
)


def test_artifact_register_basic():
    reg = ArtifactRegister()
    reg.record_modified_file("/workspace/foo.py")
    reg.record_git_commit("abc1234 feat: foo")
    reg.record_subagent_result("researcher", "done", "found answer")
    reg.record_read_file("/workspace/bar.py")

    assert "/workspace/foo.py" in reg.modified_files
    assert "/workspace/bar.py" in reg.read_files
    assert len(reg.git_commits) == 1
    assert len(reg.subagent_results) == 1

    md = reg.render_markdown()
    assert PROMPT_CACHE_PREFIX_MARKER in md
    assert "<artifact_register>" in md
    assert "`/workspace/foo.py`" in md
    assert "`abc1234 feat: foo`" in md
    assert "[done] researcher: found answer" in md
    assert "`/workspace/bar.py`" in md

    d = reg.to_dict()
    restored = ArtifactRegister.from_dict(d)
    assert restored.modified_files == reg.modified_files
    assert restored.git_commits == reg.git_commits

    reg.clear()
    assert len(reg.modified_files) == 0


def test_context_overflow_guard_artifact_preservation(tmp_path: Path):
    reg = ArtifactRegister()
    reg.record_modified_file("src/main.py")
    guard = ContextOverflowGuard(workspace=tmp_path, context_window_tokens=1000, artifact_register=reg)

    messages = [
        {"role": "system", "content": "System prompt instructions."},
        {"role": "user", "content": "Msg 1 " * 100},
        {"role": "assistant", "content": "Reply 1 " * 100},
        {"role": "user", "content": "Msg 2 " * 100},
        {"role": "assistant", "content": "Reply 2 " * 100},
        {"role": "user", "content": "Recent msg"},
    ]

    budgeted = guard.budget_context(messages, max_tokens=150)
    assert len(budgeted) < len(messages)
    sys_content = budgeted[0]["content"]
    assert "<artifact_register>" in sys_content
    assert "`src/main.py`" in sys_content
    assert PROMPT_CACHE_PREFIX_MARKER in sys_content

    summary = guard.format_compacted_summary("Session summary")
    assert "Session summary" in summary
    assert "<artifact_register>" in summary


@pytest.mark.asyncio
async def test_file_read_deduplication_and_cache(tmp_path: Path):
    test_file = tmp_path / "sample.txt"
    test_file.write_text("line 1\nline 2\nline 3\n", encoding="utf-8")

    cache = FileReadCache()
    reg = ArtifactRegister()

    read_tool = ReadFileTool(workspace=tmp_path, read_cache=cache, artifact_register=reg)
    write_tool = WriteFileTool(workspace=tmp_path, read_cache=cache, artifact_register=reg)
    edit_tool = EditFileTool(workspace=tmp_path, read_cache=cache, artifact_register=reg)

    # First read: returns full content
    res1 = await read_tool.execute(path=str(test_file))
    assert "1| line 1" in res1
    assert "3| line 3" in res1
    assert str(test_file.resolve()) in reg.read_files

    # Second read: deduplicated stub returned
    res2 = await read_tool.execute(path=str(test_file))
    assert "[File Read Deduplicated:" in res2
    assert "Content is unchanged from prior read" in res2

    # Third read with force_reload=True: returns full content
    res3 = await read_tool.execute(path=str(test_file), force_reload=True)
    assert "1| line 1" in res3
    assert "[File Read Deduplicated:" not in res3

    # Edit file: invalidates cache and records modification
    edit_res = await edit_tool.execute(path=str(test_file), old_text="line 2", new_text="line 2 edited")
    assert "Successfully edited" in edit_res
    assert str(test_file.resolve()) in reg.modified_files

    # Read after edit: returns full updated content (not deduplicated)
    res4 = await read_tool.execute(path=str(test_file))
    assert "line 2 edited" in res4
    assert "[File Read Deduplicated:" not in res4

    # Write file: invalidates cache again
    write_res = await write_tool.execute(path=str(test_file), content="brand new content\n")
    assert "Successfully wrote" in write_res

    res5 = await read_tool.execute(path=str(test_file))
    assert "brand new content" in res5
