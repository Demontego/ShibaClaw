import ctypes
import logging
import os
import subprocess
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_TH32CS_SNAPPROCESS = 0x00000002


class _ProcessEntry32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_ulong),
        ("cntUsage", ctypes.c_ulong),
        ("th32ProcessID", ctypes.c_ulong),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", ctypes.c_ulong),
        ("cntThreads", ctypes.c_ulong),
        ("th32ParentProcessID", ctypes.c_ulong),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", ctypes.c_ulong),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def _windows_child_pids() -> list[int]:
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateToolhelp32Snapshot.argtypes = [ctypes.c_ulong, ctypes.c_ulong]
    kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    kernel32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_ProcessEntry32W)]
    kernel32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_ProcessEntry32W)]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    snapshot = kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == ctypes.c_void_p(-1).value:
        return []
    try:
        entry = _ProcessEntry32W()
        entry.dwSize = ctypes.sizeof(entry)
        parent = os.getpid()
        pids: list[int] = []
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            if entry.th32ParentProcessID == parent:
                pids.append(int(entry.th32ProcessID))
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
        return pids
    finally:
        kernel32.CloseHandle(snapshot)

class ProcessGuard:
    """
    Monitors and prevents process leaks by tracking active child processes
    and automatically terminating stale or leaked processes when they exceed safe limits.
    """
    def __init__(self, max_processes: int = 10):
        self.max_processes = max_processes

    def get_child_pids(self) -> List[int]:
        """Returns a list of PIDs of currently active child processes."""
        if os.name == "nt":
            try:
                return _windows_child_pids()
            except Exception as e:
                logger.error("ProcessGuard: Failed to get child processes: %s", e)
                return []
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
