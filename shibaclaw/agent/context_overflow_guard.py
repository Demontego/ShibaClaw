import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

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
