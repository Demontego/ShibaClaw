from shibaclaw.agent.heap_memory_guard import HeapMemoryGuard

def test_memory_guard_get_memory_usage():
    guard = HeapMemoryGuard()
    usage = guard.get_memory_usage_mb()
    assert isinstance(usage, float)
    assert usage >= 0.0

def test_memory_guard_detect_leak():
    # Set a very low limit to trigger leak detection
    guard = HeapMemoryGuard(max_memory_mb=0.01)
    status = guard.check_and_resolve_leaks()
    
    assert status["leak_detected"] is True
    assert status["old_memory_mb"] > 0.01
    assert "leak_detected" in status
    assert "new_memory_mb" in status

def test_memory_guard_no_leak():
    # Set a very high limit to ensure no leak is detected
    guard = HeapMemoryGuard(max_memory_mb=100000.0)
    status = guard.check_and_resolve_leaks()
    
    assert status["leak_detected"] is False
