from pathlib import Path
from shibaclaw.agent.sre_monitor import SREMonitor
from shibaclaw.agent.checkpoint_manager import CheckpointManager
from shibaclaw.agent.agentic_sre import AgenticSRE

def test_agentic_sre_healthy_flow(tmp_path: Path):
    monitor = SREMonitor()
    checkpoint_mgr = CheckpointManager(tmp_path)
    sre = AgenticSRE(tmp_path, monitor, checkpoint_mgr)

    result = sre.run_sre_cycle("session_123")
    assert result["healthy"] is True
    assert result["reason"] == "Healthy"
    assert result["action"]["type"] == "none"

def test_agentic_sre_liveness_failure_recovery(tmp_path: Path):
    monitor = SREMonitor(max_consecutive_repeats=3)
    checkpoint_mgr = CheckpointManager(tmp_path)
    sre = AgenticSRE(tmp_path, monitor, checkpoint_mgr)

    # Trigger liveness failure
    monitor.add_response("Hello")
    monitor.add_response("Hello")
    monitor.add_response("Hello")

    result = sre.run_sre_cycle("session_123")
    assert result["healthy"] is False
    assert "Liveness failure" in result["reason"]
    assert result["action"]["type"] == "inject_prompt"
    assert "loop or progress stall" in result["action"]["prompt"]

    # Verify learning was logged
    learnings_file = tmp_path / "memory" / "learnings.md"
    assert learnings_file.is_file()
    assert "Liveness failure" in learnings_file.read_text(encoding="utf-8")

def test_agentic_sre_quality_failure_rollback(tmp_path: Path):
    monitor = SREMonitor()
    checkpoint_mgr = CheckpointManager(tmp_path)
    sre = AgenticSRE(tmp_path, monitor, checkpoint_mgr)

    # Save a checkpoint first
    checkpoint_mgr.save_checkpoint("session_123", [{"role": "user", "content": "Hello"}], 1)

    # Trigger quality failure
    monitor.add_response("Hi")

    result = sre.run_sre_cycle("session_123")
    assert result["healthy"] is False
    assert "Quality failure" in result["reason"]
    assert result["action"]["type"] == "rollback"
    assert result["action"]["session_key"] == "session_123"
