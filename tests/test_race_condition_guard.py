import pytest
from shibaclaw.agent.race_condition_guard import RaceConditionGuard

def test_race_condition_guard_extract_resource():
    guard = RaceConditionGuard()
    
    # Test file-based tools
    assert guard.extract_resource("read_file", {"path": "test.txt"}) == "test.txt"
    assert guard.extract_resource("write_file", {"path": "test.txt"}) == "test.txt"
    assert guard.extract_resource("edit_file", {"path": "test.txt"}) == "test.txt"
    
    # Test non-file-based tools
    assert guard.extract_resource("web_search", {"query": "test"}) is None

@pytest.mark.asyncio
async def test_race_condition_guard_acquire_release():
    guard = RaceConditionGuard()
    resource = "test.txt"
    
    # Acquire lock
    acquired = await guard.acquire(resource, "tool_1")
    assert acquired is True
    
    # Try to acquire lock again (should fail/timeout)
    acquired_again = await guard.acquire(resource, "tool_2", timeout=0.1)
    assert acquired_again is False
    
    # Release lock
    guard.release(resource, "tool_1")
    
    # Acquire lock again (should succeed now)
    acquired_after_release = await guard.acquire(resource, "tool_2")
    assert acquired_after_release is True
    
    # Clean up
    guard.release(resource, "tool_2")
