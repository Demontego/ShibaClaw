from shibaclaw.agent.idempotency_guard import IdempotencyGuard

def test_idempotency_guard_execute_once():
    guard = IdempotencyGuard()
    runs = 0
    
    def action():
        nonlocal runs
        runs += 1
        return f"result_{runs}"
        
    # First call
    res1 = guard.execute_once("test_op", {"arg": 1}, action)
    assert res1 == "result_1"
    assert runs == 1
    
    # Second call (should be intercepted and return cached result)
    res2 = guard.execute_once("test_op", {"arg": 1}, action)
    assert res2 == "result_1"
    assert runs == 1

def test_idempotency_guard_different_args():
    guard = IdempotencyGuard()
    runs = 0
    
    def action():
        nonlocal runs
        runs += 1
        return f"result_{runs}"
        
    # First call
    res1 = guard.execute_once("test_op", {"arg": 1}, action)
    assert res1 == "result_1"
    assert runs == 1
    
    # Second call with different args (should execute again)
    res2 = guard.execute_once("test_op", {"arg": 2}, action)
    assert res2 == "result_2"
    assert runs == 2
