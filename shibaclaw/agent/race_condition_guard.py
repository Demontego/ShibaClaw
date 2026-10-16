import asyncio
import logging
from pathlib import Path
from typing import Dict, Set, Any

logger = logging.getLogger(__name__)

class RaceConditionGuard:
    """
    Detects and prevents race conditions during parallel tool execution.
    Manages locks for shared resources (e.g., file paths, database keys).
    """
    def __init__(self):
        self._locks: Dict[str, asyncio.Lock] = {}
        self._active_resources: Set[str] = set()

    def _normalize_resource(self, resource: str) -> str:
        """Normalizes resource paths or keys to prevent duplicate locks on the same resource."""
        try:
            path = Path(resource).resolve()
            return str(path)
        except Exception:
            return resource.strip().lower()

    def extract_resource(self, tool_name: str, arguments: Any) -> str | None:
        """Extracts the resource path or key from tool arguments if applicable."""
        if not isinstance(arguments, dict):
            return None
        # Common file-based tools
        if tool_name in {"read_file", "write_file", "edit_file"}:
            return arguments.get("path")
        return None

    async def acquire(self, resource: str, tool_name: str, timeout: float = 5.0) -> bool:
        """
        Acquires a lock for a resource.
        Returns True if acquired successfully, False if timed out or conflicted.
        """
        norm_res = self._normalize_resource(resource)
        if norm_res not in self._locks:
            self._locks[norm_res] = asyncio.Lock()

        lock = self._locks[norm_res]
        logger.info("RaceConditionGuard: Tool '%s' requesting lock for resource '%s'", tool_name, norm_res)

        try:
            await asyncio.wait_for(lock.acquire(), timeout=timeout)
            self._active_resources.add(norm_res)
            logger.info("RaceConditionGuard: Tool '%s' acquired lock for resource '%s'", tool_name, norm_res)
            return True
        except asyncio.TimeoutError:
            logger.warning(
                "RaceConditionGuard: Tool '%s' timed out waiting for resource '%s' (lock held by another tool)",
                tool_name,
                norm_res
            )
            return False

    def release(self, resource: str, tool_name: str) -> None:
        """Releases a lock for a resource."""
        norm_res = self._normalize_resource(resource)
        lock = self._locks.get(norm_res)
        if lock and lock.locked():
            lock.release()
            self._active_resources.discard(norm_res)
            logger.info("RaceConditionGuard: Tool '%s' released lock for resource '%s'", tool_name, norm_res)
