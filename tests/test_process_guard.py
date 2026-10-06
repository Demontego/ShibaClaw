import subprocess
import sys
import time
from shibaclaw.agent.process_guard import ProcessGuard

def test_process_guard_get_child_pids():
    guard = ProcessGuard()
    pids = guard.get_child_pids()
    assert isinstance(pids, list)

def test_process_guard_detect_leak():
    guard = ProcessGuard(max_processes=0)
    
    # Spawn a dummy child process portably
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
    try:
        # Give it a tiny bit of time to start
        time.sleep(0.1)
        status = guard.check_and_resolve_leaks()
        
        assert status["leak_detected"] is True
        assert status["num_processes"] >= 1
        assert "leak_detected" in status
        assert "child_pids" in status
    finally:
        proc.terminate()
        proc.wait()

def test_process_guard_no_leak():
    # Set a very high limit to ensure no leak is detected
    guard = ProcessGuard(max_processes=10000)
    status = guard.check_and_resolve_leaks()
    
    assert status["leak_detected"] is False
