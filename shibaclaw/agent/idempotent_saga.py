import logging
from typing import Dict, Any, List, Callable

logger = logging.getLogger(__name__)

class SagaStep:
    def __init__(self, step_id: str, action_fn: Callable[[], Any], compensate_fn: Callable[[], Any]):
        self.step_id = step_id
        self.action_fn = action_fn
        self.compensate_fn = compensate_fn
        self.status = "pending"  # pending, success, failed, compensated

class IdempotentSaga:
    """
    Implements the Idempotent Saga Pattern for safe execution of multi-step
    transactional tasks with side effects and automatic rollback on failure.
    """
    def __init__(self):
        self.steps: List[SagaStep] = []
        self.completed_steps: Dict[str, Any] = {}

    def add_step(self, step_id: str, action_fn: Callable[[], Any], compensate_fn: Callable[[], Any]):
        self.steps.append(SagaStep(step_id, action_fn, compensate_fn))

    def execute(self) -> bool:
        logger.info("IdempotentSaga: Starting execution of %d steps", len(self.steps))
        for step in self.steps:
            if step.step_id in self.completed_steps:
                logger.info("IdempotentSaga: Step %s already completed (idempotency guard)", step.step_id)
                step.status = "success"
                continue

            try:
                logger.info("IdempotentSaga: Executing step %s", step.step_id)
                result = step.action_fn()
                step.status = "success"
                self.completed_steps[step.step_id] = result
            except Exception as e:
                logger.error("IdempotentSaga: Step %s failed: %s. Initiating rollback...", step.step_id, e)
                step.status = "failed"
                self.rollback()
                return False
        return True

    def rollback(self):
        logger.warning("IdempotentSaga: Rolling back completed steps in reverse order")
        for step in reversed(self.steps):
            if step.status == "success":
                try:
                    logger.warning("IdempotentSaga: Compensating step %s", step.step_id)
                    step.compensate_fn()
                    step.status = "compensated"
                    self.completed_steps.pop(step.step_id, None)
                except Exception as e:
                    logger.critical("IdempotentSaga: Compensation failed for step %s: %s", step.step_id, e)
