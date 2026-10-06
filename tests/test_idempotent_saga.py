from shibaclaw.agent.idempotent_saga import IdempotentSaga

def test_saga_success():
    saga = IdempotentSaga()
    step1_done = False
    step2_done = False
    
    def action1():
        nonlocal step1_done
        step1_done = True
        
    def action2():
        nonlocal step2_done
        step2_done = True
        
    saga.add_step("step1", action1, lambda: None)
    saga.add_step("step2", action2, lambda: None)
    
    assert saga.execute() is True
    assert step1_done is True
    assert step2_done is True

def test_saga_rollback():
    saga = IdempotentSaga()
    step1_done = False
    step1_compensated = False
    
    def action1():
        nonlocal step1_done
        step1_done = True
        
    def compensate1():
        nonlocal step1_compensated
        step1_compensated = True
        
    def action2():
        raise ValueError("Simulated failure")
        
    saga.add_step("step1", action1, compensate1)
    saga.add_step("step2", action2, lambda: None)
    
    assert saga.execute() is False
    assert step1_done is True
    assert step1_compensated is True

def test_saga_idempotency():
    saga = IdempotentSaga()
    runs = 0
    
    def action1():
        nonlocal runs
        runs += 1
        
    saga.add_step("step1", action1, lambda: None)
    
    # First execution
    assert saga.execute() is True
    assert runs == 1
    
    # Second execution (should skip due to idempotency)
    assert saga.execute() is True
    assert runs == 1
