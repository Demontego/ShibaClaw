import threading
from shibaclaw.agent.thread_guard import ThreadGuard

def test_thread_guard_get_active_threads():
    guard = ThreadGuard()
    threads = guard.get_active_threads()
    assert isinstance(threads, list)
    assert len(threads) > 0
    assert threading.current_thread().name in threads

def test_thread_guard_detect_leak():
    # Set a very low limit to trigger leak detection
    guard = ThreadGuard(max_threads=0)
    status = guard.check_and_resolve_leaks()
    
    assert status["leak_detected"] is True
    assert status["num_threads"] >= 1
    assert "leak_detected" in status
    assert "active_threads" in status

def test_thread_guard_no_leak():
    # Set a very high limit to ensure no leak is detected
    guard = ThreadGuard(max_threads=10000)
    status = guard.check_and_resolve_leaks()
    
    assert status["leak_detected"] is False
