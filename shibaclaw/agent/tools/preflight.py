"""Tool Call Pre-flight Guard & Argument Schema Normalization."""

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from shibaclaw.agent.tools.preflight_guard import ToolCallPreFlightGuard

if TYPE_CHECKING:
    from shibaclaw.agent.tools.base import Tool

# Alias mapping for tool parameters to auto-repair missing required parameters
PARAM_ALIASES: Dict[str, Dict[str, List[str]]] = {
    "read_file": {"path": ["file", "filename", "filepath", "file_path", "p"]},
    "write_file": {
        "path": ["file", "filename", "filepath", "file_path", "p"],
        "content": ["text", "body", "data", "code", "contents"],
    },
    "edit_file": {
        "path": ["file", "filename", "filepath", "file_path", "p"],
        "old_text": ["old", "search", "find", "target_text"],
        "new_text": ["new", "replace", "replacement", "new_content"],
    },
    "list_dir": {"path": ["dir", "folder", "directory", "dir_path", "p"]},
    "exec": {"command": ["cmd", "shell", "script", "cli"]},
    "web_search": {"query": ["q", "search", "search_query", "keywords", "text"]},
    "web_fetch": {"url": ["link", "uri", "address", "target_url"]},
    "memory_search": {"query": ["q", "search", "search_query", "text"]},
    "business_send": {
        "peer": ["to", "target", "recipient", "user_id"],
        "content": ["text", "message", "body", "msg"],
    },
    "business_search": {"query": ["q", "search", "text"]},
    "ask_user": {"prompt": ["question", "prompt_text", "msg", "text"]},
    "automation": {"action": ["cmd", "type", "operation"]},
}


@dataclass
class PreflightResult:
    """Result of pre-flight argument validation and normalization."""

    success: bool
    arguments: Dict[str, Any]
    error: Optional[str] = None
    repairs_applied: Optional[List[str]] = None


