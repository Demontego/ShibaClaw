import hashlib
from pathlib import Path
import pytest
from shibaclaw.agent.context_overflow_guard import (
    ContextOverflowGuard,
    ContextOverflowError,
    CompactionCircuitBreakerError,
    tombstone_tool_result,
    enforce_schema_invariants,
)


def test_context_overflow_guard_healthy(tmp_path: Path):
    assert issubclass(CompactionCircuitBreakerError, ContextOverflowError)
    guard = ContextOverflowGuard(tmp_path, context_window_tokens=1000)
    action = guard.evaluate(500)
    assert action is None


def test_context_overflow_guard_warning(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path, context_window_tokens=1000)
    action = guard.evaluate(750)
    assert action == "warning"


def test_context_overflow_guard_critical(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path, context_window_tokens=1000)
    action = guard.evaluate(860)
    assert action == "compress"


def test_context_overflow_guard_hard_limit(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path, context_window_tokens=1000)
    with pytest.raises(ContextOverflowError):
        guard.evaluate(960)


def test_context_overflow_guard_budget_context(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path, context_window_tokens=1000)

    # Create messages that exceed the budget
    messages = [
        {"role": "system", "content": "System prompt " * 100},
        {"role": "user", "content": "Middle message 1 " * 100},
        {"role": "assistant", "content": "Middle message 2 " * 100},
        {"role": "user", "content": "Recent message 1 " * 10},
        {"role": "assistant", "content": "Recent message 2 " * 10},
        {"role": "user", "content": "Recent message 3 " * 10},
    ]

    budgeted = guard.budget_context(messages)

    assert budgeted[0] == messages[0]
    assert budgeted[-3:] == messages[-3:]
    assert len(budgeted) < len(messages)


def test_tombstone_tool_result():
    raw_content = "Detailed tool output data with 12345 tokens..."
    msg = {"role": "tool", "tool_call_id": "call_abc123", "name": "exec", "content": raw_content}

    tombstoned = tombstone_tool_result(msg)

    assert tombstoned["role"] == "tool"
    assert tombstoned["tool_call_id"] == "call_abc123"
    assert tombstoned["name"] == "exec"

    content = tombstoned["content"]
    assert "[Tombstone: tool_result pruned (" in content
    assert f"{len(raw_content)} chars -> hash=" in content
    assert "Schema invariant preserved.]" in content

    expected_hash = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()[:8]
    assert f"hash={expected_hash}" in content


def test_enforce_schema_invariants():
    messages = [
        {"role": "system", "content": "System prompt"},
        {
            "role": "assistant",
            "content": "Running tool",
            "tool_calls": [{"id": "call_1", "function": {"name": "read_file"}}],
        },
        {"role": "user", "content": "Follow up"},
    ]

    enforced = enforce_schema_invariants(messages)

    assert len(enforced) == 4
    tool_resp = enforced[2]
    assert tool_resp["role"] == "tool"
    assert tool_resp["tool_call_id"] == "call_1"
    assert "[Tombstone: tool_result pruned" in tool_resp["content"]
    assert "Schema invariant preserved.]" in tool_resp["content"]


def test_compaction_effectiveness_circuit_breaker(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path, context_window_tokens=1000, min_reduction_ratio=0.15)

    # Reduction 1000 -> 900 is 10% reduction (< 15%) when tokens >= critical_threshold -> Trips circuit breaker
    with pytest.raises(CompactionCircuitBreakerError):
        guard.evaluate_compaction_effectiveness(1000, 900)

    assert guard.is_circuit_breaker_tripped() is True

    # Reduction 1000 -> 800 is 20% reduction (>= 15%) -> Does not trip
    guard._circuit_breaker_tripped = False
    res = guard.evaluate_compaction_effectiveness(1000, 800)
    assert res["tripped"] is False
    assert res["reduction_ratio"] == pytest.approx(0.20)
    assert guard.is_circuit_breaker_tripped() is False


def test_evaluate_compaction_effectiveness_zero_tokens(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path)
    res = guard.evaluate_compaction_effectiveness(0, 0)
    assert res["tripped"] is False
    assert res["reduction_ratio"] == 0.0


def test_budget_context_tombstones_tool_result(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path, context_window_tokens=1000)

    messages = [
        {"role": "system", "content": "System prompt " * 50},
        {"role": "user", "content": "Run tool"},
        {"role": "assistant", "content": "Tool call", "tool_calls": [{"id": "call_789", "function": {"name": "exec"}}]},
        {"role": "tool", "tool_call_id": "call_789", "name": "exec", "content": "Large tool output " * 200},
        {"role": "user", "content": "Recent message 1 " * 10},
        {"role": "assistant", "content": "Recent message 2 " * 10},
        {"role": "user", "content": "Recent message 3 " * 10},
    ]

    budgeted = guard.budget_context(messages)

    assert len(budgeted) > 0
    # Search for tool message in budgeted messages
    tool_msgs = [m for m in budgeted if m.get("role") == "tool"]
    assert len(tool_msgs) >= 1
    assert "call_789" in tool_msgs[0].get("tool_call_id")


def test_enforce_schema_invariants_multiple_calls():
    messages = [
        {"role": "user", "content": "Run tools"},
        {
            "role": "assistant",
            "content": "Calling A and B",
            "tool_calls": [
                {"id": "call_a", "function": {"name": "tool_a"}},
                {"id": "call_b", "function": {"name": "tool_b"}},
            ],
        },
        {"role": "tool", "tool_call_id": "call_a", "name": "tool_a", "content": "Result A"},
    ]

    reconciled = enforce_schema_invariants(messages)
    tool_ids = [m.get("tool_call_id") for m in reconciled if m.get("role") == "tool"]
    assert "call_a" in tool_ids
    assert "call_b" in tool_ids


