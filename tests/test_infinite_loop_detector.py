from shibaclaw.agent.infinite_loop_detector import InfiniteLoopDetector

def test_infinite_loop_detector_no_loop():
    detector = InfiniteLoopDetector()
    
    assert detector.record_and_check("tool_a", {"arg": 1}) is False
    assert detector.record_and_check("tool_b", {"arg": 2}) is False
    assert detector.record_and_check("tool_c", {"arg": 3}) is False

def test_infinite_loop_detector_identical_calls():
    detector = InfiniteLoopDetector(max_identical_calls=3)
    
    assert detector.record_and_check("tool_a", {"arg": 1}) is False
    assert detector.record_and_check("tool_a", {"arg": 1}) is False
    assert detector.record_and_check("tool_a", {"arg": 1}) is True

def test_infinite_loop_detector_repeating_sequence():
    detector = InfiniteLoopDetector(window_size=10)
    
    # Sequence: A -> B -> A -> B
    assert detector.record_and_check("tool_a", {"arg": 1}) is False
    assert detector.record_and_check("tool_b", {"arg": 2}) is False
    assert detector.record_and_check("tool_a", {"arg": 1}) is False
    assert detector.record_and_check("tool_b", {"arg": 2}) is True
