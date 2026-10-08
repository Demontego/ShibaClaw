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


def test_budget_keeps_tool_call_with_result(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path, context_window_tokens=100)
    messages = [
        {"role": "system", "content": "sys"},
        {
            "role": "assistant",
            "tool_calls": [{"id": "call-1", "type": "function"}],
            "content": "x" * 500,
        },
        {"role": "tool", "tool_call_id": "call-1", "content": "y" * 500},
        {"role": "user", "content": "latest"},
    ]
    budgeted = guard.budget_context(messages, max_tokens=20)
    roles = [(m.get("role"), m.get("tool_call_id")) for m in budgeted]
    if any(m.get("tool_calls") for m in budgeted):
        assert ("tool", "call-1") in roles

def test_context_window_recovery(tmp_path: Path):
    from shibaclaw.agent.context_overflow_guard import ContextWindowRecovery
    guard = ContextOverflowGuard(tmp_path, context_window_tokens=1000)
    recovery = ContextWindowRecovery(guard)
    
    messages = [
        {"role": "system", "content": "System prompt " * 100}, # 1400 chars
        {"role": "user", "content": "Middle message 1 " * 100}, # 1700 chars
        {"role": "assistant", "content": "Middle message 2 " * 100}, # 1700 chars
        {"role": "user", "content": "Recent message 1 " * 10}, # 170 chars
        {"role": "assistant", "content": "Recent message 2 " * 10}, # 170 chars
        {"role": "user", "content": "Recent message 3 " * 10}, # 170 chars
    ]
    
    recovered = recovery.recover_context(messages, max_tokens=500)
    
    # System prompt and recent messages must be kept
    assert recovered[0] == messages[0]
    assert recovered[-3:] == messages[-3:]
    # Middle messages must be replaced by a single summary message
    assert len(recovered) == 5
    assert recovered[1]["role"] == "system"
    assert "[Context Window Recovery]" in recovered[1]["content"]

