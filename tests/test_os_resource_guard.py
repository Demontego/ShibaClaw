import sys
import pytest
from shibaclaw.agent.os_resource_guard import OSResourceGuard

def test_os_resource_guard_check_all_no_leak():
    # Set very high limits to ensure no leak is detected
    guard = OSResourceGuard(
        max_fds=10000,
        max_sockets=10000,
        max_threads=10000,
        max_processes=10000,
        max_memory_mb=100000.0
    )
    status = guard.check_and_resolve_all_leaks()
    
    assert status["leak_detected"] is False
    assert "fd_status" in status
    assert "socket_status" in status
    assert "thread_status" in status
    assert "process_status" in status
    assert "memory_status" in status

@pytest.mark.skipif(sys.platform == "win32", reason="FD checking is unix-only")
def test_os_resource_guard_detect_leak():
    # Set a very low limit to trigger leak detection
    guard = OSResourceGuard(
        max_fds=1,
        max_sockets=50,
        max_threads=20,
        max_processes=10,
        max_memory_mb=500.0
    )
    status = guard.check_and_resolve_all_leaks()
    
    assert status["leak_detected"] is True
    assert status["fd_status"]["leak_detected"] is True
