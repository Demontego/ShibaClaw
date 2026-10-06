import pytest
from shibaclaw.agent.subagent import SubagentManager
from shibaclaw.bus.queue import MessageBus

class MockResponse:
    def __init__(self, content: str, has_tool_calls: bool = False, tool_calls: list = None):
        self.content = content
        self.has_tool_calls = has_tool_calls
        self.tool_calls = tool_calls or []
        self.finish_reason = "stop"
        self.reasoning_content = None
        self.reasoning_details = None
        self.thinking_blocks = []

class MockProvider:
    def __init__(self):
        self.calls = []

    def get_default_model(self) -> str:
        return "mock-model"

    async def chat_with_retry(self, messages: list[dict], tools: list, model: str) -> MockResponse:
        self.calls.append(messages)
        # If the last message contains "Auditor Agent", return a PASSED verdict
        last_content = messages[-1]["content"]
        if "Auditor Agent" in last_content:
            return MockResponse("The execution was correct. PASSED")
        else:
            return MockResponse("Execution completed successfully.")

@pytest.mark.asyncio
async def test_execute_mea_loop(tmp_path):
    provider = MockProvider()
    bus = MessageBus()
    manager = SubagentManager(
        provider=provider,
        workspace=tmp_path,
        bus=bus,
    )
    
    task = "Create a hello world file"
    result = await manager.execute_mea_loop(
        task=task,
        origin_channel="cli",
        origin_chat_id="direct",
        session_key="cli:direct",
    )
    
    assert result["status"] == "completed"
    assert result["verdict"] == "PASSED"
    assert "Execution completed successfully." in result["execution_result"]
    assert "PASSED" in result["audit_result"]
    
    # Verify progress.md was created and updated
    progress_file = tmp_path / "progress.md"
    assert progress_file.is_file()
    progress_content = progress_file.read_text(encoding="utf-8")
    assert "Task Progress" in progress_content
    assert "**Verdict**: PASSED" in progress_content
    assert "**Status**: Completed" in progress_content
