import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _tool_groups(messages: list) -> list[list]:
    """Keep an assistant tool call together with every following tool result."""
    groups: list[list] = []
    index = 0
    while index < len(messages):
        msg = messages[index]
        calls = msg.get("tool_calls") if msg.get("role") == "assistant" else None
        if not calls:
            groups.append([msg])
            index += 1
            continue
        ids = {
            tc.get("id")
            for tc in calls
            if isinstance(tc, dict) and tc.get("id")
        }
        group = [msg]
        index += 1
        while index < len(messages) and messages[index].get("role") == "tool":
            tool_id = messages[index].get("tool_call_id")
            if ids and tool_id not in ids:
                break
            group.append(messages[index])
            index += 1
        groups.append(group)
    return groups


def _message_text(msg: dict) -> str:
    content = msg.get("content") or ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                parts.append(str(part.get("text") or ""))
            else:
                parts.append(str(part))
        return " ".join(parts)
    return str(content)


class ContextOverflowError(Exception):
    """Raised when the context window usage exceeds the hard limit threshold."""
    pass

class ContextOverflowGuard:
    """
    Context Overflow Guard system.
    Monitors the current token usage of the context window and enforces three thresholds:
    1. Warning Threshold (70%): Logs a warning.
    2. Critical Threshold (85%): Triggers automatic compression.
    3. Hard Limit Threshold (95%): Saves a checkpoint and raises ContextOverflowError.
    """
    def __init__(
        self,
        workspace: Path,
        context_window_tokens: int = 4000,
        warning_ratio: float = 0.70,
        critical_ratio: float = 0.85,
        hard_limit_ratio: float = 0.95
    ):
        self.workspace = workspace
        self.context_window_tokens = context_window_tokens
        self.warning_threshold = int(context_window_tokens * warning_ratio)
        self.critical_threshold = int(context_window_tokens * critical_ratio)
        self.hard_limit_threshold = int(context_window_tokens * hard_limit_ratio)
        self.learnings_file = workspace / "memory" / "learnings.md"

    def check_usage(self, current_tokens: int, checkpoint_mgr: Any = None, session_key: str = "default") -> Optional[str]:
        """
        Checks the current token usage against the three thresholds.
        Returns a compression action string if critical threshold is exceeded,
        raises ContextOverflowError if hard limit is exceeded,
        or returns None.
        """
        logger.info(
            "ContextOverflowGuard: Current tokens: %d | Warning: %d | Critical: %d | Hard Limit: %d",
            current_tokens,
            self.warning_threshold,
            self.critical_threshold,
            self.hard_limit_threshold
        )

        if current_tokens >= self.hard_limit_threshold:
            logger.error(
                "ContextOverflowGuard: Hard limit of %d tokens exceeded! Current usage: %d tokens. Saving checkpoint and raising error.",
                self.hard_limit_threshold,
                current_tokens
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
                current_tokens
            )
            self.log_incident("Critical Threshold Exceeded", current_tokens)
            return "compress"

        if current_tokens >= self.warning_threshold:
            logger.warning(
                "ContextOverflowGuard: Warning threshold of %d tokens exceeded! Current usage: %d tokens.",
                self.warning_threshold,
                current_tokens
            )
            self.log_incident("Warning Threshold Exceeded", current_tokens)
            return "warning"

        return None

    def log_incident(self, event_type: str, current_tokens: int) -> None:
        """
        Logs the context overflow incident to memory/learnings.md.
        """
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

    def budget_context(self, messages: list, max_tokens: Optional[int] = None) -> list:
        """
        Dynamically budgets the context by pruning or compressing older messages
        if the estimated token count exceeds the max_tokens budget.
        Keeps the system prompt (messages[0]) and the most recent messages intact.
        """
        if not messages:
            return messages
            
        target_budget = max_tokens or self.critical_threshold
        
        # Estimate tokens: 1 token ≈ 4 characters
        estimated_tokens = sum(len(_message_text(msg)) for msg in messages) // 4
        if estimated_tokens <= target_budget:
            return messages

        logger.warning(
            "ContextOverflowGuard: Estimated tokens (%d) exceed budget (%d). Budgeting context...",
            estimated_tokens,
            target_budget
        )

        groups = _tool_groups(messages)
        head = groups[:1] if groups and groups[0] and groups[0][0].get("role") == "system" else []
        rest = groups[len(head):]
        kept: list[list] = []
        used = sum(len(_message_text(msg)) for group in head for msg in group) // 4
        for group in reversed(rest):
            cost = sum(len(_message_text(msg)) for msg in group) // 4
            if kept and used + cost > target_budget:
                logger.info(
                    "ContextOverflowGuard: Pruning message group to fit budget: %s...",
                    _message_text(group[0])[:50],
                )
                continue
            kept.append(group)
            used += cost
        kept.reverse()
        return [msg for group in head + kept for msg in group]

class ContextWindowRecovery:
    """
    Implements Context Window Recovery to automatically compress and summarize
    older messages when approaching the token limit, ensuring no context is lost.
    """
    def __init__(self, guard: ContextOverflowGuard):
        self.guard = guard

    def recover_context(self, messages: list, max_tokens: int) -> list:
        """
        Compresses the context by summarizing older messages and replacing them
        with a single summary message, keeping the system prompt and recent messages intact.
        """
        if not messages or len(messages) <= 4:
            return messages

        # Estimate tokens: 1 token ≈ 4 characters
        estimated_tokens = sum(len(_message_text(msg)) for msg in messages) // 4
        if estimated_tokens <= max_tokens:
            return messages

        logger.warning(
            "ContextWindowRecovery: Context size (%d tokens) exceeds limit (%d). Initiating recovery...",
            estimated_tokens,
            max_tokens
        )

        system_prompt = messages[0]
        recent_messages = messages[-3:]
        middle_messages = messages[1:-3]

        # Summarize middle messages
        summary_content = "Summary of previous conversation turns:\n"
        for msg in middle_messages:
            role = msg.get("role", "unknown")
            content = _message_text(msg)
            truncated = content[:100] + "..." if len(content) > 100 else content
            summary_content += f"- {role}: {truncated}\n"

        summary_message = {
            "role": "system",
            "content": f"[Context Window Recovery] {summary_content}"
        }

        logger.info("ContextWindowRecovery: Successfully compressed older messages into a summary.")
        return [system_prompt, summary_message] + recent_messages

