from pathlib import Path
from shibaclaw.agent.self_repair import SelfRepair

def test_self_repair_successful_execution(tmp_path: Path):
    repair = SelfRepair(tmp_path)
    
    def correct_func(x, y):
        return x + y
        
    success, result = repair.execute_safe("DummyComponent", correct_func, 2, 3)
    assert success is True
    assert result == 5

def test_self_repair_exception_handling_and_logging(tmp_path: Path):
    repair = SelfRepair(tmp_path)
    
    def failing_func():
        raise ValueError("Something went wrong")
        
    success, result = repair.execute_safe("StuckDetector", failing_func)
    assert success is False
    assert result is None
    
    # Verify learning was logged
    learnings_file = tmp_path / "memory" / "learnings.md"
    assert learnings_file.is_file()
    assert "StuckDetector" in learnings_file.read_text(encoding="utf-8")
    assert "ValueError" in learnings_file.read_text(encoding="utf-8")
    assert "Reset StuckDetector history" in learnings_file.read_text(encoding="utf-8")
