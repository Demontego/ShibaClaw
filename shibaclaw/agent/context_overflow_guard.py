from dataclasses import dataclass, field
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


PROMPT_CACHE_PREFIX_MARKER = "<!-- PROMPT_CACHE_PREFIX_MARKER -->"
# A wake must still see the backlog and the evolve script reply after older tools are stubbed.
_PIN_MARKERS = ("## Open", "refuse:", "need web_search", "gate open")


def _pin_message(msg: dict) -> bool:
    content = msg.get("content")
    if not isinstance(content, str):
        return False
    return any(marker in content for marker in _PIN_MARKERS)


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
                            "[Tombstone: tool_result pruned (0 chars -> hash=00000000). "
                            "Schema invariant preserved.]"
                        ),
                    }
                    new_messages.append(tombstone_msg)
                    seen_tool_ids.add(tc_id)

    return new_messages


@dataclass
class ArtifactRegister:
    """
    Tracks artifacts produced or accessed during an execution session.
    Preserved during context compaction to ensure critical state is not lost.
    """
    modified_files: set = field(default_factory=set)
    git_commits: list = field(default_factory=list)
    subagent_results: list = field(default_factory=list)
    read_files: set = field(default_factory=set)

    def record_modified_file(self, path: str) -> None:
        self.modified_files.add(path)

    def record_git_commit(self, commit: str) -> None:
        if commit not in self.git_commits:
            self.git_commits.append(commit)

    def record_subagent_result(self, label: str, status: str, summary: str) -> None:
        self.subagent_results.append({
            "label": label,
            "status": status,
            "summary": summary,
        })

    def record_read_file(self, path: str) -> None:
        self.read_files.add(path)

    def is_empty(self) -> bool:
        return not (self.modified_files or self.git_commits or self.subagent_results or self.read_files)

    def render_markdown(self) -> str:
        """Render artifact register as a structured markdown block with prompt cache markers."""
        lines = [PROMPT_CACHE_PREFIX_MARKER, "<artifact_register>", "### Artifact Register"]

        if self.modified_files:
            lines.append("- **Modified Files**:")
            for f in sorted(self.modified_files):
                lines.append(f"  - `{f}`")
        else:
            lines.append("- **Modified Files**: (none)")

        if self.git_commits:
            lines.append("- **Git Commits**:")
            for c in self.git_commits:
                lines.append(f"  - `{c}`")
        else:
            lines.append("- **Git Commits**: (none)")

        if self.subagent_results:
            lines.append("- **Subagent Results**:")
            for sub in self.subagent_results:
                lines.append(f"  - [{sub.get('status', 'done')}] {sub.get('label', 'subagent')}: {sub.get('summary', '')}")
        else:
            lines.append("- **Subagent Results**: (none)")

        if self.read_files:
            lines.append("- **Read Files**: " + ", ".join(f"`{f}`" for f in sorted(self.read_files)))
        else:
            lines.append("- **Read Files**: (none)")

        lines.append("</artifact_register>")
        return "\n".join(lines)


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

    def evaluate_compaction_effectiveness(self, tokens_before: int, tokens_after: int) -> float:
        """
        Evaluates context reduction percentage after compaction.
        If reduction is less than min_reduction_ratio (15%) when tokens exceed critical threshold,
        trips circuit breaker and raises CompactionCircuitBreakerError.
        """
        if tokens_before <= 0:
            return 0.0

        reduction = (tokens_before - tokens_after) / float(tokens_before)
        logger.info(
            "ContextOverflowGuard: Compaction evaluated: %d -> %d tokens (%.2f%% reduction)",
            tokens_before,
            tokens_after,
            reduction * 100.0,
        )

        if tokens_before >= self.critical_threshold and reduction < self._min_reduction_ratio:
            self._circuit_breaker_tripped = True
            msg = (
                f"Compaction Circuit Breaker Tripped! Reduction was only {reduction * 100.0:.1f}% "
                f"(required >= {self._min_reduction_ratio * 100.0:.1f}%). "
                f"Tokens: {tokens_before} -> {tokens_after}."
            )
            logger.error(msg)
            self._log_incident("circuit_breaker_tripped", tokens_after)
            raise CompactionCircuitBreakerError(msg)

        return reduction

    def evaluate(self, current_tokens: int) -> str:
        """
        Evaluates token usage against thresholds.
        Returns 'ok', 'warning', 'critical', or raises ContextOverflowError if >= hard_limit_threshold.
        """
        if current_tokens >= self.hard_limit_threshold:
            self._log_incident("hard_limit_exceeded", current_tokens)
            raise ContextOverflowError(
                f"Context hard limit reached: {current_tokens} >= {self.hard_limit_threshold} tokens."
            )
        if current_tokens >= self.critical_threshold:
            logger.warning("ContextOverflowGuard: Critical threshold reached (%d tokens)", current_tokens)
            return "critical"
        if current_tokens >= self.warning_threshold:
            logger.info("ContextOverflowGuard: Warning threshold reached (%d tokens)", current_tokens)
            return "warning"
        return "ok"

    def _log_incident(self, event_type: str, current_tokens: int) -> None:
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
        Tombstones older tool outputs to prevent context rot while preserving schema invariants and tool_call_ids.
        """
        if not messages:
            return messages

        tool_calling_assistant_indices = [
            i for i, msg in enumerate(messages)
            if isinstance(msg, dict) and msg.get("role") == "assistant" and msg.get("tool_calls")
        ]

        if len(tool_calling_assistant_indices) >= keep_recent_turns:
            cutoff_index = tool_calling_assistant_indices[-keep_recent_turns]
        else:
            assistant_indices = [
                i for i, msg in enumerate(messages)
                if isinstance(msg, dict) and msg.get("role") == "assistant"
            ]
            if len(assistant_indices) <= keep_recent_turns:
                return messages
            cutoff_index = assistant_indices[-keep_recent_turns]

        new_messages = []
        for i, msg in enumerate(messages):
            if i >= cutoff_index:
                new_messages.append(msg)
                continue

            if not isinstance(msg, dict):
                new_messages.append(msg)
                continue

            role = msg.get("role")
            content = msg.get("content")

            is_tool_msg = False
            if role == "tool":
                is_tool_msg = True
            elif role == "user":
                if isinstance(content, str) and content.lower().startswith("[tool result"):
                    is_tool_msg = True

            if is_tool_msg and content and not _pin_message(msg):
                content_str = content if isinstance(content, str) else str(content)
                if not content_str.startswith("[Tombstone:") and not content_str.startswith("[Tool result masked"):
                    new_messages.append(tombstone_tool_result(msg))
                    logger.info("ContextOverflowGuard: Tombstoned observation at msg index %d", i)
                    continue

            new_messages.append(msg)

        return new_messages

    def budget_context(self, messages: list, max_tokens: Optional[int] = None) -> list:
        """
        Dynamically budgets the context by pruning or tombstoning older messages
        if the estimated token count exceeds max_tokens.
        Preserves system prompt, recent turns, and schema invariants.
        """
        if not messages:
            return messages

        target_budget = max_tokens or self.critical_threshold

        tokens_before = sum(
            len(msg.get("content") or "") for msg in messages if isinstance(msg.get("content"), str)
        ) // 4

        # Apply observation tombstoning
        messages = self.mask_observations(messages, keep_recent_turns=3)

        if tokens_before <= target_budget:
            res = enforce_schema_invariants(messages)
            tokens_after = sum(
                len(m.get("content") or "") for m in res if isinstance(m.get("content"), str)
            ) // 4
            self.evaluate_compaction_effectiveness(tokens_before, tokens_after)
            return res

        logger.warning(
            "ContextOverflowGuard: Estimated tokens (%d) exceed budget (%d). Budgeting context...",
            tokens_before,
            target_budget,
        )

        system_prompt = dict(messages[0]) if isinstance(messages[0], dict) else messages[0]
        tail = messages[-3:]
        middle_messages = messages[1:-3]

        budgeted_middle = []
        current_tokens = (
            len(system_prompt.get("content") if isinstance(system_prompt, dict) else "")
            + sum(len(msg.get("content") if isinstance(msg, dict) else "") for msg in tail)
        ) // 4

        for msg in reversed(middle_messages):
            if not isinstance(msg, dict):
                budgeted_middle.insert(0, msg)
                continue

            msg_content = msg.get("content") or ""
            msg_tokens = len(msg_content) // 4 if isinstance(msg_content, str) else 0

            if current_tokens + msg_tokens <= target_budget:
                budgeted_middle.insert(0, msg)
                current_tokens += msg_tokens
            elif msg.get("role") == "tool":
                tombstoned = tombstone_tool_result(msg)
                t_tokens = len(tombstoned.get("content") or "") // 4
                if current_tokens + t_tokens <= target_budget:
                    budgeted_middle.insert(0, tombstoned)
                    current_tokens += t_tokens

        result = [system_prompt] + budgeted_middle + tail
        result = enforce_schema_invariants(result)

        tokens_after = sum(
            len(m.get("content") or "") for m in result if isinstance(m.get("content"), str)
        ) // 4
        self.evaluate_compaction_effectiveness(tokens_before, tokens_after)

        return result
