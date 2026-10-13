from dataclasses import dataclass, field
import hashlib
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ContextOverflowError(Exception):
    """Raised when the context window usage exceeds the hard limit threshold."""
    pass


class CompactionCircuitBreakerError(ContextOverflowError):
    """Raised when context compaction reduction falls below 15% (circuit breaker tripped)."""
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
    Replaces older or pruned tool result content with an auditable tombstone stub:
    `[Tombstone: tool_result pruned ({orig_len} chars -> hash={hash_val}). Schema invariant preserved.]`
    Preserves tool_call_id, role, name, and message metadata to uphold LLM API schema invariants.
    """
    if not isinstance(msg, dict):
        return msg

    content = msg.get("content")

    # Calculate original length and hash
    if isinstance(content, str):
        raw_str = content
    elif isinstance(content, list):
        raw_str = str(content)
    elif content is None:
        raw_str = ""
    else:
        raw_str = str(content)

    orig_len = len(raw_str)
    content_hash = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()[:8]

    stub = f"[Tombstone: tool_result pruned ({orig_len} chars -> hash={content_hash}). Schema invariant preserved.]"

    tombstoned_msg = dict(msg)
    tombstoned_msg["content"] = stub
    return tombstoned_msg


def enforce_schema_invariants(messages: list[dict]) -> list[dict]:
    """
    Ensures that for every assistant message containing tool_calls, all corresponding
    tool response messages (matching tool_call_id) are present in the message history.
    If a tool response message is missing due to pruning, inserts a tombstoned tool message stub
    to preserve tool_call_id pairs and prevent 400 Bad Request errors from LLM APIs.
    """
    if not messages:
        return messages

    # Map existing tool_call_ids present in tool response messages
    existing_tool_response_ids = set()
    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "tool" and msg.get("tool_call_id"):
            existing_tool_response_ids.add(msg.get("tool_call_id"))

    new_messages = []
    for msg in messages:
        new_messages.append(msg)
        if isinstance(msg, dict) and msg.get("role") == "assistant" and msg.get("tool_calls"):
            tool_calls = msg.get("tool_calls")
            if isinstance(tool_calls, list):
                for tc in tool_calls:
                    if isinstance(tc, dict):
                        tc_id = tc.get("id")
                        func = tc.get("function") or {}
                        tool_name = func.get("name") if isinstance(func, dict) else tc.get("name", "tool")
                        if tc_id and tc_id not in existing_tool_response_ids:
                            # Insert tombstone for missing tool response to satisfy schema invariant
                            stub_msg = {
                                "role": "tool",
                                "tool_call_id": tc_id,
                                "name": tool_name or "tool",
                                "content": "[Tombstone: tool_result pruned (0 chars -> hash=e3b0c442). Schema invariant preserved.]",
                            }
                            new_messages.append(stub_msg)
                            existing_tool_response_ids.add(tc_id)
                            logger.info("ContextOverflowGuard: Enforced schema invariant by adding tombstone tool response for tool_call_id %s", tc_id)

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
            lines.append("- **Read Files**:")
            for rf in sorted(self.read_files):
                lines.append(f"  - `{rf}`")

        lines.append("</artifact_register>")
        return "\n".join(lines)

    def clear(self) -> None:
        self.modified_files.clear()
        self.git_commits.clear()
        self.subagent_results.clear()
        self.read_files.clear()

    def to_dict(self) -> dict[str, Any]:
        return {
            "modified_files": sorted(list(self.modified_files)),
            "git_commits": list(self.git_commits),
            "subagent_results": list(self.subagent_results),
            "read_files": sorted(list(self.read_files)),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArtifactRegister":
        register = cls()
        if not isinstance(data, dict):
            return register
        register.modified_files = set(data.get("modified_files") or [])
        register.git_commits = list(data.get("git_commits") or [])
        register.subagent_results = list(data.get("subagent_results") or [])
        register.read_files = set(data.get("read_files") or [])
        return register


class ContextOverflowGuard:
    """
    Monitors context window size and enforces bounds via warning, critical, and hard limits.
    Incorporate artifact register state preservation and observation masking for tool outputs.
    """

    def __init__(
        self,
        workspace_path: Optional[Any] = None,
        max_context_tokens: int = 128000,
        context_window_tokens: Optional[int] = None,
        warning_ratio: float = 0.70,
        critical_ratio: float = 0.85,
        hard_limit_ratio: float = 0.95,
        artifact_register: Optional[ArtifactRegister] = None,
        **kwargs: Any,
    ):
        if isinstance(workspace_path, (int, float)):
            tokens = int(workspace_path)
            self.workspace_path = None
        else:
            self.workspace_path = workspace_path
            tokens = context_window_tokens if context_window_tokens is not None else max_context_tokens

        self.max_context_tokens = tokens
        self.context_window_tokens = tokens
        self.warning_threshold = int(tokens * warning_ratio)
        self.critical_threshold = int(tokens * critical_ratio)
        self.hard_limit_threshold = int(tokens * hard_limit_ratio)
        self.artifact_register = artifact_register or ArtifactRegister()
        self._circuit_breaker_tripped = False

    def evaluate(self, current_tokens: int) -> Optional[str]:
        """
        Evaluates context usage level against thresholds.
        Returns 'warning', 'compress', or raises ContextOverflowError if above hard limit.
        """
        return self.check_usage(current_tokens)

    def evaluate_compaction_effectiveness(self, tokens_before: int, tokens_after: int) -> dict:
        """
        Evaluates context compression effectiveness.
        If reduction ratio (tokens_before - tokens_after) / tokens_before < 0.15 (15%),
        trips the compaction circuit breaker to prevent compression loops and raises CompactionCircuitBreakerError.
        """
        if tokens_before <= 0:
            reduction_ratio = 0.0
        else:
            reduction_ratio = max(0.0, (tokens_before - tokens_after) / float(tokens_before))

        tripped = reduction_ratio < 0.15
        if tripped:
            self._circuit_breaker_tripped = True
            logger.warning(
                "ContextOverflowGuard: Compaction Circuit Breaker Tripped: reduction ratio %.2f%% < 15.0%% (before=%d, after=%d)",
                reduction_ratio * 100.0, tokens_before, tokens_after
            )
            raise CompactionCircuitBreakerError(
                f"Compaction Circuit Breaker Tripped: reduction ratio {reduction_ratio * 100.0:.2f}% < 15.0% (before={tokens_before}, after={tokens_after})"
            )
        else:
            logger.info(
                "ContextOverflowGuard: Compaction effective: reduction ratio %.2f%% (before=%d, after=%d)",
                reduction_ratio * 100.0, tokens_before, tokens_after
            )

        return {
            "tripped": tripped,
            "reduction_ratio": reduction_ratio,
            "tokens_before": tokens_before,
            "tokens_after": tokens_after,
        }

    def is_circuit_breaker_tripped(self) -> bool:
        return getattr(self, "_circuit_breaker_tripped", False)

    def reset_circuit_breaker(self) -> None:
        self._circuit_breaker_tripped = False

    def check_usage(self, current_tokens: int) -> Optional[str]:
        """
        Check current token usage against thresholds.
        Raises ContextOverflowError if hard limit is reached.
        Returns 'compress', 'warning', or None.
        """
        if current_tokens >= self.hard_limit_threshold:
            raise ContextOverflowError(
                f"Context hard limit exceeded: {current_tokens} >= {self.hard_limit_threshold}"
            )
        elif current_tokens >= self.critical_threshold:
            return "compress"
        elif current_tokens >= self.warning_threshold:
            return "warning"
        return None

    def evaluate_usage(self, estimated_tokens: int) -> tuple[str, str]:
        """
        Evaluate current estimated tokens against context thresholds.
        Returns (level, action_recommendation).
        """
        if estimated_tokens >= self.hard_limit_threshold:
            return ("hard_limit", "raise_error")
        elif estimated_tokens >= self.critical_threshold:
            return ("critical", "compress")
        elif estimated_tokens >= self.warning_threshold:
            return ("warning", "summarize")
        return ("normal", "none")

    def mask_observations(self, messages: list[dict], keep_recent_turns: int = 3) -> list[dict]:
        """
        Observation Masking & Auditable Tool Tombstoning.
        Replaces raw tool outputs older than `keep_recent_turns` assistant turns with auditable tombstone stabs.
        Preserves assistant thoughts/reasoning, tool call IDs, and system messages while
        protecting context window from context rot and preserving KV cache ratios.
        """
        if not messages:
            return messages

        # Find indices of assistant messages that made tool calls
        tool_calling_assistant_indices = [
            i for i, msg in enumerate(messages)
            if msg.get("role") == "assistant" and msg.get("tool_calls")
        ]

        if len(tool_calling_assistant_indices) >= keep_recent_turns:
            cutoff_index = tool_calling_assistant_indices[-keep_recent_turns]
        else:
            assistant_indices = [
                i for i, msg in enumerate(messages)
                if msg.get("role") == "assistant"
            ]
            if len(assistant_indices) <= keep_recent_turns:
                return messages
            cutoff_index = assistant_indices[-keep_recent_turns]

        new_messages = []
        for i, msg in enumerate(messages):
            if i >= cutoff_index:
                # Recent turn — preserve as-is
                new_messages.append(msg)
                continue

            role = msg.get("role")
            content = msg.get("content")

            # Check if this message is a tool output
            is_tool_msg = False
            if role == "tool":
                is_tool_msg = True
            elif role == "user":
                if isinstance(content, str) and content.lower().startswith("[tool result"):
                    is_tool_msg = True
                elif isinstance(content, list) and content and isinstance(content[0], dict) and str(content[0].get("text", "")).lower().startswith("[tool result"):
                    is_tool_msg = True

            if is_tool_msg and content and not _pin_message(msg):
                content_str = content if isinstance(content, str) else str(content)
                if not content_str.startswith("[Tombstone:") and not content_str.startswith("[Tool result masked"):
                    tombstoned_msg = tombstone_tool_result(msg)
                    new_messages.append(tombstoned_msg)
                    logger.info("ContextOverflowGuard: Tombstoned observation for tool at msg index %d", i)
                    continue

            new_messages.append(msg)

        return enforce_schema_invariants(new_messages)

    def budget_context(self, messages: list, max_tokens: Optional[int] = None) -> list:
        """
        Dynamically budgets the context by pruning or compressing older messages
        if the estimated token count exceeds the max_tokens budget.
        Preserves the artifact register state, prompt cache prefix markers, and schema invariants.
        """
        if not messages:
            return messages

        tokens_before = sum(
            len(msg.get("content") or "") for msg in messages if isinstance(msg.get("content"), str)
        ) // 4

        # Apply observation masking & tombstoning first
        messages = self.mask_observations(messages, keep_recent_turns=3)

        target_budget = max_tokens or self.critical_threshold

        estimated_tokens = sum(
            len(msg.get("content") or "") for msg in messages if isinstance(msg.get("content"), str)
        ) // 4

        if estimated_tokens <= target_budget:
            if tokens_before > target_budget:
                self.evaluate_compaction_effectiveness(tokens_before, estimated_tokens)
            return enforce_schema_invariants(messages)

        logger.warning(
            "ContextOverflowGuard: Estimated tokens (%d) exceed budget (%d). Budgeting context...",
            estimated_tokens,
            target_budget
        )

        system_prompt = dict(messages[0])
        sys_content = system_prompt.get("content") or ""

        # Inject artifact register if non-empty and not present
        if not self.artifact_register.is_empty() and "<artifact_register>" not in sys_content:
            artifact_block = self.artifact_register.render_markdown()
            sys_content = f"{PROMPT_CACHE_PREFIX_MARKER}\n{artifact_block}\n\n{sys_content}"
            system_prompt["content"] = sys_content

        tail = messages[-3:]
        pinned = [msg for msg in messages[1:-3] if _pin_message(msg)]
        recent_messages = pinned + tail
        middle_messages = [msg for msg in messages[1:-3] if not _pin_message(msg)]

        budgeted_middle = []
        current_tokens = (len(sys_content) + sum(len(msg.get("content") or "") for msg in recent_messages if isinstance(msg.get("content"), str))) // 4

        for msg in reversed(middle_messages):
            msg_content = msg.get("content") or ""
            msg_tokens = len(msg_content) // 4 if isinstance(msg_content, str) else 0
            if current_tokens + msg_tokens <= target_budget:
                budgeted_middle.insert(0, msg)
                current_tokens += msg_tokens
            else:
                logger.info("ContextOverflowGuard: Pruning message to fit budget: %s...", str(msg_content)[:50])

        final_messages = enforce_schema_invariants([system_prompt] + budgeted_middle + recent_messages)

        tokens_after = sum(
            len(msg.get("content") or "") for msg in final_messages if isinstance(msg.get("content"), str)
        ) // 4

        self.evaluate_compaction_effectiveness(tokens_before, tokens_after)

        return final_messages
