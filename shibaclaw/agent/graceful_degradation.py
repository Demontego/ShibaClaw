import time
import logging
from typing import Dict, Any, List, Callable, Optional

logger = logging.getLogger(__name__)

class GracefulDegradation:
    """
    Implements Graceful Degradation Patterns (fallback chains and response caching)
    to ensure continuous operation during external API failures.
    """
    def __init__(self, cache_ttl: float = 300.0):
        self.cache_ttl = cache_ttl
        self.cache: Dict[str, Dict[str, Any]] = {}

    def execute_with_fallback(self, key: str, primary_fn: Callable[[], Any], fallbacks: List[Callable[[], Any]]) -> Any:
        """
        Executes the primary function. If it fails, tries the fallback functions in order.
        If all fail, attempts to retrieve a cached response.
        """
        # Try primary
        try:
            logger.info("GracefulDegradation: Executing primary function for %s", key)
            result = primary_fn()
            self._update_cache(key, result)
            return result
        except Exception as e:
            logger.warning("GracefulDegradation: Primary function failed for %s: %s. Trying fallbacks...", key, e)

        # Try fallbacks
        for i, fallback_fn in enumerate(fallbacks):
            try:
                logger.info("GracefulDegradation: Executing fallback %d for %s", i + 1, key)
                result = fallback_fn()
                self._update_cache(key, result)
                return result
            except Exception as fe:
                logger.warning("GracefulDegradation: Fallback %d failed for %s: %s", i + 1, key, fe)

        # Try cache fallback
        cached = self._get_cached(key)
        if cached is not None:
            logger.warning("GracefulDegradation: All functions failed. Serving cached response for %s", key)
            return cached

        raise RuntimeError(f"GracefulDegradation: All attempts failed and no cached response available for {key}")

    def _update_cache(self, key: str, value: Any):
        self.cache[key] = {
            "value": value,
            "timestamp": time.time()
        }

    def _get_cached(self, key: str) -> Optional[Any]:
        entry = self.cache.get(key)
        if entry:
            if time.time() - entry["timestamp"] <= self.cache_ttl:
                return entry["value"]
            else:
                logger.info("GracefulDegradation: Cache expired for %s", key)
        return None
