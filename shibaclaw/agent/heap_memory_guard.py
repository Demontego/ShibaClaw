import ctypes
import gc
import logging
import sys
from typing import Any, Dict

try:
    import resource
except ImportError:
    resource = None

logger = logging.getLogger(__name__)


class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _windows_rss_mb() -> float:
    counters = _ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    get_info = ctypes.windll.psapi.GetProcessMemoryInfo
    get_info.argtypes = [ctypes.c_void_p, ctypes.POINTER(_ProcessMemoryCounters), ctypes.c_ulong]
    get_info.restype = ctypes.c_int
    if not get_info(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        return 0.0
    return counters.WorkingSetSize / (1024.0 * 1024.0)

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
            if sys.platform == "win32":
                return _windows_rss_mb()
            if resource is None:
                return 0.0
            usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            if sys.platform == "darwin":
                return usage / (1024.0 * 1024.0)
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
