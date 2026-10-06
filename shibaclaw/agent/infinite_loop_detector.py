import json
import hashlib
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

class InfiniteLoopDetector:
    """
    Detects infinite loops in tool calling by tracking the history of tool calls
    and identifying repeating patterns or excessive identical calls.
    """
    def __init__(self, max_identical_calls: int = 3, window_size: int = 10):
        self.max_identical_calls = max_identical_calls
        self.window_size = window_size
        self.history: List[Tuple[str, str]] = []  # List of (tool_name, args_hash)

    def _hash_args(self, args: Dict[str, Any]) -> str:
        # Normalize and hash arguments
        try:
            serialized = json.dumps(args, sort_keys=True)
        except Exception:
            serialized = str(args)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def record_and_check(self, tool_name: str, args: Dict[str, Any]) -> bool:
        """
        Records a tool call and checks if it constitutes an infinite loop.
        Returns True if an infinite loop is detected, False otherwise.
        """
        args_hash = self._hash_args(args)
        self.history.append((tool_name, args_hash))
        
        # Keep history within window size
        if len(self.history) > self.window_size:
            self.history.pop(0)

        # Check 1: Excessive identical calls
        identical_count = sum(1 for name, h in self.history if name == tool_name and h == args_hash)
        if identical_count >= self.max_identical_calls:
            logger.warning(
                "InfiniteLoopDetector: Detected %d identical calls to tool '%s' with args hash %s",
                identical_count,
                tool_name,
                args_hash
            )
            return True

        # Check 2: Repeating sequence detection (e.g., A -> B -> A -> B)
        # We look for repeating patterns of length 2 to window_size // 2
        n = len(self.history)
        for pattern_len in range(2, n // 2 + 1):
            pattern = self.history[-pattern_len:]
            # Check if the preceding sequence matches the pattern
            prev_sequence = self.history[-2 * pattern_len : -pattern_len]
            if pattern == prev_sequence:
                logger.warning(
                    "InfiniteLoopDetector: Detected repeating sequence of length %d: %s",
                    pattern_len,
                    [name for name, _ in pattern]
                )
                return True

        return False
