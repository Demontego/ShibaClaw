"""Unit tests for Tool Call Pre-flight Guard & Argument Schema Normalization."""

from shibaclaw.agent.tools.base import Tool
from shibaclaw.agent.tools.preflight import ToolPreflightGuard


class DummyTool(Tool):
    """Dummy tool for preflight testing."""

    name = "dummy_tool"
    description = "Dummy tool"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"},
            "content": {"type": "string", "description": "File content"},
            "confirm": {"type": "boolean", "description": "Confirmation flag"},
            "limit": {"type": "integer", "description": "Limit count"},
        },
        "required": ["path", "content"],
    }

    async def execute(self, **kwargs):
        return "ok"


def test_path_normalization():
    guard = ToolPreflightGuard()
    assert guard.normalize_path("  ~/documents//test.txt  ") != "  ~/documents//test.txt  "
    assert not guard.normalize_path("~/test.txt").startswith("~")
    assert guard.normalize_path("./foo/bar.py") == "foo/bar.py"
    assert guard.normalize_path("foo/bar/") == "foo/bar"
    assert guard.normalize_path("\\windows\\path\\file.txt") == "/windows/path/file.txt"


def test_argument_alias_repair_read_file():
    tool = DummyTool()
    # Missing 'path', provided 'file'
    args = {"file": "~/test.txt", "content": "hello"}
    res = ToolPreflightGuard.process("read_file", args, tool_instance=tool)
    assert res.success is True
    assert "path" in res.arguments
    assert "file" not in res.arguments
    assert res.arguments["path"].endswith("/test.txt")


def test_argument_alias_repair_write_file():
    tool = DummyTool()
    # Missing 'path' and 'content', provided 'filepath' and 'text'
    args = {"filepath": "./test.txt", "text": "sample text"}
    res = ToolPreflightGuard.process("write_file", args, tool_instance=tool)
    assert res.success is True
    assert res.arguments["path"] == "test.txt"
    assert res.arguments["content"] == "sample text"


def test_type_coercion_boolean_and_integer():
    tool = DummyTool()
    args = {"path": "test.txt", "content": "data", "confirm": "true", "limit": "50"}
    res = ToolPreflightGuard.process("dummy_tool", args, tool_instance=tool)
    assert res.success is True
    assert res.arguments["confirm"] is True
    assert res.arguments["limit"] == 50


def test_preflight_validation_failure_returns_instant_error():
    tool = DummyTool()
    # Missing required 'content' parameter
    args = {"path": "test.txt"}
    res = ToolPreflightGuard.process("dummy_tool", args, tool_instance=tool)
    assert res.success is False
    assert res.error is not None
    assert "[PreflightGuard: Tool 'dummy_tool' pre-flight validation failed" in res.error
    assert "Missing required parameter(s): content" in res.error


def test_invalid_arguments_type():
    res = ToolPreflightGuard.process("dummy_tool", "not_a_dict", schema_properties={}, required_fields=[])
    assert res.success is False
    assert "must be a dictionary" in res.error
