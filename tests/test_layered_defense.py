from pathlib import Path
from shibaclaw.agent.layered_defense import LayeredDefense

def test_layered_defense_healthy_by_default(tmp_path: Path):
    defense = LayeredDefense(tmp_path)
    
    should_continue, recovery_prompt = defense.record_iteration(
        iteration=1,
        response_content="Hello",
        tool_names=["web_search"],
        progress_metric=1.0,
        messages=[]
    )
    
    assert should_continue is True
    assert recovery_prompt is None

def test_layered_defense_stuck_detector_trigger(tmp_path: Path):
    defense = LayeredDefense(tmp_path)
    
    # Add 3 identical responses to trigger StuckDetector
    defense.record_iteration(1, "Hello", ["web_search"], 1.0, [])
    defense.record_iteration(2, "Hello", ["web_search"], 1.0, [])
    should_continue, recovery_prompt = defense.record_iteration(3, "Hello", ["web_search"], 1.0, [])
    
    assert should_continue is True
    assert "repeating response content" in recovery_prompt["content"]

def test_layered_defense_sre_monitor_quality_trigger(tmp_path: Path):
    defense = LayeredDefense(tmp_path)
    
    # Add extremely short response to trigger SRE Monitor quality failure
    should_continue, recovery_prompt = defense.record_iteration(1, "Hi", ["web_search"], 1.0, [])
    
    assert should_continue is True
    assert "quality of your recent responses has degraded" in recovery_prompt
