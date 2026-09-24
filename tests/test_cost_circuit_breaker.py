from pathlib import Path
from shibaclaw.agent.cost_circuit_breaker import CostCircuitBreaker

def test_cost_circuit_breaker_under_limit(tmp_path: Path):
    breaker = CostCircuitBreaker(tmp_path, max_cost_usd=0.10)
    
    # Record usage for a cheap model
    turn_cost = breaker.record_usage("google/gemini-3.5-flash", prompt_tokens=10000, completion_tokens=5000)
    assert turn_cost == (10000 / 1_000_000) * 0.075 + (5000 / 1_000_000) * 0.30
    assert breaker.is_tripped() is False

def test_cost_circuit_breaker_tripped(tmp_path: Path):
    breaker = CostCircuitBreaker(tmp_path, max_cost_usd=0.10)
    
    # Record usage for an expensive model that exceeds the limit
    turn_cost = breaker.record_usage("claude-3-5-sonnet", prompt_tokens=20000, completion_tokens=10000)
    assert turn_cost == (20000 / 1_000_000) * 3.00 + (10000 / 1_000_000) * 15.00
    assert breaker.is_tripped() is True
    
    # Verify learning was logged
    learnings_file = tmp_path / "memory" / "learnings.md"
    assert learnings_file.is_file()
    assert "Cost Circuit Breaker Tripped" in learnings_file.read_text(encoding="utf-8")
    assert "Limit: $0.10" in learnings_file.read_text(encoding="utf-8")
