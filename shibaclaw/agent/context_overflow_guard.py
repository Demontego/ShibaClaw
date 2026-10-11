from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

class ContextOverflowError(Exception):
    """Raised when the context window usage exceeds the hard limit threshold."""
    pass

PROMPT_CACHE_PREFIX_MARKER = "<!-- PROMPT_CACHE_PREFIX_MARKER -->"

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
        reg = cls()
        reg.modified_files = set(data.get("modified_files", []))
        reg.git_commits = list(data.get("git_commits", []))
        reg.subagent_results = list(data.get("subagent_results", []))
        reg.read_files = set(data.get("read_files", []))
        return reg


class ContextOverflowGuard:
    """
    Context Overflow Guard system with Artifact Preservation & Prompt Cache discipline.
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
        hard_limit_ratio: float = 0.95,
        artifact_register: Optional[ArtifactRegister] = None,
    ):
        self.workspace = workspace
        self.context_window_tokens = context_window_tokens
        self.warning_threshold = int(context_window_tokens * warning_ratio)
        self.critical_threshold = int(context_window_tokens * critical_ratio)
        self.hard_limit_threshold = int(context_window_tokens * hard_limit_ratio)
        self.learnings_file = workspace / "memory" / "learnings.md"
        self.artifact_register = artifact_register or ArtifactRegister()

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

    def format_compacted_summary(self, summary_text: str) -> str:
        """Appends the rendered artifact register to summary text to preserve task state."""
        register_md = self.artifact_register.render_markdown()
        return f"{summary_text}\n\n{register_md}"

    def mask_observations(
        self,
        messages: list[dict[str, Any]],
        keep_recent_turns: int = 3,
        preserve_system: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Observation Masking & Selective Tool Result Pruning.
        Replaces raw tool outputs older than `keep_recent_turns` assistant turns with concise stubs.
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
            tool_name = msg.get("name") or msg.get("tool_name") or msg.get("function_name") or "tool"

            if role == "tool":
                is_tool_msg = True
            elif role == "user":
                if isinstance(content, str) and content.lower().startswith("[tool result"):
                    is_tool_msg = True
                elif isinstance(content, list) and content and isinstance(content[0], dict) and str(content[0].get("text", "")).lower().startswith("[tool result"):
                    is_tool_msg = True

            if is_tool_msg and content:
                content_str = content if isinstance(content, str) else str(content)
                if not content_str.startswith("[Tool result masked"):
                    # Create stub
                    stub = f"[Tool result masked: output from '{tool_name}' pruned to prevent context rot. See ArtifactRegister for state changes.]"
                    masked_msg = dict(msg)
                    masked_msg["content"] = stub
                    new_messages.append(masked_msg)
                    logger.info("ContextOverflowGuard: Masked observation for tool '%s' at msg index %d", tool_name, i)
                    continue

            new_messages.append(msg)

        return new_messages

    def budget_context(self, messages: list, max_tokens: Optional[int] = None) -> list:
        """
        Dynamically budgets the context by pruning or compressing older messages
        if the estimated token count exceeds the max_tokens budget.
        Preserves the artifact register state and prompt cache prefix markers.
        """
        if not messages:
            return messages

        # Apply observation masking to prune older raw tool outputs first
        messages = self.mask_observations(messages, keep_recent_turns=3)

        target_budget = max_tokens or self.critical_threshold

        estimated_tokens = sum(
            len(msg.get("content") or "") for msg in messages if isinstance(msg.get("content"), str)
        ) // 4
        if estimated_tokens <= target_budget:
            return messages

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

        recent_messages = messages[-3:]
        middle_messages = messages[1:-3]

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

        return [system_prompt] + budgeted_middle + recent_messages
