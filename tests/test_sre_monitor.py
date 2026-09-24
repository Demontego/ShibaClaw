from shibaclaw.agent.sre_monitor import SREMonitor

def test_sre_monitor_healthy_by_default():
    monitor = SREMonitor()
    status = monitor.get_status()
    assert status["healthy"] is True
    assert status["liveness"] == "OK"
    assert status["progress"] == "OK"
    assert status["quality"] == "OK"

def test_sre_monitor_liveness_failure_repeating_responses():
    monitor = SREMonitor(max_consecutive_repeats=3)
    
    # Add 3 identical responses
    monitor.add_response("Hello")
    monitor.add_response("Hello")
    monitor.add_response("Hello")
    
    status = monitor.get_status()
    assert status["healthy"] is False
    assert status["liveness"] == "FAIL"

def test_sre_monitor_liveness_failure_repeating_tools():
    monitor = SREMonitor()
    
    # Add 3 identical tool sequences
    monitor.add_tool_sequence(["web_search", "web_fetch"])
    monitor.add_tool_sequence(["web_search", "web_fetch"])
    monitor.add_tool_sequence(["web_search", "web_fetch"])
    
    status = monitor.get_status()
    assert status["healthy"] is False
    assert status["liveness"] == "FAIL"

def test_sre_monitor_progress_failure_stalled_metric():
    monitor = SREMonitor(progress_threshold=0.01)
    
    # Add 3 flat progress metrics
    monitor.add_progress_metric(5.0)
    monitor.add_progress_metric(5.0)
    monitor.add_progress_metric(5.0)
    
    status = monitor.get_status()
    assert status["healthy"] is False
    assert status["progress"] == "FAIL"

def test_sre_monitor_quality_failure_short_response():
    monitor = SREMonitor()
    
    # Add extremely short response
    monitor.add_response("Hi")
    
    status = monitor.get_status()
    assert status["healthy"] is False
    assert status["quality"] == "FAIL"

def test_sre_monitor_quality_failure_high_error_density():
    monitor = SREMonitor()
    
    # Add response with high density of error patterns
    monitor.add_response("Error: error: error: error:")
    
    status = monitor.get_status()
    assert status["healthy"] is False
    assert status["quality"] == "FAIL"
