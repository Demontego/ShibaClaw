"""Tool Call Pre-flight Guard: pre-execution argument validation and normalization."""

import re
from typing import Any, Dict, List, Tuple
from shibaclaw.agent.tools.base import Tool
from shibaclaw.agent.tools.error_feedback import format_structured_error_feedback


PATH_PARAM_KEYS = frozenset(
    {
        "path",
        "filepath",
        "file_path",
        "working_dir",
        "dir_path",
        "target_path",
        "destination",
        "dst",
        "src",
        "file",
        "filename",
        "directory",
        "dir",
        "script_path",
        "output_path",
        "input_path",
        "log_path",
    }
)


class ToolCallPreFlightGuard:
    """
    Validates and normalizes tool call arguments prior to execution.

    Handles:
    - Path argument normalization (stripping quotes, whitespace, backslashes, double slashes).
    - Parameter casting via tool schema.
    - Schema validation (type checking, required fields, enum/min/max bounds).
    - Empty path validation for path parameters.
    - Pre-flight structured error feedback generation.
    """

    def __init__(self):
        self.validation_count = 0
        self.error_count = 0

    @staticmethod
    def is_path_key(key: str, prop_schema: Dict[str, Any] | None = None) -> bool:
        """Determines if a parameter key or property schema represents a file/dir path."""
        k_lower = key.lower()
        if k_lower in PATH_PARAM_KEYS or any(k_lower.endswith(f"_{p}") for p in ("path", "dir", "file")):
            return True
        if prop_schema and isinstance(prop_schema, dict):
            desc = str(prop_schema.get("description", "")).lower()
            if "path" in desc or "file" in desc or "directory" in desc:
                return True
        return False

    @staticmethod
    def normalize_path_arg(val: Any) -> Any:
        """Normalizes a path string value safely."""
        if not isinstance(val, str):
            return val

        # Strip whitespace
        val = val.strip()

        # Strip outer quotes if present
        if len(val) >= 2 and ((val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'"))):
            val = val[1:-1].strip()

        if not val:
            return ""

        # Normalize backslashes on non-windows or general POSIX paths
        if "\\" in val and not re.match(r"^[a-zA-Z]:\\", val):
            val = val.replace("\\", "/")

        # Collapse redundant consecutive slashes (except e.g. http:// or file://)
        if "://" not in val:
            val = re.sub(r"/{2,}", "/", val)

        # Strip trailing slash unless it's root '/'
        if val not in (".", "..", "/"):
            val = val.rstrip("/") if len(val) > 1 else val

        return val

    def normalize_params(self, params: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively normalizes parameter values (paths, string cleanup) based on schema."""
        if not isinstance(params, dict):
            return params

        props = schema.get("properties", {})
        normalized = {}

        for k, v in params.items():
            prop_schema = props.get(k, {}) if isinstance(props, dict) else {}
            if self.is_path_key(k, prop_schema):
                if isinstance(v, str):
                    normalized[k] = self.normalize_path_arg(v)
                elif isinstance(v, list):
                    normalized[k] = [self.normalize_path_arg(item) for item in v]
                else:
                    normalized[k] = v
            elif isinstance(v, dict) and isinstance(prop_schema, dict):
                normalized[k] = self.normalize_params(v, prop_schema)
            else:
                normalized[k] = v

        return normalized

    def validate_and_normalize(
        self, tool: Tool, params: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any], str | None]:
        """
        Pre-flight validation and argument normalization for a tool call.

        Returns:
            (is_valid, normalized_params, error_feedback)
        """
        self.validation_count += 1
        schema = getattr(tool, "parameters", {}) or {"type": "object", "properties": {}}

        # 1. Cast parameters to match expected schema types
        try:
            casted = tool.cast_params(params) if hasattr(tool, "cast_params") else params
        except Exception:
            casted = params

        # 2. Normalize arguments (paths, whitespace)
        norm_params = self.normalize_params(casted, schema)

        # 3. Schema validation
        errors: List[str] = []
        if hasattr(tool, "validate_params"):
            try:
                errors = tool.validate_params(norm_params)
            except Exception as exc:
                errors = [f"Validation exception: {str(exc)}"]

        # 4. Path parameter specific pre-flight checks (e.g. empty string path)
        props = schema.get("properties", {}) if isinstance(schema, dict) else {}
        required_fields = schema.get("required", []) if isinstance(schema, dict) else []

        for k, v in norm_params.items():
            prop_schema = props.get(k, {}) if isinstance(props, dict) else {}
            if self.is_path_key(k, prop_schema):
                if isinstance(v, str) and not v and k in required_fields:
                    errors.append(f"path parameter '{k}' cannot be empty or whitespace-only")

        if errors:
            self.error_count += 1
            err_msg = "; ".join(errors)
            tool_name = getattr(tool, "name", "unknown_tool")
            feedback = format_structured_error_feedback(tool_name, err_msg, schema)
            return False, norm_params, feedback

        return True, norm_params, None
