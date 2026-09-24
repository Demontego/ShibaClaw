import pytest
from pathlib import Path
from unittest.mock import MagicMock
from shibaclaw.agent.context_overflow_guard import ContextOverflowGuard, ContextOverflowError

def test_context_overflow_guard_under_limit(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path, context_window_tokens=1000)
    
    # 500 tokens is 50% (under warning threshold of 70%)
    action = guard.check_usage(500)
    assert action is None

def test_context_overflow_guard_warning(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path, context_window_tokens=1000)
    
    # 750 tokens is 75% (exceeds warning threshold of 70%)
    action = guard.check_usage(750)
    assert action == "warning"
    
    # Verify learning was logged
    learnings_file = tmp_path / "memory" / "learnings.md"
    assert learnings_file.is_file()
    assert "Warning Threshold Exceeded" in learnings_file.read_text(encoding="utf-8")

def test_context_overflow_guard_critical(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path, context_window_tokens=1000)
    
    # 880 tokens is 88% (exceeds critical threshold of 85%)
    action = guard.check_usage(880)
    assert action == "compress"
    
    # Verify learning was logged
    learnings_file = tmp_path / "memory" / "learnings.md"
    assert learnings_file.is_file()
    assert "Critical Threshold Exceeded" in learnings_file.read_text(encoding="utf-8")

def test_context_overflow_guard_hard_limit(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path, context_window_tokens=1000)
    checkpoint_mgr = MagicMock()
    
    # 960 tokens is 96% (exceeds hard limit threshold of 95%)
    with pytest.raises(ContextOverflowError):
        guard.check_usage(960, checkpoint_mgr=checkpoint_mgr, session_key="test_session")
        
    # Verify checkpoint was saved
    checkpoint_mgr.save_checkpoint.assert_called_once_with(
        "test_session",
        {"token_usage": 960, "status": "overflow_checkpoint"}
    )
    
    # Verify learning was logged
    learnings_file = tmp_path / "memory" / "learnings.md"
    assert learnings_file.is_file()
    assert "Hard Limit Exceeded" in learnings_file.read_text(encoding="utf-8")