class ToolPreflightGuard:
    """Pre-flight validation, path normalization, and argument auto-repair guard."""

    @staticmethod
    def normalize_path(value: Any) -> Any:
        """Normalize file and directory path strings."""
        if not isinstance(value, str):
            return value

        # Strip whitespace
        val = value.strip()
        if not val:
            return val

        # Expand user home tilde ~
        if val.startswith("~"):
            val = os.path.expanduser(val)

        # Standardize slashes on POSIX (convert Windows backslashes if any)
        val = val.replace("\\", "/")

        # Clean redundant multiple slashes (e.g. // -> /) keeping initial double slash if network
        if not val.startswith("//"):
            val = re.sub(r"/{2,}", "/", val)

        # Remove trailing slash unless root '/'
        if len(val) > 1 and val.endswith("/"):
            val = val.rstrip("/")

        # Clean leading redundant ./ if path has components (e.g. ./foo/bar -> foo/bar)
        if val.startswith("./") and len(val) > 2:
            val = val[2:]

        return val

    @classmethod
    def auto_repair_arguments(
        cls,
        tool_name: str,
        args: Dict[str, Any],
        schema_properties: Dict[str, Any],
        required_fields: List[str],
    ) -> Tuple[Dict[str, Any], List[str]]:
        """Auto-repair missing required arguments using alias mappings and type coercion."""
        repaired_args = dict(args)
        repairs: List[str] = []

        # 1. Alias mapping for missing parameters
        aliases = PARAM_ALIASES.get(tool_name, {})
        for target_param in required_fields:
            if target_param not in repaired_args or repaired_args[target_param] is None:
                candidate_aliases = aliases.get(target_param, [])
                for alias in candidate_aliases:
                    if alias in repaired_args and repaired_args[alias] is not None:
                        repaired_args[target_param] = repaired_args.pop(alias)
                        repairs.append(f"Mapped alias '{alias}' -> '{target_param}'")
                        break

        # 2. Universal alias repair if still missing and args has a single unmapped argument
        unmapped_keys = [k for k in repaired_args.keys() if k not in schema_properties]
        missing_required = [
            f for f in required_fields if f not in repaired_args or repaired_args[f] is None
        ]
        if len(unmapped_keys) == 1 and len(missing_required) == 1:
            unmapped_key = unmapped_keys[0]
            target_key = missing_required[0]
            repaired_args[target_key] = repaired_args.pop(unmapped_key)
            repairs.append(
                f"Mapped unmapped parameter '{unmapped_key}' -> required '{target_key}'"
            )

        # 3. Type coercion based on schema properties
        for key, value in list(repaired_args.items()):
            if key not in schema_properties:
                continue
            prop_schema = schema_properties[key]
            expected_type = prop_schema.get("type")

            if expected_type == "boolean" and not isinstance(value, bool):
                if isinstance(value, str):
                    lower_val = value.strip().lower()
                    if lower_val in ("true", "1", "yes"):
                        repaired_args[key] = True
                        repairs.append(f"Coerced '{key}' string '{value}' -> boolean True")
                    elif lower_val in ("false", "0", "no"):
                        repaired_args[key] = False
                        repairs.append(f"Coerced '{key}' string '{value}' -> boolean False")
            elif expected_type == "integer" and not isinstance(value, int) and isinstance(value, str):
                try:
                    repaired_args[key] = int(value.strip())
                    repairs.append(
                        f"Coerced '{key}' string '{value}' -> integer {repaired_args[key]}"
                    )
                except ValueError:
                    pass
            elif expected_type == "number" and not isinstance(value, (int, float)) and isinstance(value, str):
                try:
                    repaired_args[key] = float(value.strip())
                    repairs.append(
                        f"Coerced '{key}' string '{value}' -> float {repaired_args[key]}"
                    )
                except ValueError:
                    pass

        return repaired_args, repairs

    @classmethod
    def normalize_arguments(
        cls, args: Dict[str, Any], schema_properties: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Normalize argument values including path parameters."""
        normalized = dict(args)
        for key, val in list(normalized.items()):
            prop_schema = (schema_properties or {}).get(key, {})
            if ToolCallPreFlightGuard.is_path_key(key, prop_schema):
                if isinstance(val, str):
                    normalized[key] = cls.normalize_path(val)
        return normalized

    @classmethod
    def process(
        cls,
        tool_name: str,
        args: Dict[str, Any],
        schema_properties: Optional[Dict[str, Any]] = None,
        required_fields: Optional[List[str]] = None,
        tool_instance: Optional["Tool"] = None,
    ) -> PreflightResult:
        """Execute pre-flight argument validation, path normalization, and auto-repair."""
        if tool_instance is not None:
            schema = tool_instance.parameters or {}
            schema_properties = schema.get("properties", {})
            required_fields = schema.get("required", [])
        else:
            schema_properties = schema_properties or {}
            required_fields = required_fields or []

        if not isinstance(args, dict):
            return PreflightResult(
                success=False,
                arguments={},
                error=f"[PreflightGuard: Tool '{tool_name}' arguments must be a dictionary, got {type(args).__name__}.]",
            )

        # 1. Normalize paths and basic fields
        normalized_args = cls.normalize_arguments(args, schema_properties)

        # 2. Auto-repair missing required parameters and type coercions
        repaired_args, repairs = cls.auto_repair_arguments(
            tool_name, normalized_args, schema_properties, required_fields
        )

        # Re-normalize paths in case alias mapping changed keys
        repaired_args = cls.normalize_arguments(repaired_args, schema_properties)

        # 3. Validate required fields
        missing = [
            field
            for field in required_fields
            if field not in repaired_args
            or repaired_args[field] is None
            or (
                isinstance(repaired_args[field], str)
                and not repaired_args[field].strip()
                and field in ("path", "command", "url", "query")
            )
        ]

        if missing:
            schema_summary = ", ".join(
                f"{k} ({v.get('type', 'any')})" for k, v in schema_properties.items()
            )
            err_msg = (
                f"[PreflightGuard: Tool '{tool_name}' pre-flight validation failed. "
                f"Missing required parameter(s): {', '.join(missing)}. "
                f"Accepted schema: {{{schema_summary}}}]"
            )
            return PreflightResult(
                success=False,
                arguments=repaired_args,
                error=err_msg,
                repairs_applied=repairs,
            )

        return PreflightResult(
            success=True,
            arguments=repaired_args,
            error=None,
            repairs_applied=repairs,
        )
