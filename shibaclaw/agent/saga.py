import logging
import asyncio
from typing import Any, Callable, Dict, List, Union, Awaitable

logger = logging.getLogger(__name__)

class SagaStep:
    """
    A single step in a Saga transaction.
    """
    def __init__(
        self,
        name: str,
        action: Callable[..., Union[Any, Awaitable[Any]]],
        compensate: Callable[..., Union[Any, Awaitable[Any]]],
    ):
        self.name = name
        self.action = action
        self.compensate = compensate

class IdempotentSaga:
    """
    Implements the Idempotent Saga Pattern for multi-step transactional workflows.
    If any step fails, it executes compensating actions for all completed steps in reverse order.
    """
    def __init__(self, saga_id: str):
        self.saga_id = saga_id
        self.steps: List[SagaStep] = []
        self.completed_steps: List[str] = []
        self.results: Dict[str, Any] = {}

    def add_step(
        self,
        name: str,
        action: Callable[..., Union[Any, Awaitable[Any]]],
        compensate: Callable[..., Union[Any, Awaitable[Any]]],
    ) -> "IdempotentSaga":
        """
        Registers a step with a forward action and a compensating rollback action.
        """
        self.steps.append(SagaStep(name, action, compensate))
        return self

    async def execute(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Executes the Saga steps sequentially.
        If a step fails, initiates rollback by executing compensating actions in reverse order.
        """
        logger.info("Saga %s: Starting execution of %d steps", self.saga_id, len(self.steps))
        
        for step in self.steps:
            if step.name in self.completed_steps:
                logger.info("Saga %s: Step %s already completed (idempotent skip)", self.saga_id, step.name)
                continue

            logger.info("Saga %s: Executing step %s", self.saga_id, step.name)
            try:
                if asyncio.iscoroutinefunction(step.action):
                    res = await step.action(*args, **kwargs)
                else:
                    res = step.action(*args, **kwargs)
                
                self.results[step.name] = res
                self.completed_steps.append(step.name)
                logger.info("Saga %s: Step %s completed successfully", self.saga_id, step.name)
            except Exception as e:
                logger.error("Saga %s: Step %s failed with error: %s. Initiating rollback...", self.saga_id, step.name, e)
                await self._rollback(*args, **kwargs)
                raise RuntimeError(f"Saga {self.saga_id} failed at step {step.name}: {e}") from e

        logger.info("Saga %s: All steps completed successfully", self.saga_id)
        return self.results

    async def _rollback(self, *args, **kwargs) -> None:
        """
        Executes compensating actions for all completed steps in reverse order.
        """
        logger.info("Saga %s: Rolling back %d completed steps", self.saga_id, len(self.completed_steps))
        
        # Rollback completed steps in reverse order
        for step_name in reversed(self.completed_steps):
            step = next((s for s in self.steps if s.name == step_name), None)
            if not step:
                continue

            logger.info("Saga %s: Executing compensating action for step %s", self.saga_id, step.name)
            try:
                if asyncio.iscoroutinefunction(step.compensate):
                    await step.compensate(*args, **kwargs)
                else:
                    step.compensate(*args, **kwargs)
                logger.info("Saga %s: Compensating action for step %s completed", self.saga_id, step.name)
            except Exception as e:
                logger.error("Saga %s: Compensating action for step %s failed: %s", self.saga_id, step.name, e)
                # We continue rolling back other steps even if one compensation fails
                continue

        self.completed_steps.clear()
        logger.info("Saga %s: Rollback completed", self.saga_id)
