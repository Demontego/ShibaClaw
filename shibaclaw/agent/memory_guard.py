import logging
from typing import Any, List, Dict

logger = logging.getLogger(__name__)

class MemoryGuard:
    """
    Monitors and prevents memory leaks by automatically pruning/truncating
    large internal data structures (caches, histories, lists) when they exceed safe limits.
    """
    def __init__(self, max_history_size: int = 100):
        self.max_history_size = max_history_size

    def guard_list(self, lst: List[Any], name: str) -> List[Any]:
        """Prunes a list if it exceeds the maximum allowed size."""
        if len(lst) > self.max_history_size:
            logger.warning(
                "MemoryGuard: Truncating list '%s' from %d to %d items to prevent memory leak.",
                name,
                len(lst),
                self.max_history_size
            )
            return lst[-self.max_history_size:]
        return lst

    def guard_dict(self, dct: Dict[Any, Any], name: str) -> Dict[Any, Any]:
        """Prunes a dictionary if it exceeds the maximum allowed size by removing oldest keys."""
        if len(dct) > self.max_history_size:
            logger.warning(
                "MemoryGuard: Truncating dictionary '%s' from %d to %d items to prevent memory leak.",
                name,
                len(dct),
                self.max_history_size
            )
            keys_to_keep = list(dct.keys())[-self.max_history_size:]
            return {k: dct[k] for k in keys_to_keep}
        return dct
