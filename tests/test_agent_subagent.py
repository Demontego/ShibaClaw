from pathlib import Path
from unittest.mock import MagicMock
from shibaclaw.agent.subagent import SubagentManager

def test_subagent_manager_init(tmp_path: Path):
    bus = MagicMock()
    manager = SubagentManager(None, tmp_path, bus)
    assert manager.workspace == tmp_path

def test_subagent_structured_synthesis_json(tmp_path: Path):
    bus = MagicMock()
    manager = SubagentManager(None, tmp_path, bus)
    
    json_result = '{"status": "success", "data": [1, 2, 3]}'
    synthesized = manager._synthesize_structured_result(json_result)
    
    assert "status" in synthesized
    assert "success" in synthesized

def test_subagent_structured_synthesis_text(tmp_path: Path):
    bus = MagicMock()
    manager = SubagentManager(None, tmp_path, bus)
    
    text_result = (
        "## Summary\n"
        "This is a summary of the task.\n\n"
        "## Key Findings\n"
        "- Finding 1\n"
        "- Finding 2\n"
        "- Finding 3\n"
        "- Finding 4\n"
        "- Finding 5\n"
        "- Finding 6\n"
        "- Finding 7\n"
        "- Finding 8\n"
        "- Finding 9\n"
        "- Finding 10\n"
        "- Finding 11\n"
        "- Finding 12\n"
        "- Finding 13\n"
        "- Finding 14\n"
        "- Finding 15\n"
    )
    synthesized = manager._synthesize_structured_result(text_result)
    
    assert "### Structure / Sections:" in synthesized
    assert "## Summary" in synthesized
    assert "### Key Highlights:" in synthesized
    assert "- Finding 1" in synthesized
    assert "[Full result truncated for context efficiency" in synthesized
