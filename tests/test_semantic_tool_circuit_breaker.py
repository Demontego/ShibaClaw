from shibaclaw.agent.semantic_tool_circuit_breaker import SemanticToolCircuitBreaker

def test_semantic_tool_circuit_breaker_trips(tmp_path):
    breaker = SemanticToolCircuitBreaker(tmp_path)
    
    tool_name = "read_file"
    arguments = {"path": "test.txt"}
    result = "hello world"
    
    # First call
    assert not breaker.record_call(tool_name, arguments, result)
    # Second call
    assert not breaker.record_call(tool_name, arguments, result)
    # Third call - should trip!
    assert breaker.record_call(tool_name, arguments, result)
    
    # Check tripped message
    msg = breaker.get_tripped_message(tool_name)
    assert "BreakerTripped" in msg
    assert "read_file" in msg
    assert msg.startswith("[CircuitBreaker: Tool execution stalled")
    assert breaker.is_tripped(tool_name, arguments, result)
    assert breaker.get_call_count(tool_name, arguments, result) == 3
    assert breaker.should_block(tool_name, arguments)
    assert breaker.record_call(tool_name, arguments, result)
    assert breaker.get_call_count(tool_name, arguments, result) == 4
    breaker.reset()
    assert breaker.get_call_count(tool_name, arguments, result) == 0
    assert not breaker.should_block(tool_name, arguments)

def test_semantic_tool_circuit_breaker_no_trip_different_args(tmp_path):
    breaker = SemanticToolCircuitBreaker(tmp_path)
    
    tool_name = "read_file"
    result = "hello world"
    
    # Call with different arguments
    assert not breaker.record_call(tool_name, {"path": "test1.txt"}, result)
    assert not breaker.record_call(tool_name, {"path": "test2.txt"}, result)
    assert not breaker.record_call(tool_name, {"path": "test1.txt"}, result)
    assert not breaker.record_call(tool_name, {"path": "test2.txt"}, result)

def test_semantic_tool_circuit_breaker_no_trip_different_results(tmp_path):
    breaker = SemanticToolCircuitBreaker(tmp_path)
    
    tool_name = "read_file"
    arguments = {"path": "test.txt"}
    
    # Call with different results (e.g. polling status)
    assert not breaker.record_call(tool_name, arguments, "status: pending")
    assert not breaker.record_call(tool_name, arguments, "status: running")
    assert not breaker.record_call(tool_name, arguments, "status: completed")

def test_breaker_requires_consecutive_identical_results(tmp_path):
    breaker = SemanticToolCircuitBreaker(tmp_path)
    args = {"path": "test.txt"}
    assert not breaker.record_call("read_file", args, "same")
    assert not breaker.record_call("read_file", args, "same")
    assert not breaker.record_call("read_file", args, "changed")
    assert not breaker.record_call("read_file", args, "same")
    assert not breaker.should_block("read_file", args)
    assert breaker.get_call_count("read_file", args, "same") == 1


def test_breaker_allows_pivot_after_different_completed_call(tmp_path):
    breaker = SemanticToolCircuitBreaker(tmp_path)
    args = {"path": "test.txt"}
    for _ in range(3):
        breaker.record_call("read_file", args, "unchanged")
    assert breaker.should_block("read_file", args)
    assert not breaker.record_call("list_dir", {"path": "."}, "other output")
    assert not breaker.should_block("read_file", args)
    assert not breaker.record_call("read_file", args, "unchanged")


def test_breaker_feedback_does_not_reset_stalled_trace(tmp_path):
    breaker = SemanticToolCircuitBreaker(tmp_path)
    args = {"path": "test.txt"}
    for _ in range(3):
        breaker.record_call("read_file", args, "unchanged")
    assert breaker.record_call("read_file", args, breaker.get_tripped_message("read_file"))
    assert breaker.should_block("read_file", args)


def test_semantic_tool_circuit_breaker_logs_to_learnings(tmp_path):
    breaker = SemanticToolCircuitBreaker(tmp_path)
    
    tool_name = "read_file"
    arguments = {"path": "test.txt"}
    result = "hello world"
    
    # Trip the breaker
    breaker.record_call(tool_name, arguments, result)
    breaker.record_call(tool_name, arguments, result)
    breaker.record_call(tool_name, arguments, result)
    
    learnings_file = tmp_path / "memory" / "learnings.md"
    assert learnings_file.is_file()
    content = learnings_file.read_text(encoding="utf-8")
    assert "Semantic Tool Circuit Breaker Tripped" in content
    assert "read_file" in content
