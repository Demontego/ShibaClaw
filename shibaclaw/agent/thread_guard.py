import threading
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class ThreadGuard:
    """
    Monitors and prevents thread leaks by tracking active threads
    and logging warnings when they exceed safe limits.
    """
    def __init__(self, max_threads: int = 20):
        self.max_threads = max_threads

    def get_active_threads(self) -> List[str]:
        """Returns a list of names of currently active threads."""
        return [t.name for t in threading.enumerate()]

    def check_and_resolve_leaks(self) -> Dict[str, Any]:
        """
        Checks if the number of active threads exceeds the safe limit.
        If so, logs a warning and returns diagnostic information.
        """
        active_threads = self.get_active_threads()
        num_threads = len(active_threads)
        
        logger.info("ThreadGuard: Currently active threads: %d", num_threads)
        
        if num_threads > self.max_threads:
            logger.warning(
                "ThreadGuard: Thread leak detected! Active threads: %d (limit: %d)",
                num_threads,
                self.max_threads
            )
            return {
                "leak_detected": True,
                "num_threads": num_threads,
                "active_threads": active_threads,
                "message": f"Thread leak detected: {num_threads} active threads exceeds limit of {self.max_threads}."
            }
            
        return {"leak_detected": False, "num_threads": num_threads}
