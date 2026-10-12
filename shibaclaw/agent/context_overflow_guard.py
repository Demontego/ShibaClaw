import hashlib
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ContextOverflowError(Exception):
    """Raised when the context window usage exceeds the hard limit threshold."""
    pass


class CompactionCircuitBreakerError(Exception):
    """Raised when compaction effectiveness is below threshold (circuit breaker tripped)."""
    pass


def tombstone_tool_result(msg: dict) -> dict:
    """
    Replaces tool result content with an auditable tombstone stub while preserving tool_call_id and name.
    Format: [Tombstone: tool_result pruned (N chars -> hash=...). Schema invariant preserved.]
    """
    tombstoned = dict(msg)
    raw_content = msg.get("content") or ""
    content_str = raw_content if isinstance(raw_content, str) else str(raw_content)
    char_len = len(content_str)
    content_hash = hashlib.sha256(content_str.encode("utf-8")).hexdigest()[:8]

    tombstoned["content"] = (
        f"[Tombstone: tool_result pruned ({char_len} chars -> hash={content_hash}). "
        f"Schema invariant preserved.]"
    )
    return tombstoned


def enforce_schema_invariants(messages: list) -> list:
    """
    Ensures that for every assistant tool_call, a corresponding tool message exists with matching tool_call_id.
    If missing, inserts a tombstoned tool message to prevent 400 Bad Request errors from LLM APIs.
    """
    new_messages = []
    seen_tool_ids = set()

    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "tool" and msg.get("tool_call_id"):
            seen_tool_ids.add(msg.get("tool_call_id"))

    for msg in messages:
        new_messages.append(msg)
        if isinstance(msg, dict) and msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg.get("tool_calls", []):
                tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                if tc_id and tc_id not in seen_tool_ids:
                    fn = tc.get("function", {}) if isinstance(tc, dict) else getattr(tc, "function", {})
                    fn_name = fn.get("name") if isinstance(fn, dict) else getattr(fn, "name", "tool")
                    tombstone_msg = {
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "name": fn_name,
                        "content": (
                            f"[Tombstone: tool_result pruned (0 chars -> hash=00000000). "
                            f"Schema invariant preserved.]"
                        ),
                    }
                    new_messages.append(tombstone_msg)
                    seen_tool_ids.add(tc_id)

    return new_messages


