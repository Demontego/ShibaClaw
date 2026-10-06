import pytest
from shibaclaw.agent.exponential_backoff import ExponentialBackoff

def test_exponential_backoff_success_first_attempt():
    eb = ExponentialBackoff()
    runs = 0
    
    def task():
        nonlocal runs
        runs += 1
        return "success"
        
    result = eb.execute_with_retry(task)
    assert result == "success"
    assert runs == 1

def test_exponential_backoff_retry_and_success():
    eb = ExponentialBackoff(base_delay=0.01, max_delay=0.1, jitter=False)
    runs = 0
    
    def task():
        nonlocal runs
        runs += 1
        if runs < 3:
            raise ValueError("Transient error")
        return "success"
        
    result = eb.execute_with_retry(task, max_attempts=3)
    assert result == "success"
    assert runs == 3

def test_exponential_backoff_max_attempts_reached():
    eb = ExponentialBackoff(base_delay=0.01, max_delay=0.1, jitter=False)
    runs = 0
    
    def task():
        nonlocal runs
        runs += 1
        raise ValueError("Persistent error")
        
    with pytest.raises(ValueError, match="Persistent error"):
        eb.execute_with_retry(task, max_attempts=3)
        
    assert runs == 3
