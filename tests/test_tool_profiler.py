from shibaclaw.agent.tool_profiler import ToolProfiler

def test_tool_profiler_records_execution(tmp_path):
    profiler = ToolProfiler(tmp_path, slow_threshold_seconds=2.0)
    
    tool_name = "read_file"
    
    # Record fast execution
    profiler.record_execution(tool_name, 0.5)
    assert len(profiler.execution_times[tool_name]) == 1
    assert profiler.execution_times[tool_name][0] == 0.5
    
    # Record another fast execution
    profiler.record_execution(tool_name, 1.5)
    assert len(profiler.execution_times[tool_name]) == 2
    assert sum(profiler.execution_times[tool_name]) / 2 == 1.0
    
    # Verify learnings.md was NOT created (no slow executions yet)
    learnings_file = tmp_path / "memory" / "learnings.md"
    assert not learnings_file.is_file()

def test_tool_profiler_logs_slow_execution(tmp_path):
    profiler = ToolProfiler(tmp_path, slow_threshold_seconds=2.0)
    
    tool_name = "web_search"
    
    # Record slow execution
    profiler.record_execution(tool_name, 2.5)
    
    # Verify learnings.md was created and contains the slow execution log
    learnings_file = tmp_path / "memory" / "learnings.md"
    assert learnings_file.is_file()
    content = learnings_file.read_text(encoding="utf-8")
    assert "Slow Tool Execution" in content
    assert "web_search" in content
    assert "2.50s" in content