class ContextOverflowGuard:
    """
    Context Overflow Guard system with Compaction Circuit Breaker & Auditable Tool Tombstoning.
    Monitors context window usage and enforces thresholds:
    1. Warning Threshold (70%): Logs warning.
    2. Critical Threshold (85%): Triggers automatic compression.
    3. Hard Limit Threshold (95%): Saves checkpoint & raises ContextOverflowError.
    4. Compaction Circuit Breaker: Trips if effective reduction < 15%.
    """
    def __init__(
        self,
        workspace: Path,
        context_window_tokens: int = 4000,
        warning_ratio: float = 0.70,
        critical_ratio: float = 0.85,
        hard_limit_ratio: float = 0.95,
        min_reduction_ratio: float = 0.15,
    ):
        self.workspace = workspace
        self.context_window_tokens = context_window_tokens
        self.warning_threshold = int(context_window_tokens * warning_ratio)
        self.critical_threshold = int(context_window_tokens * critical_ratio)
        self.hard_limit_threshold = int(context_window_tokens * hard_limit_ratio)
        self._min_reduction_ratio = min_reduction_ratio
        self._circuit_breaker_tripped = False
        self.learnings_file = workspace / "memory" / "learnings.md"

    def is_circuit_breaker_tripped(self) -> bool:
        return self._circuit_breaker_tripped

    def reset_circuit_breaker(self) -> None:
        self._circuit_breaker_tripped = False

    def evaluate_compaction_effectiveness(self, tokens_before: int, tokens_after: int) -> dict[str, Any]:
        """
        Evaluates effective context reduction.
        Trips circuit breaker if effective reduction < 15%.
        """
        if tokens_before <= 0:
            return {"reduction_ratio": 0.0, "tripped": False, "tokens_saved": 0}

        tokens_saved = max(0, tokens_before - tokens_after)
        reduction_ratio = tokens_saved / tokens_before

        if reduction_ratio < self._min_reduction_ratio:
            self._circuit_breaker_tripped = True
            logger.warning(
                "ContextOverflowGuard: Compaction Circuit Breaker TRIPPED! "
                "Reduction ratio %.2f < threshold %.2f (before: %d, after: %d)",
                reduction_ratio,
                self._min_reduction_ratio,
                tokens_before,
                tokens_after,
            )
        else:
            self._circuit_breaker_tripped = False

        return {
            "reduction_ratio": reduction_ratio,
            "tripped": self._circuit_breaker_tripped,
            "tokens_saved": tokens_saved,
        }

    def check_usage(self, current_tokens: int, checkpoint_mgr: Any = None, session_key: str = "default") -> Optional[str]:
        logger.info(
            "ContextOverflowGuard: Current tokens: %d | Warning: %d | Critical: %d | Hard Limit: %d",
            current_tokens,
            self.warning_threshold,
            self.critical_threshold,
            self.hard_limit_threshold,
        )

        if current_tokens >= self.hard_limit_threshold:
            logger.error(
                "ContextOverflowGuard: Hard limit of %d tokens exceeded! Current usage: %d tokens. Saving checkpoint and raising error.",
                self.hard_limit_threshold,
                current_tokens,
            )
            self.log_incident("Hard Limit Exceeded", current_tokens)
            if checkpoint_mgr:
                try:
                    checkpoint_mgr.save_checkpoint(session_key, {"token_usage": current_tokens, "status": "overflow_checkpoint"})
                    logger.info("ContextOverflowGuard: Successfully saved emergency checkpoint for session %s", session_key)
                except Exception as e:
                    logger.error("ContextOverflowGuard: Failed to save emergency checkpoint: %s", e)
            raise ContextOverflowError(
                f"Context window hard limit exceeded: {current_tokens} tokens used, limit is {self.hard_limit_threshold} tokens."
            )

        if current_tokens >= self.critical_threshold:
            logger.warning(
                "ContextOverflowGuard: Critical threshold of %d tokens exceeded! Current usage: %d tokens. Triggering automatic compression.",
                self.critical_threshold,
                current_tokens,
            )
            self.log_incident("Critical Threshold Exceeded", current_tokens)
            return "compress"

        if current_tokens >= self.warning_threshold:
            logger.warning(
                "ContextOverflowGuard: Warning threshold of %d tokens exceeded! Current usage: %d tokens.",
                self.warning_threshold,
                current_tokens,
            )
            self.log_incident("Warning Threshold Exceeded", current_tokens)
            return "warning"

        return None

    def log_incident(self, event_type: str, current_tokens: int) -> None:
        try:
            self.learnings_file.parent.mkdir(parents=True, exist_ok=True)
            entry = (
                f"\n- [Context Overflow Guard] Event: {event_type} | "
                f"Tokens: {current_tokens} / {self.context_window_tokens} | "
                f"Action: Enforced threshold guardrails.\n"
            )

            if self.learnings_file.is_file():
                content = self.learnings_file.read_text(encoding="utf-8")
                if entry not in content:
                    self.learnings_file.write_text(content + entry, encoding="utf-8")
            else:
                self.learnings_file.write_text("# Learnings\n" + entry, encoding="utf-8")

            logger.info("ContextOverflowGuard: Logged incident to learnings.md")
        except Exception as e:
            logger.error("ContextOverflowGuard: Failed to log incident: %s", e)

    def mask_observations(self, messages: list, keep_recent_turns: int = 3) -> list:
        """
        Masks/tombstones older tool outputs to prevent context rot while keeping schema invariants.
        """
        if not messages:
            return messages

        cutoff = max(1, len(messages) - (keep_recent_turns * 2))
        new_messages = []

        for i, msg in enumerate(messages):
            if i < cutoff and isinstance(msg, dict) and msg.get("role") == "tool":
                new_messages.append(tombstone_tool_result(msg))
            else:
                new_messages.append(msg)

        return new_messages

    def budget_context(self, messages: list, max_tokens: Optional[int] = None) -> list:
        """
        Dynamically budgets the context by pruning or tombstoning older messages
        if the estimated token count exceeds the max_tokens budget.
        Keeps system prompt (messages[0]), recent messages, and enforces schema invariants.
        """
        if not messages:
            return messages

        # Apply observation tombstoning first
        messages = self.mask_observations(messages, keep_recent_turns=3)

        target_budget = max_tokens or self.critical_threshold

        tokens_before = sum(
            len(msg.get("content") or "") for msg in messages if isinstance(msg.get("content"), str)
        ) // 4
        if tokens_before <= target_budget:
            return enforce_schema_invariants(messages)

        logger.warning(
            "ContextOverflowGuard: Estimated tokens (%d) exceed budget (%d). Budgeting context...",
            tokens_before,
            target_budget,
        )

        system_prompt = dict(messages[0])
        tail = messages[-3:]
        middle_messages = messages[1:-3]

        budgeted_middle = []
        current_tokens = (
            len(system_prompt.get("content") or "")
            + sum(len(msg.get("content") or "") for msg in tail if isinstance(msg.get("content"), str))
        ) // 4

        for msg in reversed(middle_messages):
            msg_content = msg.get("content") or ""
            msg_tokens = len(msg_content) // 4 if isinstance(msg_content, str) else 0
            if current_tokens + msg_tokens <= target_budget:
                budgeted_middle.insert(0, msg)
                current_tokens += msg_tokens
            elif isinstance(msg, dict) and msg.get("role") == "tool":
                tombstoned = tombstone_tool_result(msg)
                t_tokens = len(tombstoned.get("content") or "") // 4
                if current_tokens + t_tokens <= target_budget:
                    budgeted_middle.insert(0, tombstoned)
                    current_tokens += t_tokens

        result = [system_prompt] + budgeted_middle + tail
        result = enforce_schema_invariants(result)

        tokens_after = sum(
            len(msg.get("content") or "") for msg in result if isinstance(msg.get("content"), str)
        ) // 4
        self.evaluate_compaction_effectiveness(tokens_before, tokens_after)

        return result
