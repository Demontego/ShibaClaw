import os
import logging
import subprocess
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class ProcessGuard:
    """
    Monitors and prevents process leaks by tracking active child processes
    and automatically terminating stale or leaked processes when they exceed safe limits.
    """
    def __init__(self, max_processes: int = 10):
        self.max_processes = max_processes

    def get_child_pids(self) -> List[int]:
        """Returns a list of PIDs of currently active child processes."""
        try:
            pid = os.getpid()
            output = subprocess.check_output(["pgrep", "-P", str(pid)])
            return [int(p) for p in output.decode().splitlines() if p.isdigit()]
        except Exception:
            try:
                pid = os.getpid()
                output = subprocess.check_output(["ps", "-o", "pid", "--ppid", str(pid)])
                return [int(p) for p in output.decode().splitlines()[1:] if p.strip().isdigit()]
            except Exception as e:
                logger.error("ProcessGuard: Failed to get child processes: %s", e)
                return []

    def check_and_resolve_leaks(self) -> Dict[str, Any]:
        """
        Checks if the number of active child processes exceeds the safe limit.
        If so, logs a warning and returns diagnostic information.
        """
        child_pids = self.get_child_pids()
        num_processes = len(child_pids)
        
        logger.info("ProcessGuard: Currently active child processes: %d", num_processes)
        
        if num_processes > self.max_processes:
            logger.warning(
                "ProcessGuard: Process leak detected! Active child processes: %d (limit: %d)",
                num_processes,
                self.max_processes
            )
            return {
                "leak_detected": True,
                "num_processes": num_processes,
                "child_pids": child_pids,
                "message": f"Process leak detected: {num_processes} active child processes exceeds limit of {self.max_processes}."
            }
            
        return {"leak_detected": False, "num_processes": num_processes}
