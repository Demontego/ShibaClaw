from shibaclaw.agent.memory_guard import MemoryGuard
from shibaclaw.agent.stuck_detector import StuckDetector

def test_memory_guard_list():
    guard = MemoryGuard(max_history_size=5)
    lst = [1, 2, 3, 4, 5]
    
    # Under limit
    assert guard.guard_list(lst, "test") == lst
    
    # Over limit
    lst.append(6)
    pruned = guard.guard_list(lst, "test")
    assert len(pruned) == 5
    assert pruned == [2, 3, 4, 5, 6]

def test_memory_guard_dict():
    guard = MemoryGuard(max_history_size=3)
    dct = {"a": 1, "b": 2, "c": 3}
    
    # Under limit
    assert guard.guard_dict(dct, "test") == dct
    
    # Over limit
    dct["d"] = 4
    pruned = guard.guard_dict(dct, "test")
    assert len(pruned) == 3
    assert "a" not in pruned
    assert pruned == {"b": 2, "c": 3, "d": 4}

def test_stuck_detector_memory_guard():
    detector = StuckDetector()
    detector.memory_guard = MemoryGuard(max_history_size=2)
    
    # Add 3 responses (limit is 2)
    detector.add_response("Hello")
    detector.add_response("World")
    detector.add_response("Shiba")
    
    assert len(detector.response_content_history) == 2
    assert detector.response_content_history == ["World", "Shiba"]
