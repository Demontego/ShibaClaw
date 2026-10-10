import pytest
from unittest.mock import AsyncMock, MagicMock
from shibaclaw.agent.tools.base import Tool
from shibaclaw.agent.tools.preflight_guard import ToolCallPreFlightGuard
from shibaclaw.agent.tools.registry import SkillVault
from shibaclaw.agent.tools.mcp import MCPWrappedTool


class DummyTool(Tool):
    @property
    def name(self) -> str:
        return "dummy_tool"

    @property
    def description(self) -> str:
        return "A dummy tool for testing pre-flight guard."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "The file path"},
                "count": {"type": "integer", "description": "Number of items", "minimum": 1},
                "mode": {"type": "string", "enum": ["read", "write"]},
            },
            "required": ["path", "count"],
        }

    async def execute(self, path: str, count: int, mode: str = "read") -> str:
        return f"Executed dummy_tool on {path} with count={count}, mode={mode}"


def test_path_arg_normalization():
    guard = ToolCallPreFlightGuard()

    assert guard.normalize_path_arg("  /path/to/file.txt  ") == "/path/to/file.txt"
    assert guard.normalize_path_arg('"path/to/file.txt"') == "path/to/file.txt"
    assert guard.normalize_path_arg("'path\\to\\file.txt'") == "path/to/file.txt"
    assert guard.normalize_path_arg("/foo//bar///baz.txt") == "/foo/bar/baz.txt"
    assert guard.normalize_path_arg("/path/to/dir/") == "/path/to/dir"
    assert guard.normalize_path_arg("/") == "/"
    assert guard.normalize_path_arg("   ") == ""


def test_is_path_key():
    guard = ToolCallPreFlightGuard()

    assert guard.is_path_key("path") is True
    assert guard.is_path_key("working_dir") is True
    assert guard.is_path_key("target_file_path") is True
    assert guard.is_path_key("description", {"description": "Path to local repository"}) is True
    assert guard.is_path_key("count") is False


def test_validate_and_normalize_valid():
    guard = ToolCallPreFlightGuard()
    tool = DummyTool()

    raw_params = {
        "path": "  path/to//file.txt  ",
        "count": "5",  # string that can be cast to int
        "mode": "read",
    }

    is_valid, norm_params, feedback = guard.validate_and_normalize(tool, raw_params)

    assert is_valid is True
    assert norm_params == {"path": "path/to/file.txt", "count": 5, "mode": "read"}
    assert feedback is None


def test_validate_and_normalize_missing_required():
    guard = ToolCallPreFlightGuard()
    tool = DummyTool()

    raw_params = {"path": "path/to/file.txt"}  # missing required 'count'

    is_valid, norm_params, feedback = guard.validate_and_normalize(tool, raw_params)

    assert is_valid is False
    assert "missing required count" in feedback
    assert "Expected Parameter Schema:" in feedback
    assert "Example of a correct call:" in feedback


def test_validate_and_normalize_empty_path():
    guard = ToolCallPreFlightGuard()
    tool = DummyTool()

    raw_params = {"path": "   ", "count": 2}

    is_valid, norm_params, feedback = guard.validate_and_normalize(tool, raw_params)

    assert is_valid is False
    assert "cannot be empty" in feedback or "missing required" in feedback


@pytest.mark.asyncio
async def test_skill_vault_preflight_guard_execution():
    vault = SkillVault()
    tool = DummyTool()
    vault.register(tool)

    # 1. Invalid call - missing required parameter
    result = await vault.execute("dummy_tool", {"path": "test.txt"})
    assert "Error: Tool 'dummy_tool' failed:" in result
    assert "missing required count" in result
    assert "Expected Parameter Schema:" in result

    # 2. Valid call with auto-casting and normalization
    result = await vault.execute("dummy_tool", {"path": "  dir\\file.txt  ", "count": "10"})
    assert "Executed dummy_tool on dir/file.txt with count=10, mode=read" in result


@pytest.mark.asyncio
async def test_mcp_wrapped_tool_preflight_guard():
    session = AsyncMock()
    tool_def = MagicMock()
    tool_def.name = "query_db"
    tool_def.description = "Query database"
    tool_def.inputSchema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "SQL Query"},
            "limit": {"type": "integer", "minimum": 1},
        },
        "required": ["query"],
    }

    mcp_tool = MCPWrappedTool("db_server", tool_def, session, timeout=10)
    vault = SkillVault()
    vault.register(mcp_tool)

    # Invalid call - missing required query parameter
    res_invalid = await vault.execute("mcp_db_server_query_db", {"limit": 10})
    assert "Error: Tool 'mcp_db_server_query_db' failed:" in res_invalid
    assert "missing required query" in res_invalid
    # Ensure MCP session.call_tool was NOT invoked when pre-flight failed
    session.call_tool.assert_not_called()

    # Valid call - passes pre-flight and invokes MCP session
    from mcp import types
    mock_result = MagicMock()
    mock_block = types.TextContent(type="text", text="Query results ok")
    mock_result.content = [mock_block]
    session.call_tool.return_value = mock_result

    res_valid = await vault.execute("mcp_db_server_query_db", {"query": "SELECT 1;", "limit": "5"})
    assert "Query results ok" in res_valid
    session.call_tool.assert_called_once_with("query_db", arguments={"query": "SELECT 1;", "limit": 5})
