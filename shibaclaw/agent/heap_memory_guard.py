import gc
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class HeapMemoryGuard:
    """
    Monitors and prevents heap memory leaks by tracking process memory usage
    and automatically triggering garbage collection when it exceeds safe limits.
    """
    def __init__(self, max_memory_mb: float = 500.0):
        self.max_memory_mb = max_memory_mb

    def get_memory_usage_mb(self) -> float:
        """Returns the current memory usage of the process in megabytes."""
        try:
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            import sys
            if sys.platform == "darwin":
                return usage / (1024.0 * 1024.0)
            else:
                return usage / 1024.0
        except Exception as e:
            logger.error("HeapMemoryGuard: Failed to get memory usage: %s", e)
            return 0.0

    def check_and_resolve_leaks(self) -> Dict[str, Any]:
        """
        Checks if the memory usage exceeds the safe limit.
        If so, triggers garbage collection and logs a warning.
        """
        memory_mb = self.get_memory_usage_mb()
        logger.info("HeapMemoryGuard: Current memory usage: %.2f MB", memory_mb)
        
        if memory_mb > self.max_memory_mb:
            logger.warning(
                "HeapMemoryGuard: Heap memory leak detected! Memory: %.2f MB (limit: %.2f MB)",
                memory_mb,
                self.max_memory_mb
            )
            gc.collect()
            new_memory_mb = self.get_memory_usage_mb()
            logger.info("HeapMemoryGuard: Memory usage after garbage collection: %.2f MB", new_memory_mb)
            
            return {
                "leak_detected": True,
                "old_memory_mb": memory_mb,
                "new_memory_mb": new_memory_mb,
                "message": f"Heap memory leak detected: {memory_mb:.2f} MB exceeds limit of {self.max_memory_mb:.2f} MB. Garbage collection triggered."
            }
            
        return {"leak_detected": False, "memory_mb": memory_mb}
