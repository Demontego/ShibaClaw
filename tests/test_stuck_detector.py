import pytest
from shibaclaw.agent.stuck_detector import StuckDetector

def test_stuck_detector_repeating_response():
    detector = StuckDetector(max_repeats=3)
    
    # First response
    assert not detector.add_response("Hello")
    # Second response (different)
    assert not detector.add_response("World")
    # Third response (same as second)
    assert not detector.add_response("World")
    # Fourth response (same as second and third) -> Stuck!
    assert detector.add_response("World")

def test_stuck_detector_repeating_tool_sequence():
    detector = StuckDetector(max_repeats=3)
    
    # First sequence
    assert not detector.add_tool_sequence(["web_search", "web_fetch"])
    # Second sequence (different)
    assert not detector.add_tool_sequence(["read_file"])
    # Third sequence (same as second)
    assert not detector.add_tool_sequence(["read_file"])
    # Fourth sequence (same as second and third) -> Stuck!
    assert detector.add_tool_sequence(["read_file"])

def test_stuck_detector_flat_progress_metric():
    detector = StuckDetector(max_repeats=3)
    
    # Progress metric starts at 5
    assert not detector.add_progress_metric(5)
    # Stays at 5 (1st repeat)
    assert not detector.add_progress_metric(5)
    # Stays at 5 (2nd repeat)
    assert not detector.add_progress_metric(5)
    # Stays at 5 (3rd repeat) -> Stuck!
    assert detector.add_progress_metric(5)

def test_stuck_detector_goal_reassessment_prompt():
    detector = StuckDetector()
    prompt = detector.get_goal_reassessment_prompt("test reason")
    
    assert prompt["role"] == "system"
    assert "WARNING: Stuck loop detected (test reason)" in prompt["content"]
    assert "GOAL REASSESSMENT REQUIRED" in prompt["content"]

def test_stuck_detector_tool_error_pivot():
    detector = StuckDetector(max_repeats=3)
    
    # First error
    assert not detector.add_tool_error("web_fetch", "Error: 403 Forbidden")
    # Second error (different tool)
    assert not detector.add_tool_error("read_file", "Error: File not found")
    # Third error (same as second)
    assert not detector.add_tool_error("read_file", "Error: File not found")
    # Fourth error (same as second and third) -> Stuck!
    assert detector.add_tool_error("read_file", "Error: File not found")
    
    prompt = detector.get_tool_error_pivot_prompt("read_file", "Error: File not found")
    assert prompt["role"] == "system"
    assert "CRITICAL: Tool 'read_file' has failed repeatedly" in prompt["content"]
    assert "STRATEGY PIVOT REQUIRED" in prompt["content"]


class MockResponse:
    def __init__(self, content: str):
        self.content = content

class MockProvider:
    async def chat_with_retry(self, messages: list[dict], model: str) -> MockResponse:
        return MockResponse('{"intent": "file_read", "is_loop": true, "confidence": 0.95, "reason": "Repeating read_file call"}')

@pytest.mark.asyncio
async def test_stuck_detector_classify_intent_and_detect_loop():
    detector = StuckDetector()
    provider = MockProvider()
    
    result = await detector.classify_intent_and_detect_loop_async(
        response_content="I am reading the file again.",
        provider=provider,
    )
    
    assert result["intent"] == "file_read"
    assert result["is_loop"] is True
    assert result["confidence"] == 0.95
    assert result["reason"] == "Repeating read_file call"

