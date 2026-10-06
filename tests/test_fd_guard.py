import sys
import pytest
from shibaclaw.agent.fd_guard import FDGuard

@pytest.mark.skipif(sys.platform == "win32", reason="File descriptors via /proc are unix-only")
def test_fd_guard_get_open_fds():
    guard = FDGuard()
    fds = guard.get_open_fds()
    assert isinstance(fds, list)
    assert len(fds) > 0

@pytest.mark.skipif(sys.platform == "win32", reason="File descriptors via /proc are unix-only")
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

def test_fd_guard_get_open_sockets():
    guard = FDGuard()
    sockets = guard.get_open_sockets()
    assert isinstance(sockets, list)

def test_fd_guard_detect_socket_leak():
    guard = FDGuard()
    # Set a very low limit to trigger socket leak detection
    status = guard.check_and_resolve_socket_leaks(max_sockets=-1)
    
    assert status["leak_detected"] is True
    assert "open_sockets" in status

def test_fd_guard_get_active_connections():
    guard = FDGuard()
    connections = guard.get_active_connections()
    assert isinstance(connections, list)

def test_fd_guard_detect_connection_leak():
    guard = FDGuard()
    # Set a very low limit to trigger connection leak detection
    status = guard.check_and_resolve_connection_leaks(max_connections=-1)
    
    assert status["leak_detected"] is True
    assert "active_connections" in status


