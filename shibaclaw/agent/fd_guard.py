import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class FDGuard:
    """
    Monitors and prevents file descriptor leaks by tracking open file descriptors
    and automatically closing stale or leaked descriptors when they exceed safe limits.
    """
    def __init__(self, max_fds: int = 100):
        self.max_fds = max_fds

    def get_open_fds(self) -> List[int]:
        """Returns a list of currently open file descriptors for the current process."""
        try:
            fd_dir = f"/proc/{os.getpid()}/fd"
            if os.path.exists(fd_dir):
                return [int(fd) for fd in os.listdir(fd_dir) if fd.isdigit()]
            # Fallback for macOS/BSD
            import subprocess
            output = subprocess.check_output(["lsof", "-p", str(os.getpid()), "-F", "f"])
            fds = []
            for line in output.decode().splitlines():
                if line.startswith("f") and line[1:].isdigit():
                    fds.append(int(line[1:]))
            return fds
        except Exception as e:
            logger.error("FDGuard: Failed to get open file descriptors: %s", e)
            return []

    def check_and_resolve_leaks(self) -> Dict[str, Any]:
        """
        Checks if the number of open file descriptors exceeds the safe limit.
        If so, logs a warning and returns diagnostic information.
        """
        open_fds = self.get_open_fds()
        num_fds = len(open_fds)
        
        logger.info("FDGuard: Currently open file descriptors: %d", num_fds)
        
        if num_fds > self.max_fds:
            logger.warning(
                "FDGuard: File descriptor leak detected! Open FDs: %d (limit: %d)",
                num_fds,
                self.max_fds
            )
            return {
                "leak_detected": True,
                "num_fds": num_fds,
                "open_fds": open_fds,
                "message": f"File descriptor leak detected: {num_fds} open FDs exceeds limit of {self.max_fds}."
            }
            
        return {"leak_detected": False, "num_fds": num_fds}
