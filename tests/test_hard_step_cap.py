from pathlib import Path
from shibaclaw.agent.hard_step_cap import HardStepCap

def test_hard_step_cap_under_limit(tmp_path: Path):
    cap = HardStepCap(tmp_path, hard_limit=5)
    assert cap.check_step_limit(3) is True

def test_hard_step_cap_exceeded(tmp_path: Path):
    cap = HardStepCap(tmp_path, hard_limit=5)
    assert cap.check_step_limit(5) is False
    
    # Verify learning was logged
    learnings_file = tmp_path / "memory" / "learnings.md"
    assert learnings_file.is_file()
    assert "Hard Step Cap Exceeded" in learnings_file.read_text(encoding="utf-8")
    assert "Limit: 5" in learnings_file.read_text(encoding="utf-8")
