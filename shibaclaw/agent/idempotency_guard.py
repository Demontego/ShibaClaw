import json
import hashlib
import logging
from typing import Dict, Any, Callable

logger = logging.getLogger(__name__)

class IdempotencyGuard:
    """
    Prevents duplicate execution of side-effectful operations (e.g., API calls, file writes)
    by tracking executed operations and returning cached results for identical calls.
    """
    def __init__(self):
        self.executed_operations: Dict[str, Any] = {}

    def _hash_operation(self, op_name: str, args: Dict[str, Any]) -> str:
        try:
            serialized = json.dumps(args, sort_keys=True)
        except Exception:
            serialized = str(args)
        return hashlib.sha256(f"{op_name}:{serialized}".encode("utf-8")).hexdigest()

    def execute_once(self, op_name: str, args: Dict[str, Any], action_fn: Callable[[], Any]) -> Any:
        """
        Executes the action_fn only if it hasn't been executed with the same arguments before.
        Otherwise, returns the cached result.
        """
        op_hash = self._hash_operation(op_name, args)
        if op_hash in self.executed_operations:
            logger.info("IdempotencyGuard: Intercepted duplicate operation '%s'. Returning cached result.", op_name)
            return self.executed_operations[op_hash]

        logger.info("IdempotencyGuard: Executing operation '%s' for the first time.", op_name)
        result = action_fn()
        self.executed_operations[op_hash] = result
        return result
