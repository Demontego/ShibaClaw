import pytest
from pathlib import Path
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
