import time
import random
import logging
from typing import Dict, Any, Callable

logger = logging.getLogger(__name__)

class SupervisorChild:
    def __init__(self, name: str, start_fn: Callable[[], Any], max_restarts: int = 3, backoff_factor: float = 1.5):
        self.name = name
        self.start_fn = start_fn
        self.max_restarts = max_restarts
        self.backoff_factor = backoff_factor
        self.restart_count = 0
        self.last_restart_time = 0.0
        self.status = "stopped"

    def start(self) -> bool:
        try:
            logger.info("SupervisorChild: Starting child %s", self.name)
            self.start_fn()
            self.status = "running"
            return True
        except Exception as e:
            logger.error("SupervisorChild: Failed to start child %s: %s", self.name, e)
            self.status = "failed"
            return False

    def restart(self) -> bool:
        if self.restart_count >= self.max_restarts:
            logger.error("SupervisorChild: Child %s reached max restarts (%d)", self.name, self.max_restarts)
            self.status = "failed"
            return False

        # Exponential backoff with jitter to prevent thundering herd
        delay = (self.backoff_factor ** self.restart_count) + random.uniform(0.1, 1.0)
        logger.warning("SupervisorChild: Restarting child %s in %.2fs (attempt %d/%d)", self.name, delay, self.restart_count + 1, self.max_restarts)
        time.sleep(delay)

        self.restart_count += 1
        self.last_restart_time = time.time()
        return self.start()

class SupervisorTree:
    """
    Implements a Supervisor Tree Pattern to manage long-running tasks/subagents
    and prevent thundering herd problems during retries.
    """
    def __init__(self, strategy: str = "one_for_one"):
        self.strategy = strategy  # "one_for_one" or "one_for_all"
        self.children: Dict[str, SupervisorChild] = {}

    def register_child(self, name: str, start_fn: Callable[[], Any], max_restarts: int = 3, backoff_factor: float = 1.5):
        self.children[name] = SupervisorChild(name, start_fn, max_restarts, backoff_factor)

    def start_all(self):
        for child in self.children.values():
            child.start()

    def handle_child_failure(self, name: str):
        logger.warning("SupervisorTree: Handling failure for child %s using strategy %s", name, self.strategy)
        if self.strategy == "one_for_one":
            child = self.children.get(name)
            if child:
                child.restart()
        elif self.strategy == "one_for_all":
            # Restart all children
            for child in self.children.values():
                child.restart()
