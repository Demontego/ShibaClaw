from shibaclaw.agent.fd_guard import FDGuard

def test_fd_guard_get_open_fds():
    guard = FDGuard()
    fds = guard.get_open_fds()
    assert isinstance(fds, list)
    assert len(fds) > 0

def test_fd_guard_detect_leak():
    # Set a very low limit to trigger leak detection
    guard = FDGuard(max_fds=1)
    status = guard.check_and_resolve_leaks()
    
    assert status["leak_detected"] is True
    assert status["num_fds"] > 1
    assert "leak_detected" in status
    assert "open_fds" in status

def test_fd_guard_no_leak():
    # Set a very high limit to ensure no leak is detected
    guard = FDGuard(max_fds=10000)
    status = guard.check_and_resolve_leaks()
    
    assert status["leak_detected"] is False
