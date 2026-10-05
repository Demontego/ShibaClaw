from pathlib import Path
import pytest
from shibaclaw.agent.context_overflow_guard import ContextOverflowGuard, ContextOverflowError

def test_context_overflow_guard_healthy(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path, context_window_tokens=1000)
    action = guard.check_usage(500)
    assert action is None

def test_context_overflow_guard_warning(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path, context_window_tokens=1000)
    action = guard.check_usage(750)
    assert action == "warning"

def test_context_overflow_guard_critical(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path, context_window_tokens=1000)
    action = guard.check_usage(860)
    assert action == "compress"

def test_context_overflow_guard_hard_limit(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path, context_window_tokens=1000)
    with pytest.raises(ContextOverflowError):
        guard.check_usage(960)

def test_context_overflow_guard_budget_context(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path, context_window_tokens=1000)
    
    # Create messages that exceed the budget (critical threshold is 850 tokens, which is 3400 characters)
    messages = [
        {"role": "system", "content": "System prompt " * 100}, # 1400 chars
        {"role": "user", "content": "Middle message 1 " * 100}, # 1700 chars
        {"role": "assistant", "content": "Middle message 2 " * 100}, # 1700 chars
        {"role": "user", "content": "Recent message 1 " * 10}, # 170 chars
        {"role": "assistant", "content": "Recent message 2 " * 10}, # 170 chars
        {"role": "user", "content": "Recent message 3 " * 10}, # 170 chars
    ]
    
    budgeted = guard.budget_context(messages)
    
    # System prompt and recent messages must be kept
    assert budgeted[0] == messages[0]
    assert budgeted[-3:] == messages[-3:]
    # At least one middle message should be pruned to fit the budget
    assert len(budgeted) < len(messages)
