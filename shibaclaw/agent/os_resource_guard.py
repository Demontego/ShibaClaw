import logging
from typing import Dict, Any
from shibaclaw.agent.fd_guard import FDGuard
from shibaclaw.agent.thread_guard import ThreadGuard
from shibaclaw.agent.process_guard import ProcessGuard
from shibaclaw.agent.heap_memory_guard import HeapMemoryGuard

logger = logging.getLogger(__name__)

class OSResourceGuard:
    """
    A unified coordinator that monitors and prevents all types of OS resource leaks
    (file descriptors, sockets, threads, child processes, and heap memory)
    by running individual specialized guards and aggregating their diagnostics.
    """
    def __init__(self, max_fds: int = 100, max_sockets: int = 50, max_threads: int = 20, max_processes: int = 10, max_memory_mb: float = 500.0):
        self.fd_guard = FDGuard(max_fds=max_fds)
        self.thread_guard = ThreadGuard(max_threads=max_threads)
        self.process_guard = ProcessGuard(max_processes=max_processes)
        self.heap_memory_guard = HeapMemoryGuard(max_memory_mb=max_memory_mb)
        self.max_sockets = max_sockets

    def check_and_resolve_all_leaks(self) -> Dict[str, Any]:
        """
        Runs all individual OS resource guards and aggregates their diagnostic results.
        """
        fd_status = self.fd_guard.check_and_resolve_leaks()
        socket_status = self.fd_guard.check_and_resolve_socket_leaks(max_sockets=self.max_sockets)
        thread_status = self.thread_guard.check_and_resolve_leaks()
        process_status = self.process_guard.check_and_resolve_leaks()
        memory_status = self.heap_memory_guard.check_and_resolve_leaks()

        leak_detected = (
            fd_status.get("leak_detected", False) or
            socket_status.get("leak_detected", False) or
            thread_status.get("leak_detected", False) or
            process_status.get("leak_detected", False) or
            memory_status.get("leak_detected", False)
        )

        report = {
            "leak_detected": leak_detected,
            "fd_status": fd_status,
            "socket_status": socket_status,
            "thread_status": thread_status,
            "process_status": process_status,
            "memory_status": memory_status,
        }

        if leak_detected:
            logger.warning("OSResourceGuard: OS resource leak detected! Report: %s", report)
        else:
            logger.info("OSResourceGuard: All OS resources are within safe limits.")

        return report
