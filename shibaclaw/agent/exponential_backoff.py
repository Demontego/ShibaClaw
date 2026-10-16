import time
import random
import logging
from typing import Any, Callable, Type, Tuple

logger = logging.getLogger(__name__)

class ExponentialBackoff:
    """
    Implements Exponential Backoff with Jitter for retrying external API
    and tool calls to prevent thundering herd problems and handle transient errors.
    """
    def __init__(self, base_delay: float = 1.0, max_delay: float = 30.0, factor: float = 2.0, jitter: bool = True):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.factor = factor
        self.jitter = jitter

    def execute_with_retry(self, fn: Callable[[], Any], max_attempts: int = 3, exceptions_to_retry: Tuple[Type[Exception], ...] = (Exception,)) -> Any:
        """
        Executes the given function, retrying with exponential backoff and jitter if it raises an exception in exceptions_to_retry.
        """
        for attempt in range(max_attempts):
            try:
                return fn()
            except exceptions_to_retry as e:
                if attempt == max_attempts - 1:
                    logger.error("ExponentialBackoff: All %d attempts failed. Last error: %s", max_attempts, e)
                    raise

                # Calculate delay: base * factor^attempt
                delay = self.base_delay * (self.factor ** attempt)
                
                # Add full jitter if enabled: random between 0 and delay
                if self.jitter:
                    delay = random.uniform(0.1, delay)
                
                # Cap at max_delay
                delay = min(delay, self.max_delay)
                
                logger.warning(
                    "ExponentialBackoff: Attempt %d failed with error: %s. Retrying in %.2fs...",
                    attempt + 1,
                    e,
                    delay
                )
                time.sleep(delay)
