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


def test_observation_masking_prunes_old_tool_results(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path, context_window_tokens=2000)

    # 4 assistant turns with tool results
    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Run tool 1"},
        {"role": "assistant", "content": "Executing tool 1", "tool_calls": [{"id": "call_1"}]},
        {"role": "tool", "name": "exec", "tool_call_id": "call_1", "content": "Tool 1 raw result output " * 50},
        {"role": "assistant", "content": "Finished turn 1"},
        {"role": "user", "content": "Run tool 2"},
        {"role": "assistant", "content": "Executing tool 2", "tool_calls": [{"id": "call_2"}]},
        {"role": "tool", "name": "read_file", "tool_call_id": "call_2", "content": "Tool 2 raw result output " * 50},
        {"role": "assistant", "content": "Finished turn 2"},
        {"role": "user", "content": "Run tool 3"},
        {"role": "assistant", "content": "Executing tool 3", "tool_calls": [{"id": "call_3"}]},
        {"role": "tool", "name": "web_search", "tool_call_id": "call_3", "content": "Tool 3 raw result output " * 50},
        {"role": "assistant", "content": "Finished turn 3"},
        {"role": "user", "content": "Run tool 4"},
        {"role": "assistant", "content": "Executing tool 4", "tool_calls": [{"id": "call_4"}]},
        {"role": "tool", "name": "web_fetch", "tool_call_id": "call_4", "content": "Tool 4 raw result output " * 50},
        {"role": "assistant", "content": "Finished turn 4"},
    ]

    masked = guard.mask_observations(messages, keep_recent_turns=2)

    # Tool 1 and Tool 2 outputs (older than last 2 assistant turns) should be masked
    assert "[Tool result masked: output from 'exec' pruned" in masked[3]["content"]
    assert "[Tool result masked: output from 'read_file' pruned" in masked[7]["content"]

    # Tool 3 and Tool 4 outputs (within last 2 assistant turns) should be preserved
    assert "Tool 3 raw result output" in masked[11]["content"]
    assert "Tool 4 raw result output" in masked[15]["content"]

    # Assistant thoughts/messages are preserved
    assert masked[2]["content"] == "Executing tool 1"
    assert masked[4]["content"] == "Finished turn 1"


def test_observation_masking_handles_complex_content(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path, context_window_tokens=2000)

    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Run tool"},
        {"role": "assistant", "content": "Executing tool 1", "tool_calls": [{"id": "call_1"}]},
        {"role": "tool", "name": "custom_tool", "tool_call_id": "call_1", "content": [{"type": "text", "text": "Structured output"}]},
        {"role": "assistant", "content": "Finished turn 1"},
        {"role": "user", "content": "Run tool 2"},
        {"role": "assistant", "content": "Executing tool 2", "tool_calls": [{"id": "call_2"}]},
        {"role": "tool", "name": "exec", "tool_call_id": "call_2", "content": "Recent output"},
        {"role": "assistant", "content": "Finished turn 2"},
    ]

    masked = guard.mask_observations(messages, keep_recent_turns=1)
    assert "[Tool result masked: output from 'custom_tool' pruned" in masked[3]["content"]
    assert masked[7]["content"] == "Recent output"
