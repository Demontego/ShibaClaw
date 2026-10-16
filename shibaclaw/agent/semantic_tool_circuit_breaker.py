import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

class SemanticToolCircuitBreaker:
    """
    Semantic Tool Circuit Breaker.
    Tracks repeated tool calls with identical arguments and results.
    Trips when the same tool is called with the same arguments and returns the same result 3 times.
    """
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.call_history = {}  # (tool_name, args_hash, result_hash) -> consecutive count
        self._last_signature = None
        self._blocked_arguments = None
        self.learnings_file = workspace / "memory" / "learnings.md"

    def _compute_hash(self, data: Any) -> str:
        """Computes a stable SHA256 hash of any JSON-serializable data."""
        if isinstance(data, str):
            serialized = data
        else:
            try:
                serialized = json.dumps(data, sort_keys=True, ensure_ascii=False)
            except Exception:
                serialized = str(data)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def record_call(self, tool_name: str, arguments: Any, result: str) -> bool:
        """
        Records a tool call with its arguments and result.
        Returns True if the circuit breaker is tripped (3 identical calls), False otherwise.
        """
        if result.startswith("[CircuitBreaker: Tool execution stalled."):
            return True
        args_hash = self._compute_hash(arguments)
        result_hash = self._compute_hash(result)
        key = (tool_name, args_hash, result_hash)

        if key != self._last_signature:
            self.call_history.clear()
            self._blocked_arguments = None
        self._last_signature = key
        self.call_history[key] = self.call_history.get(key, 0) + 1
        count = self.call_history[key]

        logger.info(
            "SemanticToolCircuitBreaker: Recorded call for %s | Count: %d/3",
            tool_name,
            count
        )

        if count == 3:
            self._blocked_arguments = (tool_name, args_hash)
            logger.error(
                "SemanticToolCircuitBreaker: Tripped for tool '%s' with identical arguments and result!",
                tool_name
            )
            self.log_breaker_tripped(tool_name, arguments, result)
            return True

        return count >= 3

    def should_block(self, tool_name: str, arguments: Any) -> bool:
        """Block a stalled call until a different completed call changes the trace."""
        return self._blocked_arguments == (tool_name, self._compute_hash(arguments))

    def get_tripped_message(self, tool_name: str) -> str:
        """Returns the in-band BreakerTripped strategy pivot message."""
        return (
            "[CircuitBreaker: Tool execution stalled. Alternative strategy required.]\n"
            f"Error: BreakerTripped. Tool '{tool_name}' has been called 3 times "
            "with the exact same arguments and returned the exact same result. "
            "This indicates a semantic execution stall and loop. "
            f"Do NOT call '{tool_name}' again with these parameters. "
            "You MUST pivot your strategy immediately: use an alternative tool, "
            "decompose the task, or fall back to a different execution approach."
        )

    def is_tripped(self, tool_name: str, arguments: Any, result: str) -> bool:
        """Checks whether the circuit breaker is currently tripped for a given call signature."""
        args_hash = self._compute_hash(arguments)
        result_hash = self._compute_hash(result)
        key = (tool_name, args_hash, result_hash)
        return self.call_history.get(key, 0) >= 3

    def get_call_count(self, tool_name: str, arguments: Any, result: str) -> int:
        """Returns the current call count for a given call signature."""
        args_hash = self._compute_hash(arguments)
        result_hash = self._compute_hash(result)
        key = (tool_name, args_hash, result_hash)
        return self.call_history.get(key, 0)

    def reset(self) -> None:
        """Resets the circuit breaker call history."""
        self.call_history.clear()
        self._last_signature = None
        self._blocked_arguments = None

    def log_breaker_tripped(self, tool_name: str, arguments: Any, result: str) -> None:
        """Logs the semantic tool circuit breaker tripped incident to memory/learnings.md."""
        try:
            self.learnings_file.parent.mkdir(parents=True, exist_ok=True)
            entry = (
                f"\n- [Semantic Tool Circuit Breaker Tripped] Tool: {tool_name} | "
                f"Action: Tripped circuit breaker to prevent infinite semantic loop.\n"
            )
            
            if self.learnings_file.is_file():
                content = self.learnings_file.read_text(encoding="utf-8")
                if entry not in content:
                    self.learnings_file.write_text(content + entry, encoding="utf-8")
            else:
                self.learnings_file.write_text("# Learnings\n" + entry, encoding="utf-8")
            
            logger.info("SemanticToolCircuitBreaker: Logged circuit breaker tripped incident")
        except Exception as e:
            logger.error("SemanticToolCircuitBreaker: Failed to log circuit breaker tripped incident: %s", e)
