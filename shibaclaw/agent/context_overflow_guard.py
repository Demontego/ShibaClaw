from dataclasses import dataclass, field
import hashlib
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ContextOverflowError(Exception):
    \"\"\"Raised when the context window usage exceeds the hard limit threshold.\"\"\"
    pass


class CompactionCircuitBreakerError(ContextOverflowError):
    \"\"\"Raised when context compaction reduction falls below 15% (circuit breaker tripped).\"\"\"
    pass


PROMPT_CACHE_PREFIX_MARKER = \"<!-- PROMPT_CACHE_PREFIX_MARKER -->\"
_PIN_MARKERS = (\"## Open\", \"refuse:\", \"need web_search\", \"gate open\")


def _pin_message(msg: dict) -> bool:
    content = msg.get(\"content\")
    if not isinstance(content, str):
        return False
    return any(marker in content for marker in _PIN_MARKERS)


def tombstone_tool_result(msg: dict) -> dict:
    \"\"\"
    Replaces older or pruned tool result content with an auditable tombstone stub:
    `[Tombstone: tool_result pruned ({orig_len} chars -> hash={hash_val}). Schema invariant preserved.]`
    Preserves tool_call_id, role, name, and message metadata to uphold LLM API schema invariants.
    \"\"\"
    if not isinstance(msg, dict):
        return msg

    content = msg.get(\"content\")
    if isinstance(content, str) and (content.startswith(\"[Tombstone:\") or content.startswith(\"[Tool result masked\")):\
        return msg

    # Calculate original length and hash
    if isinstance(content, str):
        raw_str = content
    elif isinstance(content, list):
        raw_str = str(content)
    elif content is None:
        raw_str = \"\"
    else:
        raw_str = str(content)

    orig_len = len(raw_str)
    content_hash = hashlib.sha256(raw_str.encode(\"utf-8\")).hexdigest()[:8]

    stub = f\"[Tombstone: tool_result pruned ({orig_len} chars -> hash={content_hash}). Schema invariant preserved.]\"

    tombstoned_msg = dict(msg)
    tombstoned_msg[\"content\"] = stub
    return tombstoned_msg


def enforce_schema_invariants(messages: list[dict]) -> list[dict]:
    \"\"\"\
    Ensures that for every assistant message containing tool_calls, all corresponding
    tool response messages (matching tool_call_id) are present in the message history.
    If a tool response message is missing due to pruning, inserts a tombstoned tool message stub
    to preserve tool_call_id pairs and prevent 400 Bad Request errors from LLM APIs.
    \"\"\"\
    if not messages:
        return messages

    # Map existing tool_call_ids present in tool response messages
    existing_tool_response_ids = set()
    for msg in messages:
        if isinstance(msg, dict) and msg.get(\"role\") == \"tool\" and msg.get(\"tool_call_id\"):\
            existing_tool_response_ids.add(msg.get(\"tool_call_id\"))

    new_messages = []
    for msg in messages:
        new_messages.append(msg)
        if isinstance(msg, dict) and msg.get(\"role\") == \"assistant\" and msg.get(\"tool_calls\"):\
            tool_calls = msg.get(\"tool_calls\")
            if isinstance(tool_calls, list):\
                for tc in tool_calls:\
                    if isinstance(tc, dict):\
                        tc_id = tc.get(\"id\")
                        func = tc.get(\"function\") or {}
                        tool_name = func.get(\"name\") if isinstance(func, dict) else tc.get(\"name\", \"tool\")
                        if tc_id and tc_id not in existing_tool_response_ids:\
                            # Insert tombstone for missing tool response to satisfy schema invariant
                            stub_msg = {\
                                \"role\": \"tool\",\
                                \"tool_call_id\": tc_id,\
                                \"name\": tool_name,\
                                \"content\": f\"[Tombstone: Missing tool result for {tool_name} (ID: {tc_id}). Schema invariant preserved.]\", # Corrected content
                            }\
                            new_messages.append(stub_msg)
                            logger.info(\"ContextOverflowGuard: Inserted tombstone for missing tool response with ID %s\", tc_id)

    return new_messages


@dataclass
class ArtifactRegister:
    modified_files: list[str] = field(default_factory=list)
    committed_hashes: list[str] = field(default_factory=list)
    subagent_results: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.modified_files or self.committed_hashes or self.subagent_results)

    def render_markdown(self) -> str:
        if self.is_empty():
            return \"\"
        
        output = [\"<artifact_register>\"]
        if self.modified_files:
            output.append(\"## Modified Files:\")
            for f in self.modified_files:
                output.append(f\"- `{f}`\")
        if self.committed_hashes:
            output.append(\"## Committed Hashes:\")
            for h in self.committed_hashes:
                output.append(f\"- `{h}`\")
        if self.subagent_results:
            output.append(\"## Subagent Results:\")
            for r in self.subagent_results:
                output.append(f\"- `{r}`\")
        output.append(\"</artifact_register>\")
        return \"\\n\".join(output)


@dataclass
class ContextOverflowGuard:
    max_tokens: int = 128_000  # Max tokens for the model
    critical_threshold: int = 100_000  # Start pruning aggressively
    warning_threshold: int = 80_000  # Log warnings
    compaction_min_reduction_percent: float = 0.15  # 15% minimum reduction

    artifact_register: ArtifactRegister = field(default_factory=ArtifactRegister)

    def add_modified_file(self, path: str):
        if path not in self.artifact_register.modified_files:
            self.artifact_register.modified_files.append(path)

    def add_committed_hash(self, commit_hash: str):
        if commit_hash not in self.artifact_register.committed_hashes:
            self.artifact_register.committed_hashes.append(commit_hash)

    def add_subagent_result(self, result_summary: str):
        self.artifact_register.subagent_results.append(result_summary)

    def evaluate_compaction_effectiveness(self, tokens_before: int, tokens_after: int):
        if tokens_before <= self.critical_threshold:
            return  # Only evaluate if we were actually over budget

        reduction = (tokens_before - tokens_after) / tokens_before
        if reduction < self.compaction_min_reduction_percent:
            logger.error(
                \"ContextOverflowGuard: Compaction circuit breaker tripped! \"
                \"Reduction was %.2f%%, below minimum %.2f%%. \"
                \"Tokens before: %d, after: %d\",
                reduction * 100,
                self.compaction_min_reduction_percent * 100,
                tokens_before,
                tokens_after,
            )
            raise CompactionCircuitBreakerError(
                f\"Context compaction reduction ({reduction:.2%}) \"
                f\"fell below minimum ({self.compaction_min_reduction_percent:.2%}).\"
            )
        else:
            logger.info(
                \"ContextOverflowGuard: Compaction effective. Reduction: %.2f%%. \"
                \"Tokens before: %d, after: %d\",
                reduction * 100,
                tokens_before,
                tokens_after,
            )

    def mask_observations(self, messages: list[dict], keep_recent_turns: int = 3) -> list[dict]:
        \"\"\"\
        Masks older tool observation messages to save context, replacing them with tombstones.
        Always keeps the most recent `keep_recent_turns` of tool observations.
        \"\"\"\
        if not messages:
            return messages

        new_messages = []
        # Keep system prompt and initial assistant message
        new_messages.append(messages[0])

        # Find the index to start masking from
        # We want to keep the last `keep_recent_turns` of tool observations
        tool_observation_indices = [
            i for i, msg in enumerate(messages) if msg.get(\"role\") == \"tool\"
        ]
        
        if len(tool_observation_indices) <= keep_recent_turns:
            # Not enough tool observations to mask, append all
            new_messages.extend(messages[1:])
            return new_messages

        # Determine the cutoff index for masking
        mask_start_index = tool_observation_indices[len(tool_observation_indices) - keep_recent_turns]

        for i, msg in enumerate(messages[1:], start=1):
            if i < mask_start_index and msg.get(\"role\") == \"tool\":
                # Mask older tool observations
                content = msg.get(\"content\")
                content_str = content if isinstance(content, str) else str(content)
                if not content_str.startswith(\"[Tombstone:\") and not content_str.startswith(\"[Tool result masked\"):\
                    tombstoned_msg = tombstone_tool_result(msg)\
                    new_messages.append(tombstoned_msg)\
                    logger.info(\"ContextOverflowGuard: Tombstoned observation for tool at msg index %d\", i)\
                    continue
            new_messages.append(msg)

        return enforce_schema_invariants(new_messages)

    def budget_context(self, messages: list, max_tokens: Optional[int] = None) -> list:
        \"\"\"\
        Dynamically budgets the context by pruning or compressing older messages
        if the estimated token count exceeds the max_tokens budget.
        Preserves the artifact register state, prompt cache prefix markers, and schema invariants.
        \"\"\"\
        if not messages:
            return messages

        tokens_before = sum(
            len(msg.get(\"content\") or \"\") for msg in messages if isinstance(msg.get(\"content\"), str)
        ) // 4

        # Apply observation masking & tombstoning first
        messages = self.mask_observations(messages, keep_recent_turns=3)

        target_budget = max_tokens or self.critical_threshold

        estimated_tokens = sum(
            len(msg.get(\"content\") or \"\") for msg in messages if isinstance(msg.get(\"content\"), str)
        ) // 4

        if estimated_tokens <= target_budget:
            if tokens_before > target_budget:
                self.evaluate_compaction_effectiveness(tokens_before, estimated_tokens)
            return enforce_schema_invariants(messages)

        logger.warning(
            \"ContextOverflowGuard: Estimated tokens (%d) exceed budget (%d). Budgeting context...\",
            estimated_tokens,
            target_budget
        )

        system_prompt = dict(messages[0])
        sys_content = system_prompt.get(\"content\") or \"\"

        # Inject artifact register if non-empty and not present
        if not self.artifact_register.is_empty() and \"<artifact_register>\" not in sys_content:
            artifact_block = self.artifact_register.render_markdown()
            sys_content = f\"{PROMPT_CACHE_PREFIX_MARKER}\\n{artifact_block}\\n\\n{sys_content}\"\
            system_prompt[\"content\"] = sys_content

        tail = messages[-3:]
        pinned = [msg for msg in messages[1:-3] if _pin_message(msg)]
        recent_messages = pinned + tail
        middle_messages = [msg for msg in messages[1:-3] if not _pin_message(msg)]

        budgeted_middle = []
        current_tokens = (len(sys_content) + sum(len(msg.get(\"content\") or \"\") for msg in recent_messages if isinstance(msg.get(\"content\"), str))) // 4

        for msg in reversed(middle_messages):
            msg_content = msg.get(\"content\") or \"\"
            msg_tokens = len(msg_content) // 4 if isinstance(msg_content, str) else 0
            if current_tokens + msg_tokens <= target_budget:
                budgeted_middle.insert(0, msg)
                current_tokens += msg_tokens
            else:
                logger.info(\"ContextOverflowGuard: Pruning message to fit budget: %s...\", str(msg_content)[:50])

        final_messages = enforce_schema_invariants([system_prompt] + budgeted_middle + recent_messages)

        tokens_after = sum(
            len(msg.get(\"content\") or \"\") for msg in final_messages if isinstance(msg.get(\"content\"), str)
        ) // 4

        self.evaluate_compaction_effectiveness(tokens_before, tokens_after)

        return final_messages
