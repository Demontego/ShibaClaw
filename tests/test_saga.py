import pytest
from shibaclaw.agent.saga import IdempotentSaga

@pytest.mark.asyncio
async def test_saga_successful_execution():
    saga = IdempotentSaga("test_success")
    
    steps_executed = []
    compensations_executed = []

    async def step1():
        steps_executed.append("step1")
        return "res1"

    async def comp1():
        compensations_executed.append("comp1")

    async def step2():
        steps_executed.append("step2")
        return "res2"

    async def comp2():
        compensations_executed.append("comp2")

    saga.add_step("step1", step1, comp1)
    saga.add_step("step2", step2, comp2)

    results = await saga.execute()
    
    assert steps_executed == ["step1", "step2"]
    assert compensations_executed == []
    assert results == {"step1": "res1", "step2": "res2"}

@pytest.mark.asyncio
async def test_saga_rollback_on_failure():
    saga = IdempotentSaga("test_failure")
    
    steps_executed = []
    compensations_executed = []

    async def step1():
        steps_executed.append("step1")
        return "res1"

    async def comp1():
        compensations_executed.append("comp1")

    async def step2():
        steps_executed.append("step2")
        raise ValueError("Step 2 failed!")

    async def comp2():
        compensations_executed.append("comp2")

    saga.add_step("step1", step1, comp1)
    saga.add_step("step2", step2, comp2)

    with pytest.raises(RuntimeError) as exc_info:
        await saga.execute()

    assert "Saga test_failure failed at step step2" in str(exc_info.value)
    assert steps_executed == ["step1", "step2"]
    # Only step1 was completed, so only comp1 should be executed during rollback
    assert compensations_executed == ["comp1"]

@pytest.mark.asyncio
async def test_saga_idempotency_skip():
    saga = IdempotentSaga("test_idempotency")
    
    steps_executed = []
    
    async def step1():
        steps_executed.append("step1")
        return "res1"

    saga.add_step("step1", step1, lambda: None)
    
    # Manually mark step1 as completed
    saga.completed_steps.append("step1")
    
    results = await saga.execute()
    
    # step1 should be skipped because it is already completed
    assert steps_executed == []
    assert results == {}
