import logging
import os
from typing import Any, Dict, List

try:
    import msvcrt
except ImportError:
    msvcrt = None

logger = logging.getLogger(__name__)

_CRT_FD_SCAN = 512


def _windows_open_fds() -> list[int]:
    if msvcrt is None:
        return []
    fds: list[int] = []
    for fd in range(_CRT_FD_SCAN):
        try:
            msvcrt.get_osfhandle(fd)
        except OSError:
            continue
        fds.append(fd)
    return fds

class FDGuard:
    """
    Monitors and prevents file descriptor leaks by tracking open file descriptors
    and automatically closing stale or leaked descriptors when they exceed safe limits.
    """
    def __init__(self, max_fds: int = 100):
        self.max_fds = max_fds

    def get_open_fds(self) -> List[int]:
        """Returns a list of currently open file descriptors for the current process."""
        if os.name == "nt":
            return _windows_open_fds()
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

    def get_open_sockets(self) -> List[int]:
        """Returns a list of currently open socket file descriptors for the current process."""
        sockets = []
        try:
            fd_dir = f"/proc/{os.getpid()}/fd"
            if os.path.exists(fd_dir):
                for fd in os.listdir(fd_dir):
                    if fd.isdigit():
                        try:
                            link = os.readlink(os.path.join(fd_dir, fd))
                            if link.startswith("socket:"):
                                sockets.append(int(fd))
                        except Exception:
                            continue
            else:
                # Fallback for macOS/BSD using lsof
                import subprocess
                output = subprocess.check_output(["lsof", "-p", str(os.getpid()), "-i", "-F", "f"])
                for line in output.decode().splitlines():
                    if line.startswith("f") and line[1:].isdigit():
                        sockets.append(int(line[1:]))
        except Exception as e:
            logger.error("FDGuard: Failed to get open sockets: %s", e)
        return sockets

    def check_and_resolve_socket_leaks(self, max_sockets: int = 50) -> Dict[str, Any]:
        """
        Checks if the number of open sockets exceeds the safe limit.
        If so, logs a warning and returns diagnostic information.
        """
        open_sockets = self.get_open_sockets()
        num_sockets = len(open_sockets)
        
        logger.info("FDGuard: Currently open sockets: %d", num_sockets)
        
        if num_sockets > max_sockets:
            logger.warning(
                "FDGuard: Socket leak detected! Open sockets: %d (limit: %d)",
                num_sockets,
                max_sockets
            )
            return {
                "leak_detected": True,
                "num_sockets": num_sockets,
                "open_sockets": open_sockets,
                "message": f"Socket leak detected: {num_sockets} open sockets exceeds limit of {max_sockets}."
            }
            
        return {"leak_detected": False, "num_sockets": num_sockets}

    def get_active_connections(self) -> List[int]:
        """Returns a list of currently active network connection file descriptors for the current process."""
        connections = []
        try:
            import socket
            for fd in self.get_open_sockets():
                try:
                    s = socket.fromfd(fd, socket.AF_INET, socket.SOCK_STREAM)
                    s.getpeername()
                    connections.append(fd)
                except Exception:
                    try:
                        s = socket.fromfd(fd, socket.AF_INET, socket.SOCK_DGRAM)
                        s.getpeername()
                        connections.append(fd)
                    except Exception:
                        continue
        except Exception as e:
            logger.error("FDGuard: Failed to get active connections: %s", e)
        return connections

    def check_and_resolve_connection_leaks(self, max_connections: int = 30) -> Dict[str, Any]:
        """
        Checks if the number of active network connections exceeds the safe limit.
        If so, logs a warning and returns diagnostic information.
        """
        active_connections = self.get_active_connections()
        num_connections = len(active_connections)
        
        logger.info("FDGuard: Currently active network connections: %d", num_connections)
        
        if num_connections > max_connections:
            logger.warning(
                "FDGuard: Network connection leak detected! Active connections: %d (limit: %d)",
                num_connections,
                max_connections
            )
            return {
                "leak_detected": True,
                "num_connections": num_connections,
                "active_connections": active_connections,
                "message": f"Network connection leak detected: {num_connections} active connections exceeds limit of {max_connections}."
            }
            
        return {"leak_detected": False, "num_connections": num_connections}