def test_reset_circuit_breaker(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path, context_window_tokens=1000)
    with pytest.raises(CompactionCircuitBreakerError):
        guard.evaluate_compaction_effectiveness(1000, 900)

    assert guard.is_circuit_breaker_tripped() is True
    guard.reset_circuit_breaker()
    assert guard.is_circuit_breaker_tripped() is False



def test_get_status_and_custom_min_reduction_ratio(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path, context_window_tokens=1000, min_reduction_ratio=0.20)
    status = guard.get_status()
    assert status["max_context_tokens"] == 1000
    assert status["min_reduction_ratio"] == 0.20
    assert status["circuit_breaker_tripped"] is False
    assert "artifact_register_summary" in status

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


def test_budget_preserves_chronology_of_pinned_tool_groups(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path)
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "obsolete " * 1000},
        {"role": "assistant", "content": "call a", "tool_calls": [{"id": "a"}]},
        {"role": "tool", "tool_call_id": "a", "content": "## Open\nKeep this backlog"},
        {"role": "assistant", "content": "call b", "tool_calls": [{"id": "b"}]},
        {"role": "tool", "tool_call_id": "b", "content": "recent result"},
        {"role": "assistant", "content": "done"},
        {"role": "user", "content": "continue"},
    ]

    budgeted = guard.budget_context(messages, max_tokens=100)

    assert budgeted == [messages[0], *messages[2:]]
    assert messages[1]["content"] == "obsolete " * 1000


def test_budget_tail_boundary_preserves_complete_parallel_tool_group(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path)
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "obsolete " * 1000},
        {"role": "assistant", "content": "call both", "tool_calls": [{"id": "a"}, {"id": "b"}]},
        {"role": "tool", "tool_call_id": "a", "content": "result a"},
        {"role": "tool", "tool_call_id": "b", "content": "result b"},
        {"role": "assistant", "content": "done"},
        {"role": "user", "content": "continue"},
    ]

    budgeted = guard.budget_context(messages, max_tokens=20)

    assert budgeted == [messages[0], *messages[2:]]


def test_budget_prunes_expensive_tool_group_without_orphaning_results(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path)
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "assistant", "content": "old reasoning " * 1000, "tool_calls": [{"id": "a"}]},
        {"role": "tool", "tool_call_id": "a", "content": "result a"},
        {"role": "user", "content": "recent"},
        {"role": "assistant", "content": "done"},
        {"role": "user", "content": "continue"},
    ]

    budgeted = guard.budget_context(messages, max_tokens=20)

    assert budgeted == [messages[0], *messages[-3:]]


def test_budget_short_history_does_not_duplicate_system_prompt(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path)
    messages = [
        {"role": "system", "content": "system " * 100},
        {"role": "user", "content": "continue"},
    ]

    assert guard.budget_context(messages, max_tokens=10) == messages


def test_context_window_recovery(tmp_path: Path):
    from shibaclaw.agent.context_overflow_guard import ContextWindowRecovery
    guard = ContextOverflowGuard(tmp_path, context_window_tokens=1000)
    recovery = ContextWindowRecovery(guard)
    messages = [
        {"role": "system", "content": "System prompt " * 100},
        {"role": "user", "content": "Middle message 1 " * 100},
        {"role": "assistant", "content": "Middle message 2 " * 100},
        {"role": "user", "content": "Recent message 1 " * 10},
        {"role": "assistant", "content": "Recent message 2 " * 10},
        {"role": "user", "content": "Recent message 3 " * 10},
    ]
    recovered = recovery.recover_context(messages, max_tokens=500)
    assert recovered[0] == messages[0]
    assert recovered[-3:] == messages[-3:]
    assert len(recovered) == 5
    assert recovered[1]["role"] == "system"
    assert "[Context Window Recovery]" in recovered[1]["content"]

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


def test_observation_masking_user_role_case_insensitive(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path, context_window_tokens=2000)

    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Run tool"},
        {"role": "assistant", "content": "Executing tool 1", "tool_calls": [{"id": "call_1"}]},
        {"role": "user", "name": "exec", "content": "[tool result] stdout output from older tool run"},
        {"role": "assistant", "content": "Finished turn 1"},
        {"role": "user", "content": "Run tool 2"},
        {"role": "assistant", "content": "Executing tool 2", "tool_calls": [{"id": "call_2"}]},
        {"role": "user", "name": "exec", "content": "[Tool Result] stdout output from recent tool run"},
        {"role": "assistant", "content": "Finished turn 2"},
    ]

    masked = guard.mask_observations(messages, keep_recent_turns=1)
    assert "[Tool result masked: output from 'exec' pruned" in masked[3]["content"]
    assert "[Tool Result] stdout output from recent tool run" in masked[7]["content"]


def test_observation_masking_structured_user_content_and_fallback(tmp_path: Path):
    guard = ContextOverflowGuard(tmp_path, context_window_tokens=2000)

    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Run tool"},
        {"role": "assistant", "content": "Executing tool 1", "tool_calls": [{"id": "call_1"}]},
        {"role": "user", "tool_name": "fetch_data", "content": [{"type": "text", "text": "[tool result] stdout from old tool"}]},
        {"role": "assistant", "content": "Finished turn 1"},
        {"role": "user", "content": "Run tool 2"},
        {"role": "assistant", "content": "Executing tool 2", "tool_calls": [{"id": "call_2"}]},
        {"role": "tool", "name": "exec", "tool_call_id": "call_2", "content": "Recent output"},
        {"role": "assistant", "content": "Finished turn 2"},
    ]

    masked = guard.mask_observations(messages, keep_recent_turns=1)
    assert "[Tool result masked: output from 'fetch_data' pruned" in masked[3]["content"]
    assert masked[7]["content"] == "Recent output"

